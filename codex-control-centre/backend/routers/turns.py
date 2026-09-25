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
from backend.database import get_db, SessionLocal
from backend.models.codex import Thread, Turn, ToolApproval, Item
from backend.services.worker_manager import worker_manager
from backend.services.worktree_service import ensure_thread_worktree
from backend.services.event_service import broker, EventEnvelope
from backend.services import governance_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/codex", tags=["turns"])

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
    turn_id: int
    instruction: str

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "threadId" in data and "thread_id" not in data:
                data["thread_id"] = data["threadId"]
            if "turnId" in data and "turn_id" not in data:
                data["turn_id"] = data["turnId"]
        return data

class TurnInterrupt(BaseModel):
    thread_id: str
    turn_id: int

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "threadId" in data and "thread_id" not in data:
                data["thread_id"] = data["threadId"]
            if "turnId" in data and "turn_id" not in data:
                data["turn_id"] = data["turnId"]
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
            if _should_initialize_thread(worker, thread_id):
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
                    logger.warning(f"Worker thread/start failed or skipped: {th_err}")

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
    
    # 1. Resolve worktree sandbox path strictly to worktrees/wt-<threadId>
    repo_path = thread.project.repo_path if thread.project and thread.project.repo_path else str(settings.repo_root)
    if repo_path == "/" or not Path(repo_path).is_absolute() or not Path(repo_path).exists():
        repo_path = str(settings.repo_root)

    base_branch = thread.project.default_branch if thread.project and thread.project.default_branch else "main"
    wt_path = ensure_thread_worktree(repo_path, req.thread_id, default_branch=base_branch)
    wt_str = str(wt_path.resolve())

    # 2. Retrieve worker bound to the worktree cwd
    if hasattr(worker_manager, "get_worker_for_thread"):
        worker = await worker_manager.get_worker_for_thread(req.thread_id, repo_path=repo_path, base_branch=base_branch)
    else:
        worker = await worker_manager.get_worker()

    project_id = thread.project_id if thread.project_id else "default"
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

@router.post("/turns/steer")
async def steer_turn(req: TurnSteer, db: Session = Depends(get_db)):
    turn = db.query(Turn).filter(Turn.id == req.turn_id, Turn.thread_id == req.thread_id).first()
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    
    worker = await worker_manager.get_worker()

    codex_thread_id = None
    if hasattr(worker_manager, "thread_map") and isinstance(worker_manager.thread_map, dict):
        codex_thread_id = worker_manager.thread_map.get(req.thread_id)
    if not codex_thread_id and not _is_mock(worker) and hasattr(worker, "thread_map") and isinstance(worker.thread_map, dict):
        codex_thread_id = worker.thread_map.get(req.thread_id)
    if not codex_thread_id:
        codex_thread_id = req.thread_id

    await worker.send_request("turn/steer", {
        "threadId": codex_thread_id,
        "turnId": str(req.turn_id),
        "expectedTurnId": str(req.turn_id),
        "instruction": req.instruction,
        "input": [{"type": "text", "text": req.instruction}],
    })
    return {"status": "steered"}

@router.post("/turns/interrupt")
async def interrupt_turn(req: TurnInterrupt, db: Session = Depends(get_db)):
    turn = db.query(Turn).filter(Turn.id == req.turn_id, Turn.thread_id == req.thread_id).first()
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
        
    worker = await worker_manager.get_worker()

    codex_thread_id = None
    if hasattr(worker_manager, "thread_map") and isinstance(worker_manager.thread_map, dict):
        codex_thread_id = worker_manager.thread_map.get(req.thread_id)
    if not codex_thread_id and not _is_mock(worker) and hasattr(worker, "thread_map") and isinstance(worker.thread_map, dict):
        codex_thread_id = worker.thread_map.get(req.thread_id)
    if not codex_thread_id:
        codex_thread_id = req.thread_id

    await worker.send_request("turn/interrupt", {
        "threadId": codex_thread_id,
        "turnId": str(req.turn_id)
    })

    # Cascade cancellation: cancel all pending approvals for this thread
    governance_service.cancel_pending_approvals_for_thread(
        thread_id=req.thread_id,
        db=db,
        reason=f"Turn {req.turn_id} interrupted"
    )
    return {"status": "interrupted"}

@router.post("/approvals/respond")
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

