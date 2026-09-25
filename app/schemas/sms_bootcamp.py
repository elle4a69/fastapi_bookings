from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class BootcampPersona(BaseModel):
    id: str
    name: str
    category: str
    description: str

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampScenarioRead(BaseModel):
    id: str
    pack: str
    title: str
    description: str
    objective: str
    initial_prompt: str = Field(..., alias="initialPrompt")
    expected_outcome: str = Field(..., alias="expectedOutcome")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampScenarioPackRead(BaseModel):
    id: str
    title: str
    description: str
    scenarios: List[BootcampScenarioRead] = []

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampStyleProfile(BaseModel):
    flirtiness: int = Field(2, ge=0, le=5)
    cheerfulness: int = Field(3, ge=0, le=5)
    wit: int = Field(2, ge=0, le=5)
    sarcasm: int = Field(0, ge=0, le=5)
    warmth: int = Field(4, ge=0, le=5)
    directness: int = Field(3, ge=0, le=5)
    chattiness: int = Field(1, ge=0, le=5)
    patience: int = Field(4, ge=0, le=5)

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampRunCreate(BaseModel):
    persona_ids: List[str] = Field(..., alias="personaIds")
    max_turns: int = Field(5, alias="maxTurns", ge=1, le=20)
    style_profile: Optional[Dict[str, Any]] = Field(None, alias="styleProfile")
    sync: Optional[bool] = Field(False)
    autonomy_level: int = Field(2, alias="autonomyLevel", ge=1, le=3)
    scenario_ids: Optional[List[str]] = Field(None, alias="scenarioIds")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampRunControl(BaseModel):
    operation: Literal["pause", "resume", "stop"]

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampInfoResponse(BaseModel):
    information: str

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampCorrectionCreate(BaseModel):
    message_id: str = Field(..., alias="messageId")
    reason: str
    corrected_wording: Optional[str] = Field(None, alias="correctedWording")
    contains_dynamic_facts: bool = Field(False, alias="containsDynamicFacts")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampDraftReviewCreate(BaseModel):
    action: Literal["approve", "discard"]
    text: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampSettingsUpdate(BaseModel):
    agent_name: Optional[str] = Field(None, alias="agentName")
    custom_training_notes: Optional[str] = Field(None, alias="customTrainingNotes")
    system_prompt_template: Optional[str] = Field(None, alias="systemPromptTemplate")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampProfileApply(BaseModel):
    style_profile: Optional[Dict[str, Any]] = Field(None, alias="styleProfile")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampProfileStateResponse(BaseModel):
    active: Dict[str, int]
    defaults: Dict[str, int]
    is_applied: bool = Field(..., alias="isApplied")
    can_undo: bool = Field(..., alias="canUndo")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampMessageResponse(BaseModel):
    id: str
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    role: str
    text: str
    status: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampConversationResponse(BaseModel):
    id: str
    run_id: str = Field(..., alias="runId")
    persona_id: str = Field(..., alias="personaId")
    persona_name: str = Field(..., alias="personaName")
    scenario_id: Optional[str] = Field(None, alias="scenarioId")
    status: str
    current_turn: int = Field(..., alias="currentTurn")
    needs_handoff: bool = Field(..., alias="needsHandoff")
    handoff_reason: Optional[str] = Field(None, alias="handoffReason")
    messages: List[BootcampMessageResponse] = []
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampRunResponse(BaseModel):
    id: str
    status: str
    selected_personas: List[str] = Field(..., alias="selectedPersonaIds")
    selected_scenarios: Optional[List[str]] = Field(None, alias="selectedScenarios")
    autonomy_level: int = Field(2, alias="autonomyLevel")
    max_turns: int = Field(..., alias="maxTurns")
    style_profile: Dict[str, int] = Field(..., alias="styleProfile")
    error: Optional[str] = None
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    conversations: List[BootcampConversationResponse] = []

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BootcampSettingsResponse(BaseModel):
    id: Optional[int] = None
    tenant_id: int = Field(..., alias="tenantId")
    active_style_profile: Dict[str, int] = Field(..., alias="activeStyleProfile")
    previous_style_profile: Optional[Dict[str, int]] = Field(None, alias="previousStyleProfile")
    agent_name: str = Field("Tori", alias="agentName")
    system_prompt_template: Optional[str] = Field(None, alias="systemPromptTemplate")
    custom_training_notes: Optional[str] = Field(None, alias="customTrainingNotes")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
