from pathlib import Path
p=Path(__file__).with_name('prepare_authenticated_sweep.py')
s=p.read_text(encoding='utf-8')

# Remove null status rather than sending an invalid transition.
s=s.replace('        set_json_body(update_booking, {"notes": "Updated by Postman lifecycle sweep", "status": None})', '''        request = update_booking.get("request") or {}
        body = request.get("body") or {}
        try:
            payload = json.loads(body.get("raw") or "{}")
        except json.JSONDecodeError:
            payload = {}
        payload.pop("status", None)
        payload["notes"] = "Updated by Postman lifecycle sweep"
        body["raw"] = json.dumps(payload, indent=2)''')

# Ensure the field is public/active and associated with the current service.
s=s.replace('    if create_field:\n        add_nested_field_id_script(create_field)', '''    if create_field:
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
        add_nested_field_id_script(create_field)''')

# Replace fixed hold time with a real slot from the scheduling engine.
s=s.replace('        start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=130)', '''        from app.services.availability_service import get_available_slots
        db = SessionLocal()
        try:
            service_id = int(path_values_global.get("service_id", "1"))
            provider_id = int(path_values_global.get("provider_id", "1"))
            from app.models.service import Service
            service = db.query(Service).filter(Service.id == service_id).first()
            start = None
            end = None
            if service:
                for days in range(1, 91):
                    probe = datetime.now(timezone.utc) + timedelta(days=days)
                    slots = get_available_slots(db, service.duration, provider_id, probe)
                    if slots:
                        start = slots[0]["start"]
                        end = slots[0]["end"]
                        break
            if start is None or end is None:
                start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=130)
                end = start + timedelta(minutes=30)
        finally:
            db.close()''')
s=s.replace('            "end_time": (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),', '            "end_time": end.isoformat().replace("+00:00", "Z"),', 1)

# Remove redundant cleanup calls: client teardown is handled by cleanup helper; legacy relation unlink is non-idempotent.
s=s.replace('    prune(items)\n', '''    prune(items)
    remove_request_names(items, {"Delete Client", "Unlink Location Category"})
''', 1)

p.write_text(s,encoding='utf-8')
print('final harness fixes patched')
