#!/usr/bin/env python
"""Idempotent data import script from assistant-ui into fastapi_bookings.

Imports knowledge, operational policies, system prompts, bootcamp settings,
services catalog, and provider working hours from the reference assistant-ui
repository into FastAPI Bookings with strict multi-tenant isolation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.curated_memory import CuratedMemory
from app.models.provider import Provider
from app.models.schedule import ProviderWorkDay
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.sms_bootcamp import SmsBootcampSettings
from app.models.sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile
from app.models.tenant import Tenant

logger = logging.getLogger("import_assistant_ui_data")

DEFAULT_ASSISTANT_UI_DIR = Path(os.environ.get("ASSISTANT_UI_DIR", r"f:\Projects\assistant-ui"))

POLICY_VARIABLE_NAMES = (
    "AVAILABILITY_REPLY_POLICY",
    "BOOKING_AVAILABILITY_SAFETY_POLICY",
    "RETRIEVED_BUSINESS_CONTEXT_POLICY",
    "SERVICE_AND_BOOKING_CONVERSATION_POLICY",
    "RELEVANCE_AND_THREAD_FLOW_POLICY",
    "SMS_TYPOGRAPHY_POLICY",
)

FALLBACK_STYLE_PROFILE = {
    "flirtiness": 2,
    "cheerfulness": 3,
    "wit": 2,
    "sarcasm": 0,
    "warmth": 4,
    "directness": 3,
    "chattiness": 1,
    "patience": 4,
}


def parse_policies_from_constants(constants_path: Path) -> dict[str, str]:
    """Parse deterministic operational policies from constants.py without code execution."""
    if not constants_path.exists():
        raise FileNotFoundError(f"Constants file not found at: {constants_path}")

    content = constants_path.read_text(encoding="utf-8")
    tree = ast.parse(content)
    target_names = set(POLICY_VARIABLE_NAMES)
    policies: dict[str, str] = {}

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in target_names:
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        policies[target.id] = node.value.value

    missing = target_names - set(policies.keys())
    if missing:
        raise ValueError(f"Could not extract all required policies from {constants_path}. Missing: {missing}")

    return policies


def parse_style_profile_from_bootcamp(bootcamp_path: Path) -> dict[str, int]:
    """Extract DEFAULT_STYLE_PROFILE from bootcamp.py via AST."""
    if not bootcamp_path.exists():
        return dict(FALLBACK_STYLE_PROFILE)

    try:
        content = bootcamp_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "DEFAULT_STYLE_PROFILE":
                        parsed = ast.literal_eval(node.value)
                        if isinstance(parsed, dict):
                            return parsed
    except Exception as exc:
        logger.warning("Could not parse DEFAULT_STYLE_PROFILE from %s: %s; using fallback", bootcamp_path, exc)

    return dict(FALLBACK_STYLE_PROFILE)


def _ensure_schema_compatibility(db: Session) -> None:
    """Ensure database schema has required tables and columns for imported models."""
    bind = db.get_bind()
    insp = inspect(bind)
    table_names = set(insp.get_table_names())

    # Ensure SmsBootcampSettings table exists
    if "sms_bootcamp_settings" not in table_names:
        SmsBootcampSettings.__table__.create(bind=bind, checkfirst=True)

    # Ensure CuratedMemory table has the extended columns (added in knowledge curation)
    if "curated_memories" in table_names:
        curated_cols = {c["name"] for c in insp.get_columns("curated_memories")}
        if "content_hash" not in curated_cols:
            if bind.dialect.name == "postgresql":
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS knowledge_kind VARCHAR(32) DEFAULT 'durable_fact' NOT NULL;"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS authority VARCHAR(32) DEFAULT 'owner_verified' NOT NULL;"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS status VARCHAR(24) DEFAULT 'active' NOT NULL;"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS conflict_state VARCHAR(24) DEFAULT 'clear' NOT NULL;"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS source_reference VARCHAR(128);"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS effective_from TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS effective_until TIMESTAMP WITH TIME ZONE;"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS supersedes_id INTEGER;"))
                db.execute(text("ALTER TABLE curated_memories ADD COLUMN IF NOT EXISTS verified_by_user_id INTEGER;"))
                db.commit()
    else:
        CuratedMemory.__table__.create(bind=bind, checkfirst=True)


def import_assistant_ui_data(
    tenant_id: int = 1,
    dry_run: bool = False,
    source_dir: str | Path | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Import reference data from assistant-ui into the specified tenant in fastapi_bookings.

    Args:
        tenant_id: Target tenant database ID.
        dry_run: If True, inspect source data and calculate inventory without modifying database.
        source_dir: Root directory of assistant-ui. Defaults to DEFAULT_ASSISTANT_UI_DIR.
        db: Optional SQLAlchemy Session. If None, creates a new session.

    Returns:
        Summary dictionary with counts of upserted entities.
    """
    src_path = Path(source_dir) if source_dir else DEFAULT_ASSISTANT_UI_DIR
    if not src_path.exists():
        raise FileNotFoundError(f"Assistant UI source directory not found at: {src_path}")

    # Paths to source data files
    system_prompt_path = src_path / "backend" / "prompts" / "system_prompt.txt"
    constants_path = src_path / "backend" / "core" / "constants.py"
    intent_examples_path = src_path / "backend" / "data" / "approved_intent_examples.jsonl"
    bootcamp_path = src_path / "backend" / "bootcamp.py"
    services_path = src_path / "backend" / "data" / "services.json"
    working_hours_path = src_path / "backend" / "data" / "working_hours.json"

    # Verify required source files exist
    for p in (system_prompt_path, constants_path, intent_examples_path, services_path, working_hours_path):
        if not p.exists():
            raise FileNotFoundError(f"Required source file not found: {p}")

    # Read and parse source files
    system_prompt_text = system_prompt_path.read_text(encoding="utf-8").strip()
    policies_map = parse_policies_from_constants(constants_path)
    style_profile = parse_style_profile_from_bootcamp(bootcamp_path)

    with services_path.open("r", encoding="utf-8") as f:
        services_data = json.load(f)

    with working_hours_path.open("r", encoding="utf-8") as f:
        working_hours_data = json.load(f)

    approved_examples: list[dict[str, Any]] = []
    with intent_examples_path.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                approved_examples.append(json.loads(line_str))

    prompts_upserted = 1
    policies_upserted = len(policies_map)
    services_upserted = len(services_data)
    style_examples_total = len(approved_examples)
    style_examples_new = 0
    style_examples_skipped = 0

    if dry_run:
        summary_line = (
            f"Import Summary: {prompts_upserted} prompts upserted, "
            f"{policies_upserted} policies upserted, "
            f"{style_examples_total} style examples imported, "
            f"{services_upserted} services upserted."
        )
        print(summary_line)
        return {
            "prompts_upserted": prompts_upserted,
            "policies_upserted": policies_upserted,
            "style_examples_imported": style_examples_total,
            "services_upserted": services_upserted,
            "bootcamp_settings_upserted": 1,
            "providers_upserted": 1,
            "style_examples_new": 0,
            "style_examples_skipped": style_examples_total,
            "dry_run": True,
            "summary_line": summary_line,
        }

    # Execute database import inside a controlled session
    owns_session = False
    if db is None:
        db = SessionLocal()
        owns_session = True

    try:
        # Ensure schema compatibility before executing ORM queries
        _ensure_schema_compatibility(db)

        # 1. Verify tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise ValueError(f"Target tenant with id {tenant_id} does not exist.")

        # 2. Upsert Provider 'Tori' and Working Hours
        schedule_dict = {
            item["day"].lower(): {
                "day": item["day"],
                "is_working": item.get("enabled", True),
                "enabled": item.get("enabled", True),
                "open": item.get("open", "00:00"),
                "close": item.get("close", "23:59"),
                "recurring": True,
            }
            for item in working_hours_data
        }

        provider = (
            db.query(Provider)
            .filter(
                Provider.tenant_id == tenant_id,
                Provider.name == "Tori",
                Provider.deleted_at.is_(None),
            )
            .first()
        )

        if not provider:
            provider = Provider(
                tenant_id=tenant_id,
                name="Tori",
                active=True,
                is_visible=True,
                weekly_schedule=schedule_dict,
            )
            db.add(provider)
            db.flush()
        else:
            provider.active = True
            provider.is_visible = True
            provider.weekly_schedule = schedule_dict

        # Sync ProviderWorkDay rows
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        for item in working_hours_data:
            weekday_num = day_map.get(item["day"].lower())
            if weekday_num is None:
                continue
            workday = (
                db.query(ProviderWorkDay)
                .filter(
                    ProviderWorkDay.tenant_id == tenant_id,
                    ProviderWorkDay.provider_id == provider.id,
                    ProviderWorkDay.weekday == weekday_num,
                )
                .first()
            )
            if not workday:
                workday = ProviderWorkDay(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    weekday=weekday_num,
                    start_time=item.get("open", "00:00"),
                    end_time=item.get("close", "23:59"),
                    is_working=item.get("enabled", True),
                )
                db.add(workday)
            else:
                workday.start_time = item.get("open", "00:00")
                workday.end_time = item.get("close", "23:59")
                workday.is_working = item.get("enabled", True)

        # 3. Upsert System Prompt into SmsPromptProfile
        prompt_profile = (
            db.query(SmsPromptProfile)
            .filter(
                SmsPromptProfile.tenant_id == tenant_id,
                SmsPromptProfile.name == "Tori Canonical System Prompt",
            )
            .first()
        )
        if prompt_profile:
            prompt_profile.system_prompt = system_prompt_text
            prompt_profile.is_active = True
            prompt_profile.provider_id = provider.id
        else:
            prompt_profile = SmsPromptProfile(
                tenant_id=tenant_id,
                provider_id=provider.id,
                name="Tori Canonical System Prompt",
                system_prompt=system_prompt_text,
                is_active=True,
            )
            db.add(prompt_profile)

        # 4. Upsert Deterministic Operational Policies into SmsKnowledgeEntry
        for policy_var, policy_text in policies_map.items():
            rule_title = policy_text.splitlines()[0].strip()
            existing_entry = (
                db.query(SmsKnowledgeEntry)
                .filter(
                    SmsKnowledgeEntry.tenant_id == tenant_id,
                    SmsKnowledgeEntry.category == "policy",
                    SmsKnowledgeEntry.source == "assistant-ui:policy",
                )
                .filter(
                    or_(
                        SmsKnowledgeEntry.text.startswith(rule_title),
                        SmsKnowledgeEntry.text == policy_text,
                    )
                )
                .first()
            )
            if existing_entry:
                existing_entry.text = policy_text
                existing_entry.status = "approved"
                existing_entry.provenance = "imported:assistant-ui"
                existing_entry.source = "assistant-ui:policy"
                existing_entry.provider_id = provider.id
                existing_entry.approved_at = datetime.now(timezone.utc)
            else:
                new_entry = SmsKnowledgeEntry(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    category="policy",
                    text=policy_text,
                    source="assistant-ui:policy",
                    status="approved",
                    provenance="imported:assistant-ui",
                    approved_at=datetime.now(timezone.utc),
                )
                db.add(new_entry)

        # 5. Upsert Approved Curated Style Examples into CuratedMemory
        existing_hashes = {
            h[0]
            for h in db.query(CuratedMemory.content_hash)
            .filter(
                CuratedMemory.tenant_id == tenant_id,
                CuratedMemory.content_hash.isnot(None),
            )
            .all()
        }

        for record in approved_examples:
            incoming = record.get("incoming", "")
            reply = record.get("reply", "")
            primary_intent = record.get("primary_intent", "style_example")
            content_hash = hashlib.sha256(f"{incoming}||{reply}".encode("utf-8")).hexdigest()

            if content_hash in existing_hashes:
                style_examples_skipped += 1
                continue

            memory = CuratedMemory(
                tenant_id=tenant_id,
                provider_id=provider.id,
                category=primary_intent,
                user_query=incoming,
                ideal_response=reply,
                knowledge_kind="style_example",
                authority="owner_verified",
                status="active",
                conflict_state="clear",
                content_hash=content_hash,
                source_reference="imported:assistant-ui",
            )
            db.add(memory)
            existing_hashes.add(content_hash)
            style_examples_new += 1

        # 6. Upsert Bootcamp Settings & Style Profile
        bootcamp_settings = (
            db.query(SmsBootcampSettings)
            .filter(SmsBootcampSettings.tenant_id == tenant_id)
            .first()
        )
        if bootcamp_settings:
            bootcamp_settings.agent_name = "Tori"
            bootcamp_settings.active_style_profile = style_profile
            bootcamp_settings.system_prompt_template = system_prompt_text
        else:
            bootcamp_settings = SmsBootcampSettings(
                tenant_id=tenant_id,
                agent_name="Tori",
                active_style_profile=style_profile,
                system_prompt_template=system_prompt_text,
            )
            db.add(bootcamp_settings)

        # 7. Upsert Services Catalog
        for item in services_data:
            svc_name = item["name"]
            svc_desc = item.get("description")
            svc_dur = item["duration"]
            svc_price = item["price"]

            service = (
                db.query(Service)
                .filter(
                    Service.tenant_id == tenant_id,
                    Service.name == svc_name,
                    Service.deleted_at.is_(None),
                )
                .first()
            )
            if service:
                service.description = svc_desc
                service.duration = svc_dur
                service.price = svc_price
                service.active = True
            else:
                service = Service(
                    tenant_id=tenant_id,
                    name=svc_name,
                    description=svc_desc,
                    duration=svc_dur,
                    price=svc_price,
                    active=True,
                )
                db.add(service)
                db.flush()

            # Ensure ServiceProvider association with provider Tori
            sp = (
                db.query(ServiceProvider)
                .filter(
                    ServiceProvider.tenant_id == tenant_id,
                    ServiceProvider.service_id == service.id,
                    ServiceProvider.provider_id == provider.id,
                )
                .first()
            )
            if not sp:
                sp = ServiceProvider(
                    tenant_id=tenant_id,
                    service_id=service.id,
                    provider_id=provider.id,
                )
                db.add(sp)

        db.commit()

        summary_line = (
            f"Import Summary: {prompts_upserted} prompts upserted, "
            f"{policies_upserted} policies upserted, "
            f"{style_examples_total} style examples imported, "
            f"{services_upserted} services upserted."
        )
        print(summary_line)

        return {
            "prompts_upserted": prompts_upserted,
            "policies_upserted": policies_upserted,
            "style_examples_imported": style_examples_total,
            "services_upserted": services_upserted,
            "bootcamp_settings_upserted": 1,
            "providers_upserted": 1,
            "style_examples_new": style_examples_new,
            "style_examples_skipped": style_examples_skipped,
            "dry_run": False,
            "summary_line": summary_line,
        }

    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


def main() -> None:
    """CLI entrypoint for assistant-ui import script."""
    parser = argparse.ArgumentParser(
        description="Import knowledge, policies, prompts, and settings from assistant-ui into fastapi_bookings."
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=1,
        help="Target tenant ID (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without modifying database, reporting inventory counts",
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        default=None,
        help=f"Path to assistant-ui repository root (default: {DEFAULT_ASSISTANT_UI_DIR})",
    )

    args = parser.parse_args()
    import_assistant_ui_data(
        tenant_id=args.tenant_id,
        dry_run=args.dry_run,
        source_dir=args.source_dir,
    )


if __name__ == "__main__":
    main()
