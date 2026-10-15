"""Targeted tests for website_initial_draft service.

Verifies Task B3 requirements:
- Factual draft assembly from tenant info, business hours, services, and active providers.
- Idempotent draft creation without duplicating records.
- Preservation of existing published sites and custom user edits.
- Inclusion of eligible durable Media assets (is_public_website_eligible=True).
- Strict exclusion of non-eligible media, soft-deleted media, and confidential operational/clinical notes.
- Pydantic schema validity with WebsiteConfigSchema and PublicWebsiteData.
- Verification that gallery and contact hours are cleanly formatted with real data.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.models.media import Media
from app.models.provider import Provider
from app.models.schedule import ProviderWorkDay
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.tenant_website import TenantWebsite
from app.schemas.website import PublicWebsiteData, WebsiteConfigSchema
from app.services.website_initial_draft import (
    build_initial_website_sections,
    ensure_initial_website_draft,
)


@pytest.fixture
def draft_test_tenant(db_session):
    """Creates an isolated tenant with baseline business details."""
    tenant = Tenant(
        name="Harborview Physical Therapy",
        subdomain="harborview-pt",
        email="reception@harborviewpt.com.au",
        phone="+61 2 9555 0199",
        address="102 Pacific Highway, North Sydney NSW 2060",
        timezone="Australia/Sydney",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_factual_draft_assembly(db_session, draft_test_tenant):
    """Verify factual assembly of hero, about, services, contact, and hours without lorem ipsum."""
    # 1. Add active services
    svc1 = Service(
        tenant_id=draft_test_tenant.id,
        name="Musculoskeletal Assessment",
        description="Comprehensive 45-minute biomechanical evaluation and diagnosis.",
        duration=45,
        price=Decimal("130.00"),
        active=True,
        is_visible=True,
    )
    svc2 = Service(
        tenant_id=draft_test_tenant.id,
        name="Remedial Rehabilitation",
        description="Targeted manual therapy and exercise rehabilitation program.",
        duration=60,
        price=Decimal("160.00"),
        active=True,
        is_visible=True,
    )
    db_session.add_all([svc1, svc2])

    # 2. Add an active provider with factual description
    provider = Provider(
        tenant_id=draft_test_tenant.id,
        name="Dr. Alistair Finch",
        description="Senior manipulative physiotherapist with 15 years clinical expertise.",
        active=True,
        is_visible=True,
    )
    db_session.add(provider)

    # 3. Add operating hours via ProviderWorkDay
    # Mon-Fri: 08:30 - 17:30, Sat: 09:00 - 13:00, Sun: Closed
    workdays = [
        ProviderWorkDay(
            tenant_id=draft_test_tenant.id,
            weekday=i,
            start_time="08:30",
            end_time="17:30",
            is_working=True,
        )
        for i in range(5)
    ]
    workdays.append(
        ProviderWorkDay(
            tenant_id=draft_test_tenant.id,
            weekday=5,
            start_time="09:00",
            end_time="13:00",
            is_working=True,
        )
    )
    workdays.append(
        ProviderWorkDay(
            tenant_id=draft_test_tenant.id,
            weekday=6,
            is_working=False,
        )
    )
    db_session.add_all(workdays)
    db_session.commit()

    # 4. Generate draft
    website, created = ensure_initial_website_draft(db_session, draft_test_tenant)
    assert created is True
    assert website.is_published is False
    assert website.tenant_id == draft_test_tenant.id

    sections = website.sections_data
    assert "hero" in sections
    assert "about" in sections
    assert "services" in sections
    assert "contact" in sections
    assert "gallery" in sections
    assert "booking" in sections
    assert "testimonials" in sections

    # Hero verification
    assert sections["hero"]["headline"] == "Welcome to Harborview Physical Therapy"
    assert "Musculoskeletal Assessment" in sections["hero"]["subhead"]
    assert "102 Pacific Highway" in sections["hero"]["subhead"]
    assert sections["hero"]["cta_text"] == "Book online"
    assert sections["hero"]["cta_link"] == "#booking"

    # About verification: factual, no placeholder lorem ipsum
    about = sections["about"]
    assert about["headline"] == "About Harborview Physical Therapy"
    assert "102 Pacific Highway" in about["story"]
    assert "Musculoskeletal Assessment" in about["story"]
    assert "Dr. Alistair Finch" in about["story"] or "Senior manipulative physiotherapist" in about["story"]
    assert "lorem ipsum" not in about["story"].lower()
    assert "add a short introduction" not in about["story"].lower()

    # Services verification
    services_sec = sections["services"]
    assert services_sec["headline"] == "Our services"
    assert services_sec["show_prices"] is False
    assert svc1.id in services_sec["selected_service_ids"]
    assert svc2.id in services_sec["selected_service_ids"]
    assert len(services_sec["items"]) == 2
    assert services_sec["items"][0]["name"] == "Musculoskeletal Assessment"
    assert services_sec["items"][0]["price"] == 130.0

    # Testimonials verification: never invent reviews
    assert sections["testimonials"]["enabled"] is False
    assert sections["testimonials"]["items"] == []

    # Contact verification: real business details & hours
    contact = sections["contact"]
    assert contact["address"] == "102 Pacific Highway, North Sydney NSW 2060"
    assert contact["phone"] == "+61 2 9555 0199"
    assert contact["email"] == "reception@harborviewpt.com.au"
    assert "Mon - Fri: 8:30 AM - 5:30 PM" in contact["hours"]
    assert "Sat: 9:00 AM - 1:00 PM" in contact["hours"]
    assert "Sun: Closed" in contact["hours"]


def test_idempotent_creation(db_session, draft_test_tenant):
    """Ensure calling ensure_initial_website_draft repeatedly is idempotent."""
    site1, created1 = ensure_initial_website_draft(db_session, draft_test_tenant)
    assert created1 is True

    site2, created2 = ensure_initial_website_draft(db_session, draft_test_tenant)
    assert created2 is False
    assert site1.id == site2.id
    assert site1.tenant_id == site2.tenant_id

    # Count rows in DB
    count = db_session.query(TenantWebsite).filter(TenantWebsite.tenant_id == draft_test_tenant.id).count()
    assert count == 1


def test_preservation_of_existing_drafts_and_custom_edits(db_session, draft_test_tenant):
    """Ensure existing drafts, custom edits, or published websites are never overwritten."""
    custom_sections = {
        "hero": {"headline": "Custom User Authored Hero", "subhead": "Handcrafted tagline", "enabled": True},
        "about": {"headline": "Our Historic Legacy", "story": "Established in 1988.", "enabled": True},
    }
    existing_site = TenantWebsite(
        tenant_id=draft_test_tenant.id,
        template_id="luxury",
        theme_id="emerald_oasis",
        custom_colors={"primary": "#00AA88"},
        sections_data=custom_sections,
        is_published=True,
        seo_title="Handcrafted SEO Title",
        seo_description="Handcrafted SEO Description",
    )
    db_session.add(existing_site)
    db_session.commit()
    db_session.refresh(existing_site)

    # Calling ensure_initial_website_draft must not alter existing content
    website, created = ensure_initial_website_draft(db_session, draft_test_tenant)
    assert created is False
    assert website.id == existing_site.id
    assert website.is_published is True
    assert website.template_id == "luxury"
    assert website.theme_id == "emerald_oasis"
    assert website.custom_colors == {"primary": "#00AA88"}
    assert website.sections_data["hero"]["headline"] == "Custom User Authored Hero"
    assert website.sections_data["about"]["story"] == "Established in 1988."
    assert website.seo_title == "Handcrafted SEO Title"


def test_inclusion_of_eligible_media_and_gallery(db_session, draft_test_tenant):
    """Eligible durable media assets must populate gallery and hero background."""
    media1 = Media(
        tenant_id=draft_test_tenant.id,
        filename="clinic_reception.jpg",
        file_path="uploads/clinic_reception.jpg",
        url="https://cdn.example.com/assets/clinic_reception.jpg",
        content_type="image/jpeg",
        file_size=120400,
        title="Main Clinic Reception",
        description="Welcoming reception area with natural light.",
        alt_text="Spacious modern physical therapy clinic front desk",
        is_public_website_eligible=True,
        is_deleted=False,
    )
    media2 = Media(
        tenant_id=draft_test_tenant.id,
        filename="rehab_gym.jpg",
        file_path="uploads/rehab_gym.jpg",
        url="https://cdn.example.com/assets/rehab_gym.jpg",
        content_type="image/jpeg",
        file_size=204800,
        title="Rehabilitation Studio",
        description="Equipped studio for mobility and strength training.",
        alt_text="Gym studio with rehabilitation equipment",
        is_public_website_eligible=True,
        is_deleted=False,
    )
    db_session.add_all([media1, media2])
    db_session.commit()

    sections = build_initial_website_sections(db_session, draft_test_tenant)

    # Gallery section checks
    gallery = sections["gallery"]
    assert gallery["enabled"] is True
    assert len(gallery["items"]) == 2
    assert gallery["items"][0]["url"] == "https://cdn.example.com/assets/clinic_reception.jpg"
    assert gallery["items"][0]["title"] == "Main Clinic Reception"
    assert gallery["items"][0]["alt_text"] == "Spacious modern physical therapy clinic front desk"
    assert gallery["items"][1]["url"] == "https://cdn.example.com/assets/rehab_gym.jpg"

    # Hero and About image assignment from eligible photos
    assert sections["hero"]["bg_image_url"] == "https://cdn.example.com/assets/clinic_reception.jpg"
    assert sections["about"]["image_url"] == "https://cdn.example.com/assets/rehab_gym.jpg"


def test_exclusion_of_private_notes_and_non_eligible_media(db_session, draft_test_tenant):
    """Confidential clinical/internal notes, non-eligible media, and deleted assets must be excluded."""
    CONFIDENTIAL_NOTE = "CONFIDENTIAL: Patient X suffered spinal fracture in 2021. Review intake form."
    PRIVATE_URL = "https://cdn.example.com/assets/private_staff_only.jpg"
    DELETED_URL = "https://cdn.example.com/assets/old_deleted_billboard.jpg"

    # Eligible media WITH clinical/internal notes attached
    m_eligible = Media(
        tenant_id=draft_test_tenant.id,
        filename="treatment_room.jpg",
        file_path="uploads/treatment_room.jpg",
        url="https://cdn.example.com/assets/treatment_room.jpg",
        content_type="image/jpeg",
        file_size=95000,
        title="Treatment Room 1",
        description="Private treatment suite.",
        alt_text="Clean consultation room with examination bench",
        is_public_website_eligible=True,
        notes=CONFIDENTIAL_NOTE,
        is_deleted=False,
    )
    # Non-eligible media (e.g. staff badge / internal doc)
    m_ineligible = Media(
        tenant_id=draft_test_tenant.id,
        filename="staff_badge.jpg",
        file_path="uploads/staff_badge.jpg",
        url=PRIVATE_URL,
        content_type="image/jpeg",
        file_size=50000,
        title="Staff Badge ID",
        notes="Internal staff badge photo. Do not distribute.",
        is_public_website_eligible=False,
        is_deleted=False,
    )
    # Soft-deleted media
    m_deleted = Media(
        tenant_id=draft_test_tenant.id,
        filename="old_banner.jpg",
        file_path="uploads/old_banner.jpg",
        url=DELETED_URL,
        content_type="image/jpeg",
        file_size=88000,
        title="Old Outdated Banner",
        is_public_website_eligible=True,
        is_deleted=True,
    )
    db_session.add_all([m_eligible, m_ineligible, m_deleted])
    db_session.commit()

    sections = build_initial_website_sections(db_session, draft_test_tenant)
    serialized = json.dumps(sections)

    # 1. Confidential notes must NOT appear anywhere in the output
    assert CONFIDENTIAL_NOTE not in serialized
    assert "patient x" not in serialized.lower()

    # 2. Non-eligible and deleted URLs must NOT appear anywhere
    assert PRIVATE_URL not in serialized
    assert DELETED_URL not in serialized

    # 3. Only the eligible media item should be in gallery
    assert len(sections["gallery"]["items"]) == 1
    assert sections["gallery"]["items"][0]["url"] == "https://cdn.example.com/assets/treatment_room.jpg"
    assert "notes" not in sections["gallery"]["items"][0]


def test_valid_schema(db_session, draft_test_tenant):
    """Generated website must validate against WebsiteConfigSchema and PublicWebsiteData."""
    website, created = ensure_initial_website_draft(db_session, draft_test_tenant)
    assert created is True

    # Pydantic validation via WebsiteConfigSchema
    schema_model = WebsiteConfigSchema.model_validate(website)
    assert schema_model.tenant_id == draft_test_tenant.id
    assert schema_model.template_id == "minimalist"
    assert schema_model.theme_id == "ocean_slate"
    assert schema_model.is_published is False
    assert isinstance(schema_model.sections_data, dict)

    # PublicWebsiteData validation
    public_data = PublicWebsiteData(
        config=schema_model,
        tenant_name=draft_test_tenant.name,
        tenant_subdomain=draft_test_tenant.subdomain,
        tenant_email=draft_test_tenant.email,
        tenant_phone=draft_test_tenant.phone,
        tenant_address=draft_test_tenant.address,
    )
    assert public_data.tenant_name == "Harborview Physical Therapy"
    assert public_data.config.is_published is False
