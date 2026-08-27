import pytest
import jwt
from pydantic import ValidationError
from datetime import datetime, timedelta, timezone
from app.core.config import Settings, settings
from app.core.security import (encrypt_password,
                               verify_password,
                               create_access_token,
                               verify_access_token)


def test_encrypt_password():
    password = "test_password"
    encrypted_password = encrypt_password(password)
    assert password != encrypted_password
    assert len(encrypted_password) > len(password)


def test_verify_password():
    password = "test_password"
    wrong_password = "wrong_password"
    encrypted_password = encrypt_password(password)
    assert verify_password(password, encrypted_password) is True
    assert verify_password(wrong_password, encrypted_password) is False


def test_verify_access_token():
    user_data = {"sub": "test_user"}
    token = create_access_token(user_data)
    decoded_data = verify_access_token(token, Exception("Token verification failed"))
    assert decoded_data["sub"] == user_data["sub"]
    with pytest.raises(Exception) as e:
        verify_access_token("wrong_token", Exception("Token verification failed"))
    assert str(e.value) == "Token verification failed"


def test_create_access_token_positive():
    user_data = {"sub": "test_user"}
    token = create_access_token(user_data)

    assert isinstance(token, str)

    decoded_data = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm],
                              options={"verify_signature": False})
    assert decoded_data["sub"] == user_data["sub"]

    now = datetime.now(timezone.utc)
    exp = datetime.fromtimestamp(decoded_data["exp"], timezone.utc)
    delta = exp - now
    assert delta < timedelta(minutes=settings.access_token_expire_minutes + 1)
    assert delta > timedelta(minutes=settings.access_token_expire_minutes - 1)


def test_create_access_token_negative():
    with pytest.raises(Exception):
        invalid_data = "not_a_dict"
        create_access_token(invalid_data)


def test_settings_rejects_short_hs256_secret_key():
    with pytest.raises(ValidationError, match="secret_key is too short for HS256"):
        Settings(secret_key="bin_secret_key", algorithm="HS256")
