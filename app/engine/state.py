"""Dialogue state schemas for LangGraph massage booking engine.

Defines deterministic state models using Pydantic v2 and TypedDict.
Tracks conversation messages, tenant/provider context metadata,
and fine-grained dialogue turn slot-filling parameters.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, Optional, TypedDict
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, Field


class CustomerLocation(BaseModel):
    """Customer physical or coordinate location details for out-call services."""

    address: Optional[str] = Field(
        None, description="Formatted street address, suburb, or landmark"
    )
    lat: Optional[float] = Field(
        None, description="Latitude coordinate for routing distance calculation"
    )
    lng: Optional[float] = Field(
        None, description="Longitude coordinate for routing distance calculation"
    )

    model_config = ConfigDict(extra="allow")


class DialogueTurn(BaseModel):
    """Deterministic dialogue turn tracking slot-filling and booking progression."""

    current_intent: Optional[str] = Field(
        None,
        description=(
            "Current intent: 'greeting', 'inquire_service', 'select_location', "
            "'check_availability', 'hold_slot', 'confirm_booking', 'escalate'"
        ),
    )
    extracted_service: Optional[str] = Field(
        None, description="Name or requested keyword of the massage service"
    )
    service_id: Optional[int] = Field(
        None, description="Database ID of the matched eligible Service record"
    )
    location_type: Optional[Literal["in_call", "out_call"]] = Field(
        None,
        description="Location modality: 'in_call' (studio) or 'out_call' (mobile)",
    )
    customer_location: Optional[CustomerLocation] = Field(
        None, description="Client address or coordinates for out-call travel calculations"
    )
    calculated_outcall_fee: Optional[float] = Field(
        None, description="Calculated travel surcharge fee in dollars"
    )
    available_slots: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of live slots returned by Cal.com availability adapter",
    )
    selected_slot: Optional[str] = Field(
        None, description="Selected appointment start time in ISO 8601 format"
    )
    hold_id: Optional[str] = Field(
        None, description="Temporary booking hold identifier from Cal.com"
    )
    booking_status: Optional[str] = Field(
        None,
        description=(
            "Progress status: 'inquiry', 'service_selected', 'location_selected', "
            "'slots_presented', 'held', 'confirmed', 'escalated'"
        ),
    )
    escalation_reason: Optional[str] = Field(
        None, description="Reason if human escalation or boundary enforcement was triggered"
    )

    model_config = ConfigDict(extra="allow")


class AgentState(TypedDict, total=False):
    """LangGraph dialogue state passed deterministically through graph nodes."""

    messages: Annotated[list[BaseMessage], operator.add]
    tenant_id: int
    provider_id: Optional[int]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    conversation_id: Optional[int]
    dialogue_turn: DialogueTurn
    reply_text: Optional[str]
    should_escalate: bool
    system_prompt: Optional[str]
