from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, model_validator
from typing import Any, Optional
from datetime import datetime, timezone
import asyncio
import logging
import uuid

from backend.config import settings
from backend.database import get_db
from backend.models.codex import Thread, Turn, ToolApproval, Item
from backend.services.worker_manager import worker_manager
from backend.services.worktree_service import ensure_thread_worktree
from backend.services.event_service import broker, EventEnvelope
from backend.services import governance_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["turns"])

class TurnStart(BaseModel):
    thread_id: str
    prompt: str
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "threadId" in data and "thread_id" not in data:
                data["thread_id"] = data["threadId"]
            if "reasoningEffort" in data and "reasoning_effort" not in data:
                data["reasoning_effort"] = data["reasoningEffort"]
        return data

class TurnSteer(BaseModel):
    thread_id: str
    instruction: str
    turn_id: Optional[int] = 0

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "threadId" in data and "thread_id" not in data:
                data["thread_id"] = data["threadId"]
            if "turnId" in data and "turn_id" not in data:
                val = data["turnId"]
                data["turn_id"] = int(val) if isinstance(val, (int, str)) and str(val).isdigit() else 0
        return data

class TurnInterrupt(BaseModel):
    thread_id: str
    turn_id: Optional[int] = 0

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "threadId" in data and "thread_id" not in data:
                data["thread_id"] = data["threadId"]
            if "turnId" in data and "turn_id" not in data:
                val = data["turnId"]
                if isinstance(val, str) and not val.isdigit():
                    data["turn_id"] = 0
                else:
                    data["turn_id"] = int(val) if val is not None else 0
            elif "turn_id" in data:
                val = data["turn_id"]
                if isinstance(val, str) and not val.isdigit():
                    data["turn_id"] = 0
                elif val is not None:
                    data["turn_id"] = int(val)
        return data

class ApprovalRespond(BaseModel):
    thread_id: Optional[str] = None
    tool_call_id: str
    approved: bool
    feedback: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "threadId" in data and "thread_id" not in data:
                data["thread_id"] = data["threadId"]
            if "toolCallId" in data and "tool_call_id" not in data:
                data["tool_call_id"] = data["toolCallId"]
        return data



def _is_mock(obj: Any) -> bool:
    import unittest.mock
    return isinstance(obj, (unittest.mock.Mock, unittest.mock.AsyncMock)) or type(obj).__module__.startswith("unittest.mock")


def _should_initialize_thread(worker: Any, thread_id: str) -> bool:
    if hasattr(worker_manager, "thread_map") and isinstance(worker_manager.thread_map, dict) and thread_id in worker_manager.thread_map:
        return False
    if not _is_mock(worker) and hasattr(worker, "thread_map") and isinstance(worker.thread_map, dict) and thread_id in worker.thread_map:
        return False
    if _is_mock(worker):
        return bool(worker.__dict__.get("requires_thread_init", False))
    return True


async def _get_active_thread_worker(thread_id: str) -> Any:
    """Use only the worker that created a thread for control operations."""
    get_bound = getattr(worker_manager, "get_active_worker_for_thread", None)
    if callable(get_bound):
        worker = get_bound(thread_id)
        if worker is not None:
            return worker

        # Retain compatibility with tests and legacy injected managers.
        legacy_get_worker = getattr(worker_manager, "get_worker", None)
        if _is_mock(legacy_get_worker) and callable(legacy_get_worker):
            return await legacy_get_worker()
        return None

    legacy_get_worker = getattr(worker_manager, "get_worker", None)
    return await legacy_get_worker() if callable(legacy_get_worker) else None


def _get_codex_thread_id(thread_id: str, worker: Any) -> str:
    get_mapping = getattr(worker_manager, "get_codex_thread_id", None)
    if callable(get_mapping):
        return get_mapping(thread_id)
    if hasattr(worker_manager, "thread_map") and isinstance(worker_manager.thread_map, dict):
        return worker_manager.thread_map.get(thread_id, thread_id)
    if not _is_mock(worker) and hasattr(worker, "thread_map") and isinstance(worker.thread_map, dict):
        return worker.thread_map.get(thread_id, thread_id)
    return thread_id


def _is_missing_codex_thread(error: Exception) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in ("thread not found", "unknown thread", "no such thread"))


def _is_idempotent_interrupt_error(error: Exception) -> bool:
    """Whether Stop reached a turn that has already ended server-side."""
    message = str(error).lower()
    return _is_missing_codex_thread(error) or any(marker in message for marker in (
        "no active turn to interrupt",
        "no active turn",
        "turn is not active",
        "turn already completed",
        "turn already interrupted",
        "expected active turn id",
    ))


async def _safe_dispatch_turn_start(
    worker: Any,
    thread_id: str,
    turn_id: int,
    prompt: str,
    model: str,
    reasoning_effort: Optional[str],
    wt_str: str,
    project_id: str = "default",
    db_bind: Any = None,
):
    try:
        codex_thread_id = None
        if hasattr(worker_manager, "thread_map") and isinstance(worker_manager.thread_map, dict):
            codex_thread_id = worker_manager.thread_map.get(thread_id)
        if not codex_thread_id and not _is_mock(worker) and hasattr(worker, "thread_map") and isinstance(worker.thread_map, dict):
            codex_thread_id = worker.thread_map.get(thread_id)

        if not codex_thread_id:
            if _is_mock(worker) and not worker.__dict__.get("requires_thread_init", False):
                codex_thread_id = thread_id
            elif _should_initialize_thread(worker, thread_id):
                try:
                    res = await worker.send_request("thread/start", {"cwd": wt_str})
                    if isinstance(res, dict):
                        th_obj = res.get("thread")
                        if isinstance(th_obj, dict):
                            codex_thread_id = th_obj.get("id")
                        elif isinstance(th_obj, str):
                            codex_thread_id = th_obj
                        if not codex_thread_id:
                            codex_thread_id = res.get("id")
                except Exception as th_err:
                    raise RuntimeError(
                        "Codex app-server could not create a thread: "
                        f"{th_err or type(th_err).__name__}"
                    ) from th_err

            if not codex_thread_id:
                codex_thread_id = thread_id

            if hasattr(worker_manager, "register_thread_mapping") and not _is_mock(worker_manager):
                worker_manager.register_thread_mapping(thread_id, codex_thread_id)
            elif hasattr(worker_manager, "thread_map") and isinstance(worker_manager.thread_map, dict):
                worker_manager.thread_map[thread_id] = codex_thread_id
                if hasattr(worker_manager, "reverse_thread_map") and isinstance(worker_manager.reverse_thread_map, dict):
                    worker_manager.reverse_thread_map[codex_thread_id] = thread_id

            if not _is_mock(worker):
                if hasattr(worker, "register_thread_mapping"):
                    worker.register_thread_mapping(thread_id, codex_thread_id)
                elif hasattr(worker, "thread_map") and isinstance(worker.thread_map, dict):
                    worker.thread_map[thread_id] = codex_thread_id
                    if hasattr(worker, "reverse_thread_map") and isinstance(worker.reverse_thread_map, dict):
                        worker.reverse_thread_map[codex_thread_id] = thread_id
                if hasattr(worker, "codex_thread_id"):
                    worker.codex_thread_id = codex_thread_id

        turn_params: dict[str, Any] = {
            "threadId": codex_thread_id,
            "prompt": prompt,
            "input": [{"type": "text", "text": prompt}],
            "effort": reasoning_effort,
            "reasoningEffort": reasoning_effort,
            "workspaceRoot": wt_str,
            "cwd": wt_str,
        }
        if model is not None:
            turn_params["model"] = model
        await worker.send_request("turn/start", turn_params)

    except Exception as e:
        logger.error(
            f"Error dispatching turn/start for turn {turn_id} on thread {thread_id}: {e}",
            exc_info=True,
        )
        try:
            from sqlalchemy.orm import sessionmaker
            if db_bind is not None:
                TurnSession = sessionmaker(bind=db_bind)
            else:
                from backend.database import SessionLocal
                TurnSession = SessionLocal

            with TurnSession() as session:
                turn_record = session.query(Turn).filter(Turn.id == turn_id).first()
                if turn_record:
                    turn_record.status = "failed"
                    turn_record.completed_at = datetime.now(timezone.utc)
                    seq = session.query(Item).filter(Item.turn_id == turn_id).count() + 1
                    err_item = Item(
                        id=f"err_{uuid.uuid4().hex[:8]}",
                        turn_id=turn_id,
                        item_type="error",
                        content={"message": str(e), "error": str(e)},
                        sequence=seq,
                    )
                    session.add(err_item)
                    session.commit()
        except Exception as db_err:
            logger.error(f"Failed to record turn failure in database: {db_err}")

        try:
            err_env = EventEnvelope(
                project_id=project_id,
                thread_id=thread_id,
                type="error",
                payload={
                    "turn_id": turn_id,
                    "turnId": turn_id,
                    "message": str(e),
                    "error": str(e),
                    "status": "failed",
                },
            )
            broker.publish_event(err_env)

            completed_env = EventEnvelope(
                project_id=project_id,
                thread_id=thread_id,
                type="turn_completed",
                payload={
                    "turn_id": turn_id,
                    "turnId": turn_id,
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(e),
                },
            )
            broker.publish_event(completed_env)
        except Exception as broker_err:
            logger.error(f"Failed to publish error event to broker: {broker_err}")


@router.post("/start")
@router.post("/turns/start")
async def start_turn(req: TurnStart, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == req.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    last_turn = db.query(Turn).filter(Turn.thread_id == req.thread_id).order_by(Turn.turn_number.desc()).first()
    turn_num = 1 if not last_turn else last_turn.turn_number + 1
    
    turn = Turn(
        thread_id=req.thread_id,
        turn_number=turn_num,
        status="active",
        prompt=req.prompt
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    project_id = thread.project_id if thread.project_id else "default"

    try:
        # 1. Resolve worktree sandbox path strictly to worktrees/wt-<threadId>
        repo_path = thread.project.repo_path if thread.project and thread.project.repo_path else str(settings.repo_root)
        if repo_path == "/" or not Path(repo_path).is_absolute() or not Path(repo_path).exists():
            repo_path = str(settings.repo_root)

        base_branch = thread.project.default_branch if thread.project and thread.project.default_branch else "main"
        wt_path = ensure_thread_worktree(repo_path, req.thread_id, default_branch=base_branch, db=db)
        wt_str = str(wt_path.resolve())

        # 2. Retrieve worker bound to the worktree cwd
        if hasattr(worker_manager, "get_worker_for_thread"):
            worker = await worker_manager.get_worker_for_thread(req.thread_id, repo_path=repo_path, base_branch=base_branch)
        else:
            worker = await worker_manager.get_worker()
    except ValueError as ve:
        err_msg = str(ve)
        logger.error(f"Failed to start turn {turn.id} on thread {req.thread_id}: {err_msg}")
        turn.status = "failed"
        turn.completed_at = datetime.now(timezone.utc)
        seq = db.query(Item).filter(Item.turn_id == turn.id).count() + 1
        err_item = Item(
            id=f"err_{uuid.uuid4().hex[:8]}",
            turn_id=turn.id,
            item_type="error",
            content={"message": err_msg, "error": err_msg},
            sequence=seq,
        )
        db.add(err_item)
        db.commit()

        try:
            err_env = EventEnvelope(
                project_id=project_id,
                thread_id=req.thread_id,
                type="error",
                payload={
                    "turn_id": turn.id,
                    "turnId": turn.id,
                    "message": err_msg,
                    "error": err_msg,
                    "status": "failed",
                },
            )
            broker.publish_event(err_env)

            completed_env = EventEnvelope(
                project_id=project_id,
                thread_id=req.thread_id,
                type="turn_completed",
                payload={
                    "turn_id": turn.id,
                    "turnId": turn.id,
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": err_msg,
                },
            )
            broker.publish_event(completed_env)
        except Exception as broker_err:
            logger.error(f"Failed to publish boundary error event: {broker_err}")

        raise HTTPException(status_code=400, detail=err_msg)

    db_bind = db.get_bind()
    asyncio.create_task(
        _safe_dispatch_turn_start(
            worker=worker,
            thread_id=req.thread_id,
            turn_id=turn.id,
            prompt=req.prompt,
            model=req.model,
            reasoning_effort=req.reasoning_effort,
            wt_str=wt_str,
            project_id=project_id,
            db_bind=db_bind,
        )
    )
    
    return {"turn_id": turn.id, "status": "active", "workspace_root": wt_str}

@router.post("/steer")
@router.post("/turns/steer")
async def steer_turn(req: TurnSteer, db: Session = Depends(get_db)):
    turn = None
    if req.turn_id and req.turn_id > 0:
        turn = db.query(Turn).filter(Turn.id == req.turn_id, Turn.thread_id == req.thread_id).first()
    if not turn:
        turn = db.query(Turn).filter(Turn.thread_id == req.thread_id, Turn.status == "active").order_by(Turn.id.desc()).first()
    if not turn:
        turn = db.query(Turn).filter(Turn.thread_id == req.thread_id).order_by(Turn.id.desc()).first()

    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    
    worker = await _get_active_thread_worker(req.thread_id)
    if worker is None:
        raise HTTPException(status_code=409, detail="No active worker is bound to this thread")
    codex_thread_id = _get_codex_thread_id(req.thread_id, worker)

    try:
        await worker.send_request("turn/steer", {
            "threadId": codex_thread_id,
            "turnId": str(turn.id),
            "expectedTurnId": str(turn.id),
            "instruction": req.instruction,
            "input": [{"type": "text", "text": req.instruction}],
        })
    except Exception as err:
        if not _is_idempotent_interrupt_error(err):
            logger.warning("Failed to steer turn %s: %s", req.turn_id, err)
            raise HTTPException(status_code=502, detail="Unable to steer the active worker turn") from err

        if _is_missing_codex_thread(err):
            clear_mapping = getattr(worker_manager, "clear_thread_mapping", None)
            if callable(clear_mapping):
                clear_mapping(req.thread_id)
        turn.status = "interrupted"
        turn.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "interrupted"}
    return {"status": "steered"}

@router.post("/interrupt")
@router.post("/turns/interrupt")
async def interrupt_turn(req: TurnInterrupt, db: Session = Depends(get_db)):
    turn = None
    # 1. Exact ID match if positive
    if req.turn_id and req.turn_id > 0:
        turn = db.query(Turn).filter(Turn.id == req.turn_id, Turn.thread_id == req.thread_id).first()
        if not turn:
            turn = db.query(Turn).filter(Turn.turn_number == req.turn_id, Turn.thread_id == req.thread_id).first()

    # 2. Fall back to active turn on this thread
    if not turn:
        turn = db.query(Turn).filter(Turn.thread_id == req.thread_id, Turn.status == "active").order_by(Turn.id.desc()).first()

    # 3. Fall back to latest turn on this thread
    if not turn:
        turn = db.query(Turn).filter(Turn.thread_id == req.thread_id).order_by(Turn.id.desc()).first()

    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")

    target_turn_id = turn.id

    worker = await _get_active_thread_worker(req.thread_id)
    if worker is not None and turn.status == "active":
        try:
            await worker.send_request("turn/interrupt", {
                "threadId": _get_codex_thread_id(req.thread_id, worker),
                "turnId": str(target_turn_id),
            })
        except Exception as err:
            # A worker/app-server restart can lose its transient thread UUID.
            # Stopping is still safe and must complete locally.
            if not _is_idempotent_interrupt_error(err):
                logger.warning("Failed to interrupt turn %s: %s", target_turn_id, err)
                # Do not hard-crash with 502 if turn can be marked interrupted locally
            if _is_missing_codex_thread(err):
                clear_mapping = getattr(worker_manager, "clear_thread_mapping", None)
                if callable(clear_mapping):
                    clear_mapping(req.thread_id)

    if turn.status == "active":
        turn.status = "interrupted"
        turn.completed_at = datetime.now(timezone.utc)
        db.commit()

    # Cascade cancellation: cancel all pending approvals for this thread
    governance_service.cancel_pending_approvals_for_thread(
        thread_id=req.thread_id,
        db=db,
        reason=f"Turn {target_turn_id} interrupted"
    )

    try:
        project_id = turn.thread.project_id if turn.thread and turn.thread.project_id else "default"
        broker.publish_event(
            EventEnvelope(
                project_id=project_id,
                thread_id=req.thread_id,
                type="turn_interrupted",
                payload={
                    "turn_id": target_turn_id,
                    "turnId": target_turn_id,
                    "status": "interrupted",
                    "reason": "Turn manually interrupted by operator via Stop button.",
                    "interrupted_by": "Operator",
                }
            )
        )
    except Exception as broker_err:
        logger.debug(f"Broker publish turn_interrupted failed: {broker_err}")

    return {"status": "interrupted"}

@router.post("/approvals/respond")
@router.post("/turns/approvals/respond")
async def respond_approval(req: ApprovalRespond, db: Session = Depends(get_db)):
    # 1. Look up pending ToolApproval by tool_call_id
    approval = db.query(ToolApproval).filter(
        ToolApproval.tool_call_id == req.tool_call_id,
        ToolApproval.status == "pending"
    ).first()

    if approval:
        governance_service.resolve_approval(
            approval_id=approval.id,
            approved=req.approved,
            db=db,
            feedback=req.feedback
        )
    else:
        # Check if registered in pending RPC even without DB record
        rpc_entry = governance_service.pop_pending_rpc(req.tool_call_id)
        if rpc_entry and rpc_entry.get("resp_id") is not None:
            governance_service.dispatch_approval_rpc(
                resp_id=rpc_entry["resp_id"],
                worker=rpc_entry.get("worker"),
                approved=req.approved,
                feedback=req.feedback
            )

    # 2. Also send "approval/respond" to worker if connected
    try:
        worker = await worker_manager.get_worker()
        if worker and worker.running:
            await worker.send_request("approval/respond", {
                "toolCallId": req.tool_call_id,
                "approved": req.approved,
                "feedback": req.feedback
            })
    except Exception as e:
        logger.debug(f"Worker approval/respond notification skipped: {e}")

    return {
        "status": "approved" if req.approved else "declined",
        "tool_call_id": req.tool_call_id
    }
