"""Security utilities for FastAPI Bookings.

This module provides helpers for hashing passwords, generating and
verifying JSON Web Tokens (JWTs), and standardizing token response
payloads. It relies on ``passlib`` for password hashing and
``python‑jose`` for JWT encoding/decoding.
"""

from datetime import datetime, timedelta
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
    """Create a JWT access token.

    :param data: The payload to encode into the token. It should
        include a ``sub`` (subject) claim identifying the user.
    :param expires_delta: Optional timedelta specifying the token's
        lifespan. If omitted, defaults to ``ACCESS_TOKEN_EXPIRE_MINUTES``.
    :return: Encoded JWT as a string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT access token.

    Returns the decoded payload if the token is valid, otherwise
    returns ``None``.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None