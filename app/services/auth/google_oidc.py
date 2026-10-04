"""Google OIDC token verification."""
import logging
from typing import Any, Dict, Optional
from google.oauth2 import id_token
from google.auth.transport import requests
from ...core.config import settings

logger = logging.getLogger(__name__)


def verify_google_id_token(token: str, client_id: Optional[str] = None) -> Dict[str, Any]:
    """Verify a Google OAuth2/OIDC ID token.

    Returns the decoded token claims containing 'sub', 'email', 'name', 'picture', etc.
    Raises ValueError on invalid signature or expiration.
    """
    effective_client_id = client_id or settings.GOOGLE_CLIENT_ID
    request = requests.Request()
    payload = id_token.verify_oauth2_token(token, request, audience=effective_client_id)
    if payload.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
        raise ValueError("Invalid token issuer")
    return payload
