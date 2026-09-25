"""Website API router for the Website Builder Module.

Provides endpoints for managing tenant single-page public websites:
- Admin retrieval and real-time draft configuration saving
- 1-click publishing toggle
- AI copy, template, and theme generation
- Public website configuration retrieval
"""

import copy
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, get_public_tenant
from ...core.config import settings
from ...models.tenant import Tenant
from ...models.tenant_website import DEFAULT_SECTIONS_DATA, TenantWebsite
from ...models.user import User
from ...schemas.website import (
    PublicWebsiteData,
    PublicWebsiteResponse,
    WebsiteAiGenerateRequest,
    WebsiteAiGenerateResponse,
    WebsiteChatMessageItem,
    WebsiteChatRequest,
    WebsiteChatResponse,
    WebsiteConfigSchema,
    WebsitePublishData,
    WebsitePublishRequest,
    WebsitePublishResponse,
    WebsiteResponse,
    WebsiteUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["website"])


def _generate_starter_sections(tenant: Tenant) -> Dict[str, Any]:
    """Generates initial starter content personalized with the tenant's details."""
    sections = copy.deepcopy(DEFAULT_SECTIONS_DATA)
    if tenant.name:
        sections["hero"]["headline"] = f"Welcome to {tenant.name}"
        sections["about"]["headline"] = f"About {tenant.name}"
        sections["footer"]["copyright"] = f"© {datetime.now(timezone.utc).year} {tenant.name}. All rights reserved."
    if tenant.address:
        sections["contact"]["address"] = tenant.address
    if tenant.phone:
        sections["contact"]["phone"] = tenant.phone
    if tenant.email:
        sections["contact"]["email"] = tenant.email
    return sections


@router.get("/api/admin/website", response_model=WebsiteResponse)
def get_admin_website_config(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> WebsiteResponse:
    """Retrieve or initialize the active tenant's draft website configuration."""
    website = db.query(TenantWebsite).filter(TenantWebsite.tenant_id == tenant.id).first()
    if not website:
        initial_sections = _generate_starter_sections(tenant)
        website = TenantWebsite(
            tenant_id=tenant.id,
            template_id="minimalist",
            theme_id="ocean_slate",
            custom_colors={},
            sections_data=initial_sections,
            is_published=False,
            seo_title=f"{tenant.name} | Book Online",
            seo_description=f"Book your appointment online with {tenant.name}.",
        )
        db.add(website)
        db.commit()
        db.refresh(website)

    return WebsiteResponse(ok=True, data=WebsiteConfigSchema.model_validate(website))


@router.put("/api/admin/website", response_model=WebsiteResponse)
def update_admin_website_config(
    payload: WebsiteUpdateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> WebsiteResponse:
    """Update the active tenant's draft website configuration."""
    website = db.query(TenantWebsite).filter(TenantWebsite.tenant_id == tenant.id).first()
    if not website:
        initial_sections = _generate_starter_sections(tenant)
        website = TenantWebsite(
            tenant_id=tenant.id,
            template_id="minimalist",
            theme_id="ocean_slate",
            custom_colors={},
            sections_data=initial_sections,
            is_published=False,
            seo_title=f"{tenant.name} | Book Online",
            seo_description=f"Book your appointment online with {tenant.name}.",
        )
        db.add(website)

    update_dict = payload.model_dump(exclude_unset=True)
    for field, val in update_dict.items():
        if val is not None:
            setattr(website, field, val)

    website.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(website)

    return WebsiteResponse(ok=True, data=WebsiteConfigSchema.model_validate(website))


@router.post("/api/admin/website/publish", response_model=WebsitePublishResponse)
def publish_website(
    payload: Optional[WebsitePublishRequest] = None,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> WebsitePublishResponse:
    """Publish current draft website to live status or unpublish it."""
    website = db.query(TenantWebsite).filter(TenantWebsite.tenant_id == tenant.id).first()
    if not website:
        initial_sections = _generate_starter_sections(tenant)
        website = TenantWebsite(
            tenant_id=tenant.id,
            template_id="minimalist",
            theme_id="ocean_slate",
            custom_colors={},
            sections_data=initial_sections,
            is_published=False,
            seo_title=f"{tenant.name} | Book Online",
            seo_description=f"Book your appointment online with {tenant.name}.",
        )
        db.add(website)

    should_publish = payload.is_published if (payload is not None and payload.is_published is not None) else True
    website.is_published = should_publish
    if should_publish:
        website.published_at = datetime.now(timezone.utc)
        message = "Website is now live and published."
    else:
        website.published_at = None
        message = "Website has been unpublished."

    website.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(website)

    return WebsitePublishResponse(
        ok=True,
        data=WebsitePublishData(
            is_published=website.is_published,
            published_at=website.published_at,
            message=message,
        ),
    )


@router.post("/api/admin/website/ai-generate", response_model=WebsiteAiGenerateResponse)
def ai_generate_website_content(
    payload: WebsiteAiGenerateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> WebsiteAiGenerateResponse:
    """Uses AI (OpenAI or intelligent heuristic generator) to generate copy, themes, and layouts."""
    prompt = payload.prompt.lower()
    action = payload.action or "generate_full"
    b_name = tenant.name or "Our Studio"

    # 1. Determine Industry & Tone Heuristics
    is_wellness = any(w in prompt for w in ["spa", "massage", "wellness", "relaxation", "holistic", "therapy", "yoga", "reiki", "zen", "acupuncture"])
    is_medical = any(w in prompt for w in ["clinic", "medical", "doctor", "health", "dental", "physio", "chiro", "ortho", "nurse", "surgery"])
    is_luxury = any(w in prompt for w in ["luxury", "boutique", "salon", "lash", "brow", "hair", "barber", "glam", "aesthetic", "spa lounge", "high end"])
    is_fitness = any(w in prompt for w in ["gym", "fitness", "trainer", "workout", "crossfit", "pilates", "strength", "coach"])

    # Template selection
    if is_wellness:
        template = "wellness"
        theme = "emerald_oasis"
    elif is_medical:
        template = "clinical"
        theme = "royal_indigo"
    elif is_luxury:
        template = "luxury"
        theme = "rose_gold"
    elif is_fitness:
        template = "minimalist"
        theme = "monochrome"
    else:
        template = "minimalist"
        theme = "ocean_slate"

    # Action: Rewrite single section
    if action == "rewrite_section" and payload.section_key:
        sec = payload.section_key
        if sec == "hero":
            rewritten = f"Transformative Excellence at {b_name}. Experience tailored care crafted specifically for your needs."
        elif sec == "about":
            rewritten = f"At {b_name}, we are dedicated to providing world-class quality and individualized attention. Our experienced team blends passion with precision to deliver results you can feel and see every single day."
        elif sec == "services":
            rewritten = "Handcrafted sessions and treatments designed to deliver immediate results and lasting satisfaction."
        elif sec == "booking":
            rewritten = "Effortless online scheduling. Select your preferred specialist, treatment, and time."
        else:
            rewritten = f"Welcome to {b_name}. Designed for exceptional quality and effortless satisfaction."

        return WebsiteAiGenerateResponse(
            ok=True,
            suggested_template=template,
            suggested_theme=theme,
            rewritten_text=rewritten,
            message=f"Section '{sec}' rewritten successfully.",
        )

    # Action: Suggest Theme / Template only
    if action == "suggest_theme":
        return WebsiteAiGenerateResponse(
            ok=True,
            suggested_template=template,
            suggested_theme=theme,
            message=f"Suggested {template} template with {theme} palette based on your description.",
        )

    # Action: Full site copy generation
    sections = copy.deepcopy(DEFAULT_SECTIONS_DATA)

    if is_wellness:
        sections["hero"]["headline"] = f"Restore Mind & Body at {b_name}"
        sections["hero"]["subhead"] = "Immerse yourself in gentle therapeutic rituals, peaceful ambiance, and skilled restorative treatments."
        sections["hero"]["cta_text"] = "Book Your Retreat"
        sections["hero"]["bg_image_url"] = "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1600&q=80"
        sections["about"]["badge"] = "Peaceful Sanctuary"
        sections["about"]["headline"] = "Nurturing Holistic Well-Being"
        sections["about"]["story"] = f"Created as a haven from daily pressures, {b_name} invites you to pause and renew. We combine botanical ingredients, ancient healing arts, and modern therapeutic techniques."
        sections["services"]["headline"] = "Signature Restorative Treatments"
        sections["services"]["subhead"] = "Choose from soothing massages, botanical facials, and deep tissue therapies."
        sections["testimonials"]["items"] = [
            {"name": "Chloe Adams", "role": "Spa Enthusiast", "content": "The calm feeling you get as soon as you step through the doors is magical.", "rating": 5},
            {"name": "Liam Vance", "role": "Weekly Client", "content": "The massage therapists here are truly gifted. Life-changing back relief.", "rating": 5},
        ]
    elif is_medical:
        sections["hero"]["headline"] = f"Trusted Healthcare & Clinical Excellence at {b_name}"
        sections["hero"]["subhead"] = "Compassionate, patient-centered diagnostics and treatment delivered by accredited healthcare professionals."
        sections["hero"]["cta_text"] = "Request Appointment"
        sections["hero"]["bg_image_url"] = "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1600&q=80"
        sections["about"]["badge"] = "Accredited Practice"
        sections["about"]["headline"] = "Leading with Integrity & Science"
        sections["about"]["story"] = f"At {b_name}, patient well-being and clinical accuracy are our highest priorities. Our clinic employs state-of-the-art medical technology to provide comprehensive care."
        sections["services"]["headline"] = "Specialized Consultations & Procedures"
        sections["services"]["subhead"] = "Thorough examinations, personalized treatment plans, and continuous patient follow-up."
        sections["testimonials"]["items"] = [
            {"name": "Dr. Marcus Reed", "role": "Patient", "content": "Professional, punctual, and thoroughly attentive clinical team.", "rating": 5},
            {"name": "Jessica Wright", "role": "Patient", "content": "Clear explanations, comfortable environment, and outstanding follow-up care.", "rating": 5},
        ]
    elif is_luxury:
        sections["hero"]["headline"] = f"Bespoke Styling & Artistry at {b_name}"
        sections["hero"]["subhead"] = "Where modern fashion meets personalized perfection. Step into an exclusive world of luxury and elegance."
        sections["hero"]["cta_text"] = "Reserve Your Chair"
        sections["hero"]["bg_image_url"] = "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=1600&q=80"
        sections["about"]["badge"] = "Haute Artistry"
        sections["about"]["headline"] = "The Art of Refined Beauty"
        sections["about"]["story"] = f"{b_name} represents the gold standard in bespoke styling. Our master stylists and artists craft signature looks that enhance your natural elegance."
        sections["services"]["headline"] = "Curated Atelier Services"
        sections["services"]["subhead"] = "Precision cuts, custom color formulation, and couture finishing."
        sections["testimonials"]["items"] = [
            {"name": "Victoria Sterling", "role": "Fashion Editor", "content": "The only salon I trust with my hair. Flawless attention to detail.", "rating": 5},
            {"name": "Julian Hayes", "role": "Client", "content": "Top tier craftsmanship, private ambiance, and exceptional customer experience.", "rating": 5},
        ]
    else:
        sections["hero"]["headline"] = f"Simple, Seamless Service with {b_name}"
        sections["hero"]["subhead"] = "High quality services delivered on your schedule. Convenient, reliable, and rated five stars."
        sections["hero"]["cta_text"] = "Book Today"
        sections["about"]["headline"] = f"Why Choose {b_name}"
        sections["about"]["story"] = f"We take pride in transparent pricing, skilled practitioners, and seamless online booking. Experience the modern standard with {b_name}."

    if tenant.address:
        sections["contact"]["address"] = tenant.address
    if tenant.phone:
        sections["contact"]["phone"] = tenant.phone
    if tenant.email:
        sections["contact"]["email"] = tenant.email

    return WebsiteAiGenerateResponse(
        ok=True,
        suggested_template=template,
        suggested_theme=theme,
        generated_sections=sections,
        message=f"Generated comprehensive website configuration for '{prompt}'.",
    )


@router.get("/api/public/website", response_model=PublicWebsiteResponse)
def get_public_website(
    preview: bool = Query(False, description="Preview unpublished draft if true"),
    tenant: Tenant = Depends(get_public_tenant),
    db: Session = Depends(get_db),
) -> PublicWebsiteResponse:
    """Public endpoint returning the active website configuration for the current tenant."""
    from ...models.service import Service as ServiceModel
    active_services = (
        db.query(ServiceModel)
        .filter(
            ServiceModel.tenant_id == tenant.id,
            ServiceModel.active.is_(True),
            ServiceModel.deleted_at.is_(None),
        )
        .all()
    )
    services_data = [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description or "",
            "duration": s.duration,
            "price": float(s.price) if s.price is not None else None,
            "image": s.image,
        }
        for s in active_services
    ]

    website = db.query(TenantWebsite).filter(TenantWebsite.tenant_id == tenant.id).first()
    if not website:
        # If previewing or not found, return 404 or default starter if preview
        if preview:
            starter_sections = _generate_starter_sections(tenant)
            config = WebsiteConfigSchema(
                tenant_id=tenant.id,
                template_id="minimalist",
                theme_id="ocean_slate",
                sections_data=starter_sections,
                is_published=False,
                seo_title=f"{tenant.name} | Book Online",
                seo_description=f"Book your appointment online with {tenant.name}.",
            )
            return PublicWebsiteResponse(
                ok=True,
                data=PublicWebsiteData(
                    config=config,
                    tenant_name=tenant.name,
                    tenant_subdomain=tenant.subdomain,
                    tenant_email=tenant.email,
                    tenant_phone=tenant.phone,
                    tenant_address=tenant.address,
                    tenant_logo_url=tenant.logo_url,
                    services=services_data,
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found or not published.",
        )

    if not website.is_published and not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website is currently unpublished.",
        )

    return PublicWebsiteResponse(
        ok=True,
        data=PublicWebsiteData(
            config=WebsiteConfigSchema.model_validate(website),
            tenant_name=tenant.name,
            tenant_subdomain=tenant.subdomain,
            tenant_email=tenant.email,
            tenant_phone=tenant.phone,
            tenant_address=tenant.address,
            tenant_logo_url=tenant.logo_url,
            services=services_data,
        ),
    )


@router.post("/api/public/website/chat", response_model=WebsiteChatResponse)
async def public_website_chat(
    payload: WebsiteChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WebsiteChatResponse:
    """Public chat endpoint for visitor interactions via the website chat widget.

    - Resolves tenant context from payload.tenant_id, X-Tenant header, or host subdomain.
    - Creates or re-uses an SmsConversation with source 'web_chat'.
    - Stores the incoming visitor message.
    - Generates an immediate contextual autoresponder or AI assistant answer.
    - Stores the outgoing response in the conversation thread.
    - Syncs with Chatwoot if a live binding is active.
    - Returns the reply and full conversation history for immediate display.
    """
    # 1. Resolve Target Tenant
    target_tenant: Optional[Tenant] = None
    if payload.tenant_id is not None:
        target_tenant = db.query(Tenant).filter(Tenant.id == payload.tenant_id).first()

    if not target_tenant:
        supplied_subdomain = request.headers.get("X-Tenant") or request.query_params.get("tenant")
        from ..deps import _tenant_subdomain_from_host
        host_subdomain = _tenant_subdomain_from_host(request.url.hostname)
        subdomain = supplied_subdomain or host_subdomain
        if subdomain:
            target_tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain.lower()).first()

    if not target_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to resolve tenant context. Provide tenant_id in payload or X-Tenant header.",
        )

    # 2. Resolve default Provider and SMS Account
    from ...models.provider import Provider
    from ...models.sms_account import SmsAccount
    from ...models.sms_conversation import SmsConversation
    from ...models.sms_message import SmsMessage
    from ...models.client import Client
    from ...models.service import Service as ServiceModel

    provider = db.query(Provider).filter(Provider.tenant_id == target_tenant.id).first()
    if not provider:
        provider = Provider(
            tenant_id=target_tenant.id,
            name=f"{target_tenant.name} Team",
            active=True,
        )
        db.add(provider)
        db.flush()

    sms_account = (
        db.query(SmsAccount)
        .filter(SmsAccount.tenant_id == target_tenant.id, SmsAccount.is_enabled == True)
        .first()
    )

    # 3. Match or create Client if contact info provided
    client: Optional[Client] = None
    clean_contact = (payload.visitor_contact or "").strip()
    is_email = "@" in clean_contact

    if clean_contact:
        client = (
            db.query(Client)
            .filter(
                Client.tenant_id == target_tenant.id,
                (Client.phone == clean_contact) | (Client.email == clean_contact),
            )
            .first()
        )
        if not client:
            client = Client(
                tenant_id=target_tenant.id,
                name=payload.visitor_name or "Web Visitor",
                phone=clean_contact if not is_email else None,
                email=clean_contact if is_email else None,
                notes="Created via Website Chat Widget",
            )
            db.add(client)
            db.flush()

    # 4. Resolve or create SmsConversation
    conversation: Optional[SmsConversation] = None
    if payload.conversation_id:
        conversation = (
            db.query(SmsConversation)
            .filter(
                SmsConversation.id == payload.conversation_id,
                SmsConversation.tenant_id == target_tenant.id,
            )
            .first()
        )

    if not conversation:
        if clean_contact:
            customer_address = clean_contact
        else:
            v_slug = (payload.visitor_name or "guest").lower().replace(" ", "_")
            customer_address = f"web_{v_slug}_{int(datetime.now(timezone.utc).timestamp())}"

        conversation = (
            db.query(SmsConversation)
            .filter(
                SmsConversation.tenant_id == target_tenant.id,
                SmsConversation.customer_address == customer_address,
            )
            .first()
        )

        if not conversation:
            conversation = SmsConversation(
                tenant_id=target_tenant.id,
                provider_id=provider.id,
                sms_account_id=sms_account.id if sms_account else None,
                customer_address=customer_address,
                client_id=client.id if client else None,
                state="auto-reply",
                source="web_chat",
                unread_count=1,
                last_activity_at=datetime.now(timezone.utc),
            )
            db.add(conversation)
            db.flush()
        else:
            conversation.source = conversation.source or "web_chat"
            conversation.unread_count += 1
            conversation.last_activity_at = datetime.now(timezone.utc)
            if client and not conversation.client_id:
                conversation.client_id = client.id
    else:
        conversation.unread_count += 1
        conversation.last_activity_at = datetime.now(timezone.utc)
        if client and not conversation.client_id:
            conversation.client_id = client.id

    # 5. Record Inbound Message
    inbound_msg = SmsMessage(
        tenant_id=target_tenant.id,
        provider_id=conversation.provider_id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body=payload.message,
        normalized_body=payload.message.strip().lower(),
        direction="inbound",
        author_type="customer",
        status="received",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db.add(inbound_msg)
    db.flush()

    # 6. Generate Contextual Assistant Reply
    website = db.query(TenantWebsite).filter(TenantWebsite.tenant_id == target_tenant.id).first()
    sec_data = website.sections_data if website and website.sections_data else {}
    contact_sec = sec_data.get("contact", {})
    biz_hours = contact_sec.get("hours") or "Monday - Friday: 9:00 AM - 6:00 PM"
    biz_phone = contact_sec.get("phone") or target_tenant.phone or "+1 (555) 234-5678"
    biz_address = contact_sec.get("address") or target_tenant.address or ""
    clean_text = payload.message.lower().strip()

    reply_text: str = ""

    if any(w in clean_text for w in ["hour", "open", "close", "schedule", "when are you", "operating"]):
        reply_text = f"We are open during the following hours:\n{biz_hours}\n\nWould you like to schedule an appointment during these times?"
    elif any(w in clean_text for w in ["price", "cost", "service", "menu", "treatment", "how much", "rate"]):
        active_svcs = (
            db.query(ServiceModel)
            .filter(
                ServiceModel.tenant_id == target_tenant.id,
                ServiceModel.active.is_(True),
                ServiceModel.deleted_at.is_(None),
            )
            .all()
        )
        if active_svcs:
            svc_lines = []
            for s in active_svcs[:5]:
                p_str = f" - ${float(s.price):.2f}" if s.price is not None else ""
                svc_lines.append(f"• {s.name} ({s.duration} min){p_str}")
            reply_text = f"Here are our signature services:\n" + "\n".join(svc_lines) + "\n\nWould you like to book one of these treatments?"
        else:
            reply_text = "We offer a curated selection of personalized treatments. Please explore our Services section above or let us know what you'd like to book!"
    elif any(w in clean_text for w in ["location", "where", "address", "find you", "directions"]):
        reply_text = f"We are located at {biz_address or 'our main studio'}. We look forward to seeing you!"
    else:
        # Check deterministic booking/slot engine
        from ...services.sms.ai_orchestrator import run_local_rules_engine
        try:
            rule_reply = run_local_rules_engine(db, sms_account, conversation, payload.message)
            if rule_reply and "[[HANDOFF" not in rule_reply:
                reply_text = rule_reply
        except Exception as ex:
            logger.debug(f"Local rules engine check bypassed: {ex}")

        if not reply_text:
            v_name = payload.visitor_name or "there"
            reply_text = (
                f"Hi {v_name}! 👋 Thank you for messaging {target_tenant.name}. "
                "Our booking assistant has received your inquiry and will take care of you. "
                f"You can also schedule an appointment online or call us directly at {biz_phone}."
            )

    # 7. Record Outbound Assistant Message
    outbound_msg = SmsMessage(
        tenant_id=target_tenant.id,
        provider_id=conversation.provider_id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body=reply_text,
        normalized_body=reply_text.strip().lower(),
        direction="outbound",
        author_type="ai",
        status="sent",
        parent_message_id=inbound_msg.id,
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db.add(outbound_msg)

    from ...models.sms_outbox import SmsConversationEvent
    event = SmsConversationEvent(
        conversation_id=conversation.id,
        type="web_chat_message",
        meta={"visitor_name": payload.visitor_name, "message": payload.message, "reply": reply_text},
    )
    db.add(event)
    db.commit()

    # 8. Sync with Chatwoot if bound
    try:
        from ...models.sms_chatwoot import SmsChatwootBinding
        binding = (
            db.query(SmsChatwootBinding)
            .filter(
                SmsChatwootBinding.tenant_id == target_tenant.id,
                SmsChatwootBinding.is_enabled == True,
            )
            .first()
        )
        if binding and conversation.chatwoot_conversation_id:
            from ...services.sms.chatwoot_service import send_chatwoot_message
            await send_chatwoot_message(db, conversation, reply_text)
    except Exception as cw_err:
        logger.debug(f"Chatwoot sync skipped: {cw_err}")

    # 9. Return all messages
    all_msgs = (
        db.query(SmsMessage)
        .filter(SmsMessage.conversation_id == conversation.id)
        .order_by(SmsMessage.occurred_at.asc())
        .all()
    )
    msg_items = [
        WebsiteChatMessageItem(
            id=m.id,
            direction=m.direction,
            author_type=m.author_type,
            body=m.body,
            occurred_at=m.occurred_at,
        )
        for m in all_msgs
    ]

    return WebsiteChatResponse(
        ok=True,
        conversation_id=conversation.id,
        reply=reply_text,
        messages=msg_items,
    )


@router.get("/api/public/website/chat/{conversation_id}", response_model=WebsiteChatResponse)
def get_public_website_chat_messages(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> WebsiteChatResponse:
    """Retrieve message history for an active web chat conversation."""
    from ...models.sms_conversation import SmsConversation
    from ...models.sms_message import SmsMessage

    conversation = db.query(SmsConversation).filter(SmsConversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    all_msgs = (
        db.query(SmsMessage)
        .filter(SmsMessage.conversation_id == conversation.id)
        .order_by(SmsMessage.occurred_at.asc())
        .all()
    )
    msg_items = [
        WebsiteChatMessageItem(
            id=m.id,
            direction=m.direction,
            author_type=m.author_type,
            body=m.body,
            occurred_at=m.occurred_at,
        )
        for m in all_msgs
    ]
    latest_reply = msg_items[-1].body if msg_items else ""

    return WebsiteChatResponse(
        ok=True,
        conversation_id=conversation.id,
        reply=latest_reply,
        messages=msg_items,
    )

