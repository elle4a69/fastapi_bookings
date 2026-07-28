"""Idempotently add the dedicated configurable booking-form workflow folder."""

import json
from pathlib import Path


PATH = Path(__file__).with_name("FastAPI-Bookings-Local.postman_collection.json")


def request(name, method, path, body=None, tests=None):
    item = {
        "name": name,
        "event": [{
            "listen": "test",
            "script": {"type": "text/javascript", "exec": tests or [
                "pm.test('Expected success status', () => pm.expect(pm.response.code).to.be.oneOf([200, 201, 204]));"
            ]},
        }],
        "request": {
            "method": method,
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "url": {"raw": "{{baseUrl}}" + path, "host": ["{{baseUrl}}"], "path": path.strip("/").split("/")},
        },
    }
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2), "options": {"raw": {"language": "json"}}}
    return item


def main():
    collection = json.loads(PATH.read_text(encoding="utf-8"))
    collection["item"] = [item for item in collection["item"] if item.get("name") != "Configurable Booking Forms"]
    default_form = {
        "name": "Postman configurable form",
        "slug": "postman-configurable-form-{{$timestamp}}",
        "module_order": ["location", "category", "service", "provider", "time"],
        "enabled_modules": {"location": True, "category": True, "service": True, "provider": True, "time": True},
        "predefined_values": {},
        "provider_selection_mode": "required",
    }
    save_form = [
        "pm.test('Created', () => pm.response.to.have.status(201));",
        "pm.collectionVariables.set('booking_form_id', pm.response.json().id); pm.collectionVariables.set('booking_form_slug', pm.response.json().slug);",
    ]
    folder = {
        "name": "Configurable Booking Forms",
        "description": "Stateful coverage for persisted forms, propagation, provider modes, universal-default restrictions, and atomic relationship creation.",
        "item": [
            request("0a. Reactivate service", "PUT", "/api/admin/services/{{serviceId}}", {"active": True, "is_visible": True}),
            request("0b. Reactivate provider", "PUT", "/api/admin/providers/{{providerId}}", {"active": True, "is_visible": True}),
            request("0c. Reactivate category", "PUT", "/api/admin/categories/{{categoryId}}", {"name": "Postman active category", "active": True}),
            request("0d. Link location and category", "POST", "/api/admin/relationships/location/{{locationId}}/category/{{categoryId}}"),
            request("1. No presets", "POST", "/api/admin/booking-forms", default_form, save_form),
            request("2. Resolve no presets", "POST", "/api/public/booking-forms/{{booking_form_slug}}/resolve", {"selections": {}}),
            request("3. Predefined location", "PUT", "/api/admin/booking-forms/{{booking_form_id}}", {"predefined_values": {"location_id": "{{locationId}}"}}),
            request("4. Predefined location and category", "PUT", "/api/admin/booking-forms/{{booking_form_id}}", {"predefined_values": {"location_id": "{{locationId}}", "category_id": "{{categoryId}}"}}),
            request("5. Predefined service unique path", "PUT", "/api/admin/booking-forms/{{booking_form_id}}", {"predefined_values": {"service_id": "{{serviceId}}"}}),
            request("6. Predefined service multiple providers", "POST", "/api/public/booking-forms/{{booking_form_slug}}/resolve", {"selections": {"service_id": "{{serviceId}}"}}),
            request("7. Automatic provider mode", "PUT", "/api/admin/booking-forms/{{booking_form_id}}", {"provider_selection_mode": "automatic", "predefined_values": {"service_id": "{{serviceId}}"}}),
            request("8. Universal then explicit restriction", "POST", "/api/admin/relationships/service/{{serviceId}}/provider/{{providerId}}"),
            request("9. Inline create-and-connect", "POST", "/api/admin/relationships/provider/{{providerId}}/service/create-and-connect", {"record": {"name": "Postman inline service", "duration": 30, "active": True}}),
            request("10. Structured preview", "GET", "/api/admin/booking-forms/{{booking_form_id}}/preview"),
        ],
    }
    collection["item"].append(folder)
    PATH.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
