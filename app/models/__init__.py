"""SQLAlchemy ORM models used by the application.

Importing this package automatically imports all models so that
SQLAlchemy's metadata can discover them when creating tables.
"""

from .user import User
from .service import Service
from .provider import Provider
from .client import Client
from .location import Location
from .booking import Booking
from .audit import AuditLog
from .payment import Payment
from .notification import (
    Notification,
    NotificationTemplate,
    ReminderRule,
    NotificationLog,
    DeviceToken,
    NotificationPreference,
)

# Core domain models
from .tenant import Tenant
from .resource import (
    Resource,
    ServiceResourceRequirement,
    BookingResourceAllocation,
)
from .category import Category, ServiceCategory
from .service_provider import ServiceProvider
from .addon import AddOn
from .product import Product, ServiceProduct
from .package import ServicePackage, PackageStep
from .outbox import OutboxEvent, BookingEvent, BookingEventType
from .hold import Hold, HoldStatus
from .waitlist import WaitlistEntry, WaitlistStatus
from .booking_series import BookingSeries

# Schedule / work calendar models
from .schedule import (
    ProviderWorkDay,
    ProviderSpecialDay,
    BlockedTime,
    ReservedTime,
)

# Intake / additional fields
from .additional_field import AdditionalField, AdditionalFieldResponse

# Checkout / commercial models
from .checkout import (
    Invoice,
    InvoiceLine,
    PromotionCode,
    TaxRate,
    Tip,
    PaymentProcessorConfig,
)

# System models (from FastBook merge)
from .webhook import WebhookRegistration
from .calendar_note import CalendarNote
from .general_systems import PluginState, GdprConsent

# System models (from FastBook merge)
from .webhook import WebhookRegistration
from .calendar_note import CalendarNote
from .general_systems import PluginState, GdprConsent
from .outbox import OutboxEvent, BookingEvent, BookingEventType
from .hold import Hold, HoldStatus
from .waitlist import WaitlistEntry, WaitlistStatus

__all__ = [
    "User",
    "Service",
    "Provider",
    "Client",
    "Location",
    "Booking",
    "AuditLog",
    "Payment",
    "Notification",
    # Advanced models
    "Tenant",
    "Resource",
    "ServiceResourceRequirement",
    "BookingResourceAllocation",
    "Category",
    "ServiceCategory",
    "ServiceProvider",
    "AddOn",
    "Product",
    "ServiceProduct",
    "ServicePackage",
    "PackageStep",
    "OutboxEvent",
    "BookingEvent",
    "BookingEventType",
    "Hold",
    "HoldStatus",
    "WaitlistEntry",
    "WaitlistStatus",
]