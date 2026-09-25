"""Tenant Website model for the Website Builder Module.

Stores website templates, custom theme styling, section content,
and publication state for tenant single-page public websites.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..db.database import Base


DEFAULT_SECTIONS_DATA = {
    "hero": {
        "headline": "Elevate Your Wellness & Beauty",
        "subhead": "Experience personalized care and rejuvenating treatments tailored specifically to your lifestyle and goals.",
        "cta_text": "Book Appointment",
        "cta_link": "#booking",
        "bg_image_url": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1600&q=80",
        "enabled": True,
    },
    "about": {
        "badge": "Our Story",
        "headline": "Dedicated to Exceptional Care",
        "story": "Founded with a mission to bring world-class services and mindful relaxation together. Our expert practitioners combine modern techniques with time-honored treatments to deliver an unforgettable experience every visit.",
        "image_url": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1000&q=80",
        "enabled": True,
    },
    "services": {
        "headline": "Signature Services & Treatments",
        "subhead": "Explore our top rated sessions crafted to restore balance and vitality.",
        "show_prices": True,
        "selected_service_ids": [],
        "enabled": True,
    },
    "booking": {
        "headline": "Schedule Your Visit",
        "subhead": "Choose your preferred service, provider, and time in just a few clicks.",
        "embedded_style": "card",
        "enabled": True,
    },
    "testimonials": {
        "headline": "What Our Clients Say",
        "subhead": "Trusted by hundreds of happy clients every month.",
        "items": [
            {
                "name": "Sarah Jenkins",
                "role": "Regular Client",
                "content": "The attention to detail and relaxing ambiance made all the difference. Booking online was effortless!",
                "rating": 5,
            },
            {
                "name": "David Miller",
                "role": "Verified Client",
                "content": "Outstanding service from start to finish. Highly recommend their skilled team.",
                "rating": 5,
            },
            {
                "name": "Elena Rostova",
                "role": "Monthly Member",
                "content": "A true sanctuary in the middle of a busy week. My favourite place to unwind.",
                "rating": 5,
            },
        ],
        "enabled": True,
    },
    "contact": {
        "headline": "Visit or Reach Out",
        "subhead": "We look forward to welcoming you soon.",
        "address": "123 Harmony Boulevard, Suite 400",
        "phone": "+1 (555) 234-5678",
        "email": "hello@serenityhaven.com",
        "hours": "Mon - Sat: 9:00 AM - 7:00 PM\nSunday: 10:00 AM - 5:00 PM",
        "enabled": True,
    },
    "footer": {
        "copyright": "All rights reserved.",
        "social_links": {
            "instagram": "https://instagram.com",
            "facebook": "https://facebook.com",
            "twitter": "https://twitter.com",
        },
        "enabled": True,
    },
    "chat_widget": {
        "enabled": True,
        "invitation_title": "Need help booking?",
        "invitation_message": "Hi there! 👋 Have questions about our services or need to book? Chat with us!",
        "invitation_delay_seconds": 3,
        "show_sms_fallback": True,
    },
}


class TenantWebsite(Base):
    """Represents the custom public single-page website configuration for a tenant.

    Attributes:
        id: Primary key.
        tenant_id: Foreign key referencing the Tenant.
        template_id: Template identifier (minimalist, wellness, clinical, luxury).
        theme_id: Color palette identifier (ocean_slate, emerald_oasis, rose_gold, royal_indigo, monochrome).
        custom_colors: Optional custom palette overrides (JSON dict).
        sections_data: Structured JSON storing hero, about, services, booking, testimonials, contact, footer.
        is_published: Whether the public website is live.
        published_at: Timestamp when published live.
        seo_title: SEO meta title for the website.
        seo_description: SEO meta description.
        created_at: Record creation timestamp.
        updated_at: Record last update timestamp.
    """

    __tablename__ = "tenant_websites"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    template_id = Column(String, default="minimalist", nullable=False)
    theme_id = Column(String, default="ocean_slate", nullable=False)
    custom_colors = Column(JSON, nullable=True)
    sections_data = Column(JSON, nullable=False, default=dict)
    is_published = Column(Boolean, default=False, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    seo_title = Column(String, nullable=True)
    seo_description = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant", backref="tenant_website")

    def __repr__(self) -> str:
        return f"<TenantWebsite id={self.id} tenant_id={self.tenant_id} template={self.template_id} published={self.is_published}>"


def init_website_tables(bind=None) -> None:
    """Helper to ensure the tenant_websites table exists."""
    TenantWebsite.__table__.create(bind=bind, checkfirst=True)
