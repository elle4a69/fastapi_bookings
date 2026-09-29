"""Compatibility Facade for Channel-Neutral & Legacy Messaging.

Provides a unified interface across new channel-neutral models (Conversation,
Message, ChannelAccount) and legacy single-channel storage (SmsConversation,
SmsMessage, SmsAccount) ensuring non-destructive backward compatibility.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from ...models.conversation import (
    ChannelAccount,
    ChannelType,
    Conversation,
    DeliveryStatus,
    Message,
    MessageDirection,
    MessageSource,
)
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...schemas.conversation import (
    ConversationDetailOut,
    ConversationOut,
    MessageCreate,
    MessageOut,
)
from .channel_service import ChannelService

logger = logging.getLogger(__name__)


class ChannelCompatibilityFacade:
    """Facade exposing legacy and neutral messaging models through a unified contract."""

    # -------------------------------------------------------------------------
    # Converters / Adapters
    # -------------------------------------------------------------------------

    @staticmethod
    def adapt_sms_conversation(sms_conv: SmsConversation) -> ConversationOut:
        """Project a legacy SmsConversation into the channel-neutral ConversationOut schema."""
        client_name = None
        if getattr(sms_conv, "client", None) and hasattr(sms_conv.client, "name"):
            client_name = sms_conv.client.name

        metadata = {
            "is_legacy_sms": True,
            "source": sms_conv.source,
            "chatwoot_inbox_id": sms_conv.chatwoot_inbox_id,
            "chatwoot_contact_id": sms_conv.chatwoot_contact_id,
            "unread_count": sms_conv.unread_count,
            "is_pinned": sms_conv.is_pinned,
            "is_blocked": sms_conv.is_blocked,
            "ai_enabled": sms_conv.ai_enabled,
            "last_activity_at": sms_conv.last_activity_at.isoformat() if sms_conv.last_activity_at else None,
        }

        ext_conv_id = (
            str(sms_conv.chatwoot_conversation_id)
            if sms_conv.chatwoot_conversation_id is not None
            else None
        )

        return ConversationOut(
            id=sms_conv.id,
            tenant_id=sms_conv.tenant_id,
            provider_id=sms_conv.provider_id,
            channel_account_id=sms_conv.sms_account_id,
            channel_type=ChannelType.SMS,
            external_conversation_id=ext_conv_id,
            contact_identifier=sms_conv.customer_address,
            contact_name=client_name,
            status=sms_conv.state or "active",
            metadata_payload=metadata,
            created_at=sms_conv.created_at,
            updated_at=sms_conv.updated_at,
            messages=None,
        )

    @staticmethod
    def adapt_sms_message(sms_msg: SmsMessage) -> MessageOut:
        """Project a legacy SmsMessage into the channel-neutral MessageOut schema."""
        # Direction mapping
        if (sms_msg.direction or "").lower() == "inbound":
            direction = MessageDirection.INBOUND
        else:
            direction = MessageDirection.OUTBOUND

        # Source mapping
        author = (sms_msg.author_type or "").lower()
        if author == "customer":
            source = MessageSource.CLIENT
        elif author in ("ai", "fixed_autoresponder"):
            source = MessageSource.ASSISTANT
        elif author == "chatwoot":
            source = MessageSource.CHATWOOT
        elif author == "simulated":
            source = MessageSource.SIMULATED
        else:
            source = MessageSource.OPERATOR

        # Delivery status mapping
        status_raw = (sms_msg.status or "").lower()
        if status_raw == "delivered":
            delivery_status = DeliveryStatus.DELIVERED
        elif status_raw in ("sent", "sending"):
            delivery_status = DeliveryStatus.SENT
        elif status_raw in ("failed", "cancelled", "discarded"):
            delivery_status = DeliveryStatus.FAILED
        elif status_raw == "read":
            delivery_status = DeliveryStatus.READ
        else:
            delivery_status = DeliveryStatus.PENDING

        ext_id = (
            str(sms_msg.chatwoot_message_id)
            if sms_msg.chatwoot_message_id is not None
            else str(sms_msg.provider_message_id)
            if sms_msg.provider_message_id is not None
            else None
        )

        metadata = {
            "is_legacy_sms": True,
            "author_type": sms_msg.author_type,
            "normalized_body": sms_msg.normalized_body,
            "client_request_id": sms_msg.client_request_id,
            "customer_turn_ref": sms_msg.customer_turn_ref,
            "ai_metadata": sms_msg.ai_metadata,
        }

        return MessageOut(
            id=sms_msg.id,
            conversation_id=sms_msg.conversation_id,
            tenant_id=sms_msg.tenant_id,
            provider_id=sms_msg.provider_id,
            direction=direction,
            source=source,
            content=sms_msg.body,
            external_message_id=ext_id,
            delivery_status=delivery_status,
            tool_calls=None,
            metadata_payload=metadata,
            created_at=sms_msg.occurred_at or datetime.now(timezone.utc),
            updated_at=sms_msg.received_at or datetime.now(timezone.utc),
        )

    # -------------------------------------------------------------------------
    # Retrieval Operations
    # -------------------------------------------------------------------------

    @staticmethod
    def get_conversation(
        db: Session,
        conversation_id: int,
        tenant_id: Optional[int] = None,
        include_legacy: bool = True,
    ) -> Optional[ConversationOut]:
        """Fetch conversation by ID, checking neutral first, then legacy SmsConversation."""
        # 1. Neutral table lookup
        neutral = ChannelService.get_conversation(db, conversation_id=conversation_id, tenant_id=tenant_id)
        if neutral:
            return ConversationOut.model_validate(neutral)

        # 2. Legacy lookup fallback
        if include_legacy:
            query = db.query(SmsConversation).filter(SmsConversation.id == conversation_id)
            if tenant_id is not None:
                query = query.filter(SmsConversation.tenant_id == tenant_id)
            sms_conv = query.options(joinedload(SmsConversation.client)).first()
            if sms_conv:
                return ChannelCompatibilityFacade.adapt_sms_conversation(sms_conv)

        return None

    @staticmethod
    def get_conversation_detail(
        db: Session,
        conversation_id: int,
        tenant_id: Optional[int] = None,
        include_legacy: bool = True,
    ) -> Optional[ConversationDetailOut]:
        """Fetch detailed conversation including message history from either store."""
        # 1. Neutral table lookup
        neutral = ChannelService.get_conversation(
            db, conversation_id=conversation_id, tenant_id=tenant_id, load_messages=True
        )
        if neutral:
            base_out = ConversationOut.model_validate(neutral)
            messages_out = [MessageOut.model_validate(m) for m in (neutral.messages or [])]
            return ConversationDetailOut(
                **base_out.model_dump(exclude={"messages"}),
                messages=messages_out,
            )

        # 2. Legacy lookup fallback
        if include_legacy:
            query = db.query(SmsConversation).filter(SmsConversation.id == conversation_id)
            if tenant_id is not None:
                query = query.filter(SmsConversation.tenant_id == tenant_id)
            sms_conv = query.options(
                joinedload(SmsConversation.client),
                joinedload(SmsConversation.messages),
            ).first()
            if sms_conv:
                base_out = ChannelCompatibilityFacade.adapt_sms_conversation(sms_conv)
                raw_messages = sorted(
                    sms_conv.messages or [],
                    key=lambda m: m.occurred_at or datetime.min.replace(tzinfo=timezone.utc),
                )
                messages_out = [ChannelCompatibilityFacade.adapt_sms_message(m) for m in raw_messages]
                return ConversationDetailOut(
                    **base_out.model_dump(exclude={"messages"}),
                    messages=messages_out,
                )

        return None

    @staticmethod
    def list_conversations(
        db: Session,
        tenant_id: int,
        provider_id: Optional[int] = None,
        channel_type: Optional[ChannelType] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_legacy: bool = True,
    ) -> Tuple[List[ConversationOut], int]:
        """List conversations across neutral and legacy tables with pagination."""
        neutral_items, _ = ChannelService.list_conversations(
            db,
            tenant_id=tenant_id,
            provider_id=provider_id,
            channel_type=channel_type,
            status=status,
            limit=limit + offset,  # Fetch enough for local merge
            offset=0,
        )
        all_convs: List[ConversationOut] = [ConversationOut.model_validate(c) for c in neutral_items]

        # Include legacy if channel_type is None or SMS
        if include_legacy and (channel_type is None or channel_type == ChannelType.SMS):
            sms_query = db.query(SmsConversation).filter(SmsConversation.tenant_id == tenant_id)
            if provider_id is not None:
                sms_query = sms_query.filter(SmsConversation.provider_id == provider_id)
            if status is not None:
                sms_query = sms_query.filter(SmsConversation.state == status)

            legacy_items = (
                sms_query.options(joinedload(SmsConversation.client))
                .order_by(desc(SmsConversation.updated_at))
                .limit(limit + offset)
                .all()
            )

            # Deduplicate by (tenant_id, contact_identifier) if necessary
            seen_contacts = {c.contact_identifier for c in all_convs}
            for legacy in legacy_items:
                if legacy.customer_address not in seen_contacts:
                    all_convs.append(ChannelCompatibilityFacade.adapt_sms_conversation(legacy))
                    seen_contacts.add(legacy.customer_address)

        # Sort combined items by updated_at descending
        all_convs.sort(key=lambda x: x.updated_at, reverse=True)
        total = len(all_convs)
        paginated = all_convs[offset : offset + limit]
        return paginated, total

    # -------------------------------------------------------------------------
    # Message Dispatch / Creation
    # -------------------------------------------------------------------------

    @staticmethod
    def record_outbound_message(
        db: Session,
        conversation_id: int,
        tenant_id: int,
        data: MessageCreate,
        provider_id: Optional[int] = None,
        include_legacy: bool = True,
    ) -> MessageOut:
        """Record an outbound/simulated message, dispatching to neutral or legacy storage."""
        # Check neutral first
        neutral = ChannelService.get_conversation(db, conversation_id=conversation_id, tenant_id=tenant_id)
        if neutral:
            msg = ChannelService.create_message(
                db,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                data=data,
                provider_id=provider_id or neutral.provider_id,
            )
            return MessageOut.model_validate(msg)

        # Fallback to legacy
        if include_legacy:
            sms_conv = (
                db.query(SmsConversation)
                .filter(SmsConversation.id == conversation_id, SmsConversation.tenant_id == tenant_id)
                .first()
            )
            if sms_conv:
                author_type = "staff"
                if data.source == MessageSource.ASSISTANT:
                    author_type = "ai"
                elif data.source == MessageSource.SIMULATED:
                    author_type = "simulated"
                elif data.source == MessageSource.CHATWOOT:
                    author_type = "chatwoot"

                sms_msg = SmsMessage(
                    tenant_id=tenant_id,
                    provider_id=provider_id or sms_conv.provider_id,
                    sms_account_id=sms_conv.sms_account_id,
                    conversation_id=conversation_id,
                    body=data.content,
                    direction="outbound" if data.direction == MessageDirection.OUTBOUND else "inbound",
                    author_type=author_type,
                    status="sent" if data.delivery_status == DeliveryStatus.SENT else data.delivery_status.value,
                    provider_message_id=data.external_message_id,
                    ai_metadata=data.metadata_payload,
                    occurred_at=datetime.now(timezone.utc),
                    received_at=datetime.now(timezone.utc),
                )
                db.add(sms_msg)
                sms_conv.last_activity_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(sms_msg)
                return ChannelCompatibilityFacade.adapt_sms_message(sms_msg)

        raise ValueError(f"Conversation {conversation_id} not found in tenant {tenant_id}")
