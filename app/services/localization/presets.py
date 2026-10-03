"""Pre-packaged industry presets and terminology resolution logic.

Supports dynamic industry adaptation across healthcare, automotive,
wellness/salons, and professional services without altering database schemas.
"""

from typing import Dict, Any, Optional

DEFAULT_TERMINOLOGY: Dict[str, str] = {
    "client": "Client",
    "clients": "Clients",
    "provider": "Provider",
    "providers": "Providers",
    "booking": "Booking",
    "bookings": "Bookings",
    "service": "Service",
    "services": "Services",
    "location": "Location",
    "locations": "Locations",
}

INDUSTRY_PRESETS: Dict[str, Dict[str, Any]] = {
    "allied_health": {
        "id": "allied_health",
        "name": "Allied Health & Medical",
        "description": "Terminology tailored for clinics, physiotherapists, medical practitioners, and specialists.",
        "terminology": {
            "client": "Patient",
            "clients": "Patients",
            "provider": "Practitioner",
            "providers": "Practitioners",
            "service": "Treatment",
            "services": "Treatments",
            "booking": "Consultation",
            "bookings": "Consultations",
            "location": "Clinic",
            "locations": "Clinics",
        },
    },
    "automotive": {
        "id": "automotive",
        "name": "Automotive & Mechanical",
        "description": "Terminology tailored for auto repair shops, mechanics, inspection centers, and tire bays.",
        "terminology": {
            "client": "Customer",
            "clients": "Customers",
            "provider": "Technician",
            "providers": "Technicians",
            "service": "Service/Repair",
            "services": "Services/Repairs",
            "booking": "Service",
            "bookings": "Services",
            "location": "Workshop/Bay",
            "locations": "Workshops/Bays",
        },
    },
    "wellness_salon": {
        "id": "wellness_salon",
        "name": "Wellness, Spa & Salon",
        "description": "Terminology tailored for hair salons, day spas, massage therapists, and beauty clinics.",
        "terminology": {
            "client": "Client",
            "clients": "Clients",
            "provider": "Stylist",
            "providers": "Stylists",
            "service": "Treatment",
            "services": "Treatments",
            "booking": "Appointment",
            "bookings": "Appointments",
            "location": "Salon/Studio",
            "locations": "Salons/Studios",
        },
    },
    "professional_services": {
        "id": "professional_services",
        "name": "Professional Services & Advisory",
        "description": "Terminology tailored for consultancies, accounting firms, legal practices, and agencies.",
        "terminology": {
            "client": "Client",
            "clients": "Clients",
            "provider": "Consultant",
            "providers": "Consultants",
            "service": "Session",
            "services": "Sessions",
            "booking": "Appointment",
            "bookings": "Appointments",
            "location": "Office",
            "locations": "Offices",
        },
    },
}


def get_preset(preset_key: str) -> Optional[Dict[str, str]]:
    """Retrieve terminology dictionary for a specific preset key."""
    preset = INDUSTRY_PRESETS.get(preset_key)
    if preset:
        return dict(preset["terminology"])
    return None


def list_presets() -> Dict[str, Dict[str, Any]]:
    """List all available industry presets."""
    return INDUSTRY_PRESETS


def resolve_terminology(
    custom_terminology: Optional[Dict[str, str]] = None,
    preset_key: Optional[str] = None,
) -> Dict[str, str]:
    """Resolve the merged terminology dictionary.

    Layering precedence:
    1. Base defaults (DEFAULT_TERMINOLOGY)
    2. Selected industry preset (if any)
    3. Custom tenant overrides (if any)
    """
    resolved = dict(DEFAULT_TERMINOLOGY)

    if preset_key and preset_key in INDUSTRY_PRESETS:
        preset_terms = INDUSTRY_PRESETS[preset_key]["terminology"]
        resolved.update(preset_terms)

    if custom_terminology:
        for k, v in custom_terminology.items():
            if v and isinstance(v, str) and v.strip():
                resolved[k] = v.strip()

    return resolved
