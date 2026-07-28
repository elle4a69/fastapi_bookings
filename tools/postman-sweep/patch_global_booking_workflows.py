from pathlib import Path

path = Path(__file__).with_name('prepare_authenticated_sweep.py')
text = path.read_text(encoding='utf-8')

marker = 'def defer_delete_requests(items: list[dict]) -> tuple[list[dict], list[dict]]:\n'
insert = '''def find_request_item(items: list[dict], target_name: str) -> dict | None:\n    for item in items:\n        if str(item.get("name", "")) == target_name and "request" in item:\n            return item\n        children = item.get("item")\n        if isinstance(children, list):\n            found = find_request_item(children, target_name)\n            if found:\n                return found\n    return None\n\n\ndef remove_request_names(items: list[dict], names: set[str]) -> None:\n    retained = []\n    for item in items:\n        children = item.get("item")\n        if isinstance(children, list):\n            remove_request_names(children, names)\n        if str(item.get("name", "")) in names and "request" in item:\n            continue\n        retained.append(item)\n    items[:] = retained\n\n\ndef build_booking_transition_workflows(items: list[dict]) -> None:\n    create = find_request_item(items, "Create Booking")\n    confirm = find_request_item(items, "Confirm Booking")\n    actions = {\n        "Complete Booking": (70, "Complete"),\n        "Noshow Booking": (80, "No-show"),\n        "Reschedule Booking": (90, "Reschedule"),\n    }\n    if not create or not confirm:\n        return\n    originals = {name: find_request_item(items, name) for name in actions}\n    remove_request_names(items, set(actions))\n    workflow_items = []\n    for action_name, (day_offset, label) in actions.items():\n        action = originals.get(action_name)\n        if not action:\n            continue\n        create_clone = copy.deepcopy(create)\n        create_clone["name"] = f"Create Booking For {label}"\n        set_booking_request_time(create_clone, day_offset)\n        confirm_clone = copy.deepcopy(confirm)\n        confirm_clone["name"] = f"Confirm Booking For {label}"\n        workflow_items.extend([create_clone, confirm_clone, action])\n    if workflow_items:\n        items.append({"name": "Booking Transition Workflows", "item": workflow_items})\n\n\n'''
if insert not in text:
    if marker not in text:
        raise SystemExit('marker not found')
    text = text.replace(marker, insert + marker)

text = text.replace(
    '    split_booking_transition_workflows(collection.get("item", []))\n',
    '    build_booking_transition_workflows(collection.get("item", []))\n',
)

path.write_text(text, encoding='utf-8')
print('global booking workflows patched')
