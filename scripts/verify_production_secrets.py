#!/usr/bin/env python3
"""Production secrets and configuration validation script.

Validates that when APP_ENV=production:
- Critical secrets (SECRET_KEY, PUBLIC_API_KEY, NEO4J_PASSWORD, DATABASE_URL)
  do not use default development values or weak placeholders.
- Development OTP bypasses are blocked and disabled.
- Status is reported as SECURE / INSECURE / MISSING without leaking or
  printing any sensitive secret values.

Conforms to Section 25 of the Production Readiness Specification.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Tuple
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Default/insecure values that must never appear in production
INSECURE_SECRET_KEYS = {
    "changeme",
    "secret",
    "dev",
    "development",
    "production-secret-key-must-be-configured",
    "test",
    "test-secret-key",
    "jwt-secret",
    "supersecret",
}

INSECURE_PUBLIC_API_KEYS = {
    "local-public-key-change-me",
    "production-public-key-must-be-configured",
    "changeme",
    "test",
    "public-key",
}

INSECURE_NEO4J_PASSWORDS = {
    "bookings_dev_neo4j_password",
    "neo4j",
    "password",
    "changeme",
    "admin",
    "secret",
}

OTP_BYPASS_ENV_VARS = [
    "DEV_OTP_BYPASS",
    "ALLOW_DEV_OTP",
    "OTP_BYPASS",
    "ENABLE_DEV_OTP",
    "DEV_OTP",
]


def check_secret_key(val: str | None) -> Tuple[str, str]:
    if not val:
        return "MISSING", "Secret key is not set or empty"
    val_lower = val.strip().lower()
    if val_lower in INSECURE_SECRET_KEYS or "change-me" in val_lower or "changeme" in val_lower:
        return "INSECURE", "Matches known default or template development secret"
    if len(val.strip()) < 32:
        return "INSECURE", "Length is under 32 characters; insufficient entropy for production"
    return "SECURE", "High-entropy non-default secret key configured"


def check_public_api_key(val: str | None) -> Tuple[str, str]:
    if not val:
        return "MISSING", "Public API key is not set or empty"
    val_lower = val.strip().lower()
    if val_lower in INSECURE_PUBLIC_API_KEYS or "change-me" in val_lower or "changeme" in val_lower:
        return "INSECURE", "Matches default development public API key"
    if len(val.strip()) < 16:
        return "INSECURE", "Length is under 16 characters"
    return "SECURE", "Non-default public API key configured"


def check_neo4j_password(val: str | None) -> Tuple[str, str]:
    if not val:
        return "MISSING", "Neo4j password is not set or empty"
    val_lower = val.strip().lower()
    if val_lower in INSECURE_NEO4J_PASSWORDS:
        return "INSECURE", "Matches default development Neo4j password"
    if len(val.strip()) < 8:
        return "INSECURE", "Password length is under 8 characters"
    return "SECURE", "Non-default Neo4j password configured"


def check_database_url(val: str | None) -> Tuple[str, str]:
    if not val:
        return "MISSING", "DATABASE_URL is not set or empty"
    if val.startswith("sqlite"):
        return "INSECURE", "SQLite is not permitted in production"

    try:
        parsed = urlparse(val)
        user = parsed.username
        password = parsed.password
        if user == "postgres" and password == "postgres":
            return "INSECURE", "Default postgres:postgres credentials in connection URL"
        if not password:
            return "INSECURE", "Database URL does not specify a password"
        if password in {"postgres", "password", "root", "changeme", "admin"}:
            return "INSECURE", "Database password matches known default value"
    except Exception as exc:
        return "INSECURE", f"Failed to parse database URL securely ({type(exc).__name__})"

    return "SECURE", "Production PostgreSQL connection URL with dedicated credentials"


def check_otp_bypasses() -> Tuple[str, str]:
    active_bypasses = []
    for var in OTP_BYPASS_ENV_VARS:
        raw = os.getenv(var, "").strip().lower()
        if raw in {"1", "true", "yes", "enabled", "on"}:
            active_bypasses.append(var)

    if active_bypasses:
        return "INSECURE", f"Active OTP bypass flags detected: {', '.join(active_bypasses)}"
    return "SECURE", "Development OTP bypass flags are disabled or unset"


def evaluate_secrets(app_env: str) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []

    # 1. SECRET_KEY
    status, detail = check_secret_key(os.getenv("SECRET_KEY"))
    results.append({"Item": "SECRET_KEY", "Status": status, "Detail": detail})

    # 2. PUBLIC_API_KEY
    status, detail = check_public_api_key(os.getenv("PUBLIC_API_KEY"))
    results.append({"Item": "PUBLIC_API_KEY", "Status": status, "Detail": detail})

    # 3. NEO4J_PASSWORD
    status, detail = check_neo4j_password(os.getenv("NEO4J_PASSWORD"))
    results.append({"Item": "NEO4J_PASSWORD", "Status": status, "Detail": detail})

    # 4. DATABASE_URL
    status, detail = check_database_url(os.getenv("DATABASE_URL"))
    results.append({"Item": "DATABASE_URL", "Status": status, "Detail": detail})

    # 5. OTP Bypasses
    status, detail = check_otp_bypasses()
    results.append({"Item": "DEV_OTP_BYPASS_GUARD", "Status": status, "Detail": detail})

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify production secrets, credentials, and security toggles."
    )
    parser.add_argument(
        "--env",
        dest="app_env",
        default=None,
        help="Target environment to evaluate against (default: APP_ENV env var or 'production').",
    )
    parser.add_argument(
        "--env-file",
        dest="env_file",
        default=".env",
        help="Path to environment file to load variables from (default: .env).",
    )
    args = parser.parse_args()

    if load_dotenv and args.env_file and os.path.exists(args.env_file):
        load_dotenv(args.env_file, override=False)

    target_env = (args.app_env or os.getenv("APP_ENV") or "production").strip().lower()
    is_prod = target_env in {"production", "prod"}

    print("=" * 80)
    print("PRODUCTION SECRETS & SECURITY TOGGLE VALIDATION (Section 25)")
    print(f"Target Environment: {target_env.upper()} (Enforce Strict: {is_prod})")
    print("=" * 80)
    print(f"{'CHECK ITEM':<26} | {'STATUS':<10} | {'DETAIL'}")
    print("-" * 80)

    results = evaluate_secrets(target_env)
    has_insecure = False
    has_missing = False

    for r in results:
        status = r["Status"]
        if status == "INSECURE":
            has_insecure = True
        elif status == "MISSING":
            has_missing = True
        print(f"{r['Item']:<26} | {status:<10} | {r['Detail']}")

    print("=" * 80)

    if is_prod:
        if has_insecure or has_missing:
            print("RESULT: FAILED - Insecure or missing secrets detected for production.")
            print("Action required: Set unique high-entropy credentials before deployment.")
            return 1
        print("RESULT: PASSED - All secrets, credentials, and OTP guards are SECURE for production.")
        return 0
    else:
        print(f"RESULT: COMPLETED - Non-production environment '{target_env}'.")
        if has_insecure or has_missing:
            print("Notice: Development default values detected (expected in local dev/staging).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
