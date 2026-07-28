import json
from pathlib import Path

from app.main import app


ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_booking_form_paths_and_deprecations():
    schema = app.openapi()
    for path in (
        "/api/admin/booking-forms",
        "/api/admin/booking-forms/{form_id}/preview",
        "/api/public/booking-forms/{slug}",
        "/api/public/booking-forms/{slug}/resolve",
        "/api/public/booking-forms/{slug}/availability",
        "/api/public/booking-forms/{slug}/bookings",
    ):
        assert path in schema["paths"]
    assert schema["paths"]["/api/public/ui-config"]["get"]["deprecated"] is True
    assert schema["paths"]["/api/public/services"]["get"]["deprecated"] is True


def test_manifest_booking_form_paths_exist_in_openapi():
    schema_paths = set(app.openapi()["paths"])
    manifest = json.loads((ROOT / "contracts" / "route-manifest.json").read_text(encoding="utf-8"))
    for group in ("public", "admin"):
        for name, path in manifest[group].items():
            if "BookingForm" in name:
                assert path in schema_paths
