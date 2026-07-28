from pathlib import Path

path = Path(__file__).with_name('prepare_authenticated_sweep.py')
text = path.read_text(encoding='utf-8')

text = text.replace(
    'from app.core.security import create_access_token, get_password_hash\n',
    'from app.core.config import settings\nfrom app.core.security import create_access_token, get_password_hash\n',
)
text = text.replace(
    'TEMP_LOGIN = "__postman_sweep_owner__"\n',
    'TEMP_LOGIN = "__postman_sweep_owner__"\nTEMP_ADMIN_PASSWORD = "PostmanAdmin123!"\n',
)

old_user_block = '''        user = (\n            db.query(User)\n            .filter(User.tenant_id == tenant.id, User.role.in_(["owner", "admin"]))\n            .order_by(User.id.asc())\n            .first()\n        )\n        if user is None:\n            user = User(\n                tenant_id=tenant.id,\n                login=TEMP_LOGIN,\n                password_hash="not-used-by-token-authentication",\n                role="owner",\n            )\n            db.add(user)\n            db.commit()\n            db.refresh(user)\n'''
new_user_block = '''        user = User(\n            tenant_id=tenant.id,\n            login=TEMP_LOGIN,\n            password_hash=get_password_hash(TEMP_ADMIN_PASSWORD),\n            role="owner",\n        )\n        db.add(user)\n        db.commit()\n        db.refresh(user)\n'''
if old_user_block not in text:
    raise SystemExit('user block not found')
text = text.replace(old_user_block, new_user_block)

marker = 'def normalise_request_body(request: dict, id_values: dict[str, str], request_name: str) -> None:\n'
insert = '''def add_login_capture_script(item: dict) -> None:\n    name = str(item.get("name", ""))\n    variable = None\n    if name == "Admin Login":\n        variable = "adminToken"\n    elif name == "Public Login":\n        variable = "publicToken"\n    if not variable:\n        return\n    script = [\n        "if (pm.response.code >= 200 && pm.response.code < 300) {",\n        "  try {",\n        "    const payload = pm.response.json();",\n        "    const token = payload && payload.data && payload.data.access_token;",\n        f"    if (token) pm.environment.set('{variable}', token);",\n        "  } catch (error) {}",\n        "}",\n    ]\n    item.setdefault("event", []).append({\n        "listen": "test",\n        "script": {"type": "text/javascript", "exec": script},\n    })\n\n\n'''
if insert not in text:
    text = text.replace(marker, insert + marker)

old_body_tail = '''        if request_name == "Login Client":\n            payload["email"] = TEMP_CLIENT_EMAIL\n            payload["password"] = TEMP_CLIENT_PASSWORD\n        if "event" in payload and payload["event"] in {"test", "<string>"}:\n            payload["event"] = "booking.created"\n'''
new_body_tail = '''        if request_name == "Admin Login":\n            payload["company"] = TENANT\n            payload["login"] = TEMP_LOGIN\n            payload["password"] = TEMP_ADMIN_PASSWORD\n        elif request_name == "Public Login":\n            payload["company"] = TENANT\n            payload["key"] = settings.PUBLIC_API_KEY\n        elif request_name == "Login Client":\n            payload["email"] = TEMP_CLIENT_EMAIL\n            payload["password"] = TEMP_CLIENT_PASSWORD\n        if request_name in {"Create Booking", "Create Public Booking"}:\n            from datetime import datetime, timedelta, timezone\n            offset = int(uuid4().hex[:6], 16) % 120\n            start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=45, minutes=offset * 30)\n            payload["start_time"] = start.isoformat().replace("+00:00", "Z")\n            payload["end_time"] = (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")\n        if request_name == "Reschedule Booking":\n            from datetime import datetime, timedelta, timezone\n            offset = int(uuid4().hex[:6], 16) % 120\n            start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=60, minutes=offset * 30)\n            payload["new_start"] = start.isoformat().replace("+00:00", "Z")\n            payload["new_end"] = (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")\n        if "event" in payload and payload["event"] in {"test", "<string>"}:\n            payload["event"] = "booking.created"\n'''
if old_body_tail not in text:
    raise SystemExit('body tail not found')
text = text.replace(old_body_tail, new_body_tail)

text = text.replace(
    '        add_capture_script(item)\n        add_delete_guard(item)\n',
    '        add_capture_script(item)\n        add_login_capture_script(item)\n        add_delete_guard(item)\n',
)

text = text.replace(
    '{"key": "clientToken", "value": client_token, "enabled": True, "type": "secret"},\n',
    '{"key": "clientToken", "value": client_token, "enabled": True, "type": "secret"},\n            {"key": "adminLogin", "value": TEMP_LOGIN, "enabled": True, "type": "default"},\n            {"key": "adminPassword", "value": TEMP_ADMIN_PASSWORD, "enabled": True, "type": "secret"},\n            {"key": "publicApiKey", "value": settings.PUBLIC_API_KEY, "enabled": True, "type": "secret"},\n',
)

path.write_text(text, encoding='utf-8')
print('real authentication and booking timestamps patched')
