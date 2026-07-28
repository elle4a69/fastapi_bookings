import json
import re
from pathlib import Path

path = Path(__file__).with_name("FastAPI-Bookings-Local-Authenticated.postman_collection.json")
collection = json.loads(path.read_text(encoding="utf-8"))
pattern = re.compile(r"(?<=/):[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\}|<(?:integer|number|string|date|dateTime|boolean)>")
bad = []
stack = list(collection.get("item", []))
while stack:
    item = stack.pop()
    if "item" in item:
        stack.extend(item["item"])
        continue
    request = item.get("request", {})
    url = request.get("url", {})
    raw = url.get("raw", "") if isinstance(url, dict) else str(url)
    if pattern.search(raw):
        bad.append((item.get("name", ""), raw))

print(f"UNRESOLVED_URLS={len(bad)}")
for name, raw in bad:
    print(f"{name} -> {raw}")
