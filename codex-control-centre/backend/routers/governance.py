from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services import governance_service
from backend.services.worker_manager import worker_manager

router = APIRouter(prefix="/codex/governance", tags=["governance"])


# -------------------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------------------

class ToolApprovalResponse(BaseModel):
    id: str
    thread_id: str
    tool_call_id: str
    command: str
    risk_level: str
    consequence: str
    status: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreateApprovalRequest(BaseModel):
    thread_id: str
    tool_call_id: str
    command: str
    risk_level: Optional[str] = None
    consequence: Optional[str] = None
    profile: Optional[str] = governance_service.PROFILE_MANAGED


class ResolveApprovalRequest(BaseModel):
    approved: bool
    feedback: Optional[str] = None


class SubAgentResponse(BaseModel):
    id: str
    thread_id: str
    parent_thread_id: Optional[str] = None
    name: str
    role: str
    status: str
    progress: int
    current_action: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RegisterSubAgentRequest(BaseModel):
    thread_id: str
    parent_thread_id: Optional[str] = None
    name: str
    role: str


class SteerSubAgentRequest(BaseModel):
    instruction: str


class UpdateProgressRequest(BaseModel):
    progress: int = Field(ge=0, le=100)
    current_action: Optional[str] = None
    status: str = "active"


class EvaluateRiskRequest(BaseModel):
    command: str
    tool_name: Optional[str] = None
    profile: Optional[str] = governance_service.PROFILE_MANAGED


class RiskEvaluationResponse(BaseModel):
    command: str
    tool_name: Optional[str] = None
    risk_level: str
    requires_approval: bool
    consequence: str
    profile: str


# -------------------------------------------------------------
# Approval Endpoints
# -------------------------------------------------------------

@router.get("/approvals/pending", response_model=List[ToolApprovalResponse])
def get_pending_approvals(
    thread_id: Optional[str] = Query(None, description="Optional thread ID filter"),
    db: Session = Depends(get_db)
):
    """
    Lists all pending tool approval requests, optionally filtered by thread_id.
    """
    return governance_service.list_pending_approvals(db=db, thread_id=thread_id)


@router.post("/approvals", response_model=ToolApprovalResponse)
def create_approval(
    req: CreateApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Creates a new tool approval gate request.
    """
    risk_level = req.risk_level
    consequence = req.consequence
    if not risk_level or not consequence:
        eval_risk, _, eval_consequence = governance_service.evaluate_tool_risk(
            command=req.command,
            profile=req.profile or governance_service.PROFILE_MANAGED
        )
        risk_level = risk_level or eval_risk
        consequence = consequence or eval_consequence

    try:
        return governance_service.create_approval_request(
            thread_id=req.thread_id,
            tool_call_id=req.tool_call_id,
            command=req.command,
            risk_level=risk_level,
            consequence=consequence,
            db=db
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/approvals/{approval_id}/resolve", response_model=ToolApprovalResponse)
async def resolve_approval_endpoint(
    approval_id: str,
    req: ResolveApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Resolves an approval gate ('approved' or 'declined') and notifies worker process.
    """
    try:
        approval = governance_service.resolve_approval(
            approval_id=approval_id,
            approved=req.approved,
            db=db,
            feedback=req.feedback
        )
        try:
            worker = await worker_manager.get_worker()
            if worker and worker.running:
                await worker.send_request("approval/respond", {
                    "toolCallId": approval.tool_call_id,
                    "approved": req.approved,
                    "feedback": req.feedback
                })
        except Exception:
            pass
        return approval
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -------------------------------------------------------------
# Subagent Governance Endpoints
# -------------------------------------------------------------

@router.get("/subagents/{thread_id}", response_model=List[SubAgentResponse])
def get_subagents_for_thread(
    thread_id: str,
    db: Session = Depends(get_db)
):
    """
    Lists all subagents attached to a thread.
    """
    return governance_service.list_subagents_for_thread(thread_id=thread_id, db=db)


@router.post("/subagents/register", response_model=SubAgentResponse)
def register_subagent_endpoint(
    req: RegisterSubAgentRequest,
    db: Session = Depends(get_db)
):
    """
    Registers a new subagent while enforcing maximum active concurrency (6).
    """
    try:
        return governance_service.register_subagent(
            thread_id=req.thread_id,
            parent_thread_id=req.parent_thread_id,
            name=req.name,
            role=req.role,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/subagents/{subagent_id}/progress", response_model=SubAgentResponse)
def update_subagent_progress_endpoint(
    subagent_id: str,
    req: UpdateProgressRequest,
    db: Session = Depends(get_db)
):
    """
    Updates progress telemetry for a subagent.
    """
    try:
        return governance_service.update_subagent_progress(
            subagent_id=subagent_id,
            progress=req.progress,
            current_action=req.current_action,
            status=req.status,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/subagents/{subagent_id}/steer")
def steer_subagent_endpoint(
    subagent_id: str,
    req: SteerSubAgentRequest,
    db: Session = Depends(get_db)
):
    """
    Transmits steering guidance to a running subagent.
    """
    try:
        return governance_service.steer_subagent(
            subagent_id=subagent_id,
            instruction=req.instruction,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/subagents/{subagent_id}/stop", response_model=SubAgentResponse)
def stop_subagent_endpoint(
    subagent_id: str,
    db: Session = Depends(get_db)
):
    """
    Stops/terminates a running subagent.
    """
    try:
        return governance_service.stop_subagent(subagent_id=subagent_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/threads/{thread_id}/terminate-subagents")
def terminate_thread_subagents_endpoint(
    thread_id: str,
    db: Session = Depends(get_db)
):
    """
    Cascades termination to all active child subagents for a thread.
    """
    terminated = governance_service.terminate_subagents_for_thread(thread_id=thread_id, db=db)
    return {
        "status": "terminated",
        "thread_id": thread_id,
        "count": len(terminated),
        "terminated_ids": [s.id for s in terminated]
    }


# -------------------------------------------------------------
# Risk Evaluation Endpoint
# -------------------------------------------------------------

@router.post("/evaluate", response_model=RiskEvaluationResponse)
def evaluate_risk_endpoint(req: EvaluateRiskRequest):
    """
    Evaluates command or tool call risk against security policy profile.
    """
    profile = req.profile or governance_service.PROFILE_MANAGED
    risk_level, requires_approval, consequence = governance_service.evaluate_tool_risk(
        command=req.command,
        tool_name=req.tool_name,
        profile=profile
    )
    return RiskEvaluationResponse(
        command=req.command,
        tool_name=req.tool_name,
        risk_level=risk_level,
        requires_approval=requires_approval,
        consequence=consequence,
        profile=profile
    )
