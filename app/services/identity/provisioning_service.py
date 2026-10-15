"""Identity and Organization Provisioning & Linking Service (WP1).

Provides idempotent, retry-safe operations for:
1. Mapping external identity subjects to internal users.
2. Mapping external organizations to internal tenants.
3. Processing identity outbox events for asynchronous provisioning.
4. Linking identities during tenant invitation acceptance.
"""

from datetime import datetime, timezone
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ...models.user import User
from ...models.tenant import Tenant
from ...models.invitation import TenantInvitation
from ...models.external_identity import (
    ExternalIdentityLink,
    ExternalOrganizationLink,
    IdentityOutboxEvent,
)
from .logto_client import LogtoClient, logto_client

logger = logging.getLogger(__name__)


class IdentityProvisioningError(Exception):
    """Raised when identity linking or provisioning fails."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class IdentityProvisioningService:
    """Service encapsulating all identity and organization linking and outbox logic."""

    @staticmethod
    def link_identity(
        db: Session,
        provider: str,
        external_subject_id: str,
        user_id: int,
        email: Optional[str] = None,
    ) -> ExternalIdentityLink:
        """Idempotently link an external subject to an internal user.

        Raises:
            IdentityProvisioningError: If the subject is already linked to a different user.
        """
        existing = (
            db.query(ExternalIdentityLink)
            .filter(
                ExternalIdentityLink.provider == provider,
                ExternalIdentityLink.external_subject_id == external_subject_id,
            )
            .first()
        )
        if existing:
            if existing.user_id != user_id:
                raise IdentityProvisioningError(
                    code="IDENTITY_CONFLICT",
                    message="External identity is already linked to another user account.",
                )
            # Update email if changed
            if email and existing.email != email:
                existing.email = email
                db.commit()
                db.refresh(existing)
            return existing

        link = ExternalIdentityLink(
            provider=provider,
            external_subject_id=external_subject_id,
            user_id=user_id,
            email=email,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(link)
        try:
            db.commit()
            db.refresh(link)
            return link
        except IntegrityError:
            db.rollback()
            # Handle race condition
            conflicting = (
                db.query(ExternalIdentityLink)
                .filter(
                    ExternalIdentityLink.provider == provider,
                    ExternalIdentityLink.external_subject_id == external_subject_id,
                )
                .first()
            )
            if conflicting:
                if conflicting.user_id != user_id:
                    raise IdentityProvisioningError(
                        code="IDENTITY_CONFLICT",
                        message="External identity is already linked to another user account.",
                    )
                return conflicting
            raise

    @staticmethod
    def link_organization(
        db: Session,
        provider: str,
        external_organization_id: str,
        tenant_id: int,
        provisioning_state: str = "provisioned",
    ) -> ExternalOrganizationLink:
        """Idempotently link an external organization ID to an internal tenant."""
        existing = (
            db.query(ExternalOrganizationLink)
            .filter(
                ExternalOrganizationLink.provider == provider,
                (ExternalOrganizationLink.external_organization_id == external_organization_id)
                | (ExternalOrganizationLink.tenant_id == tenant_id),
            )
            .first()
        )
        if existing:
            if existing.external_organization_id != external_organization_id:
                # Update external org id if tenant was pending
                existing.external_organization_id = external_organization_id
            existing.provisioning_state = provisioning_state
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            return existing

        org_link = ExternalOrganizationLink(
            provider=provider,
            external_organization_id=external_organization_id,
            tenant_id=tenant_id,
            provisioning_state=provisioning_state,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(org_link)
        try:
            db.commit()
            db.refresh(org_link)
            return org_link
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(ExternalOrganizationLink)
                .filter(
                    ExternalOrganizationLink.provider == provider,
                    ExternalOrganizationLink.external_organization_id == external_organization_id,
                )
                .first()
            )
            if existing:
                return existing
            raise

    @staticmethod
    def get_user_by_external_identity(
        db: Session,
        provider: str,
        external_subject_id: str,
    ) -> Optional[User]:
        """Retrieve the internal User mapped to an external identity subject."""
        link = (
            db.query(ExternalIdentityLink)
            .filter(
                ExternalIdentityLink.provider == provider,
                ExternalIdentityLink.external_subject_id == external_subject_id,
            )
            .first()
        )
        if link and link.user_id:
            return db.query(User).filter(User.id == link.user_id).first()
        return None

    @staticmethod
    def get_tenant_by_external_organization(
        db: Session,
        provider: str,
        external_organization_id: str,
    ) -> Optional[Tenant]:
        """Retrieve the internal Tenant mapped to an external organization ID."""
        link = (
            db.query(ExternalOrganizationLink)
            .filter(
                ExternalOrganizationLink.provider == provider,
                ExternalOrganizationLink.external_organization_id == external_organization_id,
            )
            .first()
        )
        if link and link.tenant_id:
            return db.query(Tenant).filter(Tenant.id == link.tenant_id).first()
        return None

    @staticmethod
    def get_user_accessible_tenants(
        db: Session,
        user: User,
    ) -> List[Dict[str, Any]]:
        """Return list of tenants accessible to the user with roles and external org mappings."""
        is_platform = (
            bool(getattr(user, "is_platform_owner", False))
            or bool(getattr(user, "is_superuser", False))
            or (getattr(user, "role", "") or "").lower() == "platform_owner"
        )

        results: List[Dict[str, Any]] = []

        if is_platform:
            tenants = db.query(Tenant).filter(Tenant.status == "active").all()
            for t in tenants:
                org_link = (
                    db.query(ExternalOrganizationLink)
                    .filter(ExternalOrganizationLink.tenant_id == t.id)
                    .first()
                )
                results.append({
                    "tenant_id": t.id,
                    "tenant_name": t.name,
                    "tenant_subdomain": t.subdomain,
                    "external_organization_id": org_link.external_organization_id if org_link else None,
                    "role": "platform_owner",
                    "status": t.status,
                })
            return results

        if user.tenant_id:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id, Tenant.status == "active").first()
            if tenant:
                org_link = (
                    db.query(ExternalOrganizationLink)
                    .filter(ExternalOrganizationLink.tenant_id == tenant.id)
                    .first()
                )
                results.append({
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "tenant_subdomain": tenant.subdomain,
                    "external_organization_id": org_link.external_organization_id if org_link else None,
                    "role": user.role,
                    "status": tenant.status,
                })

        return results

    @staticmethod
    def link_identity_via_invitation(
        db: Session,
        invitation_token: str,
        provider: str,
        external_subject_id: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Tuple[User, ExternalIdentityLink]:
        """Redeem a tenant invitation and link the external identity to the new or existing user."""
        invitation = (
            db.query(TenantInvitation)
            .filter(TenantInvitation.token == invitation_token)
            .first()
        )
        if not invitation:
            raise IdentityProvisioningError(
                code="INVITATION_NOT_FOUND",
                message="Tenant invitation token was not found.",
            )

        if invitation.status != "pending":
            raise IdentityProvisioningError(
                code="INVITATION_NOT_PENDING",
                message=f"Invitation has status '{invitation.status}' and cannot be redeemed.",
            )

        now = datetime.now(timezone.utc)
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            invitation.status = "expired"
            db.commit()
            raise IdentityProvisioningError(
                code="INVITATION_EXPIRED",
                message="Invitation has expired.",
            )

        target_email = email or invitation.email
        # Look for existing user in tenant with this email or login
        user = (
            db.query(User)
            .filter(
                User.tenant_id == invitation.tenant_id,
                (User.email == target_email) | (User.login == target_email),
            )
            .first()
        )

        if not user:
            from ...core.security import get_password_hash
            user = User(
                tenant_id=invitation.tenant_id,
                login=target_email,
                email=target_email,
                password_hash=get_password_hash(uuid.uuid4().hex),
                role=invitation.role or "owner",
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                created_at=now,
            )
            db.add(user)
            db.flush()

        # Update invitation
        invitation.status = "accepted"
        invitation.accepted_at = now

        # Create external identity link
        link = IdentityProvisioningService.link_identity(
            db=db,
            provider=provider,
            external_subject_id=external_subject_id,
            user_id=user.id,
            email=target_email,
        )

        db.commit()
        db.refresh(user)
        db.refresh(link)
        return user, link

    @staticmethod
    def enqueue_organization_provisioning(
        db: Session,
        tenant: Tenant,
    ) -> IdentityOutboxEvent:
        """Enqueue an asynchronous outbox event to provision a Logto organization for a tenant."""
        idempotency_key = f"provision:logto:tenant:{tenant.id}"
        existing = (
            db.query(IdentityOutboxEvent)
            .filter(IdentityOutboxEvent.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

        payload = {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "tenant_subdomain": tenant.subdomain,
            "action": "create_organization",
        }

        event = IdentityOutboxEvent(
            tenant_id=tenant.id,
            event_type="organization.provision",
            payload=json.dumps(payload),
            status="PENDING",
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    async def process_identity_outbox(
        db: Session,
        client: Optional[LogtoClient] = None,
    ) -> int:
        """Process pending identity outbox events and provision Logto organizations."""
        logto = client or logto_client
        pending_events = (
            db.query(IdentityOutboxEvent)
            .filter(IdentityOutboxEvent.status.in_(["PENDING", "RETRY"]))
            .order_by(IdentityOutboxEvent.id.asc())
            .limit(20)
            .all()
        )

        processed_count = 0
        for event in pending_events:
            event.status = "PROCESSING"
            db.commit()

            try:
                data = event.data() or {}
                event_type = event.event_type

                if event_type == "organization.provision":
                    tenant_id = data.get("tenant_id")
                    tenant_name = data.get("tenant_name", f"Tenant {tenant_id}")
                    tenant_subdomain = data.get("tenant_subdomain", "")

                    # Call Logto to get or create organization
                    org_data = await logto.get_or_create_organization(
                        name=f"{tenant_name} ({tenant_subdomain})" if tenant_subdomain else tenant_name,
                        description=f"Auto-provisioned organization for tenant {tenant_id}",
                    )
                    external_org_id = org_data.get("id")

                    if external_org_id and tenant_id:
                        IdentityProvisioningService.link_organization(
                            db=db,
                            provider="logto",
                            external_organization_id=external_org_id,
                            tenant_id=tenant_id,
                            provisioning_state="provisioned",
                        )

                event.status = "SUCCEEDED"
                event.processed_at = datetime.now(timezone.utc)
                event.error_message = None
                processed_count += 1
            except Exception as exc:
                event.retry_count += 1
                event.error_message = f"Provisioning failed: {type(exc).__name__}"
                if event.retry_count >= event.max_retries:
                    event.status = "FAILED"
                else:
                    event.status = "RETRY"
                logger.error("Error processing identity outbox event %d: %s", event.id, exc)

            db.commit()

        return processed_count


identity_service = IdentityProvisioningService()
