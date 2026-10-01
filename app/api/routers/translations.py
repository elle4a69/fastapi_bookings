"""Tenant Translations and Dynamic Wording API router.

Exposes public and admin endpoints for customizable industry terminology,
locale resolution, and pre-packaged industry presets.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_public_tenant, get_current_tenant, get_current_admin
from ...models.tenant import Tenant
from ...models.tenant_translation import TenantTranslation
from ...models.user import User
from ...schemas.translation import (
    AdminTranslationsResponse,
    IndustryPresetInfo,
    PublicTranslationsResponse,
    TenantTranslationOut,
    TenantTranslationUpdate,
)
from ...services.localization.presets import (
    DEFAULT_TERMINOLOGY,
    INDUSTRY_PRESETS,
    get_preset,
    resolve_terminology,
)

router = APIRouter(tags=["translations"])


def _get_or_create_tenant_translation(tenant_id: int, db: Session) -> TenantTranslation:
    """Retrieve the existing TenantTranslation record or create a default one."""
    record = (
        db.query(TenantTranslation)
        .filter(TenantTranslation.tenant_id == tenant_id)
        .first()
    )
    if not record:
        record = TenantTranslation(
            tenant_id=tenant_id,
            locale="en",
            terminology=dict(DEFAULT_TERMINOLOGY),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


@router.get(
    "/api/public/translations",
    response_model=PublicTranslationsResponse,
    summary="Get tenant terminology and locale for public booking portals",
)
def get_public_translations(
    tenant: Tenant = Depends(get_public_tenant),
    db: Session = Depends(get_db),
) -> PublicTranslationsResponse:
    """Retrieve active terminology and locale for public booking workflows.

    Tenant is resolved via host subdomain or X-Tenant header.
    Returns fully resolved terminology with fallbacks applied.
    """
    record = (
        db.query(TenantTranslation)
        .filter(TenantTranslation.tenant_id == tenant.id)
        .first()
    )
    if not record:
        resolved = dict(DEFAULT_TERMINOLOGY)
        locale = "en"
    else:
        resolved = resolve_terminology(custom_terminology=record.terminology)
        locale = record.locale or "en"

    return PublicTranslationsResponse(
        locale=locale,
        terminology=resolved,
    )


@router.get(
    "/api/admin/translations",
    response_model=AdminTranslationsResponse,
    summary="Get tenant translations, resolved terms, and available presets",
)
def get_admin_translations(
    tenant: Tenant = Depends(get_current_tenant),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminTranslationsResponse:
    """Retrieve tenant translation settings, active terminology, and available presets."""
    record = _get_or_create_tenant_translation(tenant.id, db)
    resolved = resolve_terminology(custom_terminology=record.terminology)

    preset_list = [
        IndustryPresetInfo(
            id=p["id"],
            name=p["name"],
            description=p["description"],
            terminology=p["terminology"],
        )
        for p in INDUSTRY_PRESETS.values()
    ]

    return AdminTranslationsResponse(
        translation=TenantTranslationOut.model_validate(record),
        presets=preset_list,
        resolved_terminology=resolved,
        locale=record.locale or "en",
        terminology=record.terminology or {},
    )


@router.put(
    "/api/admin/translations",
    response_model=TenantTranslationOut,
    summary="Update tenant translations or apply an industry preset",
)
def update_admin_translations(
    payload: TenantTranslationUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TenantTranslationOut:
    """Update tenant dynamic wording dictionary or apply an industry preset.

    Enforces strict tenant isolation: changes only apply to the active tenant.
    """
    record = (
        db.query(TenantTranslation)
        .filter(TenantTranslation.tenant_id == tenant.id)
        .first()
    )
    if not record:
        record = TenantTranslation(
            tenant_id=tenant.id,
            locale=payload.locale or "en",
            terminology={},
        )
        db.add(record)

    current_terms = dict(record.terminology or {})

    # 1. If preset requested, validate and load preset terms
    if payload.preset:
        preset_terms = get_preset(payload.preset)
        if preset_terms is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown industry preset '{payload.preset}'. Available: {list(INDUSTRY_PRESETS.keys())}",
            )
        # Apply preset terms
        current_terms = dict(preset_terms)
        current_terms["_preset"] = payload.preset

        # Trigger Chatwoot industry automation if tenant has a Chatwoot account bound
        if tenant.chatwoot_account_id:
            try:
                from ...services.sms.chatwoot_industry_service import sync_industry_presets
                sync_industry_presets(
                    account_id=tenant.chatwoot_account_id,
                    industry=payload.preset,
                )
            except Exception:
                pass

    # 2. If custom terminology overrides provided, merge them
    if payload.terminology is not None:
        for k, v in payload.terminology.items():
            if v is not None and isinstance(v, str) and v.strip():
                current_terms[k.strip()] = v.strip()

    # 3. Update locale if provided
    if payload.locale:
        record.locale = payload.locale.strip()

    record.terminology = current_terms

    db.commit()
    db.refresh(record)

    return TenantTranslationOut.model_validate(record)
