"""Media API Router for durable tenant-scoped media assets.

Endpoints:
- POST   /api/admin/media/upload        - Safe upload & persist media
- GET    /api/admin/media               - List tenant media with optional eligibility filtering
- GET    /api/admin/media/{id}          - Retrieve media details
- DELETE /api/admin/media/{id}          - Delete media item
- PATCH  /api/admin/media/{id}/eligibility - Update public website eligibility
- GET    /api/admin/media/{id}/file     - Download/stream media file for admin
- GET    /api/public/media/{tenant_id}/{filename} - Public media delivery for website-eligible assets
"""

import os
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.media import (
    MediaDeleteResponse,
    MediaDetailResponse,
    MediaEligibilityUpdate,
    MediaItemResponse,
    MediaItemSummary,
    MediaListResponse,
)
from ...services.media_service import MediaService, get_media_base_dir

logger = logging.getLogger(__name__)

router = APIRouter(tags=["media"])


@router.post("/api/admin/media/upload", response_model=MediaDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    provider_id: Optional[int] = Form(None),
    is_public_website_eligible: bool = Form(False),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MediaDetailResponse:
    """Upload and durably persist a tenant-scoped media file."""
    media_item = await MediaService.save_upload(
        db=db,
        tenant_id=tenant.id,
        file=file,
        title=title,
        description=description,
        notes=notes,
        provider_id=provider_id,
        is_public_website_eligible=is_public_website_eligible,
    )
    return MediaDetailResponse(
        ok=True,
        data=MediaItemResponse.model_validate(media_item),
    )


@router.get("/api/admin/media", response_model=MediaListResponse)
def list_media(
    is_public_website_eligible: Optional[bool] = Query(None, description="Filter by website eligibility"),
    provider_id: Optional[int] = Query(None, description="Filter by provider ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MediaListResponse:
    """List tenant-scoped media items with pagination and eligibility filter."""
    items, total = MediaService.list_media(
        db=db,
        tenant_id=tenant.id,
        is_public_website_eligible=is_public_website_eligible,
        provider_id=provider_id,
        limit=limit,
        offset=offset,
    )
    return MediaListResponse(
        ok=True,
        data=[MediaItemResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/api/admin/media/{id}", response_model=MediaDetailResponse)
def get_media_detail(
    id: int,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MediaDetailResponse:
    """Retrieve details for a single media item, strictly tenant isolated."""
    media_item = MediaService.get_media(db=db, tenant_id=tenant.id, media_id=id)
    if not media_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media item {id} not found.",
        )
    return MediaDetailResponse(
        ok=True,
        data=MediaItemResponse.model_validate(media_item),
    )


@router.delete("/api/admin/media/{id}", response_model=MediaDeleteResponse)
def delete_media_item(
    id: int,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MediaDeleteResponse:
    """Delete a media item within the active tenant."""
    deleted = MediaService.delete_media(db=db, tenant_id=tenant.id, media_id=id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media item {id} not found.",
        )
    return MediaDeleteResponse(
        ok=True,
        message="Media item deleted successfully.",
        id=id,
    )


@router.patch("/api/admin/media/{id}/eligibility", response_model=MediaDetailResponse)
def update_media_eligibility(
    id: int,
    payload: MediaEligibilityUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MediaDetailResponse:
    """Update public website eligibility for a tenant's media item."""
    media_item = MediaService.update_eligibility(
        db=db,
        tenant_id=tenant.id,
        media_id=id,
        is_eligible=payload.is_public_website_eligible,
    )
    if not media_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media item {id} not found.",
        )
    return MediaDetailResponse(
        ok=True,
        data=MediaItemResponse.model_validate(media_item),
    )


@router.get("/api/admin/media/{id}/file")
def get_admin_media_file(
    id: int,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Serve the media file binary to authorized tenant admin."""
    media_item = MediaService.get_media(db=db, tenant_id=tenant.id, media_id=id)
    if not media_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media item {id} not found.",
        )

    base_dir = get_media_base_dir()
    file_path = os.path.abspath(os.path.join(base_dir, media_item.file_path))
    if not os.path.exists(file_path) or not file_path.startswith(base_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media binary file not found on disk.",
        )

    return FileResponse(
        path=file_path,
        media_type=media_item.content_type,
        filename=media_item.filename,
    )


@router.get("/api/public/media/{tenant_id}/{filename}")
def get_public_media_file(
    tenant_id: int,
    filename: str,
    db: Session = Depends(get_db),
):
    """Serve media file for public display ONLY if marked is_public_website_eligible=True."""
    media_item = MediaService.get_media_by_stored_filename(
        db=db,
        tenant_id=tenant_id,
        stored_filename=filename,
    )
    if not media_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media item not found.",
        )

    if not media_item.is_public_website_eligible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Media item is not approved for public display.",
        )

    base_dir = get_media_base_dir()
    file_path = os.path.abspath(os.path.join(base_dir, media_item.file_path))
    if not os.path.exists(file_path) or not file_path.startswith(base_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media binary file not found on disk.",
        )

    return FileResponse(
        path=file_path,
        media_type=media_item.content_type,
        filename=media_item.filename,
    )
