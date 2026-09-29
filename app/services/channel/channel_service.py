"""Channel Service.

Provides core domain operations for channel-neutral messaging accounts,
conversations, and messages.
"""

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
from ...models.provider import Provider
from ...schemas.channel import ChannelAccountCreate, ChannelAccountUpdate
from ...schemas.conversation import ConversationCreate, MessageCreate

logger = logging.getLogger(__name__)


class ChannelService:
    """Core domain service for omnichannel accounts and conversations."""

    # -------------------------------------------------------------------------
    # Channel Accounts
    # -------------------------------------------------------------------------

    @staticmethod
    def create_channel_account(
        db: Session,
        tenant_id: int,
        data: ChannelAccountCreate,
    ) -> ChannelAccount:
        if data.provider_id is not None:
            provider = db.query(Provider).filter(Provider.id == data.provider_id).first()
            if not provider or provider.tenant_id != tenant_id:
                raise ValueError(f"Provider {data.provider_id} does not belong to tenant {tenant_id}")

        account = ChannelAccount(
            tenant_id=tenant_id,
            provider_id=data.provider_id,
            channel_type=data.channel_type,
            inbox_name=data.inbox_name,
            account_identifier=data.account_identifier,
            chatwoot_inbox_id=data.chatwoot_inbox_id,
            is_active=data.is_active,
        )
        if data.credentials:
            account.credentials = data.credentials

        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info(
            f"Created ChannelAccount id={account.id} channel_type={account.channel_type} for tenant={tenant_id}"
        )
        return account

    @staticmethod
    def get_channel_account(
        db: Session,
        account_id: int,
        tenant_id: Optional[int] = None,
    ) -> Optional[ChannelAccount]:
        query = db.query(ChannelAccount).filter(ChannelAccount.id == account_id)
        if tenant_id is not None:
            query = query.filter(ChannelAccount.tenant_id == tenant_id)
        return query.first()

    @staticmethod
    def list_channel_accounts(
        db: Session,
        tenant_id: int,
        provider_id: Optional[int] = None,
        channel_type: Optional[ChannelType] = None,
        active_only: bool = True,
    ) -> List[ChannelAccount]:
        query = db.query(ChannelAccount).filter(ChannelAccount.tenant_id == tenant_id)
        if provider_id is not None:
            query = query.filter(ChannelAccount.provider_id == provider_id)
        if channel_type is not None:
            query = query.filter(ChannelAccount.channel_type == channel_type)
        if active_only:
            query = query.filter(ChannelAccount.is_active.is_(True))
        return query.order_by(ChannelAccount.id.asc()).all()

    @staticmethod
    def update_channel_account(
        db: Session,
        account_id: int,
        tenant_id: int,
        data: ChannelAccountUpdate,
    ) -> Optional[ChannelAccount]:
        account = ChannelService.get_channel_account(db, account_id=account_id, tenant_id=tenant_id)
        if not account:
            return None

        if data.inbox_name is not None:
            account.inbox_name = data.inbox_name
        if data.account_identifier is not None:
            account.account_identifier = data.account_identifier
        if data.chatwoot_inbox_id is not None:
            account.chatwoot_inbox_id = data.chatwoot_inbox_id
        if data.is_active is not None:
            account.is_active = data.is_active
        if data.credentials is not None:
            account.credentials = data.credentials

        db.commit()
        db.refresh(account)
        return account

    # -------------------------------------------------------------------------
    # Conversations
    # -------------------------------------------------------------------------

    @staticmethod
    def create_conversation(
        db: Session,
        tenant_id: int,
        data: ConversationCreate,
    ) -> Conversation:
        account = None
        if data.provider_id is not None:
            provider = db.query(Provider).filter(Provider.id == data.provider_id).first()
            if not provider or provider.tenant_id != tenant_id:
                raise ValueError(f"Provider {data.provider_id} does not belong to tenant {tenant_id}")

        if data.channel_account_id is not None:
            account = db.query(ChannelAccount).filter(ChannelAccount.id == data.channel_account_id).first()
            if not account or account.tenant_id != tenant_id:
                raise ValueError(f"ChannelAccount {data.channel_account_id} does not belong to tenant {tenant_id}")

        if data.provider_id is not None and account is not None:
            if account.provider_id is not None and account.provider_id != data.provider_id:
                raise ValueError("Channel account is dedicated to a different provider")

        metadata = dict(data.metadata_payload or {})
        if data.channel_type:
            metadata["channel_type"] = (
                data.channel_type.value if hasattr(data.channel_type, "value") else str(data.channel_type)
            )

        conversation = Conversation(
            tenant_id=tenant_id,
            provider_id=data.provider_id,
            channel_account_id=data.channel_account_id,
            external_conversation_id=data.external_conversation_id,
            contact_identifier=data.contact_identifier,
            contact_name=data.contact_name,
            status=data.status or "active",
            metadata_payload=metadata,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        logger.info(f"Created Conversation id={conversation.id} for tenant={tenant_id}")
        return conversation

    @staticmethod
    def get_conversation(
        db: Session,
        conversation_id: int,
        tenant_id: Optional[int] = None,
        load_messages: bool = False,
    ) -> Optional[Conversation]:
        query = db.query(Conversation).filter(Conversation.id == conversation_id)
        if tenant_id is not None:
            query = query.filter(Conversation.tenant_id == tenant_id)
        if load_messages:
            query = query.options(joinedload(Conversation.messages), joinedload(Conversation.channel_account))
        else:
            query = query.options(joinedload(Conversation.channel_account))
        return query.first()

    @staticmethod
    def list_conversations(
        db: Session,
        tenant_id: int,
        provider_id: Optional[int] = None,
        channel_type: Optional[ChannelType] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Conversation], int]:
        query = (
            db.query(Conversation)
            .outerjoin(ChannelAccount, Conversation.channel_account_id == ChannelAccount.id)
            .filter(Conversation.tenant_id == tenant_id)
        )

        if provider_id is not None:
            query = query.filter(Conversation.provider_id == provider_id)
        if status is not None:
            query = query.filter(Conversation.status == status)
        if channel_type is not None:
            channel_val = channel_type.value if hasattr(channel_type, "value") else str(channel_type)
            query = query.filter(ChannelAccount.channel_type == channel_val)

        total = query.count()
        items = (
            query.options(joinedload(Conversation.channel_account))
            .order_by(desc(Conversation.updated_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    @staticmethod
    def get_or_create_conversation(
        db: Session,
        tenant_id: int,
        contact_identifier: str,
        channel_account_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        contact_name: Optional[str] = None,
        external_conversation_id: Optional[str] = None,
    ) -> Conversation:
        query = db.query(Conversation).filter(
            Conversation.tenant_id == tenant_id,
            Conversation.contact_identifier == contact_identifier,
        )
        if channel_account_id is not None:
            query = query.filter(Conversation.channel_account_id == channel_account_id)
        if provider_id is not None:
            query = query.filter(Conversation.provider_id == provider_id)

        conv = query.order_by(desc(Conversation.id)).first()
        if conv:
            if contact_name and not conv.contact_name:
                conv.contact_name = contact_name
            if external_conversation_id and not conv.external_conversation_id:
                conv.external_conversation_id = external_conversation_id
            db.commit()
            db.refresh(conv)
            return conv

        create_data = ConversationCreate(
            provider_id=provider_id,
            channel_account_id=channel_account_id,
            external_conversation_id=external_conversation_id,
            contact_identifier=contact_identifier,
            contact_name=contact_name,
            status="active",
        )
        return ChannelService.create_conversation(db, tenant_id=tenant_id, data=create_data)

    @staticmethod
    def find_by_external_conversation_id(
        db: Session,
        tenant_id: int,
        external_conversation_id: str,
    ) -> Optional[Conversation]:
        return (
            db.query(Conversation)
            .filter(
                Conversation.tenant_id == tenant_id,
                Conversation.external_conversation_id == str(external_conversation_id),
            )
            .first()
        )

    # -------------------------------------------------------------------------
    # Messages
    # -------------------------------------------------------------------------

    @staticmethod
    def create_message(
        db: Session,
        tenant_id: int,
        conversation_id: int,
        data: MessageCreate,
        provider_id: Optional[int] = None,
    ) -> Message:
        conversation = ChannelService.get_conversation(db, conversation_id=conversation_id, tenant_id=tenant_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found in tenant {tenant_id}")

        msg = Message(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            provider_id=provider_id or conversation.provider_id,
            direction=data.direction,
            source=data.source,
            content=data.content,
            external_message_id=data.external_message_id,
            delivery_status=data.delivery_status,
            tool_calls=data.tool_calls,
            metadata_payload=data.metadata_payload or {},
        )
        db.add(msg)
        # Touch conversation updated_at
        from datetime import datetime, timezone
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(msg)
        logger.info(f"Created Message id={msg.id} in conversation={conversation_id}")
        return msg

    @staticmethod
    def get_messages(
        db: Session,
        conversation_id: int,
        tenant_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        query = db.query(Message).filter(Message.conversation_id == conversation_id)
        if tenant_id is not None:
            query = query.filter(Message.tenant_id == tenant_id)
        return query.order_by(Message.created_at.asc()).offset(offset).limit(limit).all()

    @staticmethod
    def update_delivery_status(
        db: Session,
        message_id: int,
        status: DeliveryStatus,
        external_message_id: Optional[str] = None,
        tenant_id: Optional[int] = None,
    ) -> Optional[Message]:
        query = db.query(Message).filter(Message.id == message_id)
        if tenant_id is not None:
            query = query.filter(Message.tenant_id == tenant_id)
        msg = query.first()
        if not msg:
            return None

        msg.delivery_status = status
        if external_message_id:
            msg.external_message_id = external_message_id
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def find_by_external_message_id(
        db: Session,
        tenant_id: int,
        external_message_id: str,
    ) -> Optional[Message]:
        return (
            db.query(Message)
            .filter(
                Message.tenant_id == tenant_id,
                Message.external_message_id == str(external_message_id),
            )
            .first()
        )
