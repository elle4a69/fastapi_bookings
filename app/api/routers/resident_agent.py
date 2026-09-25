"""Codex Resident Autonomous Agent API router.

Exposes endpoints for overall system health, real-time deep audits, SSE streaming
of agent thoughts and command events, automated remediation planning, safe fix
execution, and conversational AI advisory with web research capabilities.
"""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...api.deps import get_current_admin
from ...db.database import get_db
from ...models.user import User
from ...services.resident_agent import (
    resident_agent_engine,
    event_broker,
    FixExecutionError,
    skill_library,
    sentinel_scheduler,
    alert_dispatcher,
    stress_fuzzer,
    tech_radar,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/resident-agent", tags=["resident-agent"])


class PlanFixRequest(BaseModel):
    issue_id: str = Field(..., description="ID of the issue to remediate (e.g. ISSUE-SMS-001)")
    issue_title: Optional[str] = Field(None, description="Optional custom title for the issue")
    category: Optional[str] = Field(None, description="Optional category (sms_outbox, telemetry, etc.)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context or parameters")


class ExecuteFixRequest(BaseModel):
    plan_id: str = Field(..., description="Unique plan ID to execute")
    approved: bool = Field(False, description="Explicit approval gate flag (must be true)")
    simulate_only: bool = Field(False, description="Simulate execution without modifying files")


class AdvisoryRequest(BaseModel):
    prompt: str = Field(..., min_length=2, description="Inquiry or problem statement for AI advisory")
    enable_web_research: bool = Field(True, description="Enable real-time documentation and internet research")
    domain: Optional[str] = Field(None, description="Optional technology domain (e.g., fastapi, react, twilio)")


class RemoteActionRequest(BaseModel):
    command: Optional[str] = Field(None, description="Raw command string e.g. 'APPROVE <plan_id>'")
    plan_id: Optional[str] = Field(None, description="Plan ID to approve and execute")
    action: Optional[str] = Field(None, description="Action name e.g. 'approve'")


class RaceConditionFuzzRequest(BaseModel):
    concurrency: int = Field(15, ge=2, le=50, description="Number of concurrent booking requests to simulate")


@router.get("/status")
def get_resident_agent_status(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return overall health score, latest code audit summary, telemetry baseline, and active issues."""
    return resident_agent_engine.get_system_status(db)


@router.post("/audit")
async def trigger_deep_audit(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger an immediate deep audit across Code, Telemetry, and SMS Outbox queues."""
    return await resident_agent_engine.run_deep_audit(db)


@router.get("/events")
async def stream_agent_events(
    request: Request,
    token: Optional[str] = Query(None, description="Optional auth token for SSE EventSource clients"),
) -> StreamingResponse:
    """Stream live agent thought tokens, audit progress, commands, and telemetry events via SSE."""
    # Yield standard event stream
    return StreamingResponse(
        event_broker.subscribe(replay_count=25),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/plan-fix")
def generate_remediation_plan(
    payload: PlanFixRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate an automated remediation plan with RCA, diffs, and verification steps."""
    plan = resident_agent_engine.plan_remediation_for_issue(
        issue_id=payload.issue_id,
        context={
            **(payload.context or {}),
            "issue_title": payload.issue_title,
            "category": payload.category,
        },
    )
    return plan


@router.post("/execute-fix")
async def execute_remediation_fix(
    payload: ExecuteFixRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Safely execute an approved remediation plan with rollback and verification."""
    if not payload.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Execution rejected: Remediation plan requires explicit approval ('approved: true').",
        )

    try:
        result = await resident_agent_engine.execute_remediation_plan(
            plan_id=payload.plan_id,
            approved=payload.approved,
            simulate_only=payload.simulate_only,
        )
        return result
    except FixExecutionError as fee:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(fee))
    except Exception as exc:
        logger.error("Unexpected error during fix execution: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/advisory")
async def consult_ai_advisory(
    payload: AdvisoryRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Conversational AI advisory endpoint with internet research and best-practice proposals."""
    return await resident_agent_engine.provide_advisory(
        prompt=payload.prompt,
        enable_web_research=payload.enable_web_research,
        domain=payload.domain,
    )


@router.post("/remote-action")
async def execute_remote_action(
    payload: RemoteActionRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Execute remote action triggers dispatched via Chatwoot or SMS (e.g. 'APPROVE <plan_id>')."""
    plan_id = payload.plan_id
    action = (payload.action or "").lower()

    if payload.command:
        parts = payload.command.strip().split()
        if len(parts) >= 2 and parts[0].upper() == "APPROVE":
            action = "approve"
            plan_id = parts[1]
        elif len(parts) == 1 and parts[0].upper() == "STATUS":
            return resident_agent_engine.get_system_status(db)

    if not plan_id or action != "approve":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid remote command. Format must be 'APPROVE <plan_id>' or provide plan_id with action='approve'.",
        )

    try:
        result = await resident_agent_engine.execute_remediation_plan(
            plan_id=plan_id,
            approved=True,
            simulate_only=False,
        )
        return {
            "success": True,
            "action": "approve",
            "plan_id": plan_id,
            "execution_result": result,
            "message": f"Autonomous remediation plan '{plan_id}' approved and executed successfully.",
        }
    except FixExecutionError as fee:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(fee))
    except Exception as exc:
        logger.error("Error executing remote action for plan %s: %s", plan_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/fuzz/race-condition")
async def run_race_condition_fuzzer(
    payload: RaceConditionFuzzRequest = RaceConditionFuzzRequest(),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Simulate N concurrent booking attempts against the same slot to stress-test transactional lock integrity."""
    return await stress_fuzzer.run_race_condition_test(db=db, concurrency=payload.concurrency)


@router.get("/tech-radar")
def get_competitor_tech_radar(
    current_admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Return competitive market radar comparing FastAPI Bookings against industry leaders."""
    return tech_radar.get_radar_analysis()


@router.get("/skills")
def search_skills_library(
    query: str = Query("fastapi", description="Query to search skills library"),
    top_k: int = Query(5, ge=1, le=20, description="Max skills to return"),
    current_admin: User = Depends(get_current_admin),
) -> List[Dict[str, Any]]:
    """Search the local library of 1,600+ skills at C:\\Users\\Frank\\skills without loading full files into memory."""
    return skill_library.find_relevant_skills(query=query, top_k=top_k)


@router.get("/skills/{skill_id}")
def read_skill_content(
    skill_id: str,
    current_admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Load specific SKILL.md on demand for surgical token usage."""
    try:
        content = skill_library.read_skill(skill_id)
        return {"skill_id": skill_id, "content": content}
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_id}' not found in library.",
        )


@router.post("/sentinel/sweep")
async def trigger_sentinel_sweep(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger an immediate autonomous health sweep across SMS queues, Chatwoot, and database."""
    return await sentinel_scheduler.run_sweep(db=db)


@router.get("/sentinel/status")
def get_sentinel_status(
    current_admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Return current status of the autonomous background sentinel scheduler."""
    return sentinel_scheduler.get_status()

