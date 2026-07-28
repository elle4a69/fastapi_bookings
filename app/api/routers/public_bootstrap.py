"""Public bootstrap endpoint."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from ..deps import get_public_tenant, get_db
from ...models.tenant import Tenant
from ...models.location import Location
from ...models.provider import Provider
from ...models.service import Service


class PublicBootstrapData(BaseModel):
    company: str
    tenant: Dict[str, Any]
    services: List[Dict[str, Any]]
    providers: List[Dict[str, Any]]
    locations: List[Dict[str, Any]]
    categories: List[Dict[str, Any]]
    bookingRules: Dict[str, Any]
    timezone: Optional[str] = None


class PublicBootstrapResponse(BaseModel):
    ok: bool
    data: PublicBootstrapData


router = APIRouter()


def _row_to_dict(row: object) -> dict[str, Any]:
    """Serialize a SQLAlchemy model using mapped column values only."""
    mapper = sa_inspect(row).mapper
    return {column.key: getattr(row, column.key) for column in mapper.column_attrs}


@router.get("/public/bootstrap", response_model=PublicBootstrapResponse, tags=["public"])
def public_bootstrap(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> Dict[str, Any]:
    """Return data required to bootstrap the public booking interface."""
    services = (
        db.query(Service)
        .filter(Service.tenant_id == tenant.id, Service.active.is_(True))
        .all()
    )
    providers = (
        db.query(Provider)
        .filter(Provider.tenant_id == tenant.id, Provider.active.is_(True))
        .all()
    )
    locations = db.query(Location).filter(Location.tenant_id == tenant.id).all()
    timezone = locations[0].timezone if locations else None

    return {
        "ok": True,
        "data": {
            "company": tenant.subdomain,
            "tenant": {
                "id": tenant.id,
                "name": tenant.name,
                "subdomain": tenant.subdomain,
                "timezone": tenant.timezone or "UTC",
            },
            "services": [_row_to_dict(row) for row in services],
            "providers": [_row_to_dict(row) for row in providers],
            "locations": [_row_to_dict(row) for row in locations],
            "categories": [],
            "bookingRules": {"allowSameDayBooking": True, "maxAdvanceDays": 60},
            "timezone": timezone,
        },
    }
