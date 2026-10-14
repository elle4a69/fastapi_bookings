"""Authenticated Codex plugin discovery and installation endpoints.

The Codex app-server owns the plugin catalog and installation state.  This
router deliberately exposes only a sanitized projection of that state and
resolves install targets from the server-provided catalog instead of accepting
filesystem marketplace paths from the browser.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from backend.services.worker_manager import worker_manager


router = APIRouter(prefix="/codex/plugins", tags=["plugins"])

MARKETPLACE_KINDS = [
    "local",
    "vertical",
    "workspace-directory",
    "shared-with-me",
    "created-by-me-remote",
]


def _safe_web_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and bool(parsed.netloc) else None


def _sanitize_interface(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "displayName": value.get("displayName"),
        "shortDescription": value.get("shortDescription"),
        "longDescription": value.get("longDescription"),
        "developerName": value.get("developerName"),
        "category": value.get("category"),
        "capabilities": value.get("capabilities") if isinstance(value.get("capabilities"), list) else [],
        "websiteUrl": _safe_web_url(value.get("websiteUrl")),
        "privacyPolicyUrl": _safe_web_url(value.get("privacyPolicyUrl")),
        "termsOfServiceUrl": _safe_web_url(value.get("termsOfServiceUrl")),
        "defaultPrompt": value.get("defaultPrompt") if isinstance(value.get("defaultPrompt"), list) else [],
        "brandColor": value.get("brandColor"),
        "logoUrl": _safe_web_url(value.get("logoUrl")),
        "logoUrlDark": _safe_web_url(value.get("logoUrlDark")),
        "composerIconUrl": _safe_web_url(value.get("composerIconUrl")),
    }


def _sanitize_plugin_summary(plugin: dict[str, Any], marketplace: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": plugin.get("id"),
        "name": plugin.get("name"),
        "version": plugin.get("version"),
        "localVersion": plugin.get("localVersion"),
        "installed": bool(plugin.get("installed")),
        "enabled": bool(plugin.get("enabled")),
        "installPolicy": plugin.get("installPolicy"),
        "installPolicySource": plugin.get("installPolicySource"),
        "authPolicy": plugin.get("authPolicy"),
        "availability": plugin.get("availability"),
        "keywords": plugin.get("keywords") if isinstance(plugin.get("keywords"), list) else [],
        "interface": _sanitize_interface(plugin.get("interface")),
        "marketplace": {
            "name": marketplace.get("name"),
            "displayName": (marketplace.get("interface") or {}).get("displayName")
            if isinstance(marketplace.get("interface"), dict)
            else None,
            "remote": marketplace.get("path") is None,
        },
    }


def _sanitize_app(app: Any) -> dict[str, Any] | None:
    if not isinstance(app, dict):
        return None
    return {
        "id": app.get("id"),
        "name": app.get("name"),
        "description": app.get("description"),
        "category": app.get("category"),
        "installUrl": _safe_web_url(app.get("installUrl")),
    }


async def _get_worker() -> Any:
    try:
        worker = await worker_manager.get_worker()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Codex app-server is unavailable") from exc
    if not worker or not getattr(worker, "running", False):
        raise HTTPException(status_code=503, detail="Codex app-server is unavailable")
    return worker


async def _catalog(worker: Any) -> dict[str, Any]:
    try:
        result = await worker.send_request(
            "plugin/list",
            {"marketplaceKinds": MARKETPLACE_KINDS},
            timeout=90,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Codex plugin catalog could not be loaded") from exc
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Codex returned an invalid plugin catalog")
    return result


def _find_catalog_plugin(catalog: dict[str, Any], plugin_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for marketplace in catalog.get("marketplaces", []):
        if not isinstance(marketplace, dict):
            continue
        for plugin in marketplace.get("plugins", []):
            if isinstance(plugin, dict) and plugin.get("id") == plugin_id:
                return marketplace, plugin
    raise HTTPException(status_code=404, detail="Plugin not found in the current Codex catalog")


def _plugin_request_params(marketplace: dict[str, Any], plugin: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {"pluginName": plugin.get("name")}
    marketplace_path = marketplace.get("path")
    if isinstance(marketplace_path, str) and marketplace_path:
        params["marketplacePath"] = marketplace_path
    else:
        params["remoteMarketplaceName"] = marketplace.get("name")
    return params


@router.get("")
async def list_plugins() -> dict[str, Any]:
    """Return the current app-server plugin catalog without local source paths."""
    worker = await _get_worker()
    catalog = await _catalog(worker)
    plugins: list[dict[str, Any]] = []
    for marketplace in catalog.get("marketplaces", []):
        if not isinstance(marketplace, dict):
            continue
        for plugin in marketplace.get("plugins", []):
            if isinstance(plugin, dict):
                plugins.append(_sanitize_plugin_summary(plugin, marketplace))
    return {
        "plugins": plugins,
        "featuredPluginIds": catalog.get("featuredPluginIds", []),
        "marketplaceLoadErrors": catalog.get("marketplaceLoadErrors", []),
        "apiStatus": "under_development",
    }


@router.get("/{plugin_id}")
async def read_plugin(plugin_id: str) -> dict[str, Any]:
    """Read a plugin's capabilities, skills, and app authorization needs."""
    worker = await _get_worker()
    catalog = await _catalog(worker)
    marketplace, summary = _find_catalog_plugin(catalog, plugin_id)
    try:
        result = await worker.send_request(
            "plugin/read",
            _plugin_request_params(marketplace, summary),
            timeout=90,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Codex plugin details could not be loaded") from exc
    raw_detail = result.get("plugin") if isinstance(result, dict) else None
    if not isinstance(raw_detail, dict):
        raise HTTPException(status_code=502, detail="Codex returned invalid plugin details")

    skills = []
    for skill in raw_detail.get("skills", []):
        if isinstance(skill, dict):
            skills.append({
                "name": skill.get("name"),
                "description": skill.get("description"),
                "shortDescription": skill.get("shortDescription"),
                "enabled": bool(skill.get("enabled")),
            })
    apps = [safe for app in raw_detail.get("apps", []) if (safe := _sanitize_app(app))]
    return {
        "summary": _sanitize_plugin_summary(summary, marketplace),
        "description": raw_detail.get("description"),
        "shareUrl": _safe_web_url(raw_detail.get("shareUrl")),
        "skills": skills,
        "apps": apps,
        "mcpServers": raw_detail.get("mcpServers", []),
        "hooks": raw_detail.get("hooks", []),
    }


@router.post("/{plugin_id}/install")
async def install_plugin(plugin_id: str) -> dict[str, Any]:
    """Install an available plugin and return any app authorization links."""
    worker = await _get_worker()
    catalog = await _catalog(worker)
    marketplace, summary = _find_catalog_plugin(catalog, plugin_id)
    if summary.get("installed"):
        return {
            "pluginId": plugin_id,
            "installed": True,
            "alreadyInstalled": True,
            "authPolicy": summary.get("authPolicy"),
            "appsNeedingAuth": [],
        }
    if summary.get("installPolicy") not in (None, "AVAILABLE", "INSTALLED"):
        raise HTTPException(status_code=403, detail="Workspace policy does not allow this plugin to be installed")
    if summary.get("availability") not in (None, "AVAILABLE"):
        raise HTTPException(status_code=403, detail="This plugin is unavailable for the current account or workspace")

    try:
        result = await worker.send_request(
            "plugin/install",
            _plugin_request_params(marketplace, summary),
            timeout=120,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Codex could not install the plugin") from exc
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Codex returned an invalid plugin installation response")
    apps = [safe for app in result.get("appsNeedingAuth", []) if (safe := _sanitize_app(app))]
    return {
        "pluginId": plugin_id,
        "installed": True,
        "alreadyInstalled": False,
        "authPolicy": result.get("authPolicy"),
        "appsNeedingAuth": apps,
    }
