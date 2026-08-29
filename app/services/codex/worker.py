import asyncio
import json
import logging
from typing import Dict, Any, Callable, Awaitable, Optional
from .protocol import JsonRpcRequest, JsonRpcResponse, JsonRpcNotification

logger = logging.getLogger(__name__)

class CodexWorker:
    def __init__(self, command: list[str]):
        self.command = command
        self.process: Optional[asyncio.subprocess.Process] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._next_id = 1
        self.running = False
        self._read_task: Optional[asyncio.Task] = None
        self.notification_handler: Optional[Callable[[JsonRpcNotification], Awaitable[None]]] = None

    async def start(self):
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self.running = True
        self._read_task = asyncio.create_task(self._read_loop())

    async def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        if self._read_task:
            self._read_task.cancel()
            
        for future in self.pending_requests.values():
            if not future.done():
                future.set_exception(RuntimeError("Worker stopped"))

    async def _read_loop(self):
        if not self.process or not self.process.stdout:
            return

        while self.running and not self.process.stdout.at_eof():
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                
                data = json.loads(line.decode('utf-8').strip())
                if "id" in data and ("result" in data or "error" in data):
                    # It's a response
                    response = JsonRpcResponse(**data)
                    req_id = str(response.id)
                    if req_id in self.pending_requests:
                        self.pending_requests[req_id].set_result(response)
                        del self.pending_requests[req_id]
                elif "method" in data:
                    if "id" in data:
                        # We don't handle incoming requests
                        pass
                    else:
                        # It's a notification
                        notification = JsonRpcNotification(**data)
                        if self.notification_handler:
                            asyncio.create_task(self.notification_handler(notification))
            except Exception as e:
                logger.error(f"Error parsing JSON-RPC line: {e}")

    async def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> JsonRpcResponse:
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not running")

        req_id = str(self._next_id)
        self._next_id += 1

        request = JsonRpcRequest(id=req_id, method=method, params=params)
        future = asyncio.get_running_loop().create_future()
        self.pending_requests[req_id] = future

        msg = request.model_dump_json(exclude_none=True) + "\n"
        self.process.stdin.write(msg.encode('utf-8'))
        await self.process.stdin.drain()

        return await future
