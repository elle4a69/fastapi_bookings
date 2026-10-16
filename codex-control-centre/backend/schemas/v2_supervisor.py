"""Closed public schemas for the WP-UI-01A supervisor facade."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SCHEMA_VERSION = "0.1"
# The original claim action remains a v0.1 contract.  Planning actions added
# by WP-UI-01B have their own explicitly enforced v0.2 registry below.
CLAIM_ACTION_REGISTRY_VERSION = "0.1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseMeta(StrictModel):
    request_id: str
    schema_version: Literal["0.1"] = SCHEMA_VERSION


class ResourceMeta(ResponseMeta):
    resource_version: int


class ClaimResponseMeta(ResourceMeta):
    idempotency_state: Literal["succeeded"] = "succeeded"


class InProgressMeta(ResponseMeta):
    idempotency_state: Literal["in_progress"] = "in_progress"


class ErrorBody(StrictModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorEnvelope(StrictModel):
    error: ErrorBody
    meta: ResponseMeta


class InfrastructureSnapshot(StrictModel):
    state: Literal["ready", "migration_required"]
    current_revision: Literal["001", "002", "003", "004", "unknown"] | None
    expected_revision: Literal["004"] = "004"
    reason_codes: list[str]


class ProjectResolutionSnapshot(StrictModel):
    state: Literal[
        "unconfigured", "claim_required", "claimed", "quarantined", "dependency_unavailable"
    ]
    reason_codes: list[str]


class ConfirmationDescriptor(StrictModel):
    kind: Literal["dialog"] = "dialog"
    phrase: None = None
    consequences: list[str]


class ClaimActionDescriptor(StrictModel):
    registry_version: Literal["0.1"] = CLAIM_ACTION_REGISTRY_VERSION
    action: Literal["claim_project"] = "claim_project"
    allowed: Literal[True] = True
    reason_code: None = None
    resource_version: Literal[0] = 0
    risk_level: Literal["medium"] = "medium"
    confirmation: ConfirmationDescriptor
    idempotency_required: Literal[True] = True
    expires_at: None = None


class ProjectSummary(StrictModel):
    project_id: str
    display_name: str
    default_branch: str
    state: Literal["claim_required", "ready"]
    version: int
    control_plane: Literal["legacy"] = "legacy"
    claim_action: ClaimActionDescriptor | None = None


class MutationAuthority(StrictModel):
    legacy_owned: Literal["v1"] = "v1"
    supervisor_owned: Literal["none"] = "none"
    allowed_drain_actions: list[str] = Field(default_factory=list)


class CutoverSnapshot(StrictModel):
    mode: Literal["v1_only"] = "v1_only"
    version: Literal[1] = 1
    mutation_authority: MutationAuthority
    allowed_transitions: list[str] = Field(default_factory=list)
    transition_absent_reason_code: Literal["deferred_by_wp_ui_01b"] = "deferred_by_wp_ui_01b"


class Capabilities(StrictModel):
    can_view_supervisor: Literal[True] = True
    can_claim_project: bool


class BootstrapData(StrictModel):
    capabilities: Capabilities
    action_registry_version: Literal["0.1"] = CLAIM_ACTION_REGISTRY_VERSION
    infrastructure: InfrastructureSnapshot
    project_resolution: ProjectResolutionSnapshot | None
    cutover: CutoverSnapshot | None
    cutover_absent_reason_code: Literal["migration_required"] | None
    project: ProjectSummary | None


class BootstrapEnvelope(StrictModel):
    data: BootstrapData
    meta: ResponseMeta


class ReadinessData(StrictModel):
    infrastructure: InfrastructureSnapshot
    project_resolution: ProjectResolutionSnapshot | None


class ReadinessEnvelope(StrictModel):
    data: ReadinessData
    meta: ResponseMeta


class CutoverEnvelope(StrictModel):
    data: CutoverSnapshot
    meta: ResourceMeta


class ProjectsData(StrictModel):
    projects: list[ProjectSummary]


class ProjectsEnvelope(StrictModel):
    data: ProjectsData
    meta: ResponseMeta


class ClaimRequest(StrictModel):
    action: Literal["claim_project"]
    registry_version: Literal["0.1"]
    expected_version: int = Field(ge=0)
    confirmation: Literal[True]


class ClaimedProject(StrictModel):
    project_id: str
    display_name: str
    default_branch: str
    state: Literal["ready"] = "ready"
    version: Literal[1] = 1
    control_plane: Literal["legacy"] = "legacy"


class ClaimData(StrictModel):
    project: ClaimedProject


class ClaimEnvelope(StrictModel):
    data: ClaimData
    meta: ClaimResponseMeta


class InProgressOperation(StrictModel):
    action: Literal["claim_project"] = "claim_project"
    state: Literal["in_progress"] = "in_progress"
    retry_after_seconds: Literal[1] = 1


class InProgressData(StrictModel):
    operation: InProgressOperation


class InProgressEnvelope(StrictModel):
    data: InProgressData
    meta: InProgressMeta


def claim_descriptor() -> dict[str, object]:
    return ClaimActionDescriptor(
        confirmation=ConfirmationDescriptor(
            consequences=[
                "The configured project will be bound to your tenant and user scope."
            ]
        )
    ).model_dump()


def fixed_cutover() -> dict[str, object]:
    return CutoverSnapshot(mutation_authority=MutationAuthority()).model_dump()
