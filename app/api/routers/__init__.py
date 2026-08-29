"""Aggregate router definitions.

Import all router modules here so that they can be easily included
within the application. When new routers are added to the project,
ensure they are imported in this file.
"""

from . import auth  # noqa: F401
from . import services  # noqa: F401
from . import providers  # noqa: F401
from . import clients  # noqa: F401
from . import locations  # noqa: F401
from . import bookings  # noqa: F401
from . import availability  # noqa: F401
from . import admin_dashboard  # noqa: F401
from . import public_bootstrap  # noqa: F401
from . import audit  # noqa: F401
from . import payments  # noqa: F401
from . import notifications  # noqa: F401

# Feature routers
from . import waitlist  # noqa: F401
from . import search  # noqa: F401
from . import ui_config  # noqa: F401
from . import booking_forms  # noqa: F401
from . import relationship_management  # noqa: F401
from . import forms  # noqa: F401
from . import diagnostics  # noqa: F401
from . import categories  # noqa: F401
from . import resources  # noqa: F401
from . import addons  # noqa: F401
from . import products  # noqa: F401
from . import packages  # noqa: F401
from . import public_bookings  # noqa: F401

# Merged and domain-specific routers
from . import admin_schedule  # noqa: F401
from . import additional_fields  # noqa: F401
from . import checkout  # noqa: F401
from . import public_clients  # noqa: F401
from . import public_entities  # noqa: F401
from . import public_timeline  # noqa: F401
from . import series  # noqa: F401
from . import service_relations  # noqa: F401
from . import webhooks  # noqa: F401
from . import calendar_notes  # noqa: F401
from . import general_systems  # noqa: F401
from . import stripe_webhooks  # noqa: F401
from . import devices  # noqa: F401
from . import management_reviews  # noqa: F401
from . import business_profile  # noqa: F401
from . import location_relations  # noqa: F401
from . import system  # noqa: F401
from . import discovery  # noqa: F401

# SMS Module routers
from . import sms_accounts  # noqa: F401
from . import sms_arrivals  # noqa: F401
from . import sms_chatwoot  # noqa: F401
from . import sms_conversations  # noqa: F401
from . import sms_settings  # noqa: F401
from . import sms_webhooks  # noqa: F401

# Assistant facade router
from . import assistant_facade  # noqa: F401

__all__ = [
    "auth",
    "services",
    "providers",
    "clients",
    "locations",
    "bookings",
    "availability",
    "admin_dashboard",
    "public_bootstrap",
    "audit",
    "payments",
    "notifications",
    "waitlist",
    "search",
    "ui_config",
    "booking_forms",
    "relationship_management",
    "forms",
    "diagnostics",
    "categories",
    "resources",
    "addons",
    "products",
    "packages",
    "public_bookings",
    "admin_schedule",
    "additional_fields",
    "checkout",
    "public_clients",
    "public_entities",
    "public_timeline",
    "series",
    "service_relations",
    "webhooks",
    "calendar_notes",
    "general_systems",
    "stripe_webhooks",
    "devices",
    "management_reviews",
    "business_profile",
    "location_relations",
    "system",
    "discovery",
    "sms_accounts",
    "sms_arrivals",
    "sms_chatwoot",
    "sms_conversations",
    "sms_settings",
    "sms_webhooks",
    "assistant_facade",
]
