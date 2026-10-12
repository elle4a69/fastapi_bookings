import time
import logging
from typing import Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.codex import SystemSetting

logger = logging.getLogger("codex.telemetry_settings")

KEY_SIGNOZ_URL = "telemetry_signoz_url"
KEY_OTLP_ENDPOINT = "telemetry_otlp_endpoint"
KEY_ENABLED = "telemetry_enabled"


def get_setting_value(db: Session, key: str, default: str) -> str:
    try:
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row:
            return row.value
    except Exception as e:
        logger.debug(f"Failed to read system setting '{key}': {e}")
    return default


def set_setting_value(db: Session, key: str, value: str) -> None:
    try:
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row:
            row.value = value
        else:
            row = SystemSetting(key=key, value=value)
            db.add(row)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist system setting '{key}': {e}")
        db.rollback()


async def test_endpoint_connectivity(endpoint: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Tests reachability of the provided HTTP/OTLP endpoint and returns truthful latency and status."""
    clean_url = endpoint.strip().rstrip("/")
    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = None
            # 1. Try /api/v1/health or /healthz or /
            for path in ["/api/v1/health", "/healthz", ""]:
                try:
                    resp = await client.get(f"{clean_url}{path}")
                    if resp.status_code < 500:
                        break
                except Exception:
                    continue

            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if resp is not None and resp.status_code < 500:
                return {
                    "connected": True,
                    "status": "Connected",
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "url": clean_url,
                }
            elif resp is not None:
                return {
                    "connected": False,
                    "status": f"HTTP {resp.status_code} Error",
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "url": clean_url,
                }
            else:
                return {
                    "connected": False,
                    "status": "Unreachable",
                    "error": "No response from collector endpoint",
                    "latency_ms": latency_ms,
                    "url": clean_url,
                }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "connected": False,
            "status": "Unreachable",
            "error": str(exc),
            "latency_ms": latency_ms,
            "url": clean_url,
        }


async def get_telemetry_settings(db: Session) -> Dict[str, Any]:
    signoz_url = get_setting_value(db, KEY_SIGNOZ_URL, getattr(settings, "signoz_url", "http://localhost:3301"))
    otlp_endpoint = get_setting_value(db, KEY_OTLP_ENDPOINT, getattr(settings, "otlp_endpoint", "http://localhost:4318"))
    enabled_str = get_setting_value(db, KEY_ENABLED, "false" if getattr(settings, "otel_sdk_disabled", True) else "true")
    enabled = enabled_str.lower() in ("true", "1", "yes")

    # Run reachability probe on active OTLP endpoint
    probe = await test_endpoint_connectivity(otlp_endpoint, timeout=1.5)

    return {
        "signoz_url": signoz_url,
        "otlp_endpoint": otlp_endpoint,
        "enabled": enabled,
        "otel_sdk_disabled": not enabled,
        "connected": probe.get("connected", False),
        "status": probe.get("status", "Unknown"),
        "latency_ms": probe.get("latency_ms", 0.0),
    }


def update_telemetry_settings(db: Session, signoz_url: str, otlp_endpoint: str, enabled: bool) -> Dict[str, Any]:
    clean_signoz = signoz_url.strip()
    clean_otlp = otlp_endpoint.strip()

    set_setting_value(db, KEY_SIGNOZ_URL, clean_signoz)
    set_setting_value(db, KEY_OTLP_ENDPOINT, clean_otlp)
    set_setting_value(db, KEY_ENABLED, "true" if enabled else "false")

    # Update runtime config
    settings.signoz_url = clean_signoz
    settings.otlp_endpoint = clean_otlp
    settings.otel_sdk_disabled = not enabled

    return {
        "signoz_url": clean_signoz,
        "otlp_endpoint": clean_otlp,
        "enabled": enabled,
        "otel_sdk_disabled": not enabled,
        "status": "Saved",
    }
