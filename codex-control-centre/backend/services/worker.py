import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Callable, Awaitable, Optional, Union, List

from backend.config import settings
from backend.services.protocol import Protocol
from backend.services.event_service import broker, EventEnvelope
from backend.database import SessionLocal
from backend.models.codex import Turn, Item, Thread

logger = logging.getLogger(__name__)

APPROVAL_METHODS = {
    "turn/toolApprovalRequested",
    "tool_approval_requested",
    "turn/tool_approval_requested",
    "toolApprovalRequested",
    "item/commandExecution/requestApproval",
    "item/fileChange/requestApproval",
}


def resolve_codex_binary(bin_path: Optional[str] = None) -> str:
    """
    Resolves the executable path for the Codex App-Server binary.
    On Windows, if a shim/script (.cmd, .bat) is resolved via PATH,
    it attempts to locate the underlying native compiled binary (codex.exe).
    """
    target = bin_path or settings.codex_bin_path

    # If target already exists as a direct executable file
    target_path = Path(target)
    if target_path.is_file() and os.access(target_path, os.X_OK):
        return str(target_path.resolve())

    which_path = shutil.which(target)
    if not which_path:
        return target

    # On non-Windows or if already an .exe, return directly
    if sys.platform != "win32" or which_path.lower().endswith(".exe"):
        return which_path

    # On Windows, if which_path is a .cmd/.bat script from npm, look for the native binary
    cmd_dir = Path(which_path).parent
    candidates = [
        cmd_dir / "node_modules" / "@openai" / "codex" / "node_modules" / "@openai" / "codex-win32-x64" / "vendor" / "x86_64-pc-windows-msvc" / "bin" / "codex.exe",
        cmd_dir / "node_modules" / "@openai" / "codex-win32-x64" / "vendor" / "x86_64-pc-windows-msvc" / "bin" / "codex.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())

    # Check LocalAppData nvm installation
    user_home = Path.home()
    appdata_local = Path(os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local"))
    nvm_dir = appdata_local / "nvm"
    if nvm_dir.exists():
        matches = list(nvm_dir.glob("**/bin/codex.exe"))
        if matches:
            return str(matches[0].resolve())

    return which_path


def resolve_codex_command(bin_path: Optional[str] = None, args: Optional[List[str]] = None) -> List[str]:
    """
    Builds the full execution command for launching the Codex App-Server.
    """
    binary = resolve_codex_binary(bin_path)
    cmd_args = args if args is not None else list(settings.codex_app_server_args)
    return [binary] + cmd_args


class WorkerProcess:
    def __init__(
        self,
        command: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        perform_handshake: bool = True,
        timeout: Optional[float] = None,
        notification_handler: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        cwd: Optional[str] = None,
    ):
        self.command = command or resolve_codex_command()
        self.env = env
        self.perform_handshake = perform_handshake
        self.timeout = timeout or float(settings.codex_worker_timeout_seconds)
        self.notification_handler = notification_handler
        self.cwd = cwd
        self.thread_id: Optional[str] = None
        self.codex_thread_id: Optional[str] = None
        self.thread_map: Dict[str, str] = {}
        self.reverse_thread_map: Dict[str, str] = {}

        self.process: Optional[asyncio.subprocess.Process] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.running: bool = False
        self._read_task: Optional[asyncio.Task] = None
        self._next_id: int = 1
        self.stderr_lines: List[str] = []
        self.init_result: Optional[Dict[str, Any]] = None

    def register_thread_mapping(self, thread_id: str, codex_thread_id: str):
        self.thread_map[thread_id] = codex_thread_id
        self.reverse_thread_map[codex_thread_id] = thread_id
        self.codex_thread_id = codex_thread_id

    def resolve_thread_id(self, raw_id: Optional[str]) -> str:
        if not raw_id:
            return self.thread_id or ""
        if raw_id in self.reverse_thread_map:
            return self.reverse_thread_map[raw_id]
        try:
            from backend.services.worker_manager import worker_manager
            if hasattr(worker_manager, "reverse_thread_map") and raw_id in worker_manager.reverse_thread_map:
                return worker_manager.reverse_thread_map[raw_id]
        except ImportError:
            pass
        return raw_id

    async def start(self):
        if self.running and self.process and self.process.returncode is None:
            return

        env = dict(os.environ)
        if settings.codex_api_key:
            env["CODEX_API_KEY"] = settings.codex_api_key
        if self.env:
            env.update(self.env)

        extra_kwargs: Dict[str, Any] = {}
        if sys.platform == "win32":
            extra_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            try:
                extra_kwargs["process_group"] = 0
            except Exception:
                pass

        if self.cwd:
            extra_kwargs["cwd"] = self.cwd

        logger.info(f"Launching worker process with command: {self.command} (cwd={self.cwd})")
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            **extra_kwargs,
        )
        self.running = True
        self._read_task = asyncio.create_task(self._read_loop())

        if self.perform_handshake:
            try:
                await self._initialize_handshake()
            except Exception as e:
                logger.error(f"Worker handshake failed: {e}")
                await self.stop()
                raise

    async def _initialize_handshake(self, timeout: float = 10.0):
        logger.info("Performing JSON-RPC 2.0 initialize handshake with Codex app-server")
        params = {
            "clientInfo": {
                "name": "CodexControlCentre",
                "version": "1.0.0",
            },
            "capabilities": {
                "streaming": True,
                "approvals": True,
            },
        }
        response = await self.send_request("initialize", params=params, timeout=timeout, req_id=1)
        self.init_result = response
        logger.info(f"Initialize handshake successful, response: {response}")

        await self.send_notification("initialized", params={})
        logger.info("Sent 'initialized' notification to Codex app-server")

    async def send_raw(self, msg: str):
        if not self.process or not self.process.stdin or self.process.returncode is not None:
            raise RuntimeError("Process not running")
        self.process.stdin.write((msg + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        if not self.process or not self.process.stdin or self.process.returncode is not None:
            raise RuntimeError("Process not running")
        msg = Protocol.build_notification(method, params if params is not None else {})
        self.process.stdin.write((msg + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        req_id: Optional[Union[str, int]] = None,
    ) -> Any:
        if not self.process or not self.process.stdin or self.process.returncode is not None:
            raise RuntimeError("Process not running")

        if req_id is None:
            req_id = self._next_id
            self._next_id += 1

        msg = Protocol.build_request(method, params, req_id)
        future = asyncio.get_running_loop().create_future()
        req_key = str(req_id)
        self.pending_requests[req_key] = future

        self.process.stdin.write((msg + "\n").encode("utf-8"))
        await self.process.stdin.drain()

        req_timeout = timeout if timeout is not None else self.timeout
        try:
            return await asyncio.wait_for(future, timeout=req_timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self.pending_requests.pop(req_key, None)
            raise

    async def _read_loop(self):
        try:
            await asyncio.gather(
                self._read_stdout(),
                self._read_stderr(),
                return_exceptions=True,
            )
        finally:
            self.running = False
            for fut in list(self.pending_requests.values()):
                if not fut.done():
                    fut.set_exception(RuntimeError("Worker process exited or stream EOF"))
            self.pending_requests.clear()

    async def _read_stdout(self):
        if not self.process or not self.process.stdout:
            return

        while self.running and not self.process.stdout.at_eof():
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break

                raw_msg = line.decode("utf-8", errors="replace").strip()
                if not raw_msg:
                    continue

                try:
                    msg = Protocol.parse_message(raw_msg)
                except Exception:
                    try:
                        msg = json.loads(raw_msg)
                    except Exception:
                        continue

                if "id" in msg and ("result" in msg or "error" in msg):
                    req_id = str(msg["id"])
                    if req_id in self.pending_requests:
                        future = self.pending_requests.pop(req_id)
                        if not future.done():
                            if "error" in msg:
                                err = msg["error"]
                                err_msg = err.get("message", "JSON-RPC error") if isinstance(err, dict) else str(err)
                                future.set_exception(Exception(err_msg))
                            else:
                                future.set_result(msg.get("result"))
                elif "method" in msg:
                    method = msg.get("method")
                    if method in APPROVAL_METHODS:
                        await self._handle_tool_approval(msg)
                    elif "id" not in msg:
                        if self.notification_handler:
                            asyncio.create_task(self.notification_handler(msg))
                        await self._handle_notification(msg)
                    else:
                        logger.info(f"Incoming request from worker: {method}")
                        err_resp = Protocol.build_error(msg["id"], -32601, f"Method '{method}' not implemented")
                        if self.process and self.process.stdin and not self.process.stdin.is_closing():
                            self.process.stdin.write((err_resp + "\n").encode("utf-8"))
                            await self.process.stdin.drain()
            except Exception as e:
                if not self.running:
                    break
                logger.error(f"Error parsing JSON-RPC line: {e}")

    async def _handle_tool_approval(self, msg: dict):
        from backend.services import governance_service
        params = msg.get("params", {}) or {}
        resp_id = msg.get("id") or params.get("resp_id") or params.get("id")
        tool_call_id = (
            params.get("toolCallId")
            or params.get("tool_call_id")
            or params.get("approval_id")
            or params.get("id")
            or f"tc_{uuid.uuid4().hex[:8]}"
        )
        command = params.get("command") or params.get("cmd") or ""
        if not command and isinstance(params.get("parameters"), dict):
            command = params["parameters"].get("command") or params["parameters"].get("cmd") or ""
        tool_name = params.get("tool_name") or params.get("toolName") or params.get("name")
        raw_thread_id = (
            params.get("threadId")
            or params.get("thread_id")
            or self.thread_id
        )
        thread_id = self.resolve_thread_id(raw_thread_id)
        if not thread_id:
            with SessionLocal() as db:
                active_turn = db.query(Turn).filter(Turn.status == "active").order_by(Turn.id.desc()).first()
                if active_turn:
                    thread_id = active_turn.thread_id
                else:
                    latest_thread = db.query(Thread).order_by(Thread.created_at.desc()).first()
                    if latest_thread:
                        thread_id = latest_thread.id
                    else:
                        thread_id = "default"

        # Evaluate risk level using governance_service
        risk_level, requires_approval, consequence = governance_service.evaluate_tool_risk(
            command=command,
            tool_name=tool_name
        )

        if not requires_approval or risk_level == governance_service.RISK_LOW:
            # LOW risk -> Auto-approve if permitted by policy
            logger.info(f"Auto-approving LOW risk command '{command}' (tool_call_id={tool_call_id})")
            if resp_id is not None:
                res_msg = Protocol.build_response(resp_id, {"approved": True})
                await self.send_raw(res_msg)
            return

        # HIGH or CRITICAL risk (or requires_approval is True) -> Pause execution and create pending ToolApproval
        logger.info(f"Tool approval required for {risk_level} command: '{command}'")
        with SessionLocal() as db:
            approval = governance_service.create_approval_request(
                thread_id=thread_id,
                tool_call_id=tool_call_id,
                command=command,
                risk_level=risk_level,
                consequence=consequence,
                db=db
            )

        # Register pending RPC so resolution can respond back to worker
        governance_service.register_pending_rpc(
            tool_call_id=tool_call_id,
            resp_id=resp_id,
            worker=self,
            approval_id=approval.id
        )

    async def _read_stderr(self):
        if not self.process or not self.process.stderr:
            return

        while self.running and not self.process.stderr.at_eof():
            try:
                line = await self.process.stderr.readline()
                if not line:
                    break
                raw_line = line.decode("utf-8", errors="replace").strip()
                if raw_line:
                    logger.debug(f"[Worker stderr] {raw_line}")
                    self.stderr_lines.append(raw_line)
                    if len(self.stderr_lines) > 100:
                        self.stderr_lines.pop(0)
            except Exception as e:
                if not self.running:
                    break
                logger.debug(f"Error reading stderr: {e}")

    async def _handle_notification(self, msg: dict):
        method = msg.get("method")
        params = msg.get("params", {})

        if method == "notification/event":
            raw_thread_id = params.get("thread_id") or params.get("threadId")
            thread_id = self.resolve_thread_id(raw_thread_id)
            if not thread_id:
                return

            env = EventEnvelope(
                project_id=params.get("project_id", "default"),
                thread_id=thread_id,
                type=params.get("type", "unknown"),
                payload=params.get("payload", {}),
            )
            broker.publish_event(env)

            if params.get("type") in ["text", "tool_call", "tool_result"]:
                try:
                    with SessionLocal() as db:
                        turn = (
                            db.query(Turn)
                            .filter(Turn.thread_id == thread_id, Turn.status == "active")
                            .order_by(Turn.turn_number.desc())
                            .first()
                        )
                        if turn:
                            seq = db.query(Item).filter(Item.turn_id == turn.id).count() + 1
                            new_item = Item(
                                id=env.id,
                                turn_id=turn.id,
                                item_type=params["type"],
                                content=params.get("payload", {}),
                                sequence=seq,
                            )
                            db.add(new_item)
                            db.commit()
                except Exception as db_err:
                    logger.error(f"Error persisting item from notification: {db_err}")
        else:
            raw_thread_id = (
                params.get("threadId")
                or params.get("thread_id")
                or self.thread_id
                or ""
            )
            eff_thread_id = self.resolve_thread_id(raw_thread_id)
            norm_env = Protocol.normalize_notification(method, params, thread_id=eff_thread_id)
            if norm_env:
                broker.publish_event(norm_env)

                try:
                    with SessionLocal() as db:
                        target_thread_id = eff_thread_id or norm_env.thread_id
                        if not target_thread_id:
                            return

                        if norm_env.type == "turn_completed":
                            turn = (
                                db.query(Turn)
                                .filter(Turn.thread_id == target_thread_id, Turn.status == "active")
                                .order_by(Turn.turn_number.desc())
                                .first()
                            )
                            if not turn:
                                turn_id_val = norm_env.payload.get("turn_id") or norm_env.payload.get("turnId")
                                if isinstance(turn_id_val, int):
                                    turn = db.query(Turn).filter(Turn.thread_id == target_thread_id, Turn.id == turn_id_val).first()
                                    if not turn:
                                        turn = db.query(Turn).filter(Turn.thread_id == target_thread_id, Turn.turn_number == turn_id_val).first()
                                elif isinstance(turn_id_val, str) and turn_id_val.isdigit():
                                    int_tid = int(turn_id_val)
                                    turn = db.query(Turn).filter(Turn.thread_id == target_thread_id, Turn.id == int_tid).first()
                                    if not turn:
                                        turn = db.query(Turn).filter(Turn.thread_id == target_thread_id, Turn.turn_number == int_tid).first()

                            if turn:
                                turn.status = "completed"
                                turn.completed_at = datetime.now(timezone.utc)
                                db.commit()

                        elif norm_env.type == "agent_message" and norm_env.payload.get("is_streaming") is False:
                            turn = (
                                db.query(Turn)
                                .filter(Turn.thread_id == target_thread_id, Turn.status == "active")
                                .order_by(Turn.turn_number.desc())
                                .first()
                            )
                            if not turn:
                                turn = (
                                    db.query(Turn)
                                    .filter(Turn.thread_id == target_thread_id)
                                    .order_by(Turn.turn_number.desc())
                                    .first()
                                )
                            if turn:
                                item_id = (
                                    norm_env.payload.get("item_id")
                                    or norm_env.payload.get("itemId")
                                    or norm_env.id
                                )
                                existing_item = db.query(Item).filter(Item.id == item_id).first()
                                if not existing_item:
                                    seq = db.query(Item).filter(Item.turn_id == turn.id).count() + 1
                                    new_item = Item(
                                        id=item_id,
                                        turn_id=turn.id,
                                        item_type="text",
                                        content=norm_env.payload,
                                        sequence=seq,
                                    )
                                    db.add(new_item)
                                    db.commit()

                        elif norm_env.type in ("command", "tool_call", "tool_result"):
                            turn = (
                                db.query(Turn)
                                .filter(Turn.thread_id == target_thread_id, Turn.status == "active")
                                .order_by(Turn.turn_number.desc())
                                .first()
                            )
                            if not turn:
                                turn = (
                                    db.query(Turn)
                                    .filter(Turn.thread_id == target_thread_id)
                                    .order_by(Turn.turn_number.desc())
                                    .first()
                                )
                            if turn:
                                item_id = (
                                    norm_env.payload.get("item_id")
                                    or norm_env.payload.get("itemId")
                                    or norm_env.id
                                )
                                existing_item = db.query(Item).filter(Item.id == item_id).first()
                                if not existing_item:
                                    seq = db.query(Item).filter(Item.turn_id == turn.id).count() + 1
                                    item_type = "command" if norm_env.type == "command" else norm_env.type
                                    new_item = Item(
                                        id=item_id,
                                        turn_id=turn.id,
                                        item_type=item_type,
                                        content=norm_env.payload,
                                        sequence=seq,
                                    )
                                    db.add(new_item)
                                    db.commit()

                except Exception as db_err:
                    logger.error(f"Error persisting item from normalized notification: {db_err}")

    async def stop(self, timeout: float = 5.0):
        self.running = False

        if self.process and self.process.returncode is None:
            if self.process.stdin and not self.process.stdin.is_closing():
                try:
                    self.process.stdin.close()
                except Exception:
                    pass

            # 1. Dispatch interrupt
            try:
                if sys.platform == "win32":
                    os.kill(self.process.pid, signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
            except Exception as e:
                logger.debug(f"Interrupt dispatch failed: {e}")
                try:
                    self.process.terminate()
                except Exception:
                    pass

            # 2. Await termination
            try:
                await asyncio.wait_for(self.process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Process {self.process.pid} did not exit within {timeout}s, killing process group")
                # 3. Fall back to process group kill
                self._kill_process_group()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except Exception:
                    pass

        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except (asyncio.CancelledError, Exception):
                pass

        for future in list(self.pending_requests.values()):
            if not future.done():
                future.set_exception(RuntimeError("Worker stopped"))
        self.pending_requests.clear()

    def _kill_process_group(self):
        if not self.process:
            return
        pid = self.process.pid
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception as e:
                logger.debug(f"taskkill failed: {e}")
            try:
                self.process.kill()
            except Exception:
                pass
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception as e:
                logger.debug(f"killpg failed: {e}")
            try:
                self.process.kill()
            except Exception:
                pass


CodexWorker = WorkerProcess
