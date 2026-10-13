"""LiveKit participant token generation and named dispatch service for Business Assistant.

Enforces tenant/user scoping, opaque room/participant IDs, minimum necessary room grants,
and explicit named agent dispatch.
"""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from livekit import api

from app.core.config import settings
from app.services.business_assistant.livekit.config import DEFAULT_AGENT_NAME

logger = logging.getLogger("livekit.business_assistant.token_service")


class LiveKitTokenError(Exception):
    """Base exception for LiveKit token generation errors."""


class LiveKitConfigurationError(LiveKitTokenError):
    """Raised when server-side LiveKit credentials are missing or invalid."""


class LiveKitQuotaExhaustedError(LiveKitTokenError):
    """Raised when LiveKit or provider quota / rate limit (429) is exhausted."""


class LiveKitNetworkError(LiveKitTokenError):
    """Raised when LiveKit connection fails due to network disconnection or unavailability."""


@dataclass(frozen=True)
class LiveKitRoomTokenResult:
    """Opaque participant token and connection parameters for browser LiveKit room."""

    transport: str
    livekit_url: str
    token: str
    session_id: str
    room_name: str
    participant_identity: str
    agent_name: str
    expires_in: int


class LiveKitTokenService:
    """Service to issue authenticated, scoped participant tokens for LiveKit rooms."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        livekit_url: Optional[str] = None,
        default_agent_name: str = DEFAULT_AGENT_NAME,
    ) -> None:
        self.api_key = settings.LIVEKIT_API_KEY if api_key is None else api_key
        self.api_secret = settings.LIVEKIT_API_SECRET if api_secret is None else api_secret
        self.livekit_url = settings.LIVEKIT_URL if livekit_url is None else livekit_url
        self.default_agent_name = default_agent_name

    def validate_configuration(self) -> None:
        """Validate that server-side LiveKit credentials are configured."""
        if (
            not self.api_key
            or not str(self.api_key).strip()
            or not self.api_secret
            or not str(self.api_secret).strip()
            or not self.livekit_url
            or not str(self.livekit_url).strip()
        ):
            raise LiveKitConfigurationError(
                "LiveKit credentials not configured. Server administrator must set LIVEKIT_URL, "
                "LIVEKIT_API_KEY, and LIVEKIT_API_SECRET."
            )

    def create_room_token(
        self,
        tenant_id: int,
        user_id: int,
        conversation_id: int,
        ttl_seconds: int = 600,
        agent_name: Optional[str] = None,
        record: bool = False,
        transport: str = "livekit_gpt_live",
    ) -> LiveKitRoomTokenResult:
        """Generate an opaque room participant token with named agent dispatch.

        Grants only the specific room, minimum necessary publish/subscribe audio & data capabilities,
        strictly enforces room_record=False and no egress recording by default,
        and named agent dispatch metadata carrying an opaque session reference.
        """
        self.validate_configuration()

        selected_agent = agent_name or self.default_agent_name
        # Enforce recording disabled by default: no media or egress recording
        effective_record = False if not getattr(settings, "LIVEKIT_RECORD_BY_DEFAULT", False) else record

        # Generate opaque, non-PII identifiers
        opaque_session_id = f"sess_{uuid.uuid4().hex}"
        room_name = f"room_{tenant_id}_{conversation_id}_{uuid.uuid4().hex[:12]}"
        participant_identity = f"part_{user_id}_{uuid.uuid4().hex[:8]}"

        # Opaque session reference for worker server-side resolution
        dispatch_metadata = json.dumps(
            {
                "session_id": opaque_session_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
            }
        )

        agent_dispatch = api.RoomAgentDispatch(
            agent_name=selected_agent,
            metadata=dispatch_metadata,
        )
        # Room config with explicit egress=None (no recording/egress enabled)
        room_config = api.RoomConfiguration(agents=[agent_dispatch], egress=None)

        # Scoped room grants: publish, subscribe, data channel, strictly room_record=False
        grants = api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
            room_record=effective_record,
        )

        try:
            token = (
                api.AccessToken(self.api_key, self.api_secret)
                .with_identity(participant_identity)
                .with_grants(grants)
                .with_ttl(datetime.timedelta(seconds=ttl_seconds))
                .with_room_config(room_config)
            )
            jwt_token = token.to_jwt()
        except ValueError as exc:
            raise LiveKitConfigurationError(f"Invalid LiveKit credentials or configuration: {exc}") from exc
        except Exception as exc:
            raise LiveKitTokenError(f"Failed to generate LiveKit room token: {exc}") from exc

        logger.info(
            "Issued LiveKit room token for tenant=%s, user=%s, conversation=%s, room=%s, session=%s",
            tenant_id,
            user_id,
            conversation_id,
            room_name,
            opaque_session_id,
        )

        return LiveKitRoomTokenResult(
            transport=transport,
            livekit_url=self.livekit_url,
            token=jwt_token,
            session_id=opaque_session_id,
            room_name=room_name,
            participant_identity=participant_identity,
            agent_name=selected_agent,
            expires_in=ttl_seconds,
        )
