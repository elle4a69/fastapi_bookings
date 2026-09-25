"""Unit tests for scripts/verify_production_secrets.py."""

from __future__ import annotations

import os
from unittest.mock import patch

from scripts.verify_production_secrets import (
    check_database_url,
    check_neo4j_password,
    check_otp_bypasses,
    check_public_api_key,
    check_secret_key,
    evaluate_secrets,
)


def test_check_secret_key():
    assert check_secret_key(None)[0] == "MISSING"
    assert check_secret_key("")[0] == "MISSING"
    assert check_secret_key("changeme")[0] == "INSECURE"
    assert check_secret_key("short")[0] == "INSECURE"
    assert check_secret_key("a" * 31)[0] == "INSECURE"
    assert check_secret_key("a" * 32)[0] == "SECURE"


def test_check_public_api_key():
    assert check_public_api_key(None)[0] == "MISSING"
    assert check_public_api_key("local-public-key-change-me")[0] == "INSECURE"
    assert check_public_api_key("short")[0] == "INSECURE"
    assert check_public_api_key("valid-public-api-key-12345")[0] == "SECURE"


def test_check_neo4j_password():
    assert check_neo4j_password(None)[0] == "MISSING"
    assert check_neo4j_password("bookings_dev_neo4j_password")[0] == "INSECURE"
    assert check_neo4j_password("admin")[0] == "INSECURE"
    assert check_neo4j_password("short")[0] == "INSECURE"
    assert check_neo4j_password("StrongNeo4jPassword99!")[0] == "SECURE"


def test_check_database_url():
    assert check_database_url(None)[0] == "MISSING"
    assert check_database_url("sqlite:///test.db")[0] == "INSECURE"
    assert check_database_url("postgresql://postgres:postgres@db:5432/fastapi_bookings")[0] == "INSECURE"
    assert check_database_url("postgresql://postgres@db:5432/fastapi_bookings")[0] == "INSECURE"
    assert check_database_url("postgresql://app_user:StrongSecretPass99@db:5432/fastapi_bookings")[0] == "SECURE"


def test_check_otp_bypasses():
    with patch.dict(os.environ, {"DEV_OTP_BYPASS": "1"}, clear=True):
        status, detail = check_otp_bypasses()
        assert status == "INSECURE"

    with patch.dict(os.environ, {"ALLOW_DEV_OTP": "true"}, clear=True):
        status, detail = check_otp_bypasses()
        assert status == "INSECURE"

    with patch.dict(os.environ, {}, clear=True):
        status, detail = check_otp_bypasses()
        assert status == "SECURE"


def test_evaluate_secrets_secure_in_production():
    secure_env = {
        "SECRET_KEY": "a" * 64,
        "PUBLIC_API_KEY": "b" * 32,
        "NEO4J_PASSWORD": "StrongPasswordNeo4j#2026",
        "DATABASE_URL": "postgresql://prod_user:StrongDbPass!2026@pg-host:5432/fastapi_bookings",
        "DEV_OTP_BYPASS": "0",
    }
    with patch.dict(os.environ, secure_env, clear=True):
        results = evaluate_secrets("production")
        assert len(results) == 5
        for item in results:
            assert item["Status"] == "SECURE"
