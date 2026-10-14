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


def _reasoning_options(*efforts: str) -> List[ReasoningEffortOption]:
    descriptions = {
        "low": "Fast responses with light reasoning",
        "medium": "Balanced speed and reasoning depth",
        "high": "Deep reasoning and analysis",
        "xhigh": "Extended reasoning for complex work",
        "max": "Maximum reasoning depth",
        "ultra": "Highest available reasoning depth",
    }
    return [
        ReasoningEffortOption(reasoningEffort=effort, description=descriptions[effort])
        for effort in efforts
    ]


FULL_REASONING = _reasoning_options("low", "medium", "high", "xhigh", "max", "ultra")
LUNA_REASONING = _reasoning_options("low", "medium", "high", "xhigh", "max")

AVAILABLE_MODELS: List[ModelItem] = [
    ModelItem(
        id="gpt-6.1-sol",
        model="gpt-6.1-sol",
        displayName="GPT-6.1 Sol",
        description="Latest workhorse model for coding and everyday work.",
        isDefault=True,
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=FULL_REASONING,
    ),
    ModelItem(
        id="gpt-6-astra",
        model="gpt-6-astra",
        displayName="GPT-6 Astra",
        description="Frontier intelligence for the most demanding work.",
        defaultReasoningEffort="high",
        supportedReasoningEfforts=FULL_REASONING,
    ),
    ModelItem(
        id="gpt-6-sol",
        model="gpt-6-sol",
        displayName="GPT-6 Sol",
        description="Previous-generation workhorse model.",
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=FULL_REASONING,
    ),
    ModelItem(
        id="gpt-6-luna",
        model="gpt-6-luna",
        displayName="GPT-6 Luna",
        description="Fast and affordable model for easier tasks.",
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=LUNA_REASONING,
    ),
    ModelItem(
        id="gpt-5.6-sol",
        model="gpt-5.6-sol",
        displayName="GPT-5.6 Sol",
        description="Older-generation workhorse model.",
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=FULL_REASONING,
    ),
    ModelItem(
        id="gpt-5.6-terra",
        model="gpt-5.6-terra",
        displayName="GPT-5.6 Terra",
        description="Older balanced model for straightforward work.",
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=FULL_REASONING,
    ),
    ModelItem(
        id="gpt-5.6-luna",
        model="gpt-5.6-luna",
        displayName="GPT-5.6 Luna",
        description="Older fast and efficient model.",
        defaultReasoningEffort="medium",
        supportedReasoningEfforts=LUNA_REASONING,
    ),
]


@router.get("", response_model=ModelListResponse)
@router.get("/", response_model=ModelListResponse)
def list_models(
    includeHidden: Optional[bool] = Query(False),
    limit: Optional[int] = Query(None),
) -> ModelListResponse:
    """List the supported Codex models for this application environment."""
    models = [model for model in AVAILABLE_MODELS if includeHidden or not model.hidden]
    if limit is not None and limit > 0:
        models = models[:limit]
    return ModelListResponse(data=models, nextCursor=None)


@router.get("/{model_id}", response_model=ModelItem)
def get_model(model_id: str) -> ModelItem:
    """Retrieve details of a supported Codex model."""
    for model in AVAILABLE_MODELS:
        if model.id == model_id or model.model == model_id:
            return model
    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
