from datetime import datetime, timezone
from sqlalchemy import (
    LargeBinary,
    CheckConstraint,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.database import Base


def _project_root_identity_default(context) -> str:
    """Populate ORM-created legacy rows while preserving fail-closed identity."""
    # Import lazily because the identity service imports settings during model
    # module initialization in several application entry points.
    from backend.services.legacy_adoption_service import root_identity_for_path

    identity = root_identity_for_path(context.get_current_parameters().get("repo_path", ""))
    if identity is None:
        raise ValueError("project_root_identity_unavailable")
    return identity[1]


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    repo_path = Column(String, nullable=False)
    default_branch = Column(String, nullable=False)
    public_id = Column(String, nullable=True, unique=True)
    tenant_id = Column(Integer, nullable=True)
    owner_user_id = Column(Integer, nullable=True)
    scope_state = Column(String, nullable=False, default="unclaimed", server_default="unclaimed")
    control_plane = Column(String, nullable=False, default="legacy", server_default="legacy")
    configured_fingerprint = Column(String, nullable=True, unique=True)
    root_identity_digest = Column(
        String(64), nullable=False, index=True, default=_project_root_identity_default
    )
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("tenant_id IS NULL OR tenant_id > 0", name="ck_projects_tenant_positive"),
        CheckConstraint("owner_user_id IS NULL OR owner_user_id > 0", name="ck_projects_owner_positive"),
        CheckConstraint(
            "scope_state IN ('unclaimed', 'claimed', 'quarantined')",
            name="ck_projects_scope_state",
        ),
        CheckConstraint("control_plane = 'legacy'", name="ck_projects_control_plane"),
        CheckConstraint(
            "length(root_identity_digest) = 64 AND "
            "root_identity_digest NOT GLOB '*[^0-9a-f]*'",
            name="ck_projects_root_identity_digest",
        ),
        CheckConstraint("version >= 0", name="ck_projects_version_nonnegative"),
    )
    
    threads = relationship("Thread", back_populates="project", cascade="all, delete-orphan")

class Thread(Base):
    __tablename__ = "threads"
    
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, nullable=False, default="active")
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    
    project = relationship("Project", back_populates="threads")
    turns = relationship("Turn", back_populates="thread", cascade="all, delete-orphan")
    tool_approvals = relationship("ToolApproval", back_populates="thread", cascade="all, delete-orphan")
    subagents = relationship("SubAgent", back_populates="thread", cascade="all, delete-orphan")

class Turn(Base):
    __tablename__ = "turns"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    prompt = Column(Text, nullable=True)
    
    __table_args__ = (UniqueConstraint('thread_id', 'turn_number'),)
    
    thread = relationship("Thread", back_populates="turns")
    items = relationship("Item", back_populates="turn", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = "items"
    
    id = Column(String, primary_key=True)
    turn_id = Column(Integer, ForeignKey("turns.id", ondelete="CASCADE"), nullable=False)
    item_type = Column(String, nullable=False)
    content = Column(JSON, nullable=False)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    turn = relationship("Turn", back_populates="items")

class ToolApproval(Base):
    __tablename__ = "tool_approvals"
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    tool_call_id = Column(String, nullable=False)
    command = Column(Text, nullable=False)
    risk_level = Column(String, nullable=False)
    consequence = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
    
    thread = relationship("Thread", back_populates="tool_approvals")

class SubAgent(Base):
    __tablename__ = "subagents"
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    parent_thread_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    status = Column(String, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    current_action = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    thread = relationship("Thread", back_populates="subagents")

class WorkspaceBoundary(Base):
    __tablename__ = "workspace_boundaries"

    id = Column(String, primary_key=True)
    path = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SchemaAdoptionMetadata(Base):
    __tablename__ = "schema_adoption_metadata"

    asset_key = Column(String, primary_key=True)
    structural_version = Column(String, nullable=False)
    structure_digest = Column(String(64), nullable=False)
    origin = Column(String, nullable=False)
    adopted_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("origin IN ('created', 'adopted')", name="ck_schema_adoption_origin"),
    )
class ControlPlaneCutoverState(Base):
    __tablename__ = "control_plane_cutover_state"

    singleton_id = Column(Integer, primary_key=True)
    mode = Column(String, nullable=False, default="v1_only", server_default="v1_only")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("singleton_id = 1", name="ck_cutover_singleton"),
        CheckConstraint("mode = 'v1_only'", name="ck_cutover_mode"),
        CheckConstraint("version = 1", name="ck_cutover_version"),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(String, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    action_code = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=False)
    request_id = Column(String, nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    lease_owner = Column(String, nullable=True)
    lease_token_hash = Column(String(64), nullable=True)
    lease_acquired_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    response_status = Column(Integer, nullable=True)
    response_body = Column(LargeBinary, nullable=True)
    response_headers = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "action_code",
            "idempotency_key",
            name="uq_idempotency_scope_key",
        ),
        CheckConstraint("tenant_id > 0 AND user_id > 0", name="ck_idempotency_scope_positive"),
        CheckConstraint(
            "status IN ('in_progress', 'succeeded', 'failed')",
            name="ck_idempotency_status",
        ),
        CheckConstraint(
            "lease_owner IS NULL OR (length(lease_owner) = 36 AND substr(lease_owner, 1, 4) = 'exe_' "
            "AND substr(lease_owner, 5) NOT GLOB '*[^0-9a-f]*')",
            name="ck_idempotency_lease_owner",
        ),
        CheckConstraint("action_code IN ('claim_project','create_mission','create_work_package','create_brief','approve_brief','record_context_checkpoint','define_audit_scope','issue_run_start_authorization','start_supervisor_run')", name="ck_idempotency_action"),
        CheckConstraint(
            "length(request_fingerprint) = 64 AND request_fingerprint NOT GLOB '*[^0-9a-f]*'",
            name="ck_idempotency_request_fingerprint",
        ),
        CheckConstraint(
            "response_status IS NULL OR response_status BETWEEN 100 AND 599",
            name="ck_idempotency_response_status",
        ),
        CheckConstraint(
            "lease_token_hash IS NULL OR (length(lease_token_hash) = 64 AND lease_token_hash NOT GLOB '*[^0-9a-f]*')",
            name="ck_idempotency_lease_hash",
        ),
        CheckConstraint(
            "(status = 'in_progress' AND completed_at IS NULL AND expires_at IS NULL "
            "AND response_status IS NULL AND response_body IS NULL AND response_headers IS NULL "
            "AND lease_owner IS NOT NULL AND lease_token_hash IS NOT NULL "
            "AND lease_acquired_at IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(status IN ('succeeded', 'failed') AND completed_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND response_status IS NOT NULL AND response_body IS NOT NULL AND response_headers IS NOT NULL "
            "AND lease_owner IS NULL AND lease_token_hash IS NULL "
            "AND lease_acquired_at IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_idempotency_lifecycle",
        ),
        CheckConstraint(
            "completed_at IS NULL OR (strftime('%s', completed_at) IS NOT NULL AND "
            "strftime('%s', expires_at) IS NOT NULL AND "
            "CAST(strftime('%s', expires_at) AS INTEGER) = "
            "CAST(strftime('%s', completed_at) AS INTEGER) + 86400)",
            name="ck_idempotency_retention_24h",
        ),
    )


class SupervisorEvent(Base):
    __tablename__ = "supervisor_events"

    event_key = Column(String, primary_key=True)
    project_public_id = Column(String, nullable=False)
    project_sequence = Column(Integer, nullable=False)
    actor_tenant_id = Column(Integer, nullable=False)
    actor_user_id = Column(Integer, nullable=False)
    action_code = Column(String, nullable=False)
    outcome = Column(String, nullable=False)
    project_version = Column(Integer, nullable=False)
    request_id = Column(String, nullable=False)
    idempotency_key_hash = Column(String(64), nullable=False)
    payload = Column(Text, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    schema_version = Column(String, nullable=False, default="0.1", server_default="0.1")
    previous_digest = Column(String(64), nullable=True)
    integrity_digest = Column(String(64), nullable=False, unique=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "project_public_id", "project_sequence", name="uq_supervisor_event_project_sequence"
        ),
        UniqueConstraint("request_id", "action_code", name="uq_supervisor_event_request_action"),
        CheckConstraint("actor_tenant_id > 0 AND actor_user_id > 0", name="ck_supervisor_event_scope"),
        CheckConstraint("action_code IN ('claim_project','create_mission','create_work_package','create_brief','approve_brief','record_context_checkpoint','define_audit_scope','issue_run_start_authorization','start_supervisor_run')", name="ck_supervisor_event_action"),
        CheckConstraint("schema_version IN ('0.1','0.2')", name="ck_supervisor_event_schema"),
        CheckConstraint("project_version >= 1", name="ck_supervisor_event_project_version"),
        CheckConstraint("project_sequence >= 1", name="ck_supervisor_event_sequence"),
        CheckConstraint("outcome = 'succeeded'", name="ck_supervisor_event_outcome"),
        CheckConstraint(
            "(project_sequence = 1 AND previous_digest IS NULL) OR "
            "(project_sequence > 1 AND length(previous_digest) = 64 "
            "AND previous_digest NOT GLOB '*[^0-9a-f]*')",
            name="ck_supervisor_event_previous_digest",
        ),
    )


class PlanningMission(Base):
    __tablename__ = "planning_missions"
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    tenant_id = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    title = Column(String(160), nullable=False)
    summary = Column(String(1200), nullable=False)
    state = Column(String, nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("id LIKE 'mis_%'", name="ck_mission_id"), CheckConstraint("tenant_id > 0 AND owner_user_id > 0 AND version >= 1", name="ck_mission_scope"), CheckConstraint("state IN ('draft','planned')", name="ck_mission_state"))


class PlanningWorkPackage(Base):
    __tablename__ = "planning_work_packages"
    id = Column(String, primary_key=True)
    mission_id = Column(String, ForeignKey("planning_missions.id", ondelete="RESTRICT"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    tenant_id = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    title = Column(String(160), nullable=False)
    scope = Column(String(1600), nullable=False)
    state = Column(String, nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("id LIKE 'wpk_%'", name="ck_work_package_id"), CheckConstraint("tenant_id > 0 AND owner_user_id > 0 AND version >= 1", name="ck_work_package_scope"), CheckConstraint("state IN ('draft','brief_ready','brief_approved')", name="ck_work_package_state"))


class PlanningBrief(Base):
    __tablename__ = "planning_briefs"
    id = Column(String, primary_key=True)
    work_package_id = Column(String, ForeignKey("planning_work_packages.id", ondelete="RESTRICT"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    tenant_id = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    revision = Column(Integer, nullable=False)
    content = Column(String(4000), nullable=False)
    content_digest = Column(String(64), nullable=False)
    future_execution_authorization_requirement = Column(String, nullable=False, default="requires_authorization")
    state = Column(String, nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    approved_by_user_id = Column(Integer, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("work_package_id", "revision", name="uq_brief_revision"), CheckConstraint("id LIKE 'brf_%'", name="ck_brief_id"), CheckConstraint("state IN ('draft','approved','superseded')", name="ck_brief_state"), CheckConstraint("future_execution_authorization_requirement IN ('requires_authorization','not_required_once_requested')", name="ck_brief_authorization"))


class PlanningContextCheckpoint(Base):
    __tablename__ = "planning_context_checkpoints"
    id = Column(String, primary_key=True)
    mission_id = Column(String, ForeignKey("planning_missions.id", ondelete="RESTRICT"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    tenant_id = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    sequence = Column(Integer, nullable=False)
    summary = Column(String(1600), nullable=False)
    decisions = Column(String(1600), nullable=False)
    constraints = Column(String(1600), nullable=False)
    open_questions = Column(String(1600), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("mission_id", "sequence", name="uq_checkpoint_sequence"), CheckConstraint("id LIKE 'ctx_%'", name="ck_checkpoint_id"))


class PlanningAuditScope(Base):
    __tablename__ = "planning_audit_scopes"
    id = Column(String, primary_key=True)
    work_package_id = Column(String, ForeignKey("planning_work_packages.id", ondelete="RESTRICT"), nullable=False, unique=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    tenant_id = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    criteria = Column(String(2000), nullable=False)
    exclusions = Column(String(1200), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("id LIKE 'asc_%'", name="ck_audit_scope_id"),)


class SupervisorRunStartAuthorizationGrant(Base):
    """Server-issued, hash-only, one-run start authority; never a tool grant."""

    __tablename__ = "supervisor_run_start_authorization_grants"
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    work_package_id = Column(String, ForeignKey("planning_work_packages.id", ondelete="RESTRICT"), nullable=False)
    brief_id = Column(String, ForeignKey("planning_briefs.id", ondelete="RESTRICT"), nullable=False)
    audit_scope_id = Column(String, ForeignKey("planning_audit_scopes.id", ondelete="RESTRICT"), nullable=False)
    tenant_id = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    authorization_hash = Column(String(64), nullable=False, unique=True)
    policy = Column(String, nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    run_id = Column(String, nullable=True, unique=True)
    __table_args__ = (
        CheckConstraint("id LIKE 'sag_%'", name="ck_run_grant_id"),
        CheckConstraint("tenant_id > 0 AND owner_user_id > 0", name="ck_run_grant_scope"),
        CheckConstraint("policy IN ('requires_authorization','not_required_once_requested')", name="ck_run_grant_policy"),
        CheckConstraint("length(authorization_hash) = 64 AND authorization_hash NOT GLOB '*[^0-9a-f]*'", name="ck_run_grant_hash"),
        CheckConstraint("expires_at > issued_at", name="ck_run_grant_expiry"),
        CheckConstraint("(consumed_at IS NULL AND run_id IS NULL) OR (consumed_at IS NOT NULL AND run_id IS NOT NULL)", name="ck_run_grant_consumption"),
    )


class SupervisorRun(Base):
    """Privacy-safe durable dispatch ledger, not a worker transcript or tool ledger."""

    __tablename__ = "supervisor_runs"
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    work_package_id = Column(String, ForeignKey("planning_work_packages.id", ondelete="RESTRICT"), nullable=False)
    brief_id = Column(String, ForeignKey("planning_briefs.id", ondelete="RESTRICT"), nullable=False)
    audit_scope_id = Column(String, ForeignKey("planning_audit_scopes.id", ondelete="RESTRICT"), nullable=False)
    grant_id = Column(String, ForeignKey("supervisor_run_start_authorization_grants.id", ondelete="RESTRICT"), nullable=False, unique=True)
    tenant_id = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    brief_content_digest = Column(String(64), nullable=False)
    capability_profile = Column(String, nullable=False, default="development_worker_v1")
    status = Column(String, nullable=False)
    request_id = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("id LIKE 'run_%'", name="ck_supervisor_run_id"),
        CheckConstraint("tenant_id > 0 AND owner_user_id > 0", name="ck_supervisor_run_scope"),
        CheckConstraint("length(brief_content_digest) = 64 AND brief_content_digest NOT GLOB '*[^0-9a-f]*'", name="ck_supervisor_run_brief_digest"),
        CheckConstraint("capability_profile = 'development_worker_v1'", name="ck_supervisor_run_capability"),
        CheckConstraint("status IN ('dispatching','dispatch_acknowledged','dispatch_unknown','dispatch_rejected')", name="ck_supervisor_run_status"),
    )


class SupervisorDispatchAttempt(Base):
    __tablename__ = "supervisor_dispatch_attempts"
    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("supervisor_runs.id", ondelete="RESTRICT"), nullable=False, unique=True)
    tenant_id = Column(Integer, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    state = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("id LIKE 'dpa_%'", name="ck_dispatch_attempt_id"),
        CheckConstraint("tenant_id > 0 AND owner_user_id > 0 AND attempt_number = 1", name="ck_dispatch_attempt_scope"),
        CheckConstraint("state IN ('intent_persisted','acknowledged','dispatch_unknown','rejected')", name="ck_dispatch_attempt_state"),
    )
