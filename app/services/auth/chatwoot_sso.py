"""Chatwoot Platform API SSO broker."""
import logging
import secrets
import string
from typing import Optional
import httpx
from ...core.config import settings
from ...models.user import User

logger = logging.getLogger(__name__)


def generate_compliant_password() -> str:
    """Generate a high-entropy password meeting Chatwoot's validation constraints:
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    - Length >= 16 characters
    """
    specials = "!@#$%^&*()_+-="
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(specials),
    ]
    all_chars = string.ascii_letters + string.digits + specials
    chars += [secrets.choice(all_chars) for _ in range(16)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def map_app_role_to_chatwoot(role: str) -> str:
    """Map FastAPI Bookings user role to Chatwoot AccountUser role."""
    normalized = (role or "").lower()
    if normalized in ("owner", "admin"):
        return "administrator"
    return "agent"


async def sync_user_to_chatwoot_platform(
    user: User,
    chatwoot_account_id: int,
) -> Optional[int]:
    """Sync or create a user in Chatwoot Platform API and bind to account.

    Returns chatwoot_user_id or None if platform API is unavailable.
    """
    platform_token = settings.CHATWOOT_PLATFORM_ACCESS_TOKEN or settings.CHATWOOT_PLATFORM_API_TOKEN
    base_url = (settings.CHATWOOT_BASE_URL or "").rstrip("/")
    if not platform_token or not base_url or not chatwoot_account_id:
        return None

    email = user.email or f"{user.login}@{user.tenant_id}.internal"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.login
    role = map_app_role_to_chatwoot(user.role)

    headers = {
        "api_access_token": platform_token,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:
            chatwoot_user_id = user.chatwoot_user_id
            # 1. If chatwoot_user_id is not stored, create user in Platform API
            if not chatwoot_user_id:
                payload = {
                    "name": name,
                    "email": email,
                    "password": generate_compliant_password(),
                }
                res = await client.post("/platform/api/v1/users", json=payload)
                if res.status_code in (200, 201):
                    chatwoot_user_id = res.json().get("id")
                elif res.status_code == 422:
                    data = res.json()
                    if "id" in data:
                        chatwoot_user_id = data["id"]
                    elif "attributes" in data and "id" in data["attributes"]:
                        chatwoot_user_id = data["attributes"]["id"]
                if not chatwoot_user_id:
                    logger.warning("Could not obtain Chatwoot user ID for %s: %s", email, res.text)
                    return None

            # 2. Bind user to account with role
            au_payload = {
                "user_id": chatwoot_user_id,
                "role": role,
            }
            au_res = await client.post(
                f"/platform/api/v1/accounts/{chatwoot_account_id}/account_users",
                json=au_payload,
            )
            if au_res.status_code not in (200, 201) and "already exists" not in au_res.text.lower():
                logger.warning("AccountUser binding response in Chatwoot: %s", au_res.text)

            return chatwoot_user_id
    except Exception as exc:
        logger.error("Error communicating with Chatwoot Platform API: %s", exc)
        return None


async def generate_chatwoot_sso_url(chatwoot_user_id: int) -> Optional[str]:
    """Generate a single-use SSO login URL with 5-minute TTL via Chatwoot Platform API."""
    platform_token = settings.CHATWOOT_PLATFORM_ACCESS_TOKEN or settings.CHATWOOT_PLATFORM_API_TOKEN
    base_url = (settings.CHATWOOT_BASE_URL or "").rstrip("/")
    if not platform_token or not base_url or not chatwoot_user_id:
        return None

    headers = {
        "api_access_token": platform_token,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:
            res = await client.get(f"/platform/api/v1/users/{chatwoot_user_id}/login")
            if res.status_code == 200:
                return res.json().get("url")
            logger.warning("Failed generating Chatwoot SSO link for user %s: %s", chatwoot_user_id, res.text)
            return None
    except Exception as exc:
        logger.error("Error requesting Chatwoot SSO URL: %s", exc)
        return None
