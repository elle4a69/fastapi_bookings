from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="", tags=["models"])


class ReasoningEffortOption(BaseModel):
    reasoningEffort: str
    description: str


class ModelItem(BaseModel):
    id: str
    model: str
    displayName: str
    description: str
    isDefault: bool = False
    hidden: bool = False
    defaultReasoningEffort: str = "medium"
    supportedReasoningEfforts: List[ReasoningEffortOption] = Field(default_factory=list)
    inputModalities: List[str] = Field(default_factory=lambda: ["text", "image"])


class ModelListResponse(BaseModel):
    data: List[ModelItem]
    nextCursor: Optional[str] = None


AVAILABLE_MODELS: List[ModelItem] = [
    ModelItem(
        id="gpt-4o",
        model="gpt-4o",
        displayName="GPT-4o",
        description="Default high-intelligence flagship omni model for general and coding workflows.",
        isDefault=True,
        hidden=False,
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=[
            ReasoningEffortOption(reasoningEffort="low", description="Fast responses with light reasoning"),
            ReasoningEffortOption(reasoningEffort="medium", description="Balanced speed and reasoning depth"),
            ReasoningEffortOption(reasoningEffort="high", description="Deepest reasoning and analysis"),
        ],
        inputModalities=["text", "image"],
    ),
    ModelItem(
        id="gpt-4o-mini",
        model="gpt-4o-mini",
        displayName="GPT-4o Mini",
        description="Fast, lightweight, and cost-effective model for routine tasks.",
        isDefault=False,
        hidden=False,
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=[
            ReasoningEffortOption(reasoningEffort="low", description="Fast execution"),
            ReasoningEffortOption(reasoningEffort="medium", description="Balanced"),
            ReasoningEffortOption(reasoningEffort="high", description="Thorough reasoning"),
        ],
        inputModalities=["text", "image"],
    ),
    ModelItem(
        id="o1",
        model="o1",
        displayName="o1",
        description="Reasoning model designed for complex coding, math, and architectural logic.",
        isDefault=False,
        hidden=False,
        defaultReasoningEffort="high",
        supportedReasoningEfforts=[
            ReasoningEffortOption(reasoningEffort="low", description="Light reasoning"),
            ReasoningEffortOption(reasoningEffort="medium", description="Standard reasoning"),
            ReasoningEffortOption(reasoningEffort="high", description="Deep reasoning"),
        ],
        inputModalities=["text", "image"],
    ),
    ModelItem(
        id="o3-mini",
        model="o3-mini",
        displayName="o3-mini",
        description="High-speed reasoning model offering high coding benchmark performance.",
        isDefault=False,
        hidden=False,
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=[
            ReasoningEffortOption(reasoningEffort="low", description="Fast reasoning"),
            ReasoningEffortOption(reasoningEffort="medium", description="Standard reasoning"),
            ReasoningEffortOption(reasoningEffort="high", description="Intense reasoning"),
        ],
        inputModalities=["text"],
    ),
    ModelItem(
        id="claude-3-5-sonnet",
        model="claude-3-5-sonnet",
        displayName="Claude 3.5 Sonnet",
        description="Anthropic state-of-the-art coding and agentic model.",
        isDefault=False,
        hidden=False,
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=[],
        inputModalities=["text", "image"],
    ),
]


@router.get("", response_model=ModelListResponse)
@router.get("/", response_model=ModelListResponse)
def list_models(
    includeHidden: Optional[bool] = Query(False),
    limit: Optional[int] = Query(None),
) -> ModelListResponse:
    """List all available models registered for Codex Control Centre."""
    models = [m for m in AVAILABLE_MODELS if includeHidden or not m.hidden]
    if limit is not None and limit > 0:
        models = models[:limit]
    return ModelListResponse(data=models, nextCursor=None)


@router.get("/{model_id}", response_model=ModelItem)
def get_model(model_id: str) -> ModelItem:
    """Retrieve details of a specific Codex model."""
    for m in AVAILABLE_MODELS:
        if m.id == model_id or m.model == model_id:
            return m
    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
