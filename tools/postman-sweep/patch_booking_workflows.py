from pathlib import Path

path = Path(__file__).with_name('prepare_authenticated_sweep.py')
text = path.read_text(encoding='utf-8')

text = text.replace('import json\nimport re\n', 'import copy\nimport json\nimport re\n')

marker = 'def defer_delete_requests(items: list[dict]) -> tuple[list[dict], list[dict]]:\n'
insert = '''def set_booking_request_time(item: dict, day_offset: int) -> None:\n    from datetime import datetime, timedelta, timezone\n\n    request = item.get("request") or {}\n    body = request.get("body") or {}\n    if body.get("mode") != "raw":\n        return\n    try:\n        payload = json.loads(body.get("raw") or "{}")\n    except json.JSONDecodeError:\n        return\n    start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=day_offset)\n    payload["start_time"] = start.isoformat().replace("+00:00", "Z")\n    payload["end_time"] = (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")\n    body["raw"] = json.dumps(payload, indent=2)\n\n\ndef split_booking_transition_workflows(items: list[dict]) -> None:\n    """Give complete, no-show and reschedule independent confirmed bookings."""\n    for container in items:\n        children = container.get("item")\n        if not isinstance(children, list):\n            continue\n        by_name = {str(child.get("name", "")): child for child in children if "request" in child}\n        create = by_name.get("Create Booking")\n        confirm = by_name.get("Confirm Booking")\n        targets = {\n            "Complete Booking": (70, "Complete"),\n            "Noshow Booking": (80, "No-show"),\n            "Reschedule Booking": (90, "Reschedule"),\n        }\n        if create and confirm and any(name in by_name for name in targets):\n            rebuilt = []\n            for child in children:\n                name = str(child.get("name", ""))\n                if name in targets:\n                    day_offset, label = targets[name]\n                    create_clone = copy.deepcopy(create)\n                    create_clone["name"] = f"Create Booking For {label}"\n                    set_booking_request_time(create_clone, day_offset)\n                    confirm_clone = copy.deepcopy(confirm)\n                    confirm_clone["name"] = f"Confirm Booking For {label}"\n                    rebuilt.extend([create_clone, confirm_clone, child])\n                else:\n                    rebuilt.append(child)\n            container["item"] = rebuilt\n        split_booking_transition_workflows(container.get("item", []))\n\n\n'''
if insert not in text:
    if marker not in text:
        raise SystemExit('defer marker not found')
    text = text.replace(marker, insert + marker)

old = '    count = patch_items(collection.get("item", []), path_values)\n    retained, cleanup_items = defer_delete_requests(collection.get("item", []))\n'
new = '    count = patch_items(collection.get("item", []), path_values)\n    split_booking_transition_workflows(collection.get("item", []))\n    retained, cleanup_items = defer_delete_requests(collection.get("item", []))\n'
if old not in text:
    raise SystemExit('main insertion point not found')
text = text.replace(old, new)

path.write_text(text, encoding='utf-8')
print('independent booking transition workflows patched')
