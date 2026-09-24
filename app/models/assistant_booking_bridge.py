"""Durable, disabled-by-default Assistant UI booking bridge bindings."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from ..db.database import Base


class AssistantBookingBridgeBinding(Base):
    __tablename__ = "assistant_booking_bridge_bindings"
    id = Column(Integer, primary_key=True)
    line_key = Column(String(64), unique=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    default_location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    credential_key_id = Column(String(96), unique=True, nullable=False)
    # SHA-256 of the server-to-server bridge secret. The plaintext is never persisted.
    secret_verifier = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AssistantBookingBridgeNonce(Base):
    __tablename__ = "assistant_booking_bridge_nonces"
    __table_args__ = (UniqueConstraint("binding_id", "nonce", name="uq_assistant_bridge_nonce"),)
    id = Column(Integer, primary_key=True)
    binding_id = Column(Integer, ForeignKey("assistant_booking_bridge_bindings.id", ondelete="CASCADE"), nullable=False, index=True)
    nonce = Column(String(96), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class AssistantBookingBridgeProposal(Base):
    __tablename__ = "assistant_booking_bridge_proposals"
    id = Column(String(36), primary_key=True)
    binding_id = Column(Integer, ForeignKey("assistant_booking_bridge_bindings.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)


class AssistantBookingBridgeReceipt(Base):
    __tablename__ = "assistant_booking_bridge_receipts"
    __table_args__ = (UniqueConstraint("binding_id", "request_id", name="uq_assistant_bridge_receipt"),)
    id = Column(Integer, primary_key=True)
    binding_id = Column(Integer, ForeignKey("assistant_booking_bridge_bindings.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id = Column(String(96), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
