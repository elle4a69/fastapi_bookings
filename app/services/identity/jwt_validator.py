"""Logto JWT Validation and Claims Extraction Service (WP1).

Verifies OIDC access tokens and organization tokens issued by Logto using
RS256 public keys (JWKS) with in-memory caching and strict claim enforcement.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from jose import JWTError, jwk, jwt

from ...core.config import settings

logger = logging.getLogger(__name__)


class LogtoValidationError(Exception):
    """Raised when Logto JWT signature or claim validation fails."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class LogtoTokenValidator:
    """Validates Logto tokens against JWKS public keys and extracts verified claims."""

    def __init__(self) -> None:
        self._cached_jwks: Optional[Dict[str, Any]] = None
        self._cache_expires_at: Optional[datetime] = None
        # In-memory registry for test keys and custom keys
        self._test_keys: Dict[str, Any] = {}

    def register_test_key(self, kid: str, public_key_pem_or_jwk: Any) -> None:
        """Register an in-memory public key for fast, offline test execution."""
        self._test_keys[kid] = public_key_pem_or_jwk

    def clear_test_keys(self) -> None:
        """Clear all registered test keys."""
        self._test_keys.clear()
        self._cached_jwks = None
        self._cache_expires_at = None

    def _get_issuer(self) -> Optional[str]:
        """Return the expected Logto token issuer."""
        if settings.LOGTO_ISSUER:
            return settings.LOGTO_ISSUER.rstrip("/")
        if settings.LOGTO_ENDPOINT:
            return f"{settings.LOGTO_ENDPOINT.rstrip('/')}/oidc"
        return None

    def _get_jwks_uri(self) -> Optional[str]:
        """Return the JWKS URI for fetching public keys."""
        if settings.LOGTO_JWKS_URI:
            return settings.LOGTO_JWKS_URI
        if settings.LOGTO_ENDPOINT:
            return f"{settings.LOGTO_ENDPOINT.rstrip('/')}/oidc/jwks"
        return None

    def _fetch_jwks(self) -> Dict[str, Any]:
        """Retrieve JWKS public keys, respecting caching and test overrides."""
        # 1. Check if configured in settings JSON
        if settings.LOGTO_PUBLIC_KEYS_JSON:
            try:
                parsed = json.loads(settings.LOGTO_PUBLIC_KEYS_JSON)
                if isinstance(parsed, dict) and "keys" in parsed:
                    return parsed
            except Exception as exc:
                logger.warning("Failed parsing LOGTO_PUBLIC_KEYS_JSON: %s", exc)

        # 2. Check in-memory cached JWKS
        now = datetime.now(timezone.utc)
        if self._cached_jwks and self._cache_expires_at and now < self._cache_expires_at:
            return self._cached_jwks

        # 3. Fetch from remote JWKS URI if configured
        jwks_uri = self._get_jwks_uri()
        if not jwks_uri:
            # If no remote URI, return empty or test keys dict
            return {"keys": []}

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(jwks_uri)
                resp.raise_for_status()
                jwks_data = resp.json()
                self._cached_jwks = jwks_data
                self._cache_expires_at = datetime.fromtimestamp(
                    now.timestamp() + settings.LOGTO_CACHE_TTL_SECONDS,
                    tz=timezone.utc,
                )
                return jwks_data
        except Exception as exc:
            logger.error("Failed fetching Logto JWKS from %s: %s", jwks_uri, exc)
            if self._cached_jwks:
                # Return stale cache on transient failure
                return self._cached_jwks
            raise LogtoValidationError(
                code="JWKS_FETCH_FAILED",
                message="Unable to fetch identity provider public keys.",
            )

    def _resolve_public_key(self, kid: Optional[str]) -> Any:
        """Resolve the cryptographic public key matching the token's key ID."""
        if kid and kid in self._test_keys:
            key_data = self._test_keys[kid]
            if isinstance(key_data, dict):
                return jwk.construct(key_data, algorithm="RS256").to_pem().decode("utf-8")
            return key_data

        jwks_data = self._fetch_jwks()
        keys: List[Dict[str, Any]] = jwks_data.get("keys", [])

        if not keys and not self._test_keys:
            raise LogtoValidationError(
                code="NO_PUBLIC_KEYS",
                message="No public keys available to verify token signature.",
            )

        if kid:
            for k in keys:
                if k.get("kid") == kid:
                    return jwk.construct(k, algorithm="RS256").to_pem().decode("utf-8")
            raise LogtoValidationError(
                code="KEY_NOT_FOUND",
                message=f"Public key with ID '{kid}' not found in provider JWKS.",
            )

        # If no kid specified, fallback to first available key if single key
        if len(keys) == 1:
            return jwk.construct(keys[0], algorithm="RS256").to_pem().decode("utf-8")
        if len(self._test_keys) == 1:
            first_val = next(iter(self._test_keys.values()))
            if isinstance(first_val, dict):
                return jwk.construct(first_val, algorithm="RS256").to_pem().decode("utf-8")
            return first_val

        raise LogtoValidationError(
            code="AMBIGUOUS_KEY_ID",
            message="Token header lacks 'kid' and multiple verification keys are registered.",
        )

    def validate_token(
        self,
        token: str,
        expected_organization_id: Optional[str] = None,
        verify_aud: bool = True,
    ) -> Dict[str, Any]:
        """Validate a Logto JWT and return its verified claims dictionary.

        Args:
            token: Encoded JWT string.
            expected_organization_id: Optional external organization ID to assert.
            verify_aud: Whether to verify the audience claim.

        Returns:
            Dict containing verified claims.

        Raises:
            LogtoValidationError: If signature, expiry, issuer, audience, or organization checks fail.
        """
        if not token or not isinstance(token, str):
            raise LogtoValidationError(code="INVALID_TOKEN", message="Missing or empty token string.")

        # 1. Inspect unverified header
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception:
            raise LogtoValidationError(code="MALFORMED_HEADER", message="Invalid token header encoding.")

        alg = unverified_header.get("alg")
        if alg != "RS256":
            raise LogtoValidationError(
                code="UNSUPPORTED_ALGORITHM",
                message=f"Expected RS256 token algorithm, received '{alg}'.",
            )

        kid = unverified_header.get("kid")
        public_key = self._resolve_public_key(kid)

        # 2. Prepare decode options and claims validation
        expected_issuer = self._get_issuer()
        expected_audience = settings.LOGTO_API_RESOURCE or settings.LOGTO_APP_ID or None

        decode_options: Dict[str, Any] = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_aud": bool(verify_aud and expected_audience),
            "verify_iss": bool(expected_issuer),
        }

        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=expected_audience if (verify_aud and expected_audience) else None,
                issuer=expected_issuer if expected_issuer else None,
                options=decode_options,
            )
        except jwt.ExpiredSignatureError:
            raise LogtoValidationError(code="TOKEN_EXPIRED", message="Token signature has expired.")
        except jwt.JWTClaimsError as exc:
            logger.warning("Token claims error: %s", exc)
            raise LogtoValidationError(code="INVALID_CLAIMS", message="Token claims verification failed.")
        except JWTError as exc:
            logger.warning("Token signature error: %s", exc)
            raise LogtoValidationError(code="INVALID_SIGNATURE", message="Token signature verification failed.")

        # 3. Validate subject presence
        sub = claims.get("sub")
        if not sub or not isinstance(sub, str) or not sub.strip():
            raise LogtoValidationError(code="MISSING_SUBJECT", message="Token missing subject ('sub') claim.")

        # 4. Extract and validate organization ID if expected or present
        # Logto organization tokens populate 'org_id', 'organization_id', or 'urn:logto:organization:id'
        token_org_id = (
            claims.get("org_id")
            or claims.get("organization_id")
            or claims.get("urn:logto:organization:id")
        )
        claims["normalized_org_id"] = token_org_id

        if expected_organization_id:
            if not token_org_id or token_org_id != expected_organization_id:
                raise LogtoValidationError(
                    code="ORGANIZATION_MISMATCH",
                    message="Token organization does not match expected organization context.",
                )

        return claims


# Global default validator instance
logto_validator = LogtoTokenValidator()
