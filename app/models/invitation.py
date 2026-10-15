"""Tenant invitation model for onboarding and ownership assignment.

This model stores secure tokens issued to prospective or existing users
to claim a role (such as initial tenant owner or staff administrator)
within a specific tenant organization.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from ..db.database import Base


class TenantInvitation(Base):
    """Represents an invitation to join a tenant with an assigned role.

    Attributes:
        id: Primary key.
        tenant_id: Tenant to which the invitee is granted access.
        email: Email address of the intended recipient.
        role: Target role to assign upon redemption (e.g. 'owner', 'admin', 'staff').
        token: Cryptographically secure single-use token or claim secret.
        invited_by_user_id: User who generated the invitation (nullable for platform/system invites).
        status: Invitation lifecycle state ('pending', 'accepted', 'expired', 'revoked').
        expires_at: Expiration timestamp.
        accepted_at: Timestamp when successfully redeemed.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "tenant_invitations"
    __table_args__ = (
        UniqueConstraint("token", name="uq_tenant_invitations_token"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, index=True, nullable=False)
    role = Column(String, default="owner", nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    invited_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="pending", nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tenant = relationship("Tenant")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])

    def __repr__(self) -> str:
        return f"<TenantInvitation id={self.id} tenant_id={self.tenant_id} email={self.email} role={self.role} status={self.status}>"
