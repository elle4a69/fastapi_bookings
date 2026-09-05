"""Tenant-admin configuration for the authenticated Chatwoot boundary."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import DatabaseId, get_current_admin, get_current_tenant, get_db
from ...models.provider import Provider
from ...models.sms_chatwoot import ChatwootConnection, SmsChatwootBinding
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.sms_chatwoot import (
    ChatwootConnectionCreate,
    ChatwootConnectionResponse,
    ChatwootConnectionUpdate,
    ChatwootInboxBindingCreate,
    ChatwootInboxBindingResponse,
    ChatwootInboxBindingUpdate,
    ChatwootSigningSecretRotate,
)
from ...services.messaging.chatwoot_security import (
    SigningSecretUnavailable,
    encrypt_signing_secret,
)


router = APIRouter(
    prefix="/messaging/chatwoot", tags=["admin-messaging-chatwoot"]
)


def _connection(
    db: Session, tenant_id: int, connection_id: int
) -> ChatwootConnection:
    result = (
        db.query(ChatwootConnection)
        .filter(
            ChatwootConnection.id == connection_id,
            ChatwootConnection.tenant_id == tenant_id,
        )
        .first()
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Chatwoot connection not found.")
    return result


def _binding(
    db: Session, tenant_id: int, binding_id: int
) -> SmsChatwootBinding:
    result = (
        db.query(SmsChatwootBinding)
        .filter(
            SmsChatwootBinding.id == binding_id,
            SmsChatwootBinding.tenant_id == tenant_id,
            SmsChatwootBinding.connection_id.is_not(None),
        )
        .first()
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Chatwoot inbox binding not found.")
    return result


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chatwoot configuration conflicts with an existing record.",
        ) from exc


@router.post(
    "/connections",
    response_model=ChatwootConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    payload: ChatwootConnectionCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    connection = ChatwootConnection(
        tenant_id=tenant.id,
        instance_origin=payload.instance_origin,
        chatwoot_account_id=payload.chatwoot_account_id,
        enabled=False,
    )
    db.add(connection)
    _commit_or_conflict(db)
    db.refresh(connection)
    return connection


@router.get("/connections", response_model=list[ChatwootConnectionResponse])
def list_connections(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(ChatwootConnection)
        .filter(ChatwootConnection.tenant_id == tenant.id)
        .order_by(ChatwootConnection.id)
        .all()
    )


@router.get(
    "/connections/{connection_id}", response_model=ChatwootConnectionResponse
)
def get_connection(
    connection_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return _connection(db, tenant.id, connection_id)


@router.patch(
    "/connections/{connection_id}", response_model=ChatwootConnectionResponse
)
def update_connection(
    connection_id: DatabaseId,
    payload: ChatwootConnectionUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    connection = _connection(db, tenant.id, connection_id)
    if payload.enabled is not None:
        if payload.enabled and not connection.has_signing_secret:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A signing secret is required before enabling the connection.",
            )
        connection.enabled = payload.enabled
        connection.updated_at = datetime.now(timezone.utc)
    _commit_or_conflict(db)
    db.refresh(connection)
    return connection


@router.put(
    "/connections/{connection_id}/signing-secret",
    response_model=ChatwootConnectionResponse,
)
def set_signing_secret(
    connection_id: DatabaseId,
    payload: ChatwootSigningSecretRotate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    connection = _connection(db, tenant.id, connection_id)
    if connection.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disable the connection before changing its signing secret.",
        )
    try:
        ciphertext = encrypt_signing_secret(payload.signing_secret.get_secret_value())
    except SigningSecretUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signing secret storage is unavailable.",
        ) from exc
    connection._signing_secret_ciphertext = ciphertext
    connection.updated_at = datetime.now(timezone.utc)
    _commit_or_conflict(db)
    db.refresh(connection)
    return connection


@router.post(
    "/inbox-bindings",
    response_model=ChatwootInboxBindingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inbox_binding(
    payload: ChatwootInboxBindingCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    connection = _connection(db, tenant.id, payload.connection_id)
    provider = (
        db.query(Provider)
        .filter(
            Provider.id == payload.provider_id,
            Provider.tenant_id == tenant.id,
        )
        .first()
    )
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        connection_id=connection.id,
        chatwoot_account_id=None,
        chatwoot_inbox_id=payload.chatwoot_inbox_id,
        chatwoot_base_url=None,
        _chatwoot_api_token=None,
        _webhook_secret=None,
        is_enabled=False,
        channel=payload.channel,
        ingress_enabled=False,
        channel_metadata=None,
    )
    db.add(binding)
    _commit_or_conflict(db)
    db.refresh(binding)
    return binding

@router.get(
    "/inbox-bindings", response_model=list[ChatwootInboxBindingResponse]
)
def list_inbox_bindings(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(SmsChatwootBinding)
        .filter(
            SmsChatwootBinding.tenant_id == tenant.id,
            SmsChatwootBinding.connection_id.is_not(None),
        )
        .order_by(SmsChatwootBinding.id)
        .all()
    )


@router.patch(
    "/inbox-bindings/{binding_id}",
    response_model=ChatwootInboxBindingResponse,
)
def update_inbox_binding(
    binding_id: DatabaseId,
    payload: ChatwootInboxBindingUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    binding = _binding(db, tenant.id, binding_id)
    if payload.ingress_enabled is not None:
        if payload.ingress_enabled:
            connection = _connection(db, tenant.id, binding.connection_id)
            if (
                binding.channel != "web_widget"
                or not connection.enabled
                or not connection.has_signing_secret
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The connection must be enabled before enabling ingress.",
                )
        binding.ingress_enabled = payload.ingress_enabled
        binding.updated_at = datetime.now(timezone.utc)
    _commit_or_conflict(db)
    db.refresh(binding)
    return binding
