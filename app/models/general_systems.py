"""General system models: plugin state toggles and GDPR consent logs."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.database import Base


class PluginState(Base):
    """Persisted on/off toggle for a named plugin or feature flag.

    Storing these in the database means an admin can toggle features at
    runtime without redeploying.  The name should match the module flag
    keys already returned by the diagnostics endpoint so the two stay
    in sync.
    """

    __tablename__ = "plugin_states"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_plugin_state_tenant_name"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, index=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<PluginState name={self.name} is_enabled={self.is_enabled}>"


class GdprConsent(Base):
    """Immutable log of a client's GDPR or privacy consent decision.

    Each time a client accepts or withdraws consent (marketing, data
    processing, terms etc.) a new row is appended.  The IP address is
    recorded for compliance audit purposes.
    """

    __tablename__ = "gdpr_consents"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_type = Column(String, default="gdpr", nullable=False)   # gdpr | marketing | terms
    is_approved = Column(Boolean, default=True, nullable=False)
    ip_address = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    client = relationship("Client")

    def __repr__(self) -> str:
        return f"<GdprConsent id={self.id} client_id={self.client_id} type={self.consent_type}>"
