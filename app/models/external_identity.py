"""External Identity and Organization Link models for Logto integration (WP1).

Defines persistence for external OAuth2/OIDC identity subject IDs mapped to
internal users, external organization IDs mapped to internal tenants, and
dedicated identity outbox events for asynchronous provisioning.
"""

from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..db.database import Base


class ExternalIdentityLink(Base):
    """Maps an external identity provider subject (e.g. Logto sub) to an internal User.

    Attributes:
        id: Primary key.
        provider: Provider identifier (e.g. 'logto').
        external_subject_id: External subject identifier ('sub' claim).
        user_id: Internal user ID.
        email: Email associated with the external identity at link time.
        created_at: Time of initial linking.
        updated_at: Time of last update.
    """

    __tablename__ = "external_identity_links"
    __table_args__ = (
        UniqueConstraint("provider", "external_subject_id", name="uq_external_identity_provider_subject"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), default="logto", nullable=False, index=True)
    external_subject_id = Column(String(128), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
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

    # Relationship to user
    user = relationship("User", backref="external_identities")

    def __repr__(self) -> str:
        return f"<ExternalIdentityLink id={self.id} provider={self.provider} sub={self.external_subject_id} user_id={self.user_id}>"


class ExternalOrganizationLink(Base):
    """Maps an external identity provider organization (e.g. Logto org_id) to an internal Tenant.

    Attributes:
        id: Primary key.
        provider: Provider identifier (e.g. 'logto').
        external_organization_id: External organization identifier in the provider.
        tenant_id: Internal tenant ID.
        provisioning_state: Lifecycle state ('pending', 'provisioned', 'failed').
        created_at: Time of link creation.
        updated_at: Time of last update.
    """

    __tablename__ = "external_organization_links"
    __table_args__ = (
        UniqueConstraint("provider", "external_organization_id", name="uq_external_org_provider_org_id"),
        UniqueConstraint("provider", "tenant_id", name="uq_external_org_provider_tenant_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), default="logto", nullable=False, index=True)
    external_organization_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provisioning_state = Column(String(32), default="provisioned", nullable=False)
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

    # Relationship to tenant
    tenant = relationship("Tenant", backref="external_organizations")

    def __repr__(self) -> str:
        return f"<ExternalOrganizationLink id={self.id} provider={self.provider} org_id={self.external_organization_id} tenant_id={self.tenant_id}>"


class IdentityOutboxEvent(Base):
    """Outbox event queue for asynchronous, retry-safe identity and organization provisioning.

    Attributes:
        id: Primary key.
        tenant_id: Optional internal tenant context.
        user_id: Optional internal user context.
        event_type: Type of identity event (e.g. 'organization.provision', 'user.link', 'membership.sync').
        payload: JSON-encoded payload.
        status: Delivery lifecycle status ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED').
        retry_count: Number of delivery attempts made.
        max_retries: Maximum attempts before terminal failure.
        error_message: Privacy-safe failure description.
        idempotency_key: Unique idempotency key to prevent duplicate event execution.
        created_at: Event creation timestamp.
        processed_at: Event resolution timestamp.
    """

    __tablename__ = "identity_outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_identity_outbox_events_idempotency_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    status = Column(String(32), default="PENDING", nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=5, nullable=False)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(
        String(128),
        default=lambda: f"id_outbox:{uuid.uuid4()}",
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)

    def data(self) -> Optional[Dict[str, Any]]:
        """Return the payload deserialized as a Python dictionary."""
        try:
            return json.loads(self.payload)
        except Exception:
            return None

    def __repr__(self) -> str:
        return f"<IdentityOutboxEvent id={self.id} type={self.event_type} status={self.status}>"
