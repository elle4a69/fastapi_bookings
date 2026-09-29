"""Channel-Neutral Conversations API Router.

Exposes administrative endpoints for listing, viewing, creating, and dispatching
messages across channel-neutral and legacy communication streams.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..deps import DatabaseId, get_current_admin, get_current_tenant, get_db
from ...models.conversation import ChannelType
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.conversation import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    MessageCreate,
    MessageOut,
)
from ...services.channel.channel_service import ChannelService
from ...services.channel.compatibility_facade import ChannelCompatibilityFacade

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=List[ConversationOut])
def list_conversations(
    provider_id: Optional[int] = Query(None, description="Filter by provider ID"),
    channel: Optional[ChannelType] = Query(None, description="Filter by channel type"),
    status: Optional[str] = Query(None, description="Filter by conversation status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_legacy: bool = Query(True, description="Include legacy SMS conversations"),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> List[ConversationOut]:
    """List conversations filtered by tenant, provider, channel, and status."""
    items, _ = ChannelCompatibilityFacade.list_conversations(
        db=db,
        tenant_id=tenant.id,
        provider_id=provider_id,
        channel_type=channel,
        status=status,
        limit=limit,
        offset=offset,
        include_legacy=include_legacy,
    )
    return items


@router.get("/{id}", response_model=ConversationDetailOut)
def get_conversation(
    id: DatabaseId,
    include_legacy: bool = Query(True, description="Include legacy SMS conversations"),
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ConversationDetailOut:
    """Retrieve detailed conversation with message history."""
    conv = ChannelCompatibilityFacade.get_conversation_detail(
        db=db,
        conversation_id=id,
        tenant_id=tenant.id,
        include_legacy=include_legacy,
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {id} not found",
        )
    return conv


@router.post("/{id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_or_record_message(
    id: DatabaseId,
    payload: MessageCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MessageOut:
    """Send or record an outbound or simulated message on a conversation."""
    try:
        msg = ChannelCompatibilityFacade.record_outbound_message(
            db=db,
            conversation_id=id,
            tenant_id=tenant.id,
            data=payload,
            provider_id=None,
            include_legacy=True,
        )
        return msg
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ConversationOut:
    """Create a new channel-neutral conversation."""
    try:
        conv = ChannelService.create_conversation(
            db=db,
            tenant_id=tenant.id,
            data=payload,
        )
        return ConversationOut.model_validate(conv)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
