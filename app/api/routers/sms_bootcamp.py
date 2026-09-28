"""SMS Assistant UI Bootcamp and isolated settings router."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...models.curated_memory import KnowledgeProposal
from ...models.learning_event import LearningEvent, compute_text_diff
from ...models.tenant import Tenant
from ...models.user import User
from ...services.sms.pii_scrubber import scrub_pii
from ...models.sms_bootcamp import (
    SmsBootcampConversation,
    SmsBootcampMessage,
    SmsBootcampRun,
    SmsBootcampSettings,
)
from ...schemas.sms_bootcamp import (
    BootcampConversationResponse,
    BootcampCorrectionCreate,
    BootcampDraftReviewCreate,
    BootcampInfoResponse,
    BootcampMessageResponse,
    BootcampPersona,
    BootcampProfileApply,
    BootcampProfileStateResponse,
    BootcampRunControl,
    BootcampRunCreate,
    BootcampRunResponse,
    BootcampScenarioPackRead,
    BootcampScenarioRead,
    BootcampSettingsResponse,
    BootcampSettingsUpdate,
    BootcampStyleProfile,
)
from ...services.sms.bootcamp import (
    DEFAULT_STYLE_PROFILE,
    PERSONAS,
    SCENARIO_PACKS,
    SCENARIOS_BY_ID,
    BootcampRunner,
    get_scenario_packs_list,
    normalize_style_profile,
)
from ...services.sms.bootcamp_service import (
    generate_bootcamp_information_resolution,
)

logger = logging.getLogger(__name__)

if not hasattr(SmsBootcampMessage, "status") or not isinstance(getattr(SmsBootcampMessage, "status"), property):
    def _get_msg_status(self) -> str:
        if hasattr(self, "_status_override"):
            return self._status_override
        return (self.meta or {}).get("status", "sent" if self.role == "tori" else "received")

    def _set_msg_status(self, val: str) -> None:
        self._status_override = val
        new_meta = dict(self.meta or {})
        new_meta["status"] = val
        self.meta = new_meta

    SmsBootcampMessage.status = property(_get_msg_status, _set_msg_status)

router = APIRouter()
BOOTCAMP_RUNNER = BootcampRunner(message_delay_seconds=0.0)


def _validate_provider_id(db: Session, tenant_id: int, provider_id: Optional[int]) -> Optional[int]:
    if provider_id is None:
        return None
    from ...models.provider import Provider
    prov = (
        db.query(Provider)
        .filter(Provider.id == provider_id, Provider.tenant_id == tenant_id)
        .first()
    )
    if not prov:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found in this tenant.",
        )
    return prov.id


def _get_or_create_settings(db: Session, tenant_id: int, provider_id: Optional[int] = None) -> SmsBootcampSettings:
    query = db.query(SmsBootcampSettings).filter(SmsBootcampSettings.tenant_id == tenant_id)
    if provider_id is not None:
        query = query.filter(SmsBootcampSettings.provider_id == provider_id)
    else:
        query = query.filter(SmsBootcampSettings.provider_id.is_(None))
    settings_obj = query.first()
    if not settings_obj:
        default_profile = dict(DEFAULT_STYLE_PROFILE)
        agent_name = "Tori"
        model = "gpt-4o-mini"
        if provider_id is not None:
            tenant_settings = (
                db.query(SmsBootcampSettings)
                .filter(SmsBootcampSettings.tenant_id == tenant_id, SmsBootcampSettings.provider_id.is_(None))
                .first()
            )
            if tenant_settings:
                default_profile = dict(tenant_settings.active_style_profile or DEFAULT_STYLE_PROFILE)
                agent_name = tenant_settings.agent_name
                model = getattr(tenant_settings, "model", "gpt-4o-mini") or "gpt-4o-mini"

        settings_obj = SmsBootcampSettings(
            tenant_id=tenant_id,
            provider_id=provider_id,
            active_style_profile=default_profile,
            previous_style_profile=None,
            agent_name=agent_name,
            model=model,
            role_description=None,
            system_prompt_template=None,
            custom_training_notes=None,
            training_notes=None,
            learned_facts=None,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return settings_obj


def _format_settings(s: SmsBootcampSettings) -> Dict[str, Any]:
    active = s.active_style_profile or dict(DEFAULT_STYLE_PROFILE)
    prev = s.previous_style_profile
    return {
        "id": s.id,
        "tenantId": s.tenant_id,
        "tenant_id": s.tenant_id,
        "providerId": s.provider_id,
        "provider_id": s.provider_id,
        "activeStyleProfile": active,
        "active_style_profile": active,
        "previousStyleProfile": prev,
        "previous_style_profile": prev,
        "activeProfile": active,
        "active_profile": active,
        "previousProfile": prev,
        "previous_profile": prev,
        "agentName": s.agent_name,
        "agent_name": s.agent_name,
        "model": getattr(s, "model", "gpt-4o-mini") or "gpt-4o-mini",
        "roleDescription": getattr(s, "role_description", None),
        "role_description": getattr(s, "role_description", None),
        "systemPromptTemplate": s.system_prompt_template,
        "system_prompt_template": s.system_prompt_template,
        "customTrainingNotes": s.custom_training_notes,
        "custom_training_notes": s.custom_training_notes,
        "trainingNotes": getattr(s, "training_notes", None) or s.custom_training_notes,
        "training_notes": getattr(s, "training_notes", None) or s.custom_training_notes,
        "learnedFacts": getattr(s, "learned_facts", None),
        "learned_facts": getattr(s, "learned_facts", None),
        "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _format_message(msg: SmsBootcampMessage) -> Dict[str, Any]:
    return {
        "id": msg.id,
        "conversationId": msg.conversation_id,
        "role": msg.role,
        "text": msg.text,
        "status": getattr(msg, "status", (msg.meta or {}).get("status", "sent" if msg.role == "tori" else "received")),
        "meta": msg.meta or {},
        "createdAt": msg.created_at.isoformat() if msg.created_at else None,
    }


def _format_conversation(conv: SmsBootcampConversation) -> Dict[str, Any]:
    return {
        "id": conv.id,
        "runId": conv.run_id,
        "run_id": conv.run_id,
        "tenantId": conv.tenant_id,
        "tenant_id": conv.tenant_id,
        "providerId": conv.provider_id,
        "provider_id": conv.provider_id,
        "personaId": conv.persona_id,
        "persona_id": conv.persona_id,
        "personaName": conv.persona_name,
        "persona_name": conv.persona_name,
        "scenarioId": getattr(conv, "scenario_id", None),
        "scenario_id": getattr(conv, "scenario_id", None),
        "status": conv.status,
        "currentTurn": conv.current_turn,
        "current_turn": conv.current_turn,
        "needsHandoff": bool(conv.needs_handoff),
        "needs_handoff": bool(conv.needs_handoff),
        "handoffReason": conv.handoff_reason,
        "handoff_reason": conv.handoff_reason,
        "createdAt": conv.created_at.isoformat() if conv.created_at else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updatedAt": conv.updated_at.isoformat() if conv.updated_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "messages": [_format_message(m) for m in conv.messages],
    }


def _format_run(run: SmsBootcampRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "status": run.status,
        "tenantId": run.tenant_id,
        "tenant_id": run.tenant_id,
        "providerId": run.provider_id,
        "provider_id": run.provider_id,
        "selectedPersonaIds": run.selected_personas or [],
        "selected_persona_ids": run.selected_personas or [],
        "selectedPersonas": run.selected_personas or [],
        "selected_personas": run.selected_personas or [],
        "selectedScenarios": getattr(run, "selected_scenarios", None),
        "selected_scenarios": getattr(run, "selected_scenarios", None),
        "selectedScenarioIds": getattr(run, "selected_scenarios", None),
        "selected_scenario_ids": getattr(run, "selected_scenarios", None),
        "autonomyLevel": getattr(run, "autonomy_level", 2),
        "autonomy_level": getattr(run, "autonomy_level", 2),
        "maxTurns": run.max_turns,
        "max_turns": run.max_turns,
        "styleProfile": run.style_profile or {},
        "style_profile": run.style_profile or {},
        "error": run.error,
        "createdAt": run.created_at.isoformat() if run.created_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updatedAt": run.updated_at.isoformat() if run.updated_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        "conversations": [_format_conversation(c) for c in run.conversations],
    }


@router.get("/scenarios", response_model=List[BootcampScenarioPackRead])
def get_bootcamp_scenarios(
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
) -> List[Dict[str, Any]]:
    """Return available scenario packs and individual scenarios."""
    return get_scenario_packs_list()


@router.get("/personas", response_model=List[BootcampPersona])
def get_bootcamp_personas(
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
) -> List[Dict[str, str]]:
    """Return the 12 canonical test personas."""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "description": p["description"],
        }
        for p in PERSONAS
    ]


@router.get("/profile", response_model=Dict[str, Any])
def get_bootcamp_profile(
    provider_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return active style profile, defaults, applied status, and undo capability."""
    prov_id = _validate_provider_id(db, tenant.id, provider_id)
    settings_obj = _get_or_create_settings(db, tenant.id, prov_id)
    active = settings_obj.active_style_profile or dict(DEFAULT_STYLE_PROFILE)
    prev = settings_obj.previous_style_profile
    can_undo = prev is not None
    is_applied = can_undo or (active != DEFAULT_STYLE_PROFILE)
    return {
        "active": active,
        "active_profile": active,
        "activeProfile": active,
        "previous_profile": prev,
        "previousProfile": prev,
        "defaults": DEFAULT_STYLE_PROFILE,
        "isApplied": is_applied,
        "is_applied": is_applied,
        "canUndo": can_undo,
        "can_undo": can_undo,
    }


@router.post("/profile/apply", response_model=Dict[str, Any])
def apply_bootcamp_profile(
    payload: Dict[str, Any],
    provider_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Save active style profile, preserving current profile for undo."""
    # Defect 1: Handle { data: { profile } }, { data: ... }, { styleProfile }, { style_profile }, or direct traits
    raw = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    profile_data = (
        raw.get("styleProfile")
        or raw.get("style_profile")
        or raw.get("profile")
        or raw
    )
    if isinstance(profile_data, dict) and "profile" in profile_data:
        profile_data = profile_data["profile"]

    prov_id_raw = (
        payload.get("provider_id")
        or payload.get("providerId")
        or (raw.get("provider_id") if isinstance(raw, dict) else None)
        or (raw.get("providerId") if isinstance(raw, dict) else None)
        or provider_id
    )
    prov_id = _validate_provider_id(db, tenant.id, prov_id_raw)

    normalized = normalize_style_profile(profile_data)
    settings_obj = _get_or_create_settings(db, tenant.id, prov_id)
    settings_obj.previous_style_profile = dict(settings_obj.active_style_profile or DEFAULT_STYLE_PROFILE)
    settings_obj.active_style_profile = normalized
    settings_obj.updated_at = datetime.now(timezone.utc)
    db.commit()

    active = settings_obj.active_style_profile
    prev = settings_obj.previous_style_profile
    return {
        "active": active,
        "active_profile": active,
        "activeProfile": active,
        "previous_profile": prev,
        "previousProfile": prev,
        "defaults": DEFAULT_STYLE_PROFILE,
        "isApplied": True,
        "is_applied": True,
        "canUndo": True,
        "can_undo": True,
    }


@router.post("/profile/undo", response_model=Dict[str, Any])
def undo_bootcamp_profile(
    provider_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Restore previously active style profile."""
    prov_id = _validate_provider_id(db, tenant.id, provider_id)
    settings_obj = _get_or_create_settings(db, tenant.id, prov_id)
    if settings_obj.previous_style_profile is None:
        active = settings_obj.active_style_profile or dict(DEFAULT_STYLE_PROFILE)
        return {
            "active": active,
            "active_profile": active,
            "activeProfile": active,
            "previous_profile": None,
            "previousProfile": None,
            "defaults": DEFAULT_STYLE_PROFILE,
            "isApplied": False,
            "is_applied": False,
            "canUndo": False,
            "can_undo": False,
        }

    restored = dict(settings_obj.previous_style_profile)
    current = dict(settings_obj.active_style_profile)
    settings_obj.active_style_profile = restored
    settings_obj.previous_style_profile = current
    settings_obj.updated_at = datetime.now(timezone.utc)
    db.commit()

    is_applied = settings_obj.active_style_profile != DEFAULT_STYLE_PROFILE
    return {
        "active": settings_obj.active_style_profile,
        "active_profile": settings_obj.active_style_profile,
        "activeProfile": settings_obj.active_style_profile,
        "previous_profile": settings_obj.previous_style_profile,
        "previousProfile": settings_obj.previous_style_profile,
        "defaults": DEFAULT_STYLE_PROFILE,
        "isApplied": is_applied,
        "is_applied": is_applied,
        "canUndo": False,
        "can_undo": False,
    }


@router.post("/runs", response_model=Dict[str, Any])
def start_bootcamp_run(
    payload: BootcampRunCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Start a new simulation run with selected personas and optional scenarios."""
    if not payload.persona_ids:
        raise HTTPException(status_code=400, detail="Select at least one persona")

    if payload.scenario_ids:
        invalid = [s for s in payload.scenario_ids if s not in SCENARIOS_BY_ID]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Unknown scenario IDs: {', '.join(invalid)}")

    prov_id = _validate_provider_id(db, tenant.id, payload.provider_id)
    settings_obj = _get_or_create_settings(db, tenant.id, prov_id)
    profile = payload.style_profile or settings_obj.active_style_profile or DEFAULT_STYLE_PROFILE

    run_id = BOOTCAMP_RUNNER.start(
        tenant_id=tenant.id,
        persona_ids=payload.persona_ids,
        max_turns=payload.max_turns,
        profile=profile,
        db=db,
        sync=bool(payload.sync),
        autonomy_level=payload.autonomy_level,
        scenario_ids=payload.scenario_ids,
        provider_id=prov_id,
    )

    run = (
        db.query(SmsBootcampRun)
        .filter(SmsBootcampRun.id == run_id, SmsBootcampRun.tenant_id == tenant.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=500, detail="Run initialization failed")

    return _format_run(run)


@router.get("/runs/latest", response_model=Dict[str, Any])
def get_latest_bootcamp_run(
    provider_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return latest run with conversations and messages for the tenant / provider."""
    prov_id = _validate_provider_id(db, tenant.id, provider_id)
    query = db.query(SmsBootcampRun).filter(SmsBootcampRun.tenant_id == tenant.id)
    if prov_id is not None:
        query = query.filter(SmsBootcampRun.provider_id == prov_id)
    run = query.order_by(SmsBootcampRun.created_at.desc()).first()
    return {"run": _format_run(run) if run else None}


@router.get("/runs/{run_id}", response_model=Dict[str, Any])
def get_bootcamp_run(
    run_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return details of a specific simulation run."""
    run = (
        db.query(SmsBootcampRun)
        .filter(SmsBootcampRun.id == run_id, SmsBootcampRun.tenant_id == tenant.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Boot Camp run not found")
    return _format_run(run)


@router.post("/runs/{run_id}/control", response_model=Dict[str, Any])
def control_bootcamp_run(
    run_id: str,
    payload: BootcampRunControl,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Control execution of a run (pause, resume, stop)."""
    run = (
        db.query(SmsBootcampRun)
        .filter(SmsBootcampRun.id == run_id, SmsBootcampRun.tenant_id == tenant.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Boot Camp run not found")

    operation = payload.operation.strip().lower()
    transitions = {"pause": "paused", "resume": "running", "stop": "stopped"}
    if operation not in transitions:
        raise HTTPException(status_code=400, detail="Use pause, resume, or stop")

    run.status = transitions[operation]
    if operation == "stop":
        for conv in run.conversations:
            if conv.status == "running":
                conv.status = "stopped"
                conv.updated_at = datetime.now(timezone.utc)

    run.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _format_run(run)


@router.delete("/runs")
def reset_bootcamp_runs(
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Reset and clear simulation run history for the active tenant."""
    latest = (
        db.query(SmsBootcampRun)
        .filter(SmsBootcampRun.tenant_id == tenant.id)
        .order_by(SmsBootcampRun.created_at.desc())
        .first()
    )
    if latest and latest.status in {"running", "paused"}:
        raise HTTPException(status_code=409, detail="Stop the active run before resetting")

    db.query(SmsBootcampRun).filter(SmsBootcampRun.tenant_id == tenant.id).delete(synchronize_session="fetch")
    db.commit()
    return {"status": "reset"}


@router.post("/conversations/{conversation_id}/information-request/respond")
def respond_to_bootcamp_information_request(
    conversation_id: str,
    payload: BootcampInfoResponse,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Resolve a Boot Camp clarification handoff using staff supplied information."""
    conv = (
        db.query(SmsBootcampConversation)
        .filter(
            SmsBootcampConversation.id == conversation_id,
            SmsBootcampConversation.tenant_id == tenant.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Boot Camp conversation not found.")

    if not conv.needs_handoff or conv.status != "handoff":
        raise HTTPException(status_code=409, detail="This Boot Camp information request is already resolved.")

    persona_msg = (
        db.query(SmsBootcampMessage)
        .filter(
            SmsBootcampMessage.conversation_id == conv.id,
            SmsBootcampMessage.tenant_id == tenant.id,
            SmsBootcampMessage.role == "persona",
        )
        .order_by(SmsBootcampMessage.created_at.desc())
        .first()
    )
    if not persona_msg:
        raise HTTPException(status_code=409, detail="No simulated customer message is available to retry.")

    resolved_prov_id = getattr(conv, "provider_id", None)
    if not resolved_prov_id and getattr(conv, "run", None):
        resolved_prov_id = getattr(conv.run, "provider_id", None)

    settings_obj = _get_or_create_settings(db, tenant.id, resolved_prov_id)
    run = (
        db.query(SmsBootcampRun)
        .filter(SmsBootcampRun.id == conv.run_id, SmsBootcampRun.tenant_id == tenant.id)
        .first()
    )
    profile = (run.style_profile if run else None) or settings_obj.active_style_profile or DEFAULT_STYLE_PROFILE

    all_messages = (
        db.query(SmsBootcampMessage)
        .filter(
            SmsBootcampMessage.conversation_id == conv.id,
            SmsBootcampMessage.tenant_id == tenant.id,
        )
        .order_by(SmsBootcampMessage.created_at)
        .all()
    )
    history = [{"id": m.id, "role": m.role, "text": m.text, "meta": m.meta} for m in all_messages]

    settings_data = {
        "agent_name": settings_obj.agent_name,
        "model": getattr(settings_obj, "model", "gpt-4o-mini") or "gpt-4o-mini",
        "custom_training_notes": settings_obj.training_notes or settings_obj.custom_training_notes,
        "training_notes": settings_obj.training_notes or settings_obj.custom_training_notes,
        "system_prompt_template": settings_obj.system_prompt_template,
        "tenant_id": tenant.id,
        "provider_id": resolved_prov_id,
        "db": db,
    }

    generated = generate_bootcamp_information_resolution(
        history=history,
        style_profile=profile,
        supplied_information=payload.information,
        settings_data=settings_data,
    )

    # 1. Save lesson into isolated SmsBootcampSettings
    lesson_entry = f"- Q: {persona_msg.text} | A: {generated['knowledge_summary']}"
    if settings_obj.custom_training_notes:
        settings_obj.custom_training_notes = f"{settings_obj.custom_training_notes}\n{lesson_entry}"
    else:
        settings_obj.custom_training_notes = lesson_entry
    settings_obj.training_notes = settings_obj.custom_training_notes
    settings_obj.updated_at = datetime.now(timezone.utc)

    # 2. Ingest into central curator KnowledgeProposal
    now = datetime.now(timezone.utc)
    scrubbed_query = scrub_pii(persona_msg.text) if persona_msg.text else ""
    scrubbed_response = scrub_pii(payload.information) if payload.information else ""
    info_proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=resolved_prov_id,
        proposal_type="gap",
        status="pending",
        category="faq",
        knowledge_kind="durable_fact",
        authority="bootcamp_info_request",
        user_query=scrubbed_query,
        proposed_response=scrubbed_response,
        fingerprint=hashlib.sha256(
            f"bootcamp:info_request:{tenant.id}:{conv.id}:{persona_msg.id}:{now.isoformat()}".encode()
        ).hexdigest(),
        reason_code=f"bootcamp_info_request: {conv.id}"[:64],
        confidence_score=1.0,
        contains_dynamic_fact=False,
        requires_review=True,
        evidence_count=1,
        created_at=now,
        updated_at=now,
    )
    db.add(info_proposal)

    # 3. LearningEvent is authoritative
    knowledge_source = "learning_event"

    # 4. Add Tori's reply message to conversation
    tori_msg = SmsBootcampMessage(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="tori",
        text=generated["customer_reply"],
        meta={
            "source": "information-request",
            "knowledgeSummary": generated["knowledge_summary"],
            "status": "sent",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(tori_msg)

    # 4b. Ingest LearningEvent and curate through UnifiedCurator (Phase 12)
    learning_event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=resolved_prov_id,
        conversation_id=conv.id,
        message_id=tori_msg.id,
        event_type="knowledge_answer",
        source="bootcamp",
        customer_message=scrubbed_query,
        human_content=scrubbed_response,
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db.add(learning_event)
    db.flush()

    from app.services.knowledge.curator import unified_curator
    unified_curator.process_learning_event(db, learning_event)

    # 5. Resolve handoff state and update conversation/run status
    conv.status = "completed"
    conv.needs_handoff = False
    conv.handoff_reason = None
    conv.updated_at = datetime.now(timezone.utc)

    if conv.run:
        all_convs = db.query(SmsBootcampConversation).filter(SmsBootcampConversation.run_id == conv.run_id).all()
        if all(c.status in {"completed", "stopped"} for c in all_convs):
            conv.run.status = "completed"
            conv.run.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conv)

    return {
        "status": "success",
        "conversation": _format_conversation(conv),
        "knowledgeSource": knowledge_source,
        "knowledgeSummary": generated["knowledge_summary"],
    }


@router.post("/conversations/{conversation_id}/corrections")
def record_bootcamp_correction(
    conversation_id: str,
    payload: BootcampCorrectionCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Record an operator correction on a Bootcamp conversation message."""
    conv = (
        db.query(SmsBootcampConversation)
        .filter(
            SmsBootcampConversation.id == conversation_id,
            SmsBootcampConversation.tenant_id == tenant.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Boot Camp conversation not found.")

    msg = (
        db.query(SmsBootcampMessage)
        .filter(
            SmsBootcampMessage.id == payload.message_id,
            SmsBootcampMessage.conversation_id == conv.id,
            SmsBootcampMessage.tenant_id == tenant.id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Boot Camp message not found.")

    now = datetime.now(timezone.utc)
    old_text = msg.text

    if payload.corrected_wording is not None and payload.corrected_wording.strip():
        msg.text = payload.corrected_wording.strip()
        msg_meta = dict(msg.meta or {})
        msg_meta["correction"] = {
            "reason": payload.reason.strip(),
            "previous_text": old_text,
            "timestamp": now.isoformat(),
        }
        msg.meta = msg_meta

    # Determine prior persona message query
    prior_persona_msg = (
        db.query(SmsBootcampMessage)
        .filter(
            SmsBootcampMessage.conversation_id == conv.id,
            SmsBootcampMessage.tenant_id == tenant.id,
            SmsBootcampMessage.role == "persona",
            SmsBootcampMessage.created_at <= msg.created_at,
        )
        .order_by(SmsBootcampMessage.created_at.desc())
        .first()
    )
    user_query = prior_persona_msg.text if prior_persona_msg else "Simulated Persona Query"

    resolved_prov_id = getattr(conv, "provider_id", None)
    if not resolved_prov_id and getattr(conv, "run", None):
        resolved_prov_id = getattr(conv.run, "provider_id", None)

    # Append correction lesson into SmsBootcampSettings.custom_training_notes
    settings_obj = _get_or_create_settings(db, tenant.id, resolved_prov_id)
    corrected_display = (payload.corrected_wording or "").strip() or old_text
    lesson_entry = f"- Correction: for query '{user_query}', replied '{old_text}' -> corrected to '{corrected_display}'. Reason: {payload.reason.strip()}"
    if settings_obj.custom_training_notes:
        settings_obj.custom_training_notes = f"{settings_obj.custom_training_notes}\n{lesson_entry}"
    else:
        settings_obj.custom_training_notes = lesson_entry
    settings_obj.training_notes = settings_obj.custom_training_notes
    settings_obj.updated_at = now

    reason_str = payload.reason.strip()
    scrubbed_query = scrub_pii(user_query) if user_query else ""
    raw_response = payload.corrected_wording or payload.reason
    scrubbed_response = scrub_pii(raw_response) if raw_response else ""
    proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=resolved_prov_id,
        proposal_type="conflict",
        status="pending",
        category="faq",
        knowledge_kind="durable_fact",
        authority="bootcamp_correction",
        user_query=scrubbed_query,
        proposed_response=scrubbed_response,
        fingerprint=hashlib.sha256(
            f"bootcamp:{tenant.id}:{conversation_id}:{msg.id}:{now.isoformat()}".encode()
        ).hexdigest(),
        reason_code=f"bootcamp_correction: {reason_str}"[:64],
        confidence_score=1.0,
        contains_dynamic_fact=payload.contains_dynamic_facts,
        requires_review=True,
        evidence_count=1,
        created_at=now,
        updated_at=now,
    )
    db.add(proposal)

    learning_event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=resolved_prov_id,
        conversation_id=conv.id,
        message_id=msg.id,
        event_type="flagged_response",
        source="bootcamp",
        customer_message=scrubbed_query,
        original_ai_content=scrub_pii(old_text) if old_text else None,
        human_content=scrubbed_response,
        metadata_payload={
            "reason": reason_str,
            "contains_dynamic_facts": payload.contains_dynamic_facts,
        },
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db.add(learning_event)

    db.commit()
    db.refresh(proposal)
    db.refresh(msg)

    return {
        "ok": True,
        "proposal_id": proposal.id,
        "learning_event_id": learning_event.id,
        "updated_text": msg.text,
    }


@router.post("/conversations/{conversation_id}/drafts/{message_id}/review")
def review_bootcamp_draft(
    conversation_id: str,
    message_id: str,
    payload: BootcampDraftReviewCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Review and approve or discard a draft message in a Bootcamp conversation."""
    conv = (
        db.query(SmsBootcampConversation)
        .filter(
            SmsBootcampConversation.id == conversation_id,
            SmsBootcampConversation.tenant_id == tenant.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Boot Camp conversation not found.")

    msg = (
        db.query(SmsBootcampMessage)
        .filter(
            SmsBootcampMessage.id == message_id,
            SmsBootcampMessage.conversation_id == conv.id,
            SmsBootcampMessage.tenant_id == tenant.id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Boot Camp message not found.")

    action = payload.action.strip().lower()
    learning_event = None
    now = datetime.now(timezone.utc)
    resolved_prov_id = getattr(conv, "provider_id", None)
    if not resolved_prov_id and getattr(conv, "run", None):
        resolved_prov_id = getattr(conv.run, "provider_id", None)

    if action == "approve":
        original_text = msg.text or ""
        clean_new = payload.text.strip() if payload.text and payload.text.strip() else None

        if clean_new and clean_new != original_text.strip():
            diff_data = compute_text_diff(original_text, clean_new)
            learning_event = LearningEvent(
                tenant_id=tenant.id,
                provider_id=resolved_prov_id,
                conversation_id=conv.id,
                message_id=msg.id,
                event_type="draft_edit",
                source="bootcamp",
                original_ai_content=scrub_pii(original_text),
                human_content=scrub_pii(clean_new),
                diff_payload=diff_data,
                status="pending",
                confidence_score=0.5,
                created_at=now,
            )
            db.add(learning_event)
            msg.text = clean_new
        else:
            learning_event = LearningEvent(
                tenant_id=tenant.id,
                provider_id=resolved_prov_id,
                conversation_id=conv.id,
                message_id=msg.id,
                event_type="approved_draft",
                source="bootcamp",
                original_ai_content=scrub_pii(original_text) if original_text else None,
                human_content=scrub_pii(original_text) if original_text else None,
                status="pending",
                confidence_score=0.2,
                created_at=now,
            )
            db.add(learning_event)

        msg.status = "sent"
        run = db.query(SmsBootcampRun).filter(SmsBootcampRun.id == conv.run_id).first()
        max_turns = run.max_turns if run else 5
        if conv.current_turn >= max_turns:
            conv.status = "completed"
        else:
            conv.status = "running"
            if run and run.status != "stopped":
                BOOTCAMP_RUNNER.advance_turn(db, conv, run)
        conv.updated_at = now

        all_convs = db.query(SmsBootcampConversation).filter(SmsBootcampConversation.run_id == conv.run_id).all()
        if all(c.status in {"completed", "stopped"} for c in all_convs):
            if run:
                run.status = "completed"
                run.updated_at = now
        elif any(c.status == "waiting_approval" for c in all_convs):
            if run:
                run.status = "waiting_approval"
                run.updated_at = now
        elif any(c.status == "handoff" for c in all_convs):
            if run:
                run.status = "paused"
                run.updated_at = now
    elif action == "discard":
        msg.status = "discarded"
        conv.status = "stopped"
        conv.updated_at = now
        all_convs = db.query(SmsBootcampConversation).filter(SmsBootcampConversation.run_id == conv.run_id).all()
        if all(c.status in {"completed", "stopped"} for c in all_convs):
            run = db.query(SmsBootcampRun).filter(SmsBootcampRun.id == conv.run_id).first()
            if run:
                run.status = "completed"
                run.updated_at = now
    else:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'discard'.")

    db.commit()
    db.refresh(msg)

    return {
        "ok": True,
        "success": True,
        "status": msg.status,
        "message_id": msg.id,
        "text": msg.text,
        "learning_event_id": learning_event.id if learning_event else None,
        "message": _format_message(msg),
        "conversation": _format_conversation(conv),
    }


@router.get("/settings", response_model=Dict[str, Any])
def get_bootcamp_settings(
    provider_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return isolated Bootcamp configuration and training notes for the tenant / provider."""
    prov_id = _validate_provider_id(db, tenant.id, provider_id)
    settings_obj = _get_or_create_settings(db, tenant.id, prov_id)
    return _format_settings(settings_obj)


@router.put("/settings", response_model=Dict[str, Any])
def update_bootcamp_settings(
    payload: Dict[str, Any],
    provider_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update isolated Bootcamp agent name, model, template, notes, or facts."""
    raw = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    prov_id_raw = (
        payload.get("provider_id")
        or payload.get("providerId")
        or (raw.get("provider_id") if isinstance(raw, dict) else None)
        or (raw.get("providerId") if isinstance(raw, dict) else None)
        or provider_id
    )
    prov_id = _validate_provider_id(db, tenant.id, prov_id_raw)
    settings_obj = _get_or_create_settings(db, tenant.id, prov_id)

    agent_name = raw.get("agent_name") or raw.get("agentName")
    if agent_name is not None and str(agent_name).strip():
        settings_obj.agent_name = str(agent_name).strip()

    model_val = raw.get("model")
    if model_val is not None and str(model_val).strip():
        settings_obj.model = str(model_val).strip()

    role_desc = raw.get("role_description") or raw.get("roleDescription")
    if role_desc is not None:
        settings_obj.role_description = str(role_desc).strip()

    template = raw.get("system_prompt_template") or raw.get("systemPromptTemplate")
    if template is not None:
        settings_obj.system_prompt_template = str(template)

    notes = raw.get("training_notes") or raw.get("trainingNotes") or raw.get("custom_training_notes") or raw.get("customTrainingNotes")
    if notes is not None:
        settings_obj.training_notes = str(notes)
        settings_obj.custom_training_notes = str(notes)

    facts = raw.get("learned_facts") or raw.get("learnedFacts")
    if facts is not None:
        if isinstance(facts, list):
            settings_obj.learned_facts = "\n".join(str(f) for f in facts)
        else:
            settings_obj.learned_facts = str(facts)

    active_profile = raw.get("active_profile") or raw.get("activeProfile") or raw.get("active_style_profile") or raw.get("activeStyleProfile")
    if active_profile and isinstance(active_profile, dict):
        settings_obj.active_style_profile = normalize_style_profile(active_profile)

    settings_obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(settings_obj)
    return _format_settings(settings_obj)
