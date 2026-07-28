from __future__ import annotations

from pathlib import Path

TARGET = Path(__file__).with_name("prepare_authenticated_sweep.py")
text = TARGET.read_text(encoding="utf-8")

text = text.replace(
    "from app.models.user import User\n",
    "from app.models.user import User\nfrom app.models.client import Client\n",
)

text = text.replace(
    "def token_values() -> tuple[str, str, int]:",
    "def token_values() -> tuple[str, str, str, int]:",
)

text = text.replace(
    "        admin_token = create_access_token({\"sub\": str(user.id), \"role\": user.role})\n"
    "        public_token = create_access_token({\"sub\": tenant.subdomain})\n"
    "        return admin_token, public_token, int(user.id)\n",
    "        client = db.query(Client).filter(Client.tenant_id == tenant.id).order_by(Client.id.asc()).first()\n"
    "        if client is None:\n"
    "            raise RuntimeError(\"No seeded client is available for client-token tests\")\n"
    "        admin_token = create_access_token({\"sub\": str(user.id), \"role\": user.role})\n"
    "        public_token = create_access_token({\"sub\": tenant.subdomain})\n"
    "        client_token = create_access_token({\"sub\": f\"client:{client.id}\", \"scope\": \"client\"})\n"
    "        return admin_token, public_token, client_token, int(user.id)\n",
)

insert_after = "def set_header(headers: list[dict], key: str, value: str) -> None:\n"
idx = text.index(insert_after)
end = text.index("\n\ndef normalise_url", idx)
helper = '''\n\ndef normalise_body_value(value, key: str | None, id_values: dict[str, str]):\n    if isinstance(value, dict):\n        return {k: normalise_body_value(v, k, id_values) for k, v in value.items()}\n    if isinstance(value, list):\n        return [normalise_body_value(v, key, id_values) for v in value]\n    if value is None:\n        return None\n    if not isinstance(value, str):\n        return value\n\n    exact = {\n        "<integer>": 1,\n        "<number>": 1.0,\n        "<boolean>": False,\n        "<date>": "2026-07-13",\n        "<dateTime>": "2026-07-13T10:00:00Z",\n        "<null>": None,\n        "<string>": "test",\n    }\n    if value in exact:\n        if key and key.endswith("_id"):\n            return int(id_values.get(key, "1"))\n        if key in {"company", "subdomain"}:\n            return TENANT\n        if key == "email":\n            return "postman-sweep@example.com"\n        if key == "phone":\n            return "+61400000000"\n        if key == "event":\n            return "booking.created"\n        if key == "code":\n            return "postman-sweep-code"\n        if key in {"url", "success_url", "cancel_url"}:\n            return "https://example.com/callback"\n        return exact[value]\n\n    if key and key.endswith("_id") and isinstance(value, str):\n        return int(id_values.get(key, "1"))\n    if key in {"company", "subdomain"}:\n        return TENANT\n    return value\n\n\ndef normalise_request_body(request: dict, id_values: dict[str, str], request_name: str) -> None:\n    body = request.get("body")\n    if not isinstance(body, dict) or body.get("mode") != "raw":\n        return\n    raw = body.get("raw")\n    if not isinstance(raw, str) or not raw.strip():\n        return\n    try:\n        payload = json.loads(raw)\n    except json.JSONDecodeError:\n        return\n    payload = normalise_body_value(payload, None, id_values)\n    if isinstance(payload, dict):\n        if payload.get("code") == "postman-sweep-code":\n            payload["code"] = "postman-" + re.sub(r"[^a-z0-9]+", "-", request_name.lower()).strip("-")\n        if "company" in payload:\n            payload["company"] = TENANT\n        if "event" in payload and payload["event"] in {"test", "<string>"}:\n            payload["event"] = "booking.created"\n    body["raw"] = json.dumps(payload, indent=2)\n'''
text = text[:end] + helper + text[end:]

text = text.replace(
    "def patch_items(items: list[dict], id_values: dict[str, str]) -> int:",
    "def patch_items(items: list[dict], id_values: dict[str, str]) -> int:",
)

text = text.replace(
    "        headers = request.setdefault(\"header\", [])\n",
    "        normalise_request_body(request, id_values, str(item.get(\"name\", \"request\")))\n"
    "        headers = request.setdefault(\"header\", [])\n",
)

text = text.replace(
    "        if path.startswith(\"/api/admin/\") or path.startswith(\"/api/public/\"):\n"
    "            set_header(headers, \"X-Tenant\", \"{{tenant}}\")\n",
    "        legacy_admin_paths = (\"/notifications\", \"/notification-templates\", \"/reminder-rules\")\n"
    "        if path.startswith(\"/api/admin/\") or path.startswith(\"/api/public/\") or path.startswith(legacy_admin_paths):\n"
    "            set_header(headers, \"X-Tenant\", \"{{tenant}}\")\n",
)

text = text.replace(
    "        elif path.startswith(\"/api/public/\") and path != \"/api/public/auth/token\":\n"
    "            set_header(headers, \"X-Token\", \"{{publicToken}}\")\n",
    "        elif path.startswith(legacy_admin_paths):\n"
    "            set_header(headers, \"X-Token\", \"{{adminToken}}\")\n"
    "        elif path.startswith(\"/api/public/\") and path != \"/api/public/auth/token\":\n"
    "            set_header(headers, \"X-Token\", \"{{publicToken}}\")\n"
    "        if path.startswith(\"/api/public/clients/me\"):\n"
    "            set_header(headers, \"X-Client-Token\", \"{{clientToken}}\")\n",
)

text = text.replace(
    "    admin_token, public_token, temp_user_id = token_values()\n",
    "    admin_token, public_token, client_token, temp_user_id = token_values()\n",
)

text = text.replace(
    "            {\"key\": \"publicToken\", \"value\": public_token, \"enabled\": True, \"type\": \"secret\"},\n",
    "            {\"key\": \"publicToken\", \"value\": public_token, \"enabled\": True, \"type\": \"secret\"},\n"
    "            {\"key\": \"clientToken\", \"value\": client_token, \"enabled\": True, \"type\": \"secret\"},\n",
)

TARGET.write_text(text, encoding="utf-8")
print("Sweep generator upgraded")
