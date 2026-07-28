from pathlib import Path

p = Path(__file__).with_name('prepare_authenticated_sweep.py')
s = p.read_text(encoding='utf-8')

insert = '''

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
'''
if 'def defer_delete_requests(' not in s:
    s = s.replace('\n\ndef main() -> None:', insert + '\n\ndef main() -> None:')

needle = '    count = patch_items(collection.get("item", []), path_values)\n'
replacement = '''    count = patch_items(collection.get("item", []), path_values)
    retained, cleanup_items = defer_delete_requests(collection.get("item", []))
    cleanup_items.sort(key=cleanup_priority)
    collection["item"] = retained
    if cleanup_items:
        collection["item"].append({"name": "Final Cleanup", "item": cleanup_items})
'''
s = s.replace(needle, replacement)

p.write_text(s, encoding='utf-8')
print('Delete ordering finalised')
