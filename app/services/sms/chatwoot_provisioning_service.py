"""Chatwoot Automated Provisioning Service.

Authoritative pipeline for Chatwoot multi-tenant provisioning:
Whenever a FastAPI tenant is onboarded or triggered via admin API, this service
provisions or synchronizes the Chatwoot account, inboxes, bindings, webhook subscriptions,
and staff memberships.
"""

import logging
import os
import secrets
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.config import settings
from ...models.provider import Provider
from ...models.location import Location
from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.tenant import Tenant
from ...models.user import User

logger = logging.getLogger(__name__)


class ProvisioningResult(BaseModel):
    """Result of tenant Chatwoot provisioning."""

    success: bool = Field(..., description="Overall provisioning success flag")
    status: str = Field(..., description="Status: 'provisioned', 'pending', or 'failed'")
    tenant_id: int = Field(..., description="FastAPI Tenant ID")
    chatwoot_account_id: Optional[int] = Field(None, description="Bound Chatwoot Account ID")
    account_created: bool = Field(False, description="Whether a new Chatwoot account was created")
    inboxes_provisioned: List[Dict[str, Any]] = Field(default_factory=list, description="List of provisioned inboxes")
    bindings_created: List[int] = Field(default_factory=list, description="IDs of created/updated SmsChatwootBindings")
    webhooks_registered: List[Dict[str, Any]] = Field(default_factory=list, description="List of registered webhook endpoints")
    staff_members_provisioned: List[Dict[str, Any]] = Field(default_factory=list, description="List of provisioned staff members")
    error_message: Optional[str] = Field(None, description="Error detail if provisioning failed or is pending")


def _get_chatwoot_config(
    chatwoot_base_url: Optional[str] = None,
    api_token: Optional[str] = None,
    platform_token: Optional[str] = None,
    webhook_base_url: Optional[str] = None,
) -> tuple[str, str, str, str]:
    """Resolve Chatwoot base URL, user API token, platform token, and webhook base URL."""
    base_url = (
        chatwoot_base_url
        or os.getenv("CHATWOOT_BASE_URL")
        or getattr(settings, "CHATWOOT_BASE_URL", "http://localhost:4000")
    ).rstrip("/")

    u_token = (
        api_token
        or os.getenv("CHATWOOT_API_ACCESS_TOKEN")
        or getattr(settings, "CHATWOOT_API_ACCESS_TOKEN", None)
        or ""
    )

    p_token = (
        platform_token
        or os.getenv("CHATWOOT_PLATFORM_API_TOKEN")
        or getattr(settings, "CHATWOOT_PLATFORM_API_TOKEN", None)
        or ""
    )

    wh_base = (
        webhook_base_url
        or os.getenv("APP_BASE_URL")
        or "http://localhost:8000"
    ).rstrip("/")

    return base_url, u_token, p_token, wh_base


def provision_tenant_chatwoot(
    db: Session,
    tenant_id: int,
    provider_ids: Optional[List[int]] = None,
    location_ids: Optional[List[int]] = None,
    chatwoot_base_url: Optional[str] = None,
    api_token: Optional[str] = None,
    platform_token: Optional[str] = None,
    webhook_base_url: Optional[str] = None,
) -> ProvisioningResult:
    """Automated idempotent provisioning pipeline for Chatwoot.

    Executes 6 core phases:
    1. Account Provisioning: Resolves or creates Chatwoot Account, commits tenant.chatwoot_account_id.
    2. Inbox Provisioning: Resolves or creates API Channel inboxes for providers and locations.
    3. Binding Provisioning: Creates or updates SmsChatwootBinding with timing-safe webhook_secret.
    4. Webhook Subscription: Subscribes FastAPI webhook to message_created and message_updated.
    5. Staff Provisioning: Syncs tenant staff/admin users to Chatwoot agents and inbox members.
    6. Idempotency: Running multiple times is safe and skips existing entities.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise ValueError(f"Tenant with ID {tenant_id} not found.")

    base_url, u_token, p_token, wh_base = _get_chatwoot_config(
        chatwoot_base_url=chatwoot_base_url,
        api_token=api_token,
        platform_token=platform_token,
        webhook_base_url=webhook_base_url,
    )

    result = ProvisioningResult(
        success=False,
        status="pending",
        tenant_id=tenant_id,
        chatwoot_account_id=tenant.chatwoot_account_id,
    )

    try:
        with httpx.Client(timeout=10.0) as client:
            # -------------------------------------------------------------
            # Phase 1: Account Provisioning
            # -------------------------------------------------------------
            account_id = tenant.chatwoot_account_id
            account_created = False

            if not account_id:
                # Attempt to match existing account by name via Platform API
                matched_id = None
                if p_token:
                    try:
                        acc_list_resp = client.get(
                            f"{base_url}/platform/api/v1/accounts",
                            headers={"api_access_token": p_token},
                        )
                        if acc_list_resp.status_code == 200:
                            acc_list = acc_list_resp.json()
                            if isinstance(acc_list, list):
                                for acc in acc_list:
                                    if acc.get("name", "").strip().lower() == tenant.name.strip().lower():
                                        matched_id = int(acc["id"])
                                        break
                    except Exception as e:
                        logger.warning(f"Failed to query platform accounts for tenant {tenant_id}: {e}")

                if matched_id:
                    account_id = matched_id
                elif p_token:
                    # Create new Account in Chatwoot via Platform API
                    acc_create_resp = client.post(
                        f"{base_url}/platform/api/v1/accounts",
                        headers={"api_access_token": p_token},
                        json={"name": tenant.name},
                    )
                    acc_create_resp.raise_for_status()
                    account_data = acc_create_resp.json()
                    account_id = int(account_data["id"])
                    account_created = True
                else:
                    raise RuntimeError("No Chatwoot platform token available to create account.")

                # Commit 1-to-1 account mapping onto Tenant
                tenant.chatwoot_account_id = account_id
                db.commit()
                db.refresh(tenant)

            result.chatwoot_account_id = account_id
            result.account_created = account_created

            # Link provisioning user (SuperAdmin) to this account if needed
            if p_token and u_token:
                try:
                    prof_resp = client.get(
                        f"{base_url}/api/v1/profile",
                        headers={"api_access_token": u_token},
                    )
                    if prof_resp.status_code == 200:
                        admin_uid = prof_resp.json().get("id")
                        if admin_uid:
                            # Add superadmin user to account
                            client.post(
                                f"{base_url}/platform/api/v1/accounts/{account_id}/account_users",
                                headers={"api_access_token": p_token},
                                json={"user_id": admin_uid, "role": "administrator"},
                            )
                except Exception as e:
                    logger.warning(f"SuperAdmin user link note for account {account_id}: {e}")

            # -------------------------------------------------------------
            # Phase 2: Resolve Target Providers
            # -------------------------------------------------------------
            target_providers_query = db.query(Provider).filter(
                Provider.tenant_id == tenant.id,
                Provider.deleted_at == None,
            )
            if provider_ids:
                target_providers_query = target_providers_query.filter(Provider.id.in_(provider_ids))
            else:
                target_providers_query = target_providers_query.filter(Provider.active == True)

            providers = target_providers_query.all()
            if not providers:
                # Ensure default provider exists for solo practice or initial tenant
                default_provider = db.query(Provider).filter(
                    Provider.tenant_id == tenant.id,
                    Provider.deleted_at == None,
                ).first()
                if not default_provider:
                    default_provider = Provider(
                        tenant_id=tenant.id,
                        name=tenant.name,
                        active=True,
                    )
                    db.add(default_provider)
                    db.commit()
                    db.refresh(default_provider)
                providers = [default_provider]

            # -------------------------------------------------------------
            # Phase 3: Inbox Provisioning
            # -------------------------------------------------------------
            # Fetch existing inboxes in Chatwoot for this account
            existing_inboxes: List[Dict[str, Any]] = []
            try:
                inboxes_resp = client.get(
                    f"{base_url}/api/v1/accounts/{account_id}/inboxes",
                    headers={"api_access_token": u_token},
                )
                if inboxes_resp.status_code == 200:
                    payload = inboxes_resp.json()
                    existing_inboxes = payload.get("payload", []) if isinstance(payload, dict) else payload
            except Exception as e:
                logger.warning(f"Could not list inboxes for account {account_id}: {e}")

            inboxes_by_name = {inb.get("name", "").strip().lower(): inb for inb in existing_inboxes}
            inboxes_by_id = {int(inb["id"]): inb for inb in existing_inboxes if "id" in inb}

            # -------------------------------------------------------------
            # Phase 4: Binding Provisioning & Webhook Setup
            # -------------------------------------------------------------
            for provider in providers:
                inbox_name = (
                    f"{tenant.name} - General"
                    if provider.name.strip().lower() == tenant.name.strip().lower()
                    else f"{tenant.name} - {provider.name}"
                )

                # Check existing binding
                binding = db.query(SmsChatwootBinding).filter(
                    SmsChatwootBinding.tenant_id == tenant.id,
                    SmsChatwootBinding.provider_id == provider.id,
                    SmsChatwootBinding.chatwoot_account_id == account_id,
                ).first()

                inbox_id: Optional[int] = None
                if binding and binding.chatwoot_inbox_id in inboxes_by_id:
                    inbox_id = binding.chatwoot_inbox_id
                elif inbox_name.lower() in inboxes_by_name:
                    inbox_id = int(inboxes_by_name[inbox_name.lower()]["id"])
                else:
                    # Create new API Channel inbox
                    create_inb_resp = client.post(
                        f"{base_url}/api/v1/accounts/{account_id}/inboxes",
                        headers={"api_access_token": u_token},
                        json={
                            "name": inbox_name,
                            "channel": {
                                "type": "api",
                                "webhook_url": f"{wh_base}/api/sms/chatwoot/webhook",
                            },
                        },
                    )
                    create_inb_resp.raise_for_status()
                    inb_data = create_inb_resp.json()
                    inbox_id = int(inb_data["id"])
                    inboxes_by_name[inbox_name.lower()] = inb_data
                    inboxes_by_id[inbox_id] = inb_data

                result.inboxes_provisioned.append({
                    "provider_id": provider.id,
                    "inbox_id": inbox_id,
                    "inbox_name": inbox_name,
                })

                # Create or update SmsChatwootBinding
                if not binding:
                    webhook_secret = secrets.token_hex(32)
                    binding = SmsChatwootBinding(
                        tenant_id=tenant.id,
                        provider_id=provider.id,
                        chatwoot_account_id=account_id,
                        chatwoot_inbox_id=inbox_id,
                        chatwoot_base_url=base_url,
                        chatwoot_api_token=u_token,
                        webhook_secret=webhook_secret,
                        is_enabled=True,
                        channel_metadata={"ai_mode": "autopilot", "ai_enabled": True},
                    )
                    db.add(binding)
                    db.commit()
                    db.refresh(binding)
                else:
                    binding.chatwoot_inbox_id = inbox_id
                    binding.chatwoot_base_url = base_url
                    binding.is_enabled = True
                    if not binding.webhook_secret:
                        binding.webhook_secret = secrets.token_hex(32)
                    db.commit()
                    db.refresh(binding)

                result.bindings_created.append(binding.id)

                # ---------------------------------------------------------
                # Phase 5: Webhook Subscription
                # ---------------------------------------------------------
                webhook_url = f"{wh_base}/api/sms/chatwoot/webhook?token={binding.webhook_secret}"
                # Check existing account webhooks
                existing_webhooks: List[Dict[str, Any]] = []
                try:
                    wh_list_resp = client.get(
                        f"{base_url}/api/v1/accounts/{account_id}/webhooks",
                        headers={"api_access_token": u_token},
                    )
                    if wh_list_resp.status_code == 200:
                        wh_payload = wh_list_resp.json()
                        existing_webhooks = wh_payload.get("payload", {}).get("webhooks", [])
                        if not existing_webhooks and isinstance(wh_payload, list):
                            existing_webhooks = wh_payload
                except Exception as e:
                    logger.warning(f"Could not list webhooks for account {account_id}: {e}")

                webhook_already_registered = any(
                    wh.get("url") == webhook_url for wh in existing_webhooks
                )

                if not webhook_already_registered:
                    try:
                        wh_create_resp = client.post(
                            f"{base_url}/api/v1/accounts/{account_id}/webhooks",
                            headers={"api_access_token": u_token},
                            json={
                                "url": webhook_url,
                                "subscriptions": ["message_created", "message_updated"],
                            },
                        )
                        if wh_create_resp.status_code in (200, 201):
                            wh_info = wh_create_resp.json()
                            result.webhooks_registered.append({
                                "url": webhook_url,
                                "inbox_id": inbox_id,
                                "status": "registered",
                                "details": wh_info,
                            })
                        else:
                            logger.warning(f"Webhook registration status {wh_create_resp.status_code}: {wh_create_resp.text}")
                    except Exception as e:
                        logger.warning(f"Failed to register webhook for inbox {inbox_id}: {e}")
                else:
                    result.webhooks_registered.append({
                        "url": webhook_url,
                        "inbox_id": inbox_id,
                        "status": "already_registered",
                    })

            # -------------------------------------------------------------
            # Phase 4b: Location Inboxes Provisioning & Webhook Setup
            # -------------------------------------------------------------
            if location_ids:
                locations = db.query(Location).filter(
                    Location.tenant_id == tenant.id,
                    Location.id.in_(location_ids),
                    Location.active == True,
                ).all()
                for location in locations:
                    loc_inbox_name = f"{tenant.name} - Location: {location.name}"

                    binding = db.query(SmsChatwootBinding).filter(
                        SmsChatwootBinding.tenant_id == tenant.id,
                        SmsChatwootBinding.location_id == location.id,
                        SmsChatwootBinding.chatwoot_account_id == account_id,
                    ).first()

                    inbox_id = None
                    if binding and binding.chatwoot_inbox_id in inboxes_by_id:
                        inbox_id = binding.chatwoot_inbox_id
                    elif loc_inbox_name.lower() in inboxes_by_name:
                        inbox_id = int(inboxes_by_name[loc_inbox_name.lower()]["id"])
                    else:
                        create_inb_resp = client.post(
                            f"{base_url}/api/v1/accounts/{account_id}/inboxes",
                            headers={"api_access_token": u_token},
                            json={
                                "name": loc_inbox_name,
                                "channel": {
                                    "type": "api",
                                    "webhook_url": f"{wh_base}/api/sms/chatwoot/webhook",
                                },
                            },
                        )
                        create_inb_resp.raise_for_status()
                        inb_data = create_inb_resp.json()
                        inbox_id = int(inb_data["id"])
                        inboxes_by_name[loc_inbox_name.lower()] = inb_data
                        inboxes_by_id[inbox_id] = inb_data

                    result.inboxes_provisioned.append({
                        "location_id": location.id,
                        "inbox_id": inbox_id,
                        "inbox_name": loc_inbox_name,
                    })

                    if not binding:
                        webhook_secret = secrets.token_hex(32)
                        binding = SmsChatwootBinding(
                            tenant_id=tenant.id,
                            provider_id=None,
                            location_id=location.id,
                            chatwoot_account_id=account_id,
                            chatwoot_inbox_id=inbox_id,
                            chatwoot_base_url=base_url,
                            chatwoot_api_token=u_token,
                            webhook_secret=webhook_secret,
                            is_enabled=True,
                            channel_metadata={"ai_mode": "autopilot", "ai_enabled": True},
                        )
                        db.add(binding)
                        db.commit()
                        db.refresh(binding)
                    else:
                        binding.chatwoot_inbox_id = inbox_id
                        binding.chatwoot_base_url = base_url
                        binding.is_enabled = True
                        if not binding.webhook_secret:
                            binding.webhook_secret = secrets.token_hex(32)
                        db.commit()
                        db.refresh(binding)

                    result.bindings_created.append(binding.id)

                    webhook_url = f"{wh_base}/api/sms/chatwoot/webhook?token={binding.webhook_secret}"
                    webhook_already_registered = any(
                        wh.get("url") == webhook_url for wh in existing_webhooks
                    )
                    if not webhook_already_registered:
                        try:
                            wh_create_resp = client.post(
                                f"{base_url}/api/v1/accounts/{account_id}/webhooks",
                                headers={"api_access_token": u_token},
                                json={
                                    "url": webhook_url,
                                    "subscriptions": ["message_created", "message_updated"],
                                },
                            )
                            if wh_create_resp.status_code in (200, 201):
                                wh_info = wh_create_resp.json()
                                result.webhooks_registered.append({
                                    "url": webhook_url,
                                    "inbox_id": inbox_id,
                                    "status": "registered",
                                    "details": wh_info,
                                })
                        except Exception as e:
                            logger.warning(f"Failed to register webhook for location inbox {inbox_id}: {e}")
                    else:
                        result.webhooks_registered.append({
                            "url": webhook_url,
                            "inbox_id": inbox_id,
                            "status": "already_registered",
                        })

            # -------------------------------------------------------------
            # Phase 6: Staff Provisioning & Inbox Membership
            # -------------------------------------------------------------
            staff_users = db.query(User).filter(
                User.tenant_id == tenant.id,
                User.role.in_(["admin", "owner", "staff"]),
            ).all()

            existing_agents: List[Dict[str, Any]] = []
            try:
                agents_resp = client.get(
                    f"{base_url}/api/v1/accounts/{account_id}/agents",
                    headers={"api_access_token": u_token},
                )
                if agents_resp.status_code == 200:
                    payload = agents_resp.json()
                    existing_agents = payload if isinstance(payload, list) else payload.get("payload", [])
            except Exception as e:
                logger.warning(f"Could not list agents for account {account_id}: {e}")

            agents_by_email = {ag.get("email", "").strip().lower(): ag for ag in existing_agents}

            for user in staff_users:
                user_email = (
                    user.login
                    if "@" in (user.login or "")
                    else (
                        getattr(user, "email", None)
                        or f"{user.login}@{tenant.subdomain}.local"
                    )
                )
                agent_id: Optional[int] = None

                if user_email.lower() in agents_by_email:
                    agent_id = int(agents_by_email[user_email.lower()]["id"])
                else:
                    try:
                        agent_create_resp = client.post(
                            f"{base_url}/api/v1/accounts/{account_id}/agents",
                            headers={"api_access_token": u_token},
                            json={
                                "name": user.login or f"Staff {user.id}",
                                "email": user_email,
                                "role": "administrator" if user.role in ("admin", "owner") else "agent",
                            },
                        )
                        if agent_create_resp.status_code in (200, 201):
                            agent_data = agent_create_resp.json()
                            agent_id = int(agent_data["id"])
                            agents_by_email[user_email.lower()] = agent_data
                    except Exception as e:
                        logger.warning(f"Could not create agent for user {user.id} in account {account_id}: {e}")

                if agent_id:
                    # Add to all provisioned inboxes for this tenant
                    for inb_info in result.inboxes_provisioned:
                        target_inbox_id = inb_info["inbox_id"]
                        try:
                            client.post(
                                f"{base_url}/api/v1/accounts/{account_id}/inbox_members",
                                headers={"api_access_token": u_token},
                                json={"inbox_id": target_inbox_id, "user_ids": [agent_id]},
                            )
                        except Exception as e:
                            logger.warning(f"Could not add agent {agent_id} to inbox {target_inbox_id}: {e}")

                    result.staff_members_provisioned.append({
                        "user_id": user.id,
                        "agent_id": agent_id,
                        "email": user_email,
                        "role": user.role,
                    })

            result.success = True
            result.status = "provisioned"

    except (httpx.ConnectError, httpx.TimeoutException) as net_err:
        logger.warning(f"Chatwoot service unreachable at {base_url}: {net_err}")
        result.success = False
        result.status = "pending"
        result.error_message = f"Chatwoot service unreachable: {str(net_err)}"
    except Exception as exc:
        logger.error(f"Chatwoot provisioning error for tenant {tenant_id}: {exc}", exc_info=True)
        result.success = False
        result.status = "failed"
        result.error_message = str(exc)

    return result


def provision_location_chatwoot(
    db: Session,
    tenant_id: int,
    location_id: int,
    chatwoot_base_url: Optional[str] = None,
    api_token: Optional[str] = None,
    platform_token: Optional[str] = None,
    webhook_base_url: Optional[str] = None,
) -> ProvisioningResult:
    """Convenience helper to provision a dedicated location inbox."""
    return provision_tenant_chatwoot(
        db=db,
        tenant_id=tenant_id,
        location_ids=[location_id],
        chatwoot_base_url=chatwoot_base_url,
        api_token=api_token,
        platform_token=platform_token,
        webhook_base_url=webhook_base_url,
    )
