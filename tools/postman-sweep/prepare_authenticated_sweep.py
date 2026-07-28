from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.models  # noqa: F401 - registers all SQLAlchemy models
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.database import Base, SessionLocal
from app.models.tenant import Tenant
from app.models.user import User
from app.models.client import Client

TOOL_DIR = Path(__file__).resolve().parent
SOURCE = TOOL_DIR / "FastAPI-Bookings-Local.postman_collection.json"
OUTPUT = TOOL_DIR / "FastAPI-Bookings-Local-Authenticated.postman_collection.json"
ENVIRONMENT = TOOL_DIR / "SimplyDemo-Local.postman_environment.json"
TEMP_USER_FILE = TOOL_DIR / ".sweep-temp-user-id"
TEMP_CLIENT_FILE = TOOL_DIR / ".sweep-temp-client-id"

TENANT = "simplydemo"
BASE_URL = os.environ.get("POSTMAN_BASE_URL", "http://127.0.0.1:8000")
TEMP_LOGIN = "__postman_sweep_owner__"
TEMP_ADMIN_PASSWORD = "PostmanAdmin123!"
TEMP_CLIENT_EMAIL = "__postman_sweep_client__@example.com"
TEMP_CLIENT_PASSWORD = "Postman123!"
RUN_SUFFIX = uuid4().hex[:10]


STATE_VARIABLES = {
    "service_id": "serviceId",
    "provider_id": "providerId",
    "client_id": "clientId",
    "location_id": "locationId",
    "category_id": "categoryId",
    "resource_id": "resourceId",
    "add_on_id": "addonId",
    "addon_id": "addonId",
    "product_id": "productId",
    "package_id": "packageId",
    "step_id": "packageStepId",
    "workday_id": "workdayId",
    "day_id": "specialDayId",
    "block_id": "blockedTimeId",
    "reserved_id": "reservedTimeId",
    "field_id": "additionalFieldId",
    "promotion_id": "promotionId",
    "tax_rate_id": "taxRateId",
    "webhook_id": "webhookId",
    "note_id": "calendarNoteId",
    "template_id": "notificationTemplateId",
    "rule_id": "reminderRuleId",
    "notification_id": "notificationId",
    "payment_id": "paymentId",
    "booking_id": "bookingId",
    "hold_id": "holdId",
    "series_id": "seriesId",
    "review_id": "reviewId",
    "invoice_id": "invoiceId",
    "config_id": "paymentConfigId",
}

CREATE_CAPTURE_VARIABLES = {
    "Create Service": "serviceId",
    "Create Provider": "providerId",
    "Create Client": "clientId",
    "Create Location": "locationId",
    "Create Category": "categoryId",
    "Create Resource": "resourceId",
    "Create Addon": "addonId",
    "Create Product": "productId",
    "Create Package": "packageId",
    "Add Package Step": "packageStepId",
    "Create Workday": "workdayId",
    "Create Special Day": "specialDayId",
    "Create Blocked Time": "blockedTimeId",
    "Create Reserved Time": "reservedTimeId",
    "Create Additional Field": "additionalFieldId",
    "Create Promotion": "promotionId",
    "Create Tax Rate": "taxRateId",
    "Create Webhook": "webhookId",
    "Create Calendar Note": "calendarNoteId",
    "Create Notification Template": "notificationTemplateId",
    "Create Reminder Rule": "reminderRuleId",
    "Create Notification": "notificationId",
    "Create Payment": "paymentId",
    "Create Booking": "bookingId",
    "Create Public Booking": "bookingId",
    "Create Hold Endpoint": "holdId",
    "Create Series": "seriesId",
    "Submit Review Request": "reviewId",
    "Create Public Invoice": "invoiceId",
}


def add_capture_script(item: dict) -> None:
    variable = CREATE_CAPTURE_VARIABLES.get(str(item.get("name", "")))
    if not variable:
        return
    script = [
        "if (pm.response.code >= 200 && pm.response.code < 300) {",
        "  try {",
        "    const payload = pm.response.json();",
        "    const data = payload && payload.data !== undefined ? payload.data : payload;",
        "    let id = data && data.id;",
        "    if (!id && data) id = data.client_id || data.booking_id || data.hold_id || data.invoice_id;",
        f"    if (id !== undefined && id !== null) {{ pm.environment.set('{variable}', String(id)); pm.environment.set('{variable}Created', 'true'); }}",
        "  } catch (error) {}",
        "}",
    ]
    item.setdefault("event", []).append({
        "listen": "test",
        "script": {"type": "text/javascript", "exec": script},
    })


DELETE_GUARD_VARIABLES = {
    "Delete Service": "serviceId",
    "Delete Provider": "providerId",
    "Delete Client": "clientId",
    "Delete Location": "locationId",
    "Delete Category": "categoryId",
    "Delete Resource": "resourceId",
    "Delete Addon": "addonId",
    "Delete Product": "productId",
    "Delete Package": "packageId",
    "Delete Package Step": "packageStepId",
    "Delete Workday": "workdayId",
    "Delete Special Day": "specialDayId",
    "Delete Blocked Time": "blockedTimeId",
    "Delete Reserved Time": "reservedTimeId",
    "Delete Additional Field": "additionalFieldId",
    "Delete Promotion": "promotionId",
    "Delete Tax Rate": "taxRateId",
    "Delete Webhook": "webhookId",
    "Delete Calendar Note": "calendarNoteId",
    "Delete Notification Template": "notificationTemplateId",
    "Delete Reminder Rule": "reminderRuleId",
}


def add_delete_guard(item: dict) -> None:
    variable = DELETE_GUARD_VARIABLES.get(str(item.get("name", "")))
    if not variable:
        return
    script = [
        f"if (pm.environment.get('{variable}Created') !== 'true') pm.environment.set('{variable}', '999999');",
    ]
    item.setdefault("event", []).append({
        "listen": "prerequest",
        "script": {"type": "text/javascript", "exec": script},
    })


def token_values() -> tuple[str, str, str, int]:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.subdomain == TENANT).first()
        if tenant is None:
            raise RuntimeError(f"Tenant {TENANT!r} was not found")

        stale = db.query(User).filter(User.tenant_id == tenant.id, User.login == TEMP_LOGIN).all()
        for row in stale:
            db.delete(row)
        if stale:
            db.commit()

        user = User(
            tenant_id=tenant.id,
            login=TEMP_LOGIN,
            password_hash=get_password_hash(TEMP_ADMIN_PASSWORD),
            role="owner",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        stale_clients = db.query(Client).filter(Client.tenant_id == tenant.id, Client.email == TEMP_CLIENT_EMAIL).all()
        for row in stale_clients:
            db.delete(row)
        if stale_clients:
            db.commit()

        client = Client(
            tenant_id=tenant.id,
            name="Postman Sweep Client",
            email=TEMP_CLIENT_EMAIL,
            phone="+61400000001",
            password_hash=get_password_hash(TEMP_CLIENT_PASSWORD),
            active=True,
            accepts_marketing=False,
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        TEMP_CLIENT_FILE.write_text(str(client.id), encoding="utf-8")

        admin_token = create_access_token({"sub": str(user.id), "role": user.role})
        public_token = create_access_token({"sub": tenant.subdomain})
        client_token = create_access_token({"sub": f"client:{client.id}", "scope": "client"})
        return admin_token, public_token, client_token, int(user.id)
    finally:
        db.close()


def discover_path_values() -> dict[str, str]:
    """Return concrete seeded IDs for Postman/OpenAPI path parameters."""
    db = SessionLocal()
    values: dict[str, str] = {}
    try:
        tenant = db.query(Tenant).filter(Tenant.subdomain == TENANT).first()
        if tenant is None:
            raise RuntimeError(f"Tenant {TENANT!r} was not found")

        for mapper in Base.registry.mappers:
            model = mapper.class_
            if not hasattr(model, "id"):
                continue
            query = db.query(model)
            if hasattr(model, "tenant_id"):
                query = query.filter(model.tenant_id == tenant.id)
            if hasattr(model, "deleted_at"):
                query = query.filter(model.deleted_at.is_(None))
            row = query.order_by(model.id.asc()).first()
            if row is None:
                continue

            value = str(row.id)
            table = str(getattr(model, "__tablename__", ""))
            class_name = re.sub(r"(?<!^)(?=[A-Z])", "_", model.__name__).lower()
            candidates = {
                f"{class_name}_id",
                f"{table.rstrip('s')}_id",
                f"{table}_id",
            }
            for candidate in candidates:
                values[candidate] = value

        values.update(
            {
                "tenant_id": str(tenant.id),
                "user_id": values.get("user_id", "1"),
                "add_on_id": values.get("addon_id", values.get("add_on_id", "1")),
                "day_id": values.get("provider_special_day_id", values.get("special_day_id", "1")),
                "block_id": values.get("blocked_time_id", "1"),
                "reserved_id": values.get("reserved_time_id", "1"),
                "rule_id": values.get("reminder_rule_id", "1"),
                "field_id": values.get("additional_field_id", "1"),
                "config_id": values.get("payment_processor_config_id", "1"),
                "note_id": values.get("calendar_note_id", "1"),
                "review_id": values.get("management_review_request_id", "1"),
                "step_id": values.get("package_step_id", "1"),
                "name": "test-plugin",
                "code": "TEST",
            }
        )
        return values
    finally:
        db.close()


def set_header(headers: list[dict], key: str, value: str) -> None:
    for header in headers:
        if str(header.get("key", "")).lower() == key.lower():
            header["value"] = value
            header["type"] = "text"
            return
    headers.append({"key": key, "value": value, "type": "text"})


def replacement_for(name: str, path_values: dict[str, str], method: str) -> str:
    variable = STATE_VARIABLES.get(name)
    if variable:
        return "{{" + variable + "}}"
    if name in path_values:
        return path_values[name]
    if name.endswith("_id"):
        return "1"
    return "test"


def normalise_body_value(value, key: str | None, id_values: dict[str, str]):
    if isinstance(value, dict):
        return {k: normalise_body_value(v, k, id_values) for k, v in value.items()}
    if isinstance(value, list):
        return [normalise_body_value(v, key, id_values) for v in value]
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    if re.fullmatch(r"\{\{[^{}]+\}\}", value):
        return value

    exact = {
        "<integer>": 1,
        "<number>": 1.0,
        "<boolean>": False,
        "<date>": "2026-07-13",
        "<dateTime>": "2026-07-13T10:00:00Z",
        "<null>": None,
        "<string>": "test",
    }
    if value in exact:
        if key in {"stripe_session_id", "device_id"}:
            return "postman-test-id"
        if key and key.endswith("_id"):
            return int(id_values.get(key, "1"))
        if key in {"company", "subdomain"}:
            return TENANT
        if key == "email":
            return "postman-sweep@example.com"
        if key == "password":
            return "Postman123!"
        if key in {"stripe_session_id", "device_id"}:
            return "postman-test-id"
        if key == "phone":
            return "+61400000000"
        if key == "event":
            return "booking.created"
        if key == "code":
            return "postman-sweep-code"
        if key in {"url", "success_url", "cancel_url"}:
            return "https://example.com/callback"
        return exact[value]

    if key in {"stripe_session_id", "device_id"}:
        return "postman-test-id"
    if key and key.endswith("_id") and isinstance(value, str):
        return int(id_values.get(key, "1"))
    if key in {"company", "subdomain"}:
        return TENANT
    return value


def add_login_capture_script(item: dict) -> None:
    name = str(item.get("name", ""))
    variable = None
    if name == "Admin Login":
        variable = "adminToken"
    elif name == "Public Login":
        variable = "publicToken"
    if not variable:
        return
    script = [
        "if (pm.response.code >= 200 && pm.response.code < 300) {",
        "  try {",
        "    const payload = pm.response.json();",
        "    const token = payload && payload.data && payload.data.access_token;",
        f"    if (token) pm.environment.set('{variable}', token);",
        "  } catch (error) {}",
        "}",
    ]
    item.setdefault("event", []).append({
        "listen": "test",
        "script": {"type": "text/javascript", "exec": script},
    })


def normalise_request_body(request: dict, id_values: dict[str, str], request_name: str) -> None:
    body = request.get("body")
    if not isinstance(body, dict) or body.get("mode") != "raw":
        return
    raw = body.get("raw")
    if not isinstance(raw, str) or not raw.strip():
        return
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return
    payload = normalise_body_value(payload, None, id_values)
    if isinstance(payload, dict):
        slug = re.sub(r"[^a-z0-9]+", "-", request_name.lower()).strip("-")
        if payload.get("code") == "postman-sweep-code":
            payload["code"] = "postman-" + slug + "-" + RUN_SUFFIX
        if payload.get("sku") in {"test", "<string>"}:
            payload["sku"] = "postman-" + slug + "-" + RUN_SUFFIX
        if "company" in payload:
            payload["company"] = TENANT
        if request_name not in {"Login Client", "Register Client"}:
            if payload.get("email") == "postman-sweep@example.com":
                payload["email"] = f"postman-{RUN_SUFFIX}@example.com"
            if payload.get("login") in {"test", "<string>"}:
                payload["login"] = f"postman-{RUN_SUFFIX}"
        if request_name == "Admin Login":
            payload["company"] = TENANT
            payload["login"] = TEMP_LOGIN
            payload["password"] = TEMP_ADMIN_PASSWORD
        elif request_name == "Public Login":
            payload["company"] = TENANT
            payload["key"] = settings.PUBLIC_API_KEY
        elif request_name == "Login Client":
            payload["email"] = TEMP_CLIENT_EMAIL
            payload["password"] = TEMP_CLIENT_PASSWORD
        if request_name in {"Create Booking", "Create Public Booking"}:
            from datetime import datetime, timedelta, timezone
            offset = int(uuid4().hex[:6], 16) % 120
            start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=45, minutes=offset * 30)
            payload["start_time"] = start.isoformat().replace("+00:00", "Z")
            payload["end_time"] = (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
        if request_name == "Reschedule Booking":
            from datetime import datetime, timedelta, timezone
            offset = int(uuid4().hex[:6], 16) % 120
            start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=60, minutes=offset * 30)
            payload["new_start"] = start.isoformat().replace("+00:00", "Z")
            payload["new_end"] = (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
        if "event" in payload and payload["event"] in {"test", "<string>"}:
            payload["event"] = "booking.created"
    body["raw"] = json.dumps(payload, indent=2)


def normalise_url(raw: str, method: str, path_values: dict[str, str]) -> str:
    raw = raw.replace("{{baseUrl}}", BASE_URL)
    safe_id = "1" if method == "GET" else "999999"
    raw = re.sub(r"<integer>", safe_id, raw)
    raw = re.sub(r"<number>", "1", raw)
    raw = re.sub(r"<boolean>", "false", raw)
    raw = re.sub(r"<dateTime>", "2026-07-13T10:00:00Z", raw)
    raw = re.sub(r"<date>", "2026-07-13", raw)
    raw = re.sub(r"<string>", "test", raw)

    raw = re.sub(
        r"(?<=/):([A-Za-z_][A-Za-z0-9_]*)",
        lambda match: replacement_for(match.group(1), path_values, method),
        raw,
    )
    raw = re.sub(
        r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})",
        lambda match: replacement_for(match.group(1), path_values, method),
        raw,
    )

    parts = urlsplit(raw)
    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        replacements = {
            "<integer>": "1",
            "integer": "1",
            "<number>": "1",
            "number": "1",
            "<boolean>": "false",
            "boolean": "false",
            "<date>": "2026-07-13",
            "date": "2026-07-13",
            "<dateTime>": "2026-07-13T10:00:00Z",
            "dateTime": "2026-07-13T10:00:00Z",
            "<string>": "test",
            "string": "test",
        }
        value = replacements.get(value, value)
        if key in {"success_url", "cancel_url"}:
            value = "https://example.com/callback"
        elif key == "amount_cents":
            value = "100"
        if value.startswith(":"):
            value = replacement_for(value[1:], path_values, method)
        query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def patch_items(items: list[dict], path_values: dict[str, str]) -> int:
    count = 0
    for item in items:
        if "item" in item:
            count += patch_items(item["item"], path_values)
            continue
        request = item.get("request")
        if not request:
            continue

        method = str(request.get("method", "GET")).upper()
        url = request.get("url")
        if isinstance(url, dict):
            raw = str(url.get("raw") or "")
            if not raw:
                host = url.get("host", [])
                host_text = ".".join(host) if isinstance(host, list) else str(host or "")
                path_parts = url.get("path", [])
                path_text = "/".join(str(part) for part in path_parts) if isinstance(path_parts, list) else str(path_parts or "")
                raw = host_text.rstrip("/") + "/" + path_text.lstrip("/")
                query_parts = []
                for entry in url.get("query", []) or []:
                    if not entry.get("disabled"):
                        query_parts.append((str(entry.get("key", "")), str(entry.get("value", ""))))
                if query_parts:
                    raw += "?" + urlencode(query_parts)
        else:
            raw = str(url or "")

        raw = normalise_url(raw, method, path_values)
        parsed = urlsplit(raw)
        request["url"] = {
            "raw": raw,
            "protocol": parsed.scheme,
            "host": [parsed.hostname] if parsed.hostname else [],
            "port": str(parsed.port) if parsed.port else None,
            "path": [part for part in parsed.path.split("/") if part],
            "query": [
                {"key": key, "value": value}
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            ],
            "variable": [],
        }

        normalise_request_body(request, path_values, str(item.get("name", "request")))
        add_capture_script(item)
        add_login_capture_script(item)
        add_delete_guard(item)
        headers = request.setdefault("header", [])
        path = parsed.path
        legacy_admin_paths = ("/notifications", "/notification-templates", "/reminder-rules")
        if path.startswith("/api/admin/") or path.startswith("/api/public/") or path.startswith(legacy_admin_paths):
            set_header(headers, "X-Tenant", "{{tenant}}")
        if path.startswith("/api/admin/") and path != "/api/admin/auth":
            set_header(headers, "X-Token", "{{adminToken}}")
        elif path.startswith(legacy_admin_paths):
            set_header(headers, "X-Token", "{{adminToken}}")
        elif path.startswith("/api/public/") and path != "/api/public/auth/token":
            set_header(headers, "X-Token", "{{publicToken}}")
        if path.startswith("/api/public/clients/me"):
            set_header(headers, "X-Client-Token", "{{clientToken}}")
        count += 1
    return count


def set_booking_request_time(item: dict, day_offset: int) -> None:
    from datetime import datetime, timedelta, timezone

    request = item.get("request") or {}
    body = request.get("body") or {}
    if body.get("mode") != "raw":
        return
    try:
        payload = json.loads(body.get("raw") or "{}")
    except json.JSONDecodeError:
        return
    start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=day_offset)
    payload["start_time"] = start.isoformat().replace("+00:00", "Z")
    payload["end_time"] = (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    body["raw"] = json.dumps(payload, indent=2)


def split_booking_transition_workflows(items: list[dict]) -> None:
    """Give complete, no-show and reschedule independent confirmed bookings."""
    for container in items:
        children = container.get("item")
        if not isinstance(children, list):
            continue
        by_name = {str(child.get("name", "")): child for child in children if "request" in child}
        create = by_name.get("Create Booking")
        confirm = by_name.get("Confirm Booking")
        targets = {
            "Complete Booking": (70, "Complete"),
            "Noshow Booking": (80, "No-show"),
            "Reschedule Booking": (90, "Reschedule"),
        }
        if create and confirm and any(name in by_name for name in targets):
            rebuilt = []
            for child in children:
                name = str(child.get("name", ""))
                if name in targets:
                    day_offset, label = targets[name]
                    create_clone = copy.deepcopy(create)
                    create_clone["name"] = f"Create Booking For {label}"
                    set_booking_request_time(create_clone, day_offset)
                    confirm_clone = copy.deepcopy(confirm)
                    confirm_clone["name"] = f"Confirm Booking For {label}"
                    rebuilt.extend([create_clone, confirm_clone, child])
                else:
                    rebuilt.append(child)
            container["item"] = rebuilt
        split_booking_transition_workflows(container.get("item", []))


def find_request_item(items: list[dict], target_name: str) -> dict | None:
    for item in items:
        if str(item.get("name", "")) == target_name and "request" in item:
            return item
        children = item.get("item")
        if isinstance(children, list):
            found = find_request_item(children, target_name)
            if found:
                return found
    return None


def remove_request_names(items: list[dict], names: set[str]) -> None:
    retained = []
    for item in items:
        children = item.get("item")
        if isinstance(children, list):
            remove_request_names(children, names)
        if str(item.get("name", "")) in names and "request" in item:
            continue
        retained.append(item)
    items[:] = retained


def build_booking_transition_workflows(items: list[dict]) -> None:
    create = find_request_item(items, "Create Booking")
    confirm = find_request_item(items, "Confirm Booking")
    actions = {
        "Complete Booking": (70, "Complete"),
        "Noshow Booking": (80, "No-show"),
        "Reschedule Booking": (90, "Reschedule"),
    }
    if not create or not confirm:
        return
    originals = {name: find_request_item(items, name) for name in actions}
    remove_request_names(items, set(actions))
    workflow_items = []
    for action_name, (day_offset, label) in actions.items():
        action = originals.get(action_name)
        if not action:
            continue
        create_clone = copy.deepcopy(create)
        create_clone["name"] = f"Create Booking For {label}"
        set_booking_request_time(create_clone, day_offset)
        confirm_clone = copy.deepcopy(confirm)
        confirm_clone["name"] = f"Confirm Booking For {label}"
        workflow_items.extend([create_clone, confirm_clone, action])
    if workflow_items:
        items.append({"name": "Booking Transition Workflows", "item": workflow_items})



def set_json_body(item: dict, updates: dict) -> None:
    request = item.get("request") or {}
    body = request.get("body") or {}
    if body.get("mode") != "raw":
        return
    try:
        payload = json.loads(body.get("raw") or "{}")
    except json.JSONDecodeError:
        payload = {}
    payload.update(updates)
    body["raw"] = json.dumps(payload, indent=2)


def add_nested_field_id_script(item: dict) -> None:
    if str(item.get("name", "")) != "Create Additional Field":
        return
    script = [
        "if (pm.response.code >= 200 && pm.response.code < 300) {",
        "  try {",
        "    const p = pm.response.json(); const d = p.data !== undefined ? p.data : p;",
        "    if (d && d.id) { pm.environment.set('additionalFieldId', String(d.id)); pm.environment.set('additionalFieldIdCreated', 'true'); }",
        "  } catch (e) {}",
        "}",
    ]
    item.setdefault("event", []).append({"listen": "test", "script": {"type": "text/javascript", "exec": script}})


def configure_remaining_workflows(items: list[dict]) -> None:
    from datetime import datetime, timedelta, timezone

    # Canonical route policy: retain /api/admin notification routes, remove legacy aliases.
    def prune(nodes: list[dict]) -> None:
        kept = []
        for node in nodes:
            children = node.get("item")
            if isinstance(children, list):
                prune(children)
            req = node.get("request") or {}
            url = req.get("url") or {}
            raw = url.get("raw", "") if isinstance(url, dict) else str(url)
            path = urlsplit(raw).path
            if path.startswith(("/notification-templates", "/reminder-rules", "/notifications")):
                continue
            kept.append(node)
        nodes[:] = kept
    prune(items)
    remove_request_names(items, {"Delete Client", "Unlink Location Category"})

    # Plugin state must exist before toggle.
    toggle = find_request_item(items, "Toggle Plugin State")
    upsert = find_request_item(items, "Upsert Plugin State")
    if not upsert:
        upsert = find_request_item(items, "Create Plugin State")
    if toggle and upsert:
        setup = copy.deepcopy(upsert)
        setup["name"] = "Setup Plugin State"
        set_json_body(setup, {"name": "test-plugin", "is_enabled": True})
        set_json_body(toggle, {"is_enabled": False})
        items.append({"name": "Plugin State Workflow", "item": [setup, toggle]})
        remove_request_names(items[:-1], {"Toggle Plugin State"})

    # Resolve a freshly captured review with an accepted target state.
    resolve = find_request_item(items, "Resolve Review Request")
    if resolve:
        set_json_body(resolve, {"state": "approved", "resolution_notes": "Postman sweep approval"})
    submit = find_request_item(items, "Submit Review Request")
    if submit:
        future = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=110)
        set_json_body(submit, {"preferred_time": future.isoformat().replace("+00:00", "Z"), "reason": f"postman-{RUN_SUFFIX}"})

    # Additional field submission uses the captured field and temporary client.
    create_field = find_request_item(items, "Create Additional Field")
    if create_field:
        set_json_body(create_field, {
            "scope": "booking",
            "service_id": None,
            "name": f"postman_field_{RUN_SUFFIX}",
            "label": "Postman Field",
            "field_type": "text",
            "required": False,
            "active": True,
            "position": 0,
        })
        add_nested_field_id_script(create_field)
    submit_fields = find_request_item(items, "Submit Public Additional Field Responses")
    if submit_fields:
        set_json_body(submit_fields, {
            "client_id": int(path_values_global.get("client_id", "1")),
            "booking_id": None,
            "responses": [{"field_id": "{{additionalFieldId}}", "client_id": int(path_values_global.get("client_id", "1")), "booking_id": None, "value": "Postman response"}],
        })

    # Update booking should be a valid neutral update, not force a terminal state.
    update_booking = find_request_item(items, "Update Booking")
    if update_booking:
        request = update_booking.get("request") or {}
        body = request.get("body") or {}
        try:
            payload = json.loads(body.get("raw") or "{}")
        except json.JSONDecodeError:
            payload = {}
        payload.pop("status", None)
        payload["notes"] = "Updated by Postman lifecycle sweep"
        body["raw"] = json.dumps(payload, indent=2)

    # Client registration tests a distinct account rather than the pre-created login client.
    register = find_request_item(items, "Register Client")
    if register:
        set_json_body(register, {
            "name": "Postman Registered Client",
            "email": f"registered-{RUN_SUFFIX}@example.com",
            "phone": "+61400000002",
            "password": "Postman123!",
            "accept_terms": True,
            "accept_privacy": True,
        })

    # Build a fresh hold lifecycle at a non-overlapping future time.
    create_hold = find_request_item(items, "Create Hold Endpoint")
    confirm_hold = find_request_item(items, "Confirm Hold Endpoint")
    cancel_hold = find_request_item(items, "Cancel Hold Endpoint")
    if create_hold and confirm_hold:
        from app.services.scheduling_service import compute_availability
        db = SessionLocal()
        try:
            service_id = int(path_values_global.get("service_id", "1"))
            provider_id = int(path_values_global.get("provider_id", "1"))
            from app.models.service import Service
            from app.models.provider import Provider
            service = db.query(Service).filter(Service.id == service_id).first()
            provider = db.query(Provider).filter(Provider.id == provider_id).first()
            start = None
            end = None
            if service:
                for days in range(1, 91):
                    probe = datetime.now(timezone.utc) + timedelta(days=days)
                    day_start = probe.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)
                    slots = compute_availability(db, service=service, provider=provider, start_time=day_start, end_time=day_end, desired_duration=service.duration)
                    if slots:
                        start = datetime.fromisoformat(slots[0]["start_time"])
                        end = datetime.fromisoformat(slots[0]["end_time"])
                        break
            if start is None or end is None:
                start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=130)
                end = start + timedelta(minutes=30)
        finally:
            db.close()
        set_json_body(create_hold, {
            "service_id": int(path_values_global.get("service_id", "1")),
            "provider_id": None,
            "location_id": None,
            "client_id": int(path_values_global.get("client_id", "1")),
            "start_time": start.isoformat().replace("+00:00", "Z"),
            "end_time": end.isoformat().replace("+00:00", "Z"),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        })
        set_json_body(confirm_hold, {"hold_id": "{{holdId}}", "client_details": None})
        workflow = [copy.deepcopy(create_hold), copy.deepcopy(confirm_hold)]
        items.append({"name": "Hold Confirmation Workflow", "item": workflow})
        remove_request_names(items[:-1], {"Confirm Hold Endpoint"})
        if cancel_hold:
            # The original cancel remains a negative/cleanup path; guard it from cancelling a confirmed hold.
            remove_request_names(items[:-1], {"Cancel Hold Endpoint"})


def rebuild_remaining_dedicated_workflows(items: list[dict]) -> None:
    """Replace duplicate/order-sensitive operations with one deterministic lifecycle each."""
    # Capture templates before removing originals.
    update_booking = find_request_item(items, "Update Booking")
    create_field = find_request_item(items, "Create Additional Field")
    submit_fields = find_request_item(items, "Submit Public Additional Field Responses")
    submit_review = find_request_item(items, "Submit Review Request")
    resolve_review = find_request_item(items, "Resolve Review Request")
    create_hold = find_request_item(items, "Create Hold Endpoint")
    confirm_hold = find_request_item(items, "Confirm Hold Endpoint")

    remove_request_names(items, {
        "Update Booking",
        "Create Additional Field",
        "Submit Public Additional Field Responses",
        "Submit Review Request",
        "Resolve Review Request",
        "Create Hold Endpoint",
        "Confirm Hold Endpoint",
    })

    workflows=[]
    if update_booking:
        upd=copy.deepcopy(update_booking)
        req=upd.get("request") or {}; body=req.get("body") or {}
        body["raw"]=json.dumps({"notes":"Updated by Postman lifecycle sweep"}, indent=2)
        workflows.append({"name":"Booking Basic Update Workflow","item":[upd]})

    if create_field and submit_fields:
        cf=copy.deepcopy(create_field)
        sf=copy.deepcopy(submit_fields)
        set_json_body(cf, {
            "scope":"booking", "service_id":None,
            "name":f"postman_field_{RUN_SUFFIX}", "label":"Postman Field",
            "field_type":"text", "required":False, "active":True, "position":0,
        })
        add_nested_field_id_script(cf)
        set_json_body(sf, {
            "client_id": int(path_values_global.get("client_id","1")),
            "booking_id": None,
            "responses":[{
                "field_id":"{{additionalFieldId}}",
                "client_id":int(path_values_global.get("client_id","1")),
                "booking_id":None,
                "value":"Postman response"
            }]
        })
        workflows.append({"name":"Additional Field Workflow","item":[cf,sf]})

    if submit_review and resolve_review:
        from datetime import datetime,timedelta,timezone
        sr=copy.deepcopy(submit_review); rr=copy.deepcopy(resolve_review)
        future=datetime.now(timezone.utc).replace(second=0,microsecond=0)+timedelta(days=140,minutes=int(RUN_SUFFIX[:4],16)%600)
        set_json_body(sr,{"preferred_time":future.isoformat().replace("+00:00","Z"),"reason":f"postman-{RUN_SUFFIX}"})
        set_json_body(rr,{"state":"approved","resolution_notes":"Postman sweep approval"})
        workflows.append({"name":"Management Review Workflow","item":[sr,rr]})

    if create_hold and confirm_hold:
        ch=copy.deepcopy(create_hold); hh=copy.deepcopy(confirm_hold)
        # Existing configure step already calculated the best available slot on the template.
        set_json_body(hh,{"hold_id":"{{holdId}}","client_details":None})
        workflows.append({"name":"Hold Confirmation Workflow","item":[ch,hh]})

    items.extend(workflows)

def defer_delete_requests(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Move DELETE operations into a final cleanup phase."""
    retained: list[dict] = []
    deletes: list[dict] = []
    for item in items:
        if "item" in item:
            children, child_deletes = defer_delete_requests(item.get("item", []))
            item["item"] = children
            if children:
                retained.append(item)
            deletes.extend(child_deletes)
            continue
        request = item.get("request") or {}
        if str(request.get("method", "")).upper() == "DELETE":
            deletes.append(item)
        else:
            retained.append(item)
    return retained, deletes


def cleanup_priority(item: dict) -> tuple[int, str]:
    name = str(item.get("name", ""))
    if name.startswith(("Unlink ", "Unassign ")):
        return (0, name)
    if any(token in name for token in ("Package Step", "Reminder Rule", "Notification Template")):
        return (1, name)
    return (2, name)


def main() -> None:
    global path_values_global
    path_values = discover_path_values()
    path_values_global = path_values
    collection = json.loads(SOURCE.read_text(encoding="utf-8"))
    count = patch_items(collection.get("item", []), path_values)
    build_booking_transition_workflows(collection.get("item", []))
    configure_remaining_workflows(collection.get("item", []))
    rebuild_remaining_dedicated_workflows(collection.get("item", []))
    retained, cleanup_items = defer_delete_requests(collection.get("item", []))
    cleanup_items.sort(key=cleanup_priority)
    collection["item"] = retained
    if cleanup_items:
        collection["item"].append({"name": "Final Cleanup", "item": cleanup_items})
    collection["info"]["name"] = "FastAPI Bookings Local Authenticated Sweep"
    OUTPUT.write_text(json.dumps(collection, indent=2), encoding="utf-8")

    admin_token, public_token, client_token, temp_user_id = token_values()
    TEMP_USER_FILE.write_text(str(temp_user_id), encoding="utf-8")
    lifecycle_values = []
    for parameter, variable in STATE_VARIABLES.items():
        lifecycle_values.append({"key": variable, "value": str(path_values.get(parameter, "1")), "enabled": True, "type": "default"})

    environment = {
        "id": "simplydemo-local-authenticated-sweep",
        "name": "SimplyDemo Local Authenticated Sweep",
        "values": [
            {"key": "baseUrl", "value": BASE_URL, "enabled": True, "type": "default"},
            {"key": "tenant", "value": TENANT, "enabled": True, "type": "default"},
            {"key": "adminToken", "value": admin_token, "enabled": True, "type": "secret"},
            {"key": "publicToken", "value": public_token, "enabled": True, "type": "secret"},
            {"key": "clientToken", "value": client_token, "enabled": True, "type": "secret"},
            {"key": "adminLogin", "value": TEMP_LOGIN, "enabled": True, "type": "default"},
            {"key": "adminPassword", "value": TEMP_ADMIN_PASSWORD, "enabled": True, "type": "secret"},
            {"key": "publicApiKey", "value": settings.PUBLIC_API_KEY, "enabled": True, "type": "secret"},
            *lifecycle_values,
        ],
        "_postman_variable_scope": "environment",
        "_postman_exported_using": "local authenticated sweep helper",
    }
    ENVIRONMENT.write_text(json.dumps(environment, indent=2), encoding="utf-8")
    print(f"Prepared {count} requests with temporary local authentication")
    print(f"Resolved {len(path_values)} concrete path values")
    print(f"Collection: {OUTPUT}")
    print(f"Environment: {ENVIRONMENT}")


if __name__ == "__main__":
    main()
