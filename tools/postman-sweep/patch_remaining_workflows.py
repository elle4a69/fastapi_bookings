from pathlib import Path

p = Path(__file__).with_name('prepare_authenticated_sweep.py')
s = p.read_text(encoding='utf-8')

insert = r'''

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
        set_json_body(update_booking, {"notes": "Updated by Postman lifecycle sweep", "status": None})

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
        start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=130)
        set_json_body(create_hold, {
            "service_id": int(path_values_global.get("service_id", "1")),
            "provider_id": int(path_values_global.get("provider_id", "1")),
            "location_id": int(path_values_global.get("location_id", "1")),
            "client_id": int(path_values_global.get("client_id", "1")),
            "start_time": start.isoformat().replace("+00:00", "Z"),
            "end_time": (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        })
        set_json_body(confirm_hold, {"hold_id": "{{holdId}}", "client_details": None})
        workflow = [copy.deepcopy(create_hold), copy.deepcopy(confirm_hold)]
        items.append({"name": "Hold Confirmation Workflow", "item": workflow})
        remove_request_names(items[:-1], {"Confirm Hold Endpoint"})
        if cancel_hold:
            # The original cancel remains a negative/cleanup path; guard it from cancelling a confirmed hold.
            remove_request_names(items[:-1], {"Cancel Hold Endpoint"})
'''

marker = '\ndef defer_delete_requests(items: list[dict])'
if 'def configure_remaining_workflows' not in s:
    s = s.replace(marker, insert + marker)

s = s.replace('def main() -> None:\n    path_values = discover_path_values()', 'def main() -> None:\n    global path_values_global\n    path_values = discover_path_values()\n    path_values_global = path_values')
s = s.replace('    build_booking_transition_workflows(collection.get("item", []))\n', '    build_booking_transition_workflows(collection.get("item", []))\n    configure_remaining_workflows(collection.get("item", []))\n')
p.write_text(s, encoding='utf-8')
print('remaining workflows patched')
