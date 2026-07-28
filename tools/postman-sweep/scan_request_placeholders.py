import json
import re
from pathlib import Path

path = Path(r"F:\Projects\fastapi_bookings\tools\postman-sweep\FastAPI-Bookings-Local-Authenticated.postman_collection.json")
collection = json.loads(path.read_text(encoding="utf-8"))
issues = []

def walk(items):
    for item in items:
        if "item" in item:
            walk(item["item"])
            continue
        request = item.get("request") or {}
        url = request.get("url")
        raw_url = url.get("raw", "") if isinstance(url, dict) else str(url or "")
        if re.search(r"(?<!\{)[:{][A-Za-z_][A-Za-z0-9_]*\}?|<(?:integer|number|boolean|date|dateTime|string|null)>", raw_url):
            issues.append((item.get("name"), "url", raw_url))
        body = request.get("body") or {}
        raw_body = body.get("raw", "") if isinstance(body, dict) else ""
        if isinstance(raw_body, str) and re.search(r"<(?:integer|number|boolean|date|dateTime|string|null)>", raw_body):
            issues.append((item.get("name"), "body", raw_body[:300]))

walk(collection.get("item", []))
print(f"PLACEHOLDER_ISSUES={len(issues)}")
for issue in issues[:100]:
    print(issue)
