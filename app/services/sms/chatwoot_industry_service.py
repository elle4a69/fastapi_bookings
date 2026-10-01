"""Chatwoot Industry Automation, Custom Attributes & Macro Provisioning Service.

Authoritative pipeline for industry-tailored Chatwoot customization:
- Custom Attribute Definitions scoped per account (allied_health, automotive, wellness_salon, professional_services)
- Canned Responses & Macros scoped per account
- Idempotent provisioning preventing duplicates
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from ...core.config import settings
from .chatwoot_provisioning_service import _get_chatwoot_config

logger = logging.getLogger(__name__)

# Industry-specific custom attribute definitions
# display_type: "text", "number", "date", etc. (Chatwoot also maps: 0=text, 1=number, 5=date)
# model: "conversation_attribute" (or 0)
INDUSTRY_CUSTOM_ATTRIBUTES: Dict[str, List[Dict[str, Any]]] = {
    "allied_health": [
        {
            "key": "gp_referral_number",
            "display_name": "GP Referral Number",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Doctor / GP Referral number for Medicare/health fund claims",
        },
        {
            "key": "health_fund",
            "display_name": "Health Fund",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Private health insurance provider or member fund",
        },
        {
            "key": "injury_type",
            "display_name": "Injury / Condition Type",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Clinical presentation, primary condition or injury area",
        },
    ],
    "automotive": [
        {
            "key": "vehicle_vin",
            "display_name": "Vehicle VIN",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "17-character vehicle identification number",
        },
        {
            "key": "vehicle_rego",
            "display_name": "Vehicle Registration",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Vehicle registration license plate number",
        },
        {
            "key": "service_mileage",
            "display_name": "Current Mileage (km)",
            "display_type": "number",
            "model": "conversation_attribute",
            "description": "Odometer reading at time of booking or drop-off",
        },
    ],
    "wellness_salon": [
        {
            "key": "preferred_practitioner",
            "display_name": "Preferred Stylist / Practitioner",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Client requested primary therapist or stylist",
        },
        {
            "key": "hair_length",
            "display_name": "Hair Length / Service Tier",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Hair length or styling tier (Short, Medium, Long, Extra Long)",
        },
        {
            "key": "patch_test_date",
            "display_name": "Patch Test Date",
            "display_type": "date",
            "model": "conversation_attribute",
            "description": "Date skin sensitivity allergy patch test was administered",
        },
    ],
    "professional_services": [
        {
            "key": "client_company",
            "display_name": "Client Company / Organization",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Corporate entity or company name representing the client",
        },
        {
            "key": "case_reference",
            "display_name": "Case / Matter Reference",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Internal matter code, case file, or project identifier",
        },
        {
            "key": "billing_reference",
            "display_name": "Billing Account Code",
            "display_type": "text",
            "model": "conversation_attribute",
            "description": "Cost center, purchase order, or billing account reference",
        },
    ],
}

# Industry-specific canned responses & macros
INDUSTRY_CANNED_RESPONSES: Dict[str, List[Dict[str, str]]] = {
    "allied_health": [
        {
            "short_code": "directions",
            "content": "Directions & Parking: We are located with accessible street parking and a dedicated patient lot behind the building.",
        },
        {
            "short_code": "late_policy",
            "content": "Late Arrival Policy: If you arrive more than 10 minutes past your appointment time, we will do our best to accommodate you, but may need to adjust your consultation duration.",
        },
        {
            "short_code": "cancellation",
            "content": "Cancellation Policy: Please provide at least 24 hours notice to reschedule or cancel your appointment without incurring a fee.",
        },
        {
            "short_code": "post_treatment",
            "content": "Post-Treatment Advice: Please stay hydrated and follow the personalized exercises provided by your practitioner. Contact us if you experience unexpected discomfort.",
        },
        {
            "short_code": "gp_referral",
            "content": "GP Referral Notice: If you are claiming under Medicare or a chronic disease management plan, please ensure your GP referral is uploaded or brought to your initial session.",
        },
    ],
    "automotive": [
        {
            "short_code": "directions",
            "content": "Directions & Workshop Bays: Enter via the main service driveway and park in the customer drop-off bay in front of reception.",
        },
        {
            "short_code": "late_policy",
            "content": "Drop-off Notice: Morning drop-offs are scheduled between 7:30 AM and 9:00 AM. If you are delayed, please notify our service desk immediately.",
        },
        {
            "short_code": "cancellation",
            "content": "Booking Rescheduling: Please notify us at least 24 hours prior to your service booking if you need to change your date or loan vehicle reservation.",
        },
        {
            "short_code": "quote_disclaimer",
            "content": "Diagnostics & Estimate Policy: Any initial quotes are subject to physical inspection. Our technician will call you for authorization prior to carrying out additional work.",
        },
        {
            "short_code": "service_ready",
            "content": "Vehicle Ready for Collection: Your vehicle service has been completed and is ready for collection before 5:00 PM today.",
        },
    ],
    "wellness_salon": [
        {
            "short_code": "directions",
            "content": "Directions & Arrival: Our salon is located on the ground floor. We recommend arriving 5 minutes early to settle in and enjoy a welcome beverage.",
        },
        {
            "short_code": "late_policy",
            "content": "Late Arrival Policy: To ensure every guest enjoys their full experience, late arrivals may result in an abbreviated service time.",
        },
        {
            "short_code": "cancellation",
            "content": "Cancellation Policy: We kindly request 24 hours notice for cancellations or rescheduling. Deposits may be forfeited for last-minute cancellations.",
        },
        {
            "short_code": "patch_test",
            "content": "Patch Test Reminder: First-time color treatments require a skin patch test at least 48 hours before your appointment.",
        },
        {
            "short_code": "aftercare",
            "content": "Hair & Skin Aftercare: To prolong the life of your treatment, avoid washing your hair for 48 hours and use sulfate-free professional products.",
        },
    ],
    "professional_services": [
        {
            "short_code": "directions",
            "content": "Office Directions & Visitor Check-In: Please check in at reception on Level 3. Photo ID may be required for building security.",
        },
        {
            "short_code": "late_policy",
            "content": "Meeting Policy: If you are delayed for your consultation, please let us know so your advisor can adjust the session agenda.",
        },
        {
            "short_code": "cancellation",
            "content": "Cancellation & Rescheduling: Advisory sessions can be rescheduled up to 24 hours prior without cancellation fees.",
        },
        {
            "short_code": "meeting_prep",
            "content": "Consultation Preparation: Please review and upload any relevant documents or financial statements in advance so we can maximize our session time.",
        },
        {
            "short_code": "billing_faq",
            "content": "Billing & Retainer Notice: Invoices are issued at the conclusion of advisory sessions or monthly under your existing retainer agreement.",
        },
    ],
}


def detect_tenant_industry(tenant: Any, db: Optional[Any] = None) -> str:
    """Infer tenant industry preset from translation settings or default to allied_health."""
    if hasattr(tenant, "translation") and tenant.translation and tenant.translation.terminology:
        terms = tenant.translation.terminology
        if terms.get("_preset"):
            return terms["_preset"]
        # Match signature terms
        client_term = str(terms.get("client", "")).lower()
        provider_term = str(terms.get("provider", "")).lower()
        if client_term == "patient" or provider_term == "practitioner":
            return "allied_health"
        if client_term == "customer" or provider_term in ("technician", "mechanic"):
            return "automotive"
        if provider_term in ("stylist", "therapist") or str(terms.get("service", "")).lower() == "treatment":
            return "wellness_salon"
        if provider_term == "consultant" or str(terms.get("booking", "")).lower() == "session":
            return "professional_services"
    return "allied_health"


def provision_industry_custom_attributes(
    account_id: int,
    industry: str,
    client: Optional[httpx.Client] = None,
    base_url: Optional[str] = None,
    api_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Idempotently provision custom attribute definitions for an industry preset."""
    industry_key = industry.strip().lower()
    if industry_key not in INDUSTRY_CUSTOM_ATTRIBUTES:
        raise ValueError(
            f"Unknown industry '{industry}'. Available: {list(INDUSTRY_CUSTOM_ATTRIBUTES.keys())}"
        )

    resolved_base_url, u_token, _, _ = _get_chatwoot_config(
        chatwoot_base_url=base_url,
        api_token=api_token,
    )
    if not u_token:
        logger.warning(f"No Chatwoot API access token available to provision attributes for account {account_id}")
        return []

    should_close_client = False
    if client is None:
        client = httpx.Client(timeout=10.0)
        should_close_client = True

    results: List[Dict[str, Any]] = []
    try:
        # 1. Fetch existing definitions
        existing_defs: List[Dict[str, Any]] = []
        try:
            get_resp = client.get(
                f"{resolved_base_url}/api/v1/accounts/{account_id}/custom_attribute_definitions",
                headers={"api_access_token": u_token},
            )
            if get_resp.status_code == 200:
                payload = get_resp.json()
                if isinstance(payload, list):
                    existing_defs = payload
                elif isinstance(payload, dict):
                    existing_defs = payload.get("payload", []) or payload.get("custom_attribute_definitions", [])
        except Exception as e:
            logger.warning(f"Could not list custom attributes for account {account_id}: {e}")

        existing_keys = {
            item.get("attribute_key")
            for item in existing_defs
            if isinstance(item, dict) and item.get("attribute_key")
        }

        # 2. Provision target attributes
        target_attributes = INDUSTRY_CUSTOM_ATTRIBUTES[industry_key]
        for attr in target_attributes:
            attr_key = attr["key"]
            if attr_key in existing_keys:
                existing_item = next((item for item in existing_defs if item.get("attribute_key") == attr_key), None)
                results.append({
                    "attribute_key": attr_key,
                    "status": "already_exists",
                    "details": existing_item,
                })
                continue

            payload = {
                "attribute_display_name": attr["display_name"],
                "attribute_key": attr["key"],
                "attribute_display_type": attr["display_type"],
                "attribute_description": attr.get("description", ""),
                "attribute_model": attr.get("model", "conversation_attribute"),
            }
            try:
                post_resp = client.post(
                    f"{resolved_base_url}/api/v1/accounts/{account_id}/custom_attribute_definitions",
                    headers={"api_access_token": u_token},
                    json=payload,
                )
                if post_resp.status_code in (200, 201):
                    created_data = post_resp.json()
                    results.append({
                        "attribute_key": attr_key,
                        "status": "created",
                        "details": created_data,
                    })
                    existing_keys.add(attr_key)
                else:
                    logger.warning(
                        f"Failed creating custom attribute {attr_key} (status {post_resp.status_code}): {post_resp.text}"
                    )
                    results.append({
                        "attribute_key": attr_key,
                        "status": "failed",
                        "error": post_resp.text,
                    })
            except Exception as exc:
                logger.error(f"Error creating custom attribute {attr_key}: {exc}")
                results.append({
                    "attribute_key": attr_key,
                    "status": "error",
                    "error": str(exc),
                })
    finally:
        if should_close_client:
            client.close()

    return results


def provision_industry_canned_responses(
    account_id: int,
    industry: str,
    client: Optional[httpx.Client] = None,
    base_url: Optional[str] = None,
    api_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Idempotently provision canned macro responses for an industry preset."""
    industry_key = industry.strip().lower()
    if industry_key not in INDUSTRY_CANNED_RESPONSES:
        raise ValueError(
            f"Unknown industry '{industry}'. Available: {list(INDUSTRY_CANNED_RESPONSES.keys())}"
        )

    resolved_base_url, u_token, _, _ = _get_chatwoot_config(
        chatwoot_base_url=base_url,
        api_token=api_token,
    )
    if not u_token:
        logger.warning(f"No Chatwoot API access token available to provision canned responses for account {account_id}")
        return []

    should_close_client = False
    if client is None:
        client = httpx.Client(timeout=10.0)
        should_close_client = True

    results: List[Dict[str, Any]] = []
    try:
        # 1. Fetch existing canned responses
        existing_canned: List[Dict[str, Any]] = []
        try:
            get_resp = client.get(
                f"{resolved_base_url}/api/v1/accounts/{account_id}/canned_responses",
                headers={"api_access_token": u_token},
            )
            if get_resp.status_code == 200:
                payload = get_resp.json()
                if isinstance(payload, list):
                    existing_canned = payload
                elif isinstance(payload, dict):
                    existing_canned = payload.get("payload", []) or payload.get("canned_responses", [])
        except Exception as e:
            logger.warning(f"Could not list canned responses for account {account_id}: {e}")

        existing_codes = {
            item.get("short_code")
            for item in existing_canned
            if isinstance(item, dict) and item.get("short_code")
        }

        # 2. Provision target canned responses
        target_responses = INDUSTRY_CANNED_RESPONSES[industry_key]
        for canned in target_responses:
            code = canned["short_code"]
            if code in existing_codes:
                existing_item = next((item for item in existing_canned if item.get("short_code") == code), None)
                results.append({
                    "short_code": code,
                    "status": "already_exists",
                    "details": existing_item,
                })
                continue

            payload = {
                "short_code": canned["short_code"],
                "content": canned["content"],
            }
            try:
                post_resp = client.post(
                    f"{resolved_base_url}/api/v1/accounts/{account_id}/canned_responses",
                    headers={"api_access_token": u_token},
                    json=payload,
                )
                if post_resp.status_code in (200, 201):
                    created_data = post_resp.json()
                    results.append({
                        "short_code": code,
                        "status": "created",
                        "details": created_data,
                    })
                    existing_codes.add(code)
                else:
                    logger.warning(
                        f"Failed creating canned response {code} (status {post_resp.status_code}): {post_resp.text}"
                    )
                    results.append({
                        "short_code": code,
                        "status": "failed",
                        "error": post_resp.text,
                    })
            except Exception as exc:
                logger.error(f"Error creating canned response {code}: {exc}")
                results.append({
                    "short_code": code,
                    "status": "error",
                    "error": str(exc),
                })
    finally:
        if should_close_client:
            client.close()

    return results


def sync_industry_presets(
    account_id: int,
    industry: str,
    client: Optional[httpx.Client] = None,
    base_url: Optional[str] = None,
    api_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Synchronize both custom attributes and canned responses for an industry preset."""
    attrs = provision_industry_custom_attributes(
        account_id=account_id,
        industry=industry,
        client=client,
        base_url=base_url,
        api_token=api_token,
    )
    canned = provision_industry_canned_responses(
        account_id=account_id,
        industry=industry,
        client=client,
        base_url=base_url,
        api_token=api_token,
    )
    return {
        "account_id": account_id,
        "industry": industry,
        "custom_attributes": attrs,
        "canned_responses": canned,
    }
