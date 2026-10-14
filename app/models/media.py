"""Media model for tenant durable assets.

Stores metadata, storage references, public website eligibility, and notes
for tenant media items (photos, videos, documents).
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db.database import Base


class Media(Base):
    """Represents a durable media asset owned by a tenant.

    Attributes:
        id: Primary key.
        tenant_id: Foreign key referencing the owning Tenant.
        provider_id: Optional foreign key referencing an associated Provider.
        filename: Original or sanitized file name.
        file_path: Relative or absolute local file path where binary is stored.
        url: Public or accessible URL for retrieving the media object.
        content_type: MIME type of the uploaded file.
        file_size: Size of the file in bytes.
        title: Safe human-readable title.
        description: Safe textual description.
        alt_text: Accessibility alternative text.
        media_type: High-level classification (image, video, document).
        is_public_website_eligible: Whether approved for public website display.
        notes: Confidential internal/clinical notes. Strictly excluded from
            assistant media context and public endpoints.
        is_deleted: Soft deletion flag.
        created_at: Upload timestamp.
        updated_at: Timestamp of last metadata change.
    """

    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id = Column(
        Integer,
        ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    url = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(String(1000), nullable=True)
    alt_text = Column(String(255), nullable=True)
    media_type = Column(String(32), default="image", nullable=False)
    is_public_website_eligible = Column(
        Boolean, default=False, nullable=False, index=True
    )
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant", backref="media_items")
    provider = relationship("Provider", backref="media_items")

    def __repr__(self) -> str:
        return (
            f"<Media id={self.id} tenant_id={self.tenant_id} "
            f"filename='{self.filename}' eligible={self.is_public_website_eligible}>"
        )


def init_media_tables(bind=None) -> None:
    """Helper to ensure the media_items table exists."""
    Media.__table__.create(bind=bind, checkfirst=True)
