"""Security utilities for FastAPI Bookings.

This module provides helpers for hashing passwords, generating and
verifying JSON Web Tokens (JWTs), and standardizing token response
payloads. It relies on ``passlib`` for password hashing and
``python‑jose`` for JWT encoding/decoding.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings


# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the provided password matches the hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash the given password and return the hash."""
    return pwd_context.hash(password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a standardized JWT access token with standard claims.

    :param data: The payload to encode into the token. Includes standard claims
        such as ``sub``, ``tenant_id``, ``role``, etc.
    :param expires_delta: Optional timedelta specifying the token lifespan.
        Defaults to ``ACCESS_TOKEN_EXPIRE_MINUTES``.
    :return: Encoded JWT as a string.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    # Standard security claims: iss, aud, iat, exp (AUTH-004)
    to_encode.setdefault("iss", settings.JWT_ISSUER)
    to_encode.setdefault("aud", settings.JWT_AUDIENCE)

    if "iat" not in to_encode:
        to_encode["iat"] = int(now.timestamp())
    elif isinstance(to_encode["iat"], datetime):
        to_encode["iat"] = int(to_encode["iat"].timestamp())
    elif isinstance(to_encode["iat"], (int, float)):
        to_encode["iat"] = int(to_encode["iat"])

    if expires_delta is not None:
        expire = now + expires_delta
        to_encode["exp"] = int(expire.timestamp())
    elif "exp" not in to_encode:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode["exp"] = int(expire.timestamp())
    elif isinstance(to_encode["exp"], datetime):
        to_encode["exp"] = int(to_encode["exp"].timestamp())
    elif isinstance(to_encode["exp"], (int, float)):
        to_encode["exp"] = int(to_encode["exp"])

    # Ensure subject is string if provided
    if "sub" in to_encode and to_encode["sub"] is not None:
        to_encode["sub"] = str(to_encode["sub"])

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_access_token(
    token: str,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT access token against standard claims.

    Enforces cryptographic signature, expected issuer, expected audience,
    and expiration timestamp. Returns payload dict on success, None on failure.
    """
    if not token or not isinstance(token, str):
        return None

    if issuer is None:
        issuer = settings.JWT_ISSUER
    if audience is None:
        audience = settings.JWT_AUDIENCE

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            issuer=issuer,
            audience=audience,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_iat": True,
                "require_aud": True,
                "require_iss": True,
                "require_exp": True,
            },
        )
        return payload
    except JWTError:
        return None