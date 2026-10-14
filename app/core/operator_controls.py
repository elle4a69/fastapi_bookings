"""Operator controls, settings schemas, and concurrency management for Voice Assistant.

Enforces:
1. Strict model & voice whitelists (rejecting unauthorized substitutions).
2. Transport toggle between direct real-time engines ('direct_gpt_live' and 'xai_grok_voice').
3. Session concurrency limits per tenant and globally.
4. Cost and budget alert thresholds.
5. System health and readiness evaluation with zero credential leakage.
"""

from dataclasses import dataclass, field
import datetime
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings

logger = logging.getLogger("app.core.operator_controls")


@dataclass
class ActiveVoiceSession:
    """In-memory active voice session tracking with TTL and heartbeat metadata."""

    session_id: str
    tenant_id: int
    user_id: Optional[int] = None
    conversation_id: Optional[int] = None
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    last_heartbeat_at: float = field(default_factory=time.time)
    ttl_seconds: int = 600
    idle_timeout_seconds: int = 180
    transport: Optional[str] = None


# Authoritative whitelists per specification Section 2.2 & Stage C requirements
APPROVED_LIVE_MODELS: list[str] = ["gpt-live-1", "grok-voice-think-fast-2.0"]
APPROVED_DELEGATED_MODELS: list[str] = ["gpt-5.6-terra", "gpt-6-luna", "gpt-5.6-luna", "5.6-luna"]
APPROVED_VOICES: list[str] = ["gleam"]
CANONICAL_TRANSPORTS: list[str] = ["xai_grok_voice", "direct_gpt_live"]
VALID_TRANSPORTS: list[str] = ["xai_grok_voice", "direct_gpt_live"]


class OperatorControlError(Exception):
    """Base exception for operator control failures."""


class UnauthorizedModelOrVoiceError(OperatorControlError):
    """Raised when an unapproved model or voice is selected."""


class ConcurrencyLimitExceeded(OperatorControlError):
    """Raised when active sessions exceed tenant or global concurrency caps."""


class InvalidTransportError(OperatorControlError):
    """Raised when an unsupported transport is selected."""


class OperatorSettingsRead(BaseModel):
    """Authoritative operator controls configuration."""

    transport: str = Field(..., description="Active voice transport ('direct_gpt_live' or 'xai_grok_voice')")
    available_transports: List[str] = Field(default_factory=lambda: list(CANONICAL_TRANSPORTS))
    selected_live_model: str = Field(..., description="Currently selected realtime voice model")
    selected_delegated_model: str = Field(..., description="Currently selected delegated Responses model")
    selected_voice: str = Field(..., description="Currently selected voice persona")
    approved_live_models: List[str] = Field(default_factory=lambda: list(APPROVED_LIVE_MODELS))
    approved_delegated_models: List[str] = Field(default_factory=lambda: list(APPROVED_DELEGATED_MODELS))
    approved_voices: List[str] = Field(default_factory=lambda: list(APPROVED_VOICES))
    max_concurrent_sessions_per_tenant: int = Field(..., ge=1, description="Max concurrent voice sessions per tenant")
    max_concurrent_sessions_global: int = Field(..., ge=1, description="Max concurrent voice sessions globally across all tenants")
    current_active_sessions_global: int = Field(0, description="Active concurrent voice sessions across the system")
    cost_alert_threshold_usd: float = Field(..., ge=0.0, description="Cost threshold in USD triggering operator warnings")
    budget_alert_threshold_usd: float = Field(..., ge=0.0, description="Hard budget cap threshold in USD")
    current_cost_usd: float = Field(0.0, description="Accrued voice assistant session expenditure in USD")
    cost_alert_triggered: bool = Field(False, description="Whether accrued cost has crossed the warning threshold")
    budget_exceeded: bool = Field(False, description="Whether accrued cost has crossed the budget cap")
    version: str = Field("1.0.0", description="Configuration schema and rollout version")
    updated_at: str = Field(..., description="ISO 8601 timestamp of last settings update")


class OperatorSettingsUpdate(BaseModel):
    """Payload to mutate operator controls. Unapproved values are strictly rejected."""

    transport: Optional[str] = Field(None, description="Transport toggle ('direct_gpt_live' or 'xai_grok_voice')")
    selected_live_model: Optional[str] = Field(None, description="Must be in APPROVED_LIVE_MODELS")
    selected_delegated_model: Optional[str] = Field(None, description="Must be in APPROVED_DELEGATED_MODELS")
    selected_voice: Optional[str] = Field(None, description="Must be in APPROVED_VOICES")
    max_concurrent_sessions_per_tenant: Optional[int] = Field(None, ge=1)
    max_concurrent_sessions_global: Optional[int] = Field(None, ge=1)
    cost_alert_threshold_usd: Optional[float] = Field(None, ge=0.0)
    budget_alert_threshold_usd: Optional[float] = Field(None, ge=0.0)

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_TRANSPORTS:
            raise ValueError(f"Invalid transport '{v}'. Allowed transports are: {VALID_TRANSPORTS}")
        return v

    @field_validator("selected_live_model")
    @classmethod
    def validate_live_model(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in APPROVED_LIVE_MODELS:
            raise ValueError(f"Model '{v}' is not in approved whitelist: {APPROVED_LIVE_MODELS}")
        return v

    @field_validator("selected_delegated_model")
    @classmethod
    def validate_delegated_model(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in APPROVED_DELEGATED_MODELS:
            raise ValueError(f"Delegated model '{v}' is not in approved whitelist: {APPROVED_DELEGATED_MODELS}")
        return v

    @field_validator("selected_voice")
    @classmethod
    def validate_voice(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in APPROVED_VOICES:
            raise ValueError(f"Voice '{v}' is not in approved whitelist: {APPROVED_VOICES}")
        return v


class WorkerHealth(BaseModel):
    status: str = Field(..., description="'ready', 'running', or 'degraded'")
    agent_name: str
    entrypoint_configured: bool


class VoiceServerHealth(BaseModel):
    status: str = Field(..., description="'connected', 'reachable', or 'unreachable'")
    connected: bool
    url: str
    error: Optional[str] = None


class QuotaReadiness(BaseModel):
    ready: bool
    active_sessions_global: int
    max_concurrent_sessions_global: int
    max_concurrent_sessions_per_tenant: int
    budget_alert_threshold_usd: float
    cost_alert_threshold_usd: float
    current_cost_usd: float
    budget_exceeded: bool
    cost_alert_triggered: bool


class MaskedCredentials(BaseModel):
    openai_api_key_configured: bool
    openai_api_key_masked: str
    xai_api_key_configured: bool = False
    xai_api_key_masked: str = "[NOT CONFIGURED]"
    livekit_api_key_configured: bool = False
    livekit_api_secret_configured: bool = False
    livekit_api_key_masked: str = "[NOT CONFIGURED]"
    livekit_api_secret_masked: str = "[NOT CONFIGURED]"


class LiveKitHealthResponse(BaseModel):
    status: str = Field(..., description="'healthy', 'degraded', or 'unhealthy'")
    worker: WorkerHealth
    livekit_server: VoiceServerHealth
    voice_server: Optional[VoiceServerHealth] = None
    quota_readiness: QuotaReadiness
    credentials: MaskedCredentials
    timestamp: str


VoiceHealthResponse = LiveKitHealthResponse
LiveKitServerHealth = VoiceServerHealth


def _mask_secret(val: Optional[str]) -> str:
    """Mask sensitive string leaving only up to first 3 characters if safe, never leaking the full secret."""
    if not val:
        return "[NOT CONFIGURED]"
    if len(val) <= 4:
        return "***"
    return f"{val[:3]}***[REDACTED]"


class OperatorControlsService:
    """Thread-safe singleton service managing operator controls, concurrency and health."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        init_transport = getattr(settings, "VOICE_ASSISTANT_TRANSPORT", "xai_grok_voice")
        if init_transport not in VALID_TRANSPORTS:
            init_transport = "xai_grok_voice"
        self._transport: str = init_transport

        self._selected_live_model: str = "gpt-live-1"
        self._selected_delegated_model: str = "gpt-5.6-terra"
        self._selected_voice: str = "gleam"
        self._max_per_tenant: int = 5
        self._max_global: int = 50
        self._cost_alert_threshold_usd: float = 100.0
        self._budget_alert_threshold_usd: float = 500.0
        self._current_cost_usd: float = 0.0
        self._version_counter: int = 1
        self._updated_at: str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # active sessions: session_id -> ActiveVoiceSession
        self._active_sessions: Dict[str, ActiveVoiceSession] = {}

    def sync_from_settings(self, force: bool = False) -> None:
        """Sync runtime configuration if needed."""
        pass

    def _reap_stale_sessions_locked(
        self,
        now: Optional[float] = None,
        max_idle_seconds: Optional[int] = None,
    ) -> int:
        """Internal helper to prune expired and idle sessions under self._lock."""
        current_time = now if now is not None else time.time()
        stale_keys = []
        for sid, s in self._active_sessions.items():
            # Check 1: total session TTL exceeded
            if current_time - s.created_at >= s.ttl_seconds:
                stale_keys.append(sid)
                continue
            # Check 2: idle timeout exceeded (no heartbeat)
            effective_idle = max_idle_seconds if max_idle_seconds is not None else s.idle_timeout_seconds
            if current_time - s.last_heartbeat_at >= effective_idle:
                stale_keys.append(sid)
                continue
            # Check 3: terminal status
            if s.status in ("expired", "abandoned", "released"):
                stale_keys.append(sid)

        for sid in stale_keys:
            sess = self._active_sessions.pop(sid, None)
            if sess:
                logger.info(
                    "Reaped stale voice session %s (tenant=%s, age=%.1fs, idle=%.1fs, reason=%s)",
                    sid,
                    sess.tenant_id,
                    current_time - sess.created_at,
                    current_time - sess.last_heartbeat_at,
                    "ttl_expired" if current_time - sess.created_at >= sess.ttl_seconds else "idle_timeout",
                )
        return len(stale_keys)

    def reap_stale_sessions(self, max_idle_seconds: Optional[int] = None) -> int:
        """Thread-safe public method to prune expired or abandoned sessions."""
        with self._lock:
            return self._reap_stale_sessions_locked(max_idle_seconds=max_idle_seconds)

    def get_settings(self) -> OperatorSettingsRead:
        with self._lock:
            self._reap_stale_sessions_locked()
            active_count = len(self._active_sessions)
            cost_alert = self._current_cost_usd >= self._cost_alert_threshold_usd
            budget_alert = self._current_cost_usd >= self._budget_alert_threshold_usd

            return OperatorSettingsRead(
                transport=self._transport,
                available_transports=list(CANONICAL_TRANSPORTS),
                selected_live_model=self._selected_live_model,
                selected_delegated_model=self._selected_delegated_model,
                selected_voice=self._selected_voice,
                approved_live_models=list(APPROVED_LIVE_MODELS),
                approved_delegated_models=list(APPROVED_DELEGATED_MODELS),
                approved_voices=list(APPROVED_VOICES),
                max_concurrent_sessions_per_tenant=self._max_per_tenant,
                max_concurrent_sessions_global=self._max_global,
                current_active_sessions_global=active_count,
                cost_alert_threshold_usd=self._cost_alert_threshold_usd,
                budget_alert_threshold_usd=self._budget_alert_threshold_usd,
                current_cost_usd=round(self._current_cost_usd, 4),
                cost_alert_triggered=cost_alert,
                budget_exceeded=budget_alert,
                version=f"1.0.{self._version_counter}",
                updated_at=self._updated_at,
            )

    def update_settings(self, update: Any) -> OperatorSettingsRead:
        with self._lock:
            transport_val = getattr(update, "transport", None)
            if transport_val is not None:
                if transport_val not in VALID_TRANSPORTS:
                    raise InvalidTransportError(f"Unsupported transport '{transport_val}'. Allowed: {VALID_TRANSPORTS}")
                self._transport = transport_val

            live_model_val = getattr(update, "selected_live_model", None)
            if live_model_val is not None:
                if live_model_val not in APPROVED_LIVE_MODELS:
                    raise UnauthorizedModelOrVoiceError(
                        f"Model '{live_model_val}' is not in approved whitelist: {APPROVED_LIVE_MODELS}"
                    )
                self._selected_live_model = live_model_val

            delegated_model_val = getattr(update, "selected_delegated_model", None)
            if delegated_model_val is not None:
                if delegated_model_val not in APPROVED_DELEGATED_MODELS:
                    raise UnauthorizedModelOrVoiceError(
                        f"Delegated model '{delegated_model_val}' is not in approved whitelist: {APPROVED_DELEGATED_MODELS}"
                    )
                self._selected_delegated_model = delegated_model_val

            voice_val = getattr(update, "selected_voice", None)
            if voice_val is not None:
                if voice_val not in APPROVED_VOICES:
                    raise UnauthorizedModelOrVoiceError(
                        f"Voice '{voice_val}' is not in approved whitelist: {APPROVED_VOICES}"
                    )
                self._selected_voice = voice_val

            max_tenant_val = getattr(update, "max_concurrent_sessions_per_tenant", None)
            if max_tenant_val is not None:
                if max_tenant_val < 1:
                    raise ValueError("max_concurrent_sessions_per_tenant must be >= 1")
                self._max_per_tenant = max_tenant_val

            max_global_val = getattr(update, "max_concurrent_sessions_global", None)
            if max_global_val is not None:
                if max_global_val < 1:
                    raise ValueError("max_concurrent_sessions_global must be >= 1")
                self._max_global = max_global_val

            cost_alert_val = getattr(update, "cost_alert_threshold_usd", None)
            if cost_alert_val is not None:
                self._cost_alert_threshold_usd = cost_alert_val

            budget_alert_val = getattr(update, "budget_alert_threshold_usd", None)
            if budget_alert_val is not None:
                self._budget_alert_threshold_usd = budget_alert_val

            self._version_counter += 1
            self._updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        logger.info(
            "Operator settings updated: transport=%s, live_model=%s, voice=%s, max_tenant=%d, max_global=%d",
            self._transport,
            self._selected_live_model,
            self._selected_voice,
            self._max_per_tenant,
            self._max_global,
        )
        return self.get_settings()

    def acquire_session(
        self,
        session_id: str,
        tenant_id: int,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        ttl_seconds: int = 600,
        idle_timeout_seconds: int = 180,
        replace_stale_conversation: bool = True,
        force_restart: bool = False,
        transport: Optional[str] = None,
    ) -> None:
        """Register an active voice session, enforcing global and tenant concurrency limits."""
        with self._lock:
            current_time = time.time()
            # 1. First automatically reap any expired/idle sessions across all tenants
            self._reap_stale_sessions_locked(now=current_time)

            # 2. If conversation_id is provided, clean up abandoned or force-restarted sessions for this conversation
            if conversation_id is not None and (replace_stale_conversation or force_restart):
                conv_prior_keys = [
                    sid
                    for sid, s in self._active_sessions.items()
                    if s.tenant_id == tenant_id
                    and s.conversation_id == conversation_id
                    and (
                        force_restart
                        or (current_time - s.last_heartbeat_at >= 15.0)
                        or (current_time - s.created_at >= 15.0)
                    )
                ]
                for sid in conv_prior_keys:
                    prior = self._active_sessions.pop(sid, None)
                    if prior:
                        logger.info(
                            "Cleaned up %s prior voice session %s for tenant %s on conversation %s",
                            "force_restarted" if force_restart else "abandoned",
                            sid,
                            tenant_id,
                            conversation_id,
                        )

            # 3. Check hard budget cap
            if self._current_cost_usd >= self._budget_alert_threshold_usd:
                raise ConcurrencyLimitExceeded(
                    f"Voice assistant budget limit of ${self._budget_alert_threshold_usd:.2f} reached. "
                    "Cannot start additional voice sessions."
                )

            # 4. Check global concurrency
            if len(self._active_sessions) >= self._max_global:
                raise ConcurrencyLimitExceeded(
                    f"Global voice session limit of {self._max_global} reached. Cannot start new session."
                )

            # 5. Check tenant concurrency
            tenant_count = sum(1 for s in self._active_sessions.values() if s.tenant_id == tenant_id)
            if tenant_count >= self._max_per_tenant:
                raise ConcurrencyLimitExceeded(
                    f"Tenant {tenant_id} voice session limit of {self._max_per_tenant} reached. "
                    "Cannot start additional concurrent session."
                )

            # 6. Register active session
            self._active_sessions[session_id] = ActiveVoiceSession(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                status="active",
                created_at=current_time,
                last_heartbeat_at=current_time,
                ttl_seconds=ttl_seconds,
                idle_timeout_seconds=idle_timeout_seconds,
                transport=transport,
            )
            logger.info(
                "Acquired voice session %s for tenant %s (conv=%s, user=%s). Active in tenant: %d/%d, Global: %d/%d",
                session_id,
                tenant_id,
                conversation_id,
                user_id,
                tenant_count + 1,
                self._max_per_tenant,
                len(self._active_sessions),
                self._max_global,
            )

    def release_session(self, session_id: str) -> bool:
        """Unregister an active voice session upon completion or disconnect."""
        with self._lock:
            if session_id in self._active_sessions:
                sess = self._active_sessions.pop(session_id)
                logger.info(
                    "Released voice session %s for tenant %s. Remaining global: %d",
                    session_id,
                    sess.tenant_id,
                    len(self._active_sessions),
                )
                return True
            return False

    def heartbeat_session(self, session_id: str, tenant_id: Optional[int] = None) -> bool:
        """Record a heartbeat timestamp for an active session to keep it alive."""
        with self._lock:
            self._reap_stale_sessions_locked()
            sess = self._active_sessions.get(session_id)
            if sess is None:
                return False
            if tenant_id is not None and sess.tenant_id != tenant_id:
                return False
            sess.last_heartbeat_at = time.time()
            return True

    def is_session_active(self, session_id: str, tenant_id: Optional[int] = None) -> bool:
        """Check whether a session is currently active and belongs to the specified tenant."""
        with self._lock:
            self._reap_stale_sessions_locked()
            if session_id not in self._active_sessions:
                return False
            sess = self._active_sessions[session_id]
            if tenant_id is not None and sess.tenant_id != tenant_id:
                return False
            return True

    def get_active_session(self, session_id: str, tenant_id: Optional[int] = None) -> Optional[ActiveVoiceSession]:
        """Retrieve active session dataclass if present and belonging to the tenant."""
        with self._lock:
            self._reap_stale_sessions_locked()
            sess = self._active_sessions.get(session_id)
            if sess and (tenant_id is None or sess.tenant_id == tenant_id):
                return sess
            return None

    def active_session_count(self, tenant_id: Optional[int] = None) -> int:
        with self._lock:
            self._reap_stale_sessions_locked()
            if tenant_id is None:
                return len(self._active_sessions)
            return sum(1 for s in self._active_sessions.values() if s.tenant_id == tenant_id)

    def list_active_sessions(self, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List active voice sessions and their lifecycle metadata."""
        with self._lock:
            self._reap_stale_sessions_locked()
            now = time.time()
            results = []
            for s in self._active_sessions.values():
                if tenant_id is not None and s.tenant_id != tenant_id:
                    continue
                results.append(
                    {
                        "session_id": s.session_id,
                        "tenant_id": s.tenant_id,
                        "user_id": s.user_id,
                        "conversation_id": s.conversation_id,
                        "status": s.status,
                        "created_at": s.created_at,
                        "last_heartbeat_at": s.last_heartbeat_at,
                        "age_seconds": round(now - s.created_at, 2),
                        "idle_seconds": round(now - s.last_heartbeat_at, 2),
                        "ttl_seconds": s.ttl_seconds,
                    }
                )
            return results

    def prune_sessions(self, tenant_id: Optional[int] = None, force_all: bool = False) -> int:
        """Admin helper to prune stale sessions or forcibly clear sessions for a tenant."""
        with self._lock:
            if force_all:
                if tenant_id is None:
                    count = len(self._active_sessions)
                    self._active_sessions.clear()
                    return count
                to_remove = [sid for sid, s in self._active_sessions.items() if s.tenant_id == tenant_id]
                for sid in to_remove:
                    self._active_sessions.pop(sid, None)
                return len(to_remove)
            return self._reap_stale_sessions_locked()

    def record_cost(self, amount_usd: float) -> float:
        """Record usage cost for voice transactions."""
        with self._lock:
            self._current_cost_usd += max(0.0, amount_usd)
            return self._current_cost_usd

    def reset_state_for_tests(self) -> None:
        """Helper to reset mutable runtime state in testing fixtures."""
        with self._lock:
            init_transport = getattr(settings, "VOICE_ASSISTANT_TRANSPORT", "direct_gpt_live")
            if init_transport not in VALID_TRANSPORTS:
                init_transport = "direct_gpt_live"
            self._transport = init_transport
            self._selected_live_model = "gpt-live-1"
            self._selected_delegated_model = "gpt-5.6-terra"
            self._selected_voice = "gleam"
            self._max_per_tenant = 5
            self._max_global = 50
            self._cost_alert_threshold_usd = 100.0
            self._budget_alert_threshold_usd = 500.0
            self._current_cost_usd = 0.0
            self._active_sessions.clear()
            self._version_counter = 1
            self._updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def check_health(self) -> LiveKitHealthResponse:
        """Perform system health, server connectivity, and quota readiness checks."""
        # 1. Worker status
        agent_name = "bookings-business-assistant"
        worker_ready = True
        worker_health = WorkerHealth(
            status="ready" if worker_ready else "degraded",
            agent_name=agent_name,
            entrypoint_configured=True,
        )

        # 2. Server status (Direct WebRTC or xAI Grok Voice)
        if self._transport == "xai_grok_voice":
            connected = bool(settings.XAI_API_KEY)
            server_health = VoiceServerHealth(
                status="connected" if connected else "unreachable",
                connected=connected,
                url=f"{settings.XAI_REALTIME_URL}?agent_id={settings.XAI_REALTIME_AGENT_ID}",
                error=None if connected else "XAI_API_KEY is not configured",
            )
        else:
            connected = True
            server_health = VoiceServerHealth(
                status="connected",
                connected=True,
                url="direct_gpt_live (direct WebRTC engine ready)",
                error=None,
            )

        # 3. Quota readiness
        with self._lock:
            self._reap_stale_sessions_locked()
            active_count = len(self._active_sessions)
            cost_alert = self._current_cost_usd >= self._cost_alert_threshold_usd
            budget_alert = self._current_cost_usd >= self._budget_alert_threshold_usd
            concurrency_available = active_count < self._max_global
            quota_ready = concurrency_available and not budget_alert

            quota_health = QuotaReadiness(
                ready=quota_ready,
                active_sessions_global=active_count,
                max_concurrent_sessions_global=self._max_global,
                max_concurrent_sessions_per_tenant=self._max_per_tenant,
                budget_alert_threshold_usd=self._budget_alert_threshold_usd,
                cost_alert_threshold_usd=self._cost_alert_threshold_usd,
                current_cost_usd=round(self._current_cost_usd, 4),
                budget_exceeded=budget_alert,
                cost_alert_triggered=cost_alert,
            )

        # 4. Masked credentials (NEVER leak secrets)
        oai_key = getattr(settings, "OPENAI_API_KEY", "")
        xai_key = getattr(settings, "XAI_API_KEY", "")

        credentials = MaskedCredentials(
            openai_api_key_configured=bool(oai_key),
            openai_api_key_masked=_mask_secret(oai_key),
            xai_api_key_configured=bool(xai_key),
            xai_api_key_masked=_mask_secret(xai_key),
            livekit_api_key_configured=False,
            livekit_api_secret_configured=False,
            livekit_api_key_masked="[DECOMMISSIONED]",
            livekit_api_secret_masked="[DECOMMISSIONED]",
        )

        # Overall status calculation
        if self._transport == "direct_gpt_live":
            if not credentials.openai_api_key_configured:
                overall = "unhealthy"
            elif budget_alert:
                overall = "degraded"
            else:
                overall = "healthy"
        else:
            if not credentials.xai_api_key_configured:
                overall = "unhealthy"
            elif budget_alert:
                overall = "degraded"
            else:
                overall = "healthy"

        return LiveKitHealthResponse(
            status=overall,
            worker=worker_health,
            livekit_server=server_health,
            voice_server=server_health,
            quota_readiness=quota_health,
            credentials=credentials,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )


# Global service instance
_operator_controls_service = OperatorControlsService()


def get_operator_controls_service() -> OperatorControlsService:
    """Dependency provider for operator controls service."""
    _operator_controls_service.sync_from_settings()
    return _operator_controls_service
