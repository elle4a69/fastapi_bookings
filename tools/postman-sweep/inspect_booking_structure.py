import json
from pathlib import Path

doc = json.loads((Path(__file__).parent / "FastAPI-Bookings-Local-Authenticated.postman_collection.json").read_text(encoding="utf-8"))

def walk(items, prefix=""):
    for item in items:
        name = item.get("name", "")
        path = f"{prefix}/{name}"
        if "Booking" in name or "booking" in name:
            print(path)
        if "item" in item:
            walk(item["item"], path)

walk(doc.get("item", []))
