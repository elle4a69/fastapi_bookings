"""Append-only supervisor event construction and digest chaining."""

from datetime import datetime
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.engine import Connection

from backend.middleware.v2_errors import canonical_json_bytes
from backend.models.codex import SupervisorEvent
from backend.services.actor_scope import ActorScope
from backend.services.idempotency_service import utc_now


def append_claim_event(
    connection: Connection,
    *,
    project_public_id: str,
    actor: ActorScope,
    project_version: int,
    request_id: str,
    idempotency_key: str,
) -> SupervisorEvent:
    table = SupervisorEvent.__table__
    previous = connection.execute(
        select(table.c.project_sequence, table.c.integrity_digest)
        .where(table.c.project_public_id == project_public_id)
        .order_by(table.c.project_sequence.desc())
        .limit(1)
    ).first()
    sequence = 1 if previous is None else int(previous.project_sequence) + 1
    previous_digest = None if previous is None else str(previous.integrity_digest)
    occurred_at = utc_now()
    payload_object = {
        "after_scope_state": "claimed",
        "before_scope_state": "unclaimed",
        "reason_code": "configured_project_claimed",
    }
    payload = canonical_json_bytes(payload_object).decode("utf-8")
    payload_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    digest_material = {
        "action_code": "claim_project",
        "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("ascii")).hexdigest(),
        "occurred_at": occurred_at.isoformat(),
        "outcome": "succeeded",
        "payload_sha256": payload_sha256,
        "previous_digest": previous_digest,
        "project_public_id": project_public_id,
        "project_sequence": sequence,
        "project_version": project_version,
        "request_id": request_id,
        "schema_version": "0.1",
    }
    integrity_digest = hashlib.sha256(canonical_json_bytes(digest_material)).hexdigest()
    event = SupervisorEvent(
        event_key=f"evt_{uuid.uuid4().hex}",
        project_public_id=project_public_id,
        project_sequence=sequence,
        actor_tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        action_code="claim_project",
        outcome="succeeded",
        project_version=project_version,
        request_id=request_id,
        idempotency_key_hash=digest_material["idempotency_key_hash"],
        payload=payload,
        payload_sha256=payload_sha256,
        schema_version="0.1",
        previous_digest=previous_digest,
        integrity_digest=integrity_digest,
        occurred_at=occurred_at,
    )
    connection.execute(table.insert().values(**{
        column.name: getattr(event, column.name) for column in table.columns
    }))
    return event


def append_planning_event(connection: Connection, *, project_public_id: str, actor: ActorScope, action_code: str, project_version: int, request_id: str, idempotency_key: str) -> SupervisorEvent:
    """Append a low-sensitivity planning action to the existing digest chain."""
    table = SupervisorEvent.__table__
    prior = connection.execute(select(table.c.project_sequence, table.c.integrity_digest).where(table.c.project_public_id == project_public_id).order_by(table.c.project_sequence.desc()).limit(1)).first()
    sequence = 1 if prior is None else int(prior.project_sequence) + 1
    previous = None if prior is None else str(prior.integrity_digest)
    occurred = utc_now()
    payload = canonical_json_bytes({"planning_action": action_code, "execution_authority": "none"}).decode("utf-8")
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    material={"action_code":action_code,"idempotency_key_hash":hashlib.sha256(idempotency_key.encode("ascii")).hexdigest(),"occurred_at":occurred.isoformat(),"outcome":"succeeded","payload_sha256":payload_hash,"previous_digest":previous,"project_public_id":project_public_id,"project_sequence":sequence,"project_version":project_version,"request_id":request_id,"schema_version":"0.2"}
    event=SupervisorEvent(event_key="evt_"+uuid.uuid4().hex,project_public_id=project_public_id,project_sequence=sequence,actor_tenant_id=actor.tenant_id,actor_user_id=actor.user_id,action_code=action_code,outcome="succeeded",project_version=project_version,request_id=request_id,idempotency_key_hash=material["idempotency_key_hash"],payload=payload,payload_sha256=payload_hash,schema_version="0.2",previous_digest=previous,integrity_digest=hashlib.sha256(canonical_json_bytes(material)).hexdigest(),occurred_at=occurred)
    connection.execute(table.insert().values(**{column.name:getattr(event,column.name) for column in table.columns}))
    return event


def verify_project_chain(connection: Connection, project_public_id: str) -> bool:
    rows = connection.execute(
        select(SupervisorEvent.__table__)
        .where(SupervisorEvent.__table__.c.project_public_id == project_public_id)
        .order_by(SupervisorEvent.__table__.c.project_sequence)
    ).all()
    prior = None
    for expected_sequence, row in enumerate(rows, start=1):
        mapping = row._mapping
        if mapping["project_sequence"] != expected_sequence or mapping["previous_digest"] != prior:
            return False
        try:
            payload = json.loads(mapping["payload"])
        except (TypeError, json.JSONDecodeError):
            return False
        payload_bytes = canonical_json_bytes(payload)
        if hashlib.sha256(payload_bytes).hexdigest() != mapping["payload_sha256"]:
            return False
        occurred_at = mapping["occurred_at"]
        if isinstance(occurred_at, datetime):
            occurred_text = occurred_at.replace(tzinfo=occurred_at.tzinfo).isoformat()
            if occurred_at.tzinfo is None:
                occurred_text = occurred_at.replace(tzinfo=__import__("datetime").timezone.utc).isoformat()
        else:
            occurred_text = str(occurred_at)
        material = {
            "action_code": mapping["action_code"],
            "idempotency_key_hash": mapping["idempotency_key_hash"],
            "occurred_at": occurred_text,
            "outcome": mapping["outcome"],
            "payload_sha256": mapping["payload_sha256"],
            "previous_digest": mapping["previous_digest"],
            "project_public_id": mapping["project_public_id"],
            "project_sequence": mapping["project_sequence"],
            "project_version": mapping["project_version"],
            "request_id": mapping["request_id"],
            "schema_version": mapping["schema_version"],
        }
        digest = hashlib.sha256(canonical_json_bytes(material)).hexdigest()
        if digest != mapping["integrity_digest"]:
            return False
        prior = digest
    return True
