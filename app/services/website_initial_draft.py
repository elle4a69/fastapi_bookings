"""Create a safe first website draft from existing tenant data.

This is deliberately deterministic: it never calls an AI provider or fills in
business claims. A website starts as a private draft built from the records
the booking platform already owns. Conversational changes afterwards go via
the Business Assistant proposal workflow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.media import Media
from ..models.provider import Provider
from ..models.schedule import ProviderWorkDay
from ..models.service import Service
from ..models.tenant import Tenant
from ..models.tenant_website import TenantWebsite


def _active_services(db: Session, tenant_id: int) -> list[Service]:
    """Retrieve active, visible, non-deleted services for the tenant."""
    return (
        db.query(Service)
        .filter(
            Service.tenant_id == tenant_id,
            Service.active.is_(True),
            Service.is_visible.is_(True),
            Service.deleted_at.is_(None),
        )
        .order_by(Service.id.asc())
        .all()
    )


def _active_providers(db: Session, tenant_id: int) -> list[Provider]:
    """Retrieve active, visible, non-deleted providers for the tenant."""
    return (
        db.query(Provider)
        .filter(
            Provider.tenant_id == tenant_id,
            Provider.active.is_(True),
            Provider.is_visible.is_(True),
            Provider.deleted_at.is_(None),
        )
        .order_by(Provider.id.asc())
        .all()
    )


def _eligible_media_assets(db: Session, tenant_id: int) -> list[Media]:
    """Return durable Media assets approved for public website use.

    Strictly filters for is_public_website_eligible=True and is_deleted=False.
    Clinical or internal operational notes on the Media record are never accessed
    or included in website copy or metadata.
    """
    return (
        db.query(Media)
        .filter(
            Media.tenant_id == tenant_id,
            Media.is_public_website_eligible.is_(True),
            Media.is_deleted.is_(False),
        )
        .order_by(Media.id.asc())
        .all()
    )


def _format_time_str(time_str: str | None) -> str:
    """Format HH:MM 24-hour string to friendly 12-hour AM/PM string."""
    if not time_str or not isinstance(time_str, str):
        return ""
    cleaned = time_str.strip()
    if not cleaned:
        return ""
    try:
        parts = cleaned.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        ampm = "AM" if hour < 12 else "PM"
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12
        if minute == 0:
            return f"{hour_12}:00 {ampm}"
        return f"{hour_12}:{minute:02d} {ampm}"
    except Exception:
        return cleaned


def _format_day_ranges(day_schedules: list[tuple[str, str]]) -> str:
    """Group consecutive days with identical operating hours."""
    if not day_schedules:
        return ""
    if all(not status for _, status in day_schedules):
        return ""

    lines = []
    i = 0
    n = len(day_schedules)
    while i < n:
        day_name, status = day_schedules[i]
        if not status:
            i += 1
            continue
        j = i
        while j + 1 < n and day_schedules[j + 1][1] == status:
            j += 1
        if i == j:
            lines.append(f"{day_name}: {status}")
        else:
            lines.append(f"{day_schedules[i][0]} - {day_schedules[j][0]}: {status}")
        i = j + 1
    return "\n".join(lines)


def _format_business_hours(db: Session, tenant_id: int, providers: list[Provider]) -> str:
    """Format real operating hours from ProviderWorkDay or Provider weekly_schedule.

    Never invents fictional hours. Returns empty string if no schedule exists.
    """
    # 1. Check ProviderWorkDay company-wide records (provider_id IS NULL)
    company_workdays = (
        db.query(ProviderWorkDay)
        .filter(
            ProviderWorkDay.tenant_id == tenant_id,
            ProviderWorkDay.provider_id.is_(None),
        )
        .order_by(ProviderWorkDay.weekday.asc())
        .all()
    )

    workdays_to_use = company_workdays
    # If no company-wide workdays, look for provider-specific workdays of active providers
    if not workdays_to_use:
        provider_ids = [p.id for p in providers]
        if provider_ids:
            workdays_to_use = (
                db.query(ProviderWorkDay)
                .filter(
                    ProviderWorkDay.tenant_id == tenant_id,
                    ProviderWorkDay.provider_id.in_(provider_ids),
                )
                .order_by(ProviderWorkDay.weekday.asc())
                .all()
            )

    day_abbrevs = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    if workdays_to_use:
        by_weekday: dict[int, list[ProviderWorkDay]] = {d: [] for d in range(7)}
        for wd in workdays_to_use:
            if 0 <= wd.weekday <= 6:
                by_weekday[wd.weekday].append(wd)

        schedules: list[tuple[str, str]] = []
        has_any_working = False
        for d in range(7):
            day_name = day_abbrevs[d]
            entries = by_weekday[d]
            if not entries:
                continue
            working_entries = [e for e in entries if e.is_working]
            if working_entries:
                has_any_working = True
                first_w = working_entries[0]
                start = _format_time_str(first_w.start_time)
                end = _format_time_str(first_w.end_time)
                if start and end:
                    schedules.append((day_name, f"{start} - {end}"))
                elif start:
                    schedules.append((day_name, f"From {start}"))
                else:
                    schedules.append((day_name, "Open"))
            else:
                schedules.append((day_name, "Closed"))

        if has_any_working and schedules:
            return _format_day_ranges(schedules)

    # 2. Fall back to provider weekly_schedule JSON if present
    for prov in providers:
        if isinstance(prov.weekly_schedule, dict) and prov.weekly_schedule:
            day_keys = [
                ("Mon", "monday"),
                ("Tue", "tuesday"),
                ("Wed", "wednesday"),
                ("Thu", "thursday"),
                ("Fri", "friday"),
                ("Sat", "saturday"),
                ("Sun", "sunday"),
            ]
            schedules = []
            has_working = False
            for abbrev, key in day_keys:
                info = prov.weekly_schedule.get(key)
                if isinstance(info, dict):
                    is_working = info.get("is_working", False)
                    if is_working:
                        has_working = True
                        start_raw = (
                            info.get("start_time")
                            or info.get("start")
                            or info.get("open")
                        )
                        end_raw = (
                            info.get("end_time") or info.get("end") or info.get("close")
                        )
                        start = _format_time_str(start_raw)
                        end = _format_time_str(end_raw)
                        if start and end:
                            schedules.append((abbrev, f"{start} - {end}"))
                        else:
                            schedules.append((abbrev, "Open"))
                    else:
                        schedules.append((abbrev, "Closed"))
            if has_working and schedules:
                return _format_day_ranges(schedules)

    return ""


def _preferred_existing_images(
    tenant: Tenant,
    services: list[Service],
    providers: list[Provider],
    eligible_media: list[Media],
) -> list[str]:
    """Return prioritized list of existing images owned by tenant records.

    Durable Media assets approved for public website use are included alongside
    tenant logo, service images, and provider images.
    """
    candidates: list[str | None] = []
    # If durable eligible media assets are present, prioritize them
    candidates.extend(m.url for m in eligible_media)
    # Include tenant logo
    candidates.append(tenant.logo_url)
    # Include service and provider images
    candidates.extend(service.image for service in services)
    candidates.extend(provider.image for provider in providers)

    return list(
        dict.fromkeys(
            value.strip()
            for value in candidates
            if isinstance(value, str) and value.strip()
        )
    )


def build_initial_website_sections(db: Session, tenant: Tenant) -> dict[str, Any]:
    """Build a private, fact-only draft suitable for a first preview."""
    services = _active_services(db, tenant.id)
    providers = _active_providers(db, tenant.id)
    eligible_media = _eligible_media_assets(db, tenant.id)
    images = _preferred_existing_images(
        tenant, services, providers, eligible_media
    )
    formatted_hours = _format_business_hours(db, tenant.id, providers)

    service_names = [
        service.name.strip()
        for service in services
        if service.name and service.name.strip()
    ]
    service_summary = ", ".join(service_names[:3])
    business_name = tenant.name.strip() if tenant.name else "Your business"

    missing: list[str] = []
    if not tenant.phone and not tenant.email:
        missing.append("a phone number or email address")
    if not service_names:
        missing.append("at least one active service")
    if not images:
        missing.append("a business photo in the Media area or a service/provider image")
    if not formatted_hours:
        missing.append("business opening hours")

    # Clean, factual Hero subhead
    if service_summary and tenant.address:
        hero_subhead = (
            f"Explore {service_summary} in {tenant.address.strip()} and book online."
        )
    elif service_summary:
        hero_subhead = f"Explore {service_summary} and book online."
    elif tenant.address:
        hero_subhead = (
            f"Professional services at {tenant.address.strip()}. Book online today."
        )
    else:
        hero_subhead = "Explore our services and book online."

    # Clean, factual About story
    story_parts = []
    if tenant.address:
        story_parts.append(
            f"Conveniently located at {tenant.address.strip()}, {business_name} offers a welcoming environment dedicated to professional care."
        )
    else:
        story_parts.append(
            f"{business_name} offers professional care tailored to your needs."
        )

    if service_names:
        if len(service_names) == 1:
            story_parts.append(f"We specialize in {service_names[0]}.")
        elif len(service_names) <= 3:
            story_parts.append(
                f"Our specialized offerings include {', '.join(service_names[:-1])} and {service_names[-1]}."
            )
        else:
            story_parts.append(
                f"Our specialized offerings include {', '.join(service_names[:3])}, and more."
            )

    provider_descs = [
        p.description.strip()
        for p in providers
        if p.description and p.description.strip()
    ]
    if provider_descs:
        story_parts.append(provider_descs[0])
    elif providers:
        p_names = [p.name.strip() for p in providers if p.name and p.name.strip()]
        if len(p_names) == 1:
            story_parts.append(f"Appointments are provided by {p_names[0]}.")
        elif len(p_names) > 1:
            story_parts.append(
                f"Our qualified team includes {', '.join(p_names[:-1])} and {p_names[-1]}."
            )

    story_parts.append("Book your appointment online or reach out with any questions.")
    about_story = " ".join(story_parts)

    # Gallery items: strictly derived from eligible media (NO internal/clinical notes)
    gallery_items = [
        {
            "id": m.id,
            "url": m.url,
            "title": m.title or "",
            "alt_text": m.alt_text or m.title or "",
            "description": m.description or "",
        }
        for m in eligible_media
    ]

    # Service items
    service_items = [
        {
            "id": s.id,
            "name": s.name.strip(),
            "description": s.description.strip() if s.description else "",
            "duration": s.duration,
            "price": float(s.price) if s.price is not None else None,
            "image": s.image or "",
        }
        for s in services
    ]

    # Services subhead
    if service_summary:
        services_subhead = (
            f"Choose from our available services including {service_summary}."
        )
    else:
        services_subhead = "Choose a service and book a time that suits you."

    sections: dict[str, Any] = {
        "hero": {
            "headline": f"Welcome to {business_name}",
            "subhead": hero_subhead,
            "cta_text": "Book online",
            "cta_link": "#booking",
            "enabled": True,
        },
        "about": {
            "badge": "About us",
            "headline": f"About {business_name}",
            "story": about_story,
            "enabled": True,
        },
        "services": {
            "headline": "Our services",
            "subhead": services_subhead,
            "show_prices": False,
            "selected_service_ids": [service.id for service in services],
            "items": service_items,
            "enabled": True,
        },
        "gallery": {
            "headline": "Photo Gallery",
            "subhead": f"Take a look at our space, services, and work at {business_name}.",
            "items": gallery_items,
            "enabled": len(gallery_items) > 0,
        },
        "booking": {
            "headline": "Book an appointment",
            "subhead": "Choose a service, date and time that suits you.",
            "embedded_style": "card",
            "enabled": True,
        },
        # Never create fictional reviews. It can be enabled later with verified ones.
        "testimonials": {
            "headline": "Client Reviews",
            "subhead": "What our clients say about us.",
            "items": [],
            "enabled": False,
        },
        "contact": {
            "headline": "Get in touch",
            "subhead": f"Reach out to {business_name} or visit our location.",
            "address": tenant.address or "",
            "phone": tenant.phone or "",
            "email": tenant.email or "",
            "hours": formatted_hours,
            "enabled": True,
        },
        "footer": {
            "copyright": f"© {datetime.now(timezone.utc).year} {business_name}. All rights reserved.",
            "social_links": {},
            "enabled": True,
        },
        "chat_widget": {
            "enabled": True,
            "invitation_title": "Need help booking?",
            "invitation_message": f"Hi! How can we help with {business_name}?",
            "invitation_delay_seconds": 3,
            "show_sms_fallback": True,
        },
        "draft_meta": {
            "generated_from": "authoritative_booking_data",
            "is_initial_system_draft": True,
            "preferred_media_sources": images,
            "missing_essential_facts": missing,
        },
    }

    if images:
        sections["hero"]["bg_image_url"] = images[0]
    if len(images) > 1:
        sections["about"]["image_url"] = images[1]
    elif images:
        sections["about"]["image_url"] = images[0]

    return sections


def ensure_initial_website_draft(
    db: Session, tenant: Tenant
) -> tuple[TenantWebsite, bool]:
    """Create exactly one private starter draft; never overwrite an existing site."""
    website = (
        db.query(TenantWebsite).filter(TenantWebsite.tenant_id == tenant.id).first()
    )
    if website:
        return website, False

    business_name = tenant.name.strip() if tenant.name else "Your business"
    website = TenantWebsite(
        tenant_id=tenant.id,
        template_id="minimalist",
        theme_id="ocean_slate",
        custom_colors={},
        sections_data=build_initial_website_sections(db, tenant),
        is_published=False,
        seo_title=f"{business_name} | Book online",
        seo_description=f"Explore services and book online with {business_name}.",
    )
    try:
        with db.begin_nested():
            db.add(website)
            db.flush()
        return website, True
    except IntegrityError:
        existing = (
            db.query(TenantWebsite).filter(TenantWebsite.tenant_id == tenant.id).first()
        )
        if existing:
            return existing, False
        raise
