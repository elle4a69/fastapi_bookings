from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "openapi.json"
OUTPUT = ROOT / "contracts" / "route-manifest.json"


def load_compatibility_manifest() -> dict:
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:contracts/route-manifest.json"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        )
        previous = json.loads(raw)
    except Exception:
        previous = {"version": "1.2", "auth": {}, "public": {}, "admin": {}, "forms": {}, "system": {}}
    for key in ("auth", "public", "admin", "forms", "system"):
        previous.setdefault(key, {})
    return previous


def main() -> None:
    spec = json.loads(OPENAPI.read_text(encoding="utf-8"))
    manifest = load_compatibility_manifest()
    manifest["version"] = "1.2"

    manifest["public"].update({
        "getBookingFormSurface": "/api/public/booking-forms/{slug}",
        "resolveBookingFormSurface": "/api/public/booking-forms/{slug}/resolve",
        "bookingFormAvailability": "/api/public/booking-forms/{slug}/availability",
        "createBookingFormBooking": "/api/public/booking-forms/{slug}/bookings",
        "getBookingFormEmbedConfig": "/api/public/booking-forms/{slug}/embed-config",
        "getBookingFormRuntimeManifest": "/api/public/booking-forms/{slug}/runtime-manifest",
    })
    manifest["admin"].update({
        "listBookingForms": "/api/admin/booking-forms",
        "createBookingForm": "/api/admin/booking-forms",
        "getBookingForm": "/api/admin/booking-forms/{form_id}",
        "updateBookingForm": "/api/admin/booking-forms/{form_id}",
        "deleteBookingForm": "/api/admin/booking-forms/{form_id}",
        "getBookingFormDesign": "/api/admin/booking-forms/{form_id}/design",
        "updateBookingFormDesign": "/api/admin/booking-forms/{form_id}/design",
        "duplicateBookingForm": "/api/admin/booking-forms/{form_id}/duplicate",
        "getBookingFormEmbed": "/api/admin/booking-forms/{form_id}/embed",
        "previewBookingForm": "/api/admin/booking-forms/{form_id}/preview",
        "getBookingFormConfigurationCatalogue": "/api/admin/booking-forms/configuration-catalogue",
    })

    operations = []
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            operations.append({
                "method": method.upper(),
                "path": path,
                "operationId": operation.get("operationId"),
                "summary": operation.get("summary"),
                "tags": operation.get("tags", []),
                "deprecated": operation.get("deprecated", False),
            })

    operations.sort(key=lambda item: (item["path"], item["method"]))
    manifest["generatedFrom"] = "openapi.json"
    manifest["operationCount"] = len(operations)
    manifest["pathCount"] = len(spec["paths"])
    manifest["operations"] = operations
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"route manifest: {len(operations)} operations across {len(spec['paths'])} paths")


if __name__ == "__main__":
    main()
