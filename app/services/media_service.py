"""Durable Media storage and management service with tenant isolation.

Enforces:
- Tenant-scoped storage path isolation
- Strict MIME and file size validation
- Prevention of directory traversal
- Exclusion of clinical, booking notes, and private customer records from assistant context
- Public website eligibility filtering
"""

import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.media import Media

logger = logging.getLogger(__name__)

# Allowed MIME types for media upload
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/svg+xml",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "application/pdf",
}

# Forbidden file extensions (executables, scripts, etc.)
FORBIDDEN_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".bash", ".ps1", ".py", ".php",
    ".js", ".ts", ".html", ".htm", ".vbs", ".jar", ".dll", ".so"
}

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB default


def get_media_base_dir() -> str:
    """Return the absolute path to the base upload directory."""
    configured_dir = getattr(settings, "MEDIA_UPLOAD_DIR", "uploads/media")
    if not os.path.isabs(configured_dir):
        base = os.path.abspath(configured_dir)
    else:
        base = configured_dir
    os.makedirs(base, exist_ok=True)
    return base


def get_tenant_media_dir(tenant_id: int) -> str:
    """Return the isolated storage directory for a specific tenant."""
    base_dir = get_media_base_dir()
    tenant_dir = os.path.abspath(os.path.join(base_dir, f"tenant_{tenant_id}"))
    # Verify the resolved path stays within the base directory (no directory traversal)
    if not tenant_dir.startswith(base_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant storage directory path.",
        )
    os.makedirs(tenant_dir, exist_ok=True)
    return tenant_dir


def sanitize_filename(filename: str) -> str:
    """Sanitize original filename to remove path separators and unsafe characters."""
    clean = os.path.basename(filename).strip()
    clean = re.sub(r"[^\w\.-]", "_", clean)
    clean = re.sub(r"_+", "_", clean)
    if not clean or clean.startswith("."):
        clean = f"media_{clean}"
    return clean[:128]


class MediaService:
    """Encapsulates business operations for durable tenant-scoped media assets."""

    @staticmethod
    def classify_media_type(content_type: str) -> str:
        """Map MIME type to high-level category: image, video, or document."""
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("video/"):
            return "video"
        return "document"

    @classmethod
    async def save_upload(
        cls,
        db: Session,
        tenant_id: int,
        file: UploadFile,
        title: Optional[str] = None,
        description: Optional[str] = None,
        notes: Optional[str] = None,
        provider_id: Optional[int] = None,
        is_public_website_eligible: bool = False,
    ) -> Media:
        """Validate, store binary file on disk in tenant directory, and record in DB."""
        original_filename = file.filename or "uploaded_media"
        clean_name = sanitize_filename(original_filename)
        _, ext = os.path.splitext(clean_name.lower())

        if ext in FORBIDDEN_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{ext}' is not permitted.",
            )

        content_type = (file.content_type or "").lower().strip()
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"MIME type '{content_type}' is not supported. Permitted types: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
            )

        tenant_dir = get_tenant_media_dir(tenant_id)
        unique_prefix = uuid.uuid4().hex[:12]
        stored_filename = f"{unique_prefix}_{clean_name}"
        destination_path = os.path.join(tenant_dir, stored_filename)

        # Enforce file size limit during chunked streaming write
        total_size = 0
        chunk_size = 64 * 1024  # 64KB chunks
        try:
            with open(destination_path, "wb") as buffer:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE_BYTES:
                        buffer.close()
                        if os.path.exists(destination_path):
                            os.remove(destination_path)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Uploaded file exceeds maximum limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
                        )
                    buffer.write(chunk)
        except HTTPException:
            raise
        except Exception as exc:
            if os.path.exists(destination_path):
                os.remove(destination_path)
            logger.error("Failed to write uploaded media file: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist uploaded file.",
            )

        # Relative storage path from base directory
        relative_path = os.path.relpath(destination_path, get_media_base_dir()).replace("\\", "/")
        media_type = cls.classify_media_type(content_type)
        url = f"/api/public/media/{tenant_id}/{stored_filename}"

        media_item = Media(
            tenant_id=tenant_id,
            provider_id=provider_id,
            filename=clean_name,
            file_path=relative_path,
            url=url,
            content_type=content_type,
            file_size=total_size,
            title=title or clean_name,
            description=description,
            media_type=media_type,
            is_public_website_eligible=is_public_website_eligible,
            notes=notes,
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.add(media_item)
        db.commit()
        db.refresh(media_item)
        return media_item

    @staticmethod
    def list_media(
        db: Session,
        tenant_id: int,
        is_public_website_eligible: Optional[bool] = None,
        provider_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Media], int]:
        """List tenant-scoped media records with optional eligibility filter."""
        query = db.query(Media).filter(
            Media.tenant_id == tenant_id,
            Media.is_deleted.is_(False),
        )
        if is_public_website_eligible is not None:
            query = query.filter(Media.is_public_website_eligible.is_(is_public_website_eligible))
        if provider_id is not None:
            query = query.filter(Media.provider_id == provider_id)

        total = query.count()
        items = query.order_by(Media.id.desc()).offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def get_media(db: Session, tenant_id: int, media_id: int) -> Optional[Media]:
        """Retrieve a single media record strictly within tenant boundary."""
        return (
            db.query(Media)
            .filter(
                Media.id == media_id,
                Media.tenant_id == tenant_id,
                Media.is_deleted.is_(False),
            )
            .first()
        )

    @staticmethod
    def get_media_by_stored_filename(db: Session, tenant_id: int, stored_filename: str) -> Optional[Media]:
        """Lookup media record by stored filename suffix/pattern within tenant boundary."""
        # file_path ends with stored_filename
        items = (
            db.query(Media)
            .filter(
                Media.tenant_id == tenant_id,
                Media.is_deleted.is_(False),
            )
            .all()
        )
        for item in items:
            if item.file_path.endswith(stored_filename) or stored_filename in item.url:
                return item
        return None

    @classmethod
    def update_eligibility(
        cls,
        db: Session,
        tenant_id: int,
        media_id: int,
        is_eligible: bool,
    ) -> Optional[Media]:
        """Update public website eligibility for a tenant's media item."""
        media = cls.get_media(db, tenant_id, media_id)
        if not media:
            return None
        media.is_public_website_eligible = is_eligible
        media.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(media)
        return media

    @classmethod
    def delete_media(
        cls,
        db: Session,
        tenant_id: int,
        media_id: int,
        purge_file: bool = True,
    ) -> bool:
        """Soft-delete media record and optionally remove physical binary."""
        media = cls.get_media(db, tenant_id, media_id)
        if not media:
            return False

        media.is_deleted = True
        media.updated_at = datetime.now(timezone.utc)
        db.commit()

        if purge_file:
            try:
                base_dir = get_media_base_dir()
                full_path = os.path.abspath(os.path.join(base_dir, media.file_path))
                if os.path.exists(full_path) and full_path.startswith(base_dir):
                    os.remove(full_path)
            except Exception as exc:
                logger.warning("Failed to remove binary for media item %d: %s", media_id, exc)

        return True

    @staticmethod
    def get_assistant_media_context(
        db: Session,
        tenant_id: int,
    ) -> List[Dict[str, Any]]:
        """Retrieve safe media context for the Business Assistant.

        CRITICAL SECURITY REQUIREMENT:
        - Must strictly exclude clinical notes, booking notes, and private customer records.
        - Must strictly include ONLY items marked is_public_website_eligible=True.
        - Must NEVER cross tenant boundaries.
        - Notes field is completely omitted from the dictionary projection.
        """
        eligible_items = (
            db.query(Media)
            .filter(
                Media.tenant_id == tenant_id,
                Media.is_public_website_eligible.is_(True),
                Media.is_deleted.is_(False),
            )
            .order_by(Media.id.desc())
            .all()
        )

        safe_context: List[Dict[str, Any]] = []
        for item in eligible_items:
            # Explicit allowlist of safe fields - strictly omitting notes and sensitive storage paths
            safe_context.append({
                "id": item.id,
                "filename": item.filename,
                "url": item.url,
                "content_type": item.content_type,
                "file_size": item.file_size,
                "title": item.title,
                "description": item.description,
                "alt_text": item.alt_text,
                "media_type": item.media_type,
                "is_public_website_eligible": True,
            })

        return safe_context
