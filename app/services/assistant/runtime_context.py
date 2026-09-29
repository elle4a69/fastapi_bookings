"""Typed Runtime Context for the Assistant Platform.

Defines strongly typed, channel-neutral data models for runtime evaluation,
tool execution, and conversational state tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClientInfo(BaseModel):
    """Normalized client identity and context."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[int] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LocationInfo(BaseModel):
    """Operating location context."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[int] = None
    name: Optional[str] = None
    address: Optional[str] = None
    timezone: str = "UTC"


class NormalizedTurn(BaseModel):
    """Channel-neutral conversation turn."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    role: str  # "system", "user", "assistant", "tool"
    content: str
    source: Optional[str] = None  # "client", "assistant", "operator", "simulated", "chatwoot"
    timestamp: datetime = Field(default_factory=_utc_now)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolExecution(BaseModel):
    """Record of a server-enforced tool execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    timestamp: datetime = Field(default_factory=_utc_now)
    success: bool = True
    error: Optional[str] = None


class RuntimeContext(BaseModel):
    """Authoritative runtime context for conversational assistant operations.

    Encapsulates multi-tenant scoping, provider binding, channel metadata,
    client identity, operational location, conversation history, and live tool
    audit execution records.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: int
    provider_id: Optional[int] = None
    channel_type: str = "sms"
    channel_account_id: Optional[Union[int, str]] = None
    client: Optional[ClientInfo] = None
    location: Optional[LocationInfo] = None
    conversation_id: Optional[Union[int, str]] = None
    message_history: List[NormalizedTurn] = Field(default_factory=list)
    tool_executions: List[ToolExecution] = Field(default_factory=list)
    evaluation_flags: Dict[str, Any] = Field(default_factory=dict)

    def add_turn(
        self,
        role: str,
        content: str,
        source: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NormalizedTurn:
        """Append a normalized turn to conversation history."""
        turn = NormalizedTurn(
            role=role,
            content=content,
            source=source,
            timestamp=timestamp or _utc_now(),
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            metadata=metadata or {},
        )
        self.message_history.append(turn)
        return turn

    def add_tool_execution(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        success: bool = True,
        error: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> ToolExecution:
        """Record a tool execution with its arguments and result."""
        record = ToolExecution(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            timestamp=timestamp or _utc_now(),
            success=success,
            error=error,
        )
        self.tool_executions.append(record)
        return record

    def set_flag(self, flag: str, value: Any) -> None:
        """Set a runtime safety/guardrail flag."""
        self.evaluation_flags[flag] = value

    def get_flag(self, flag: str, default: Any = None) -> Any:
        """Get a runtime safety/guardrail flag."""
        return self.evaluation_flags.get(flag, default)
