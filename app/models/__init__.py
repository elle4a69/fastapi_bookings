"""SQLAlchemy ORM models used by the application.

Importing this package automatically imports all models so that
SQLAlchemy's metadata can discover them when creating tables.
"""

from .user import User
from .service import Service
from .provider import Provider
from .client import Client
from .location import Location, LocationProvider, LocationService, LocationCategory, LocationProduct, LocationProvider, LocationService, LocationCategory, LocationProduct
from .booking import Booking
from .booking_slot_allocation import BookingSlotAllocation
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
from .addon import AddOn, ServiceAddOn
from .product import Product, ServiceProduct
from .provider_category import ProviderCategory
from .booking_form import BookingForm
from .package import ServicePackage, PackageStep
from .outbox import OutboxEvent, BookingEvent, BookingEventType
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
from .webhook import WebhookDelivery, WebhookRegistration
from .calendar_note import CalendarNote
from .general_systems import PluginState, GdprConsent
from .management_review_request import ManagementReviewRequest

# SMS Module models
from .sms_account import SmsAccount
from .sms_conversation import SmsConversation
from .sms_message import SmsMessage
from .sms_receipt import SmsInboundReceipt, SmsDeliveryReceipt
from .sms_outbox import SmsOutboundJob, SmsAiJob, SmsConversationEvent, SmsNote
from .sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile
from .sms_arrival import SmsArrivalSession
from .sms_chatwoot import SmsChatwootBinding
from .sms_quick_tool import SmsQuickTool

# Curated Memory model
from .curated_memory import CuratedMemory, KnowledgeProposal

# Knowledge Graph Projection model
from .knowledge_projection import KnowledgeGraphProjection

# Tenant Website model
from .tenant_website import TenantWebsite, init_website_tables

# Client Dispute model
from .client_dispute import ClientDispute, init_dispute_tables

# Learning Event model
from .learning_event import LearningEvent

# SMS Bootcamp models
from .sms_bootcamp import (
    SmsBootcampRun,
    SmsBootcampConversation,
    SmsBootcampMessage,
    SmsBootcampSettings,
)

__all__ = [
    "User",
    "Service",
    "Provider",
    "Client",
    "Location",
    "LocationProvider",
    "LocationService",
    "LocationCategory",
    "LocationProduct",
    "Booking",
    "BookingSlotAllocation",
    "AuditLog",
    "Payment",
    "Notification",
    "NotificationTemplate",
    "ReminderRule",
    "NotificationLog",
    "DeviceToken",
    "NotificationPreference",
    # Advanced models
    "Tenant",
    "Resource",
    "ServiceResourceRequirement",
    "BookingResourceAllocation",
    "Category",
    "ServiceCategory",
    "ServiceProvider",
    "AddOn",
    "ServiceAddOn",
    "Product",
    "ServiceProduct",
    "ProviderCategory",
    "BookingForm",
    "ServicePackage",
    "PackageStep",
    "OutboxEvent",
    "BookingEvent",
    "BookingEventType",
    "WaitlistEntry",
    "WaitlistStatus",
    "BookingSeries",
    "ProviderWorkDay",
    "ProviderSpecialDay",
    "BlockedTime",
    "ReservedTime",
    "AdditionalField",
    "AdditionalFieldResponse",
    "Invoice",
    "InvoiceLine",
    "PromotionCode",
    "TaxRate",
    "Tip",
    "PaymentProcessorConfig",
    "WebhookDelivery",
    "WebhookRegistration",
    "CalendarNote",
    "PluginState",
    "GdprConsent",
    "ManagementReviewRequest",
    # SMS Module
    "SmsAccount",
    "SmsConversation",
    "SmsMessage",
    "SmsInboundReceipt",
    "SmsDeliveryReceipt",
    "SmsOutboundJob",
    "SmsAiJob",
    "SmsConversationEvent",
    "SmsNote",
    "SmsKnowledgeEntry",
    "SmsPromptProfile",
    "SmsArrivalSession",
    "SmsChatwootBinding",
    "SmsQuickTool",
    "CuratedMemory",
    "KnowledgeProposal",
    "KnowledgeGraphProjection",
    "TenantWebsite",
    "init_website_tables",
    "ClientDispute",
    "init_dispute_tables",
    "LearningEvent",
    # SMS Bootcamp
    "SmsBootcampRun",
    "SmsBootcampConversation",
    "SmsBootcampMessage",
    "SmsBootcampSettings",
]

