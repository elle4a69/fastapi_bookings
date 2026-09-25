"""Test suite for assistant-ui data import script.

Verifies dry-run inventory counts, full import execution, strict idempotency,
and multi-tenant isolation.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.curated_memory import CuratedMemory
from app.models.provider import Provider
from app.models.schedule import ProviderWorkDay
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.sms_bootcamp import SmsBootcampSettings
from app.models.sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile
from app.models.tenant import Tenant
from scripts.import_assistant_ui_data import import_assistant_ui_data


@pytest.fixture
def target_tenant(db_session: Session) -> Tenant:
    """Create a synthetic tenant for import testing."""
    tenant = Tenant(name="Import Test Tenant", subdomain="import-test-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def secondary_tenant(db_session: Session) -> Tenant:
    """Create a secondary synthetic tenant for isolation testing."""
    tenant = Tenant(name="Secondary Isolation Tenant", subdomain="secondary-isolation-tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_dry_run_produces_accurate_inventory_without_modifications(
    db_session: Session, target_tenant: Tenant, capsys
) -> None:
    """Test 1: Dry run execution produces accurate inventory counts without modifying database."""
    # Ensure database is clean for this tenant
    assert db_session.query(SmsPromptProfile).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(SmsKnowledgeEntry).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(CuratedMemory).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(Service).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(SmsBootcampSettings).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(Provider).filter_by(tenant_id=target_tenant.id).count() == 0

    result = import_assistant_ui_data(
        tenant_id=target_tenant.id,
        dry_run=True,
        db=db_session,
    )

    # Verify inventory counts reported in result dict
    assert result["dry_run"] is True
    assert result["prompts_upserted"] == 1
    assert result["policies_upserted"] == 6
    assert result["style_examples_imported"] == 180
    assert result["services_upserted"] == 3
    assert result["bootcamp_settings_upserted"] == 1
    assert result["providers_upserted"] == 1

    # Verify CLI stdout contains exact required summary format
    captured = capsys.readouterr()
    expected_summary = "Import Summary: 1 prompts upserted, 6 policies upserted, 180 style examples imported, 3 services upserted."
    assert expected_summary in captured.out

    # Verify zero database modifications occurred
    assert db_session.query(SmsPromptProfile).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(SmsKnowledgeEntry).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(CuratedMemory).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(Service).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(SmsBootcampSettings).filter_by(tenant_id=target_tenant.id).count() == 0
    assert db_session.query(Provider).filter_by(tenant_id=target_tenant.id).count() == 0


def test_full_run_execution_imports_all_entities(
    db_session: Session, target_tenant: Tenant, capsys
) -> None:
    """Test 2: Full run execution imports prompt profiles, policies, curated memories, services, and bootcamp settings."""
    result = import_assistant_ui_data(
        tenant_id=target_tenant.id,
        dry_run=False,
        db=db_session,
    )

    assert result["dry_run"] is False
    assert result["prompts_upserted"] == 1
    assert result["policies_upserted"] == 6
    assert result["style_examples_imported"] == 180
    assert result["services_upserted"] == 3
    assert result["style_examples_new"] == 180

    captured = capsys.readouterr()
    expected_summary = "Import Summary: 1 prompts upserted, 6 policies upserted, 180 style examples imported, 3 services upserted."
    assert expected_summary in captured.out

    # 1. Provider Tori exists with schedule
    provider = db_session.query(Provider).filter_by(tenant_id=target_tenant.id, name="Tori").first()
    assert provider is not None
    assert provider.active is True
    assert provider.is_visible is True
    assert isinstance(provider.weekly_schedule, dict)
    assert "thursday" in provider.weekly_schedule
    assert provider.weekly_schedule["thursday"]["open"] == "15:00"

    # Provider workdays were populated
    workdays = db_session.query(ProviderWorkDay).filter_by(
        tenant_id=target_tenant.id, provider_id=provider.id
    ).all()
    assert len(workdays) == 7

    # 2. System Prompt Profile
    prompt_profile = (
        db_session.query(SmsPromptProfile)
        .filter_by(tenant_id=target_tenant.id, name="Tori Canonical System Prompt")
        .first()
    )
    assert prompt_profile is not None
    assert prompt_profile.provider_id == provider.id
    assert prompt_profile.is_active is True
    assert "You are an independent adult companion" in prompt_profile.system_prompt

    # 3. Deterministic Operational Policies
    policies = (
        db_session.query(SmsKnowledgeEntry)
        .filter_by(tenant_id=target_tenant.id, category="policy", source="assistant-ui:policy")
        .all()
    )
    assert len(policies) == 6
    for p in policies:
        assert p.status == "approved"
        assert p.provenance == "imported:assistant-ui"
        assert p.provider_id == provider.id
        assert len(p.text) > 20

    # 4. Curated Style Examples
    memories = (
        db_session.query(CuratedMemory)
        .filter_by(tenant_id=target_tenant.id, knowledge_kind="style_example")
        .all()
    )
    assert len(memories) == 180
    for m in memories:
        assert m.authority == "owner_verified"
        assert m.status == "active"
        assert m.conflict_state == "clear"
        assert m.provider_id == provider.id
        assert m.content_hash is not None
        assert len(m.content_hash) == 64
        assert m.user_query is not None
        assert m.ideal_response is not None

    # 5. Bootcamp Settings
    bootcamp_settings = (
        db_session.query(SmsBootcampSettings)
        .filter_by(tenant_id=target_tenant.id)
        .first()
    )
    assert bootcamp_settings is not None
    assert bootcamp_settings.agent_name == "Tori"
    assert bootcamp_settings.active_style_profile == {
        "flirtiness": 2,
        "cheerfulness": 3,
        "wit": 2,
        "sarcasm": 0,
        "warmth": 4,
        "directness": 3,
        "chattiness": 1,
        "patience": 4,
    }
    assert bootcamp_settings.system_prompt_template is not None
    assert "You are an independent adult companion" in bootcamp_settings.system_prompt_template

    # 6. Services & ServiceProvider bindings
    services = db_session.query(Service).filter_by(tenant_id=target_tenant.id).all()
    assert len(services) == 3
    service_names = {s.name for s in services}
    assert "Porn Star Experience (PSE) 30 mins" in service_names
    assert "Porn Star Experience (PSE) 1hr" in service_names
    assert "Deepthroat BBBJ with CIM" in service_names

    service_providers = (
        db_session.query(ServiceProvider)
        .filter_by(tenant_id=target_tenant.id, provider_id=provider.id)
        .all()
    )
    assert len(service_providers) == 3


def test_idempotency_running_import_twice_produces_identical_counts(
    db_session: Session, target_tenant: Tenant
) -> None:
    """Test 3: Idempotency test — running import twice results in exact same record counts with zero duplicates."""
    # First execution
    res1 = import_assistant_ui_data(tenant_id=target_tenant.id, dry_run=False, db=db_session)
    assert res1["style_examples_new"] == 180
    assert res1["style_examples_skipped"] == 0

    count_prompts_1 = db_session.query(SmsPromptProfile).filter_by(tenant_id=target_tenant.id).count()
    count_policies_1 = db_session.query(SmsKnowledgeEntry).filter_by(tenant_id=target_tenant.id).count()
    count_memories_1 = db_session.query(CuratedMemory).filter_by(tenant_id=target_tenant.id).count()
    count_services_1 = db_session.query(Service).filter_by(tenant_id=target_tenant.id).count()
    count_providers_1 = db_session.query(Provider).filter_by(tenant_id=target_tenant.id).count()
    count_bootcamp_1 = db_session.query(SmsBootcampSettings).filter_by(tenant_id=target_tenant.id).count()
    count_sp_1 = db_session.query(ServiceProvider).filter_by(tenant_id=target_tenant.id).count()

    # Second execution on same tenant
    res2 = import_assistant_ui_data(tenant_id=target_tenant.id, dry_run=False, db=db_session)
    assert res2["style_examples_new"] == 0
    assert res2["style_examples_skipped"] == 180

    count_prompts_2 = db_session.query(SmsPromptProfile).filter_by(tenant_id=target_tenant.id).count()
    count_policies_2 = db_session.query(SmsKnowledgeEntry).filter_by(tenant_id=target_tenant.id).count()
    count_memories_2 = db_session.query(CuratedMemory).filter_by(tenant_id=target_tenant.id).count()
    count_services_2 = db_session.query(Service).filter_by(tenant_id=target_tenant.id).count()
    count_providers_2 = db_session.query(Provider).filter_by(tenant_id=target_tenant.id).count()
    count_bootcamp_2 = db_session.query(SmsBootcampSettings).filter_by(tenant_id=target_tenant.id).count()
    count_sp_2 = db_session.query(ServiceProvider).filter_by(tenant_id=target_tenant.id).count()

    # Exact same counts, zero duplicates
    assert count_prompts_1 == count_prompts_2 == 1
    assert count_policies_1 == count_policies_2 == 6
    assert count_memories_1 == count_memories_2 == 180
    assert count_services_1 == count_services_2 == 3
    assert count_providers_1 == count_providers_2 == 1
    assert count_bootcamp_1 == count_bootcamp_2 == 1
    assert count_sp_1 == count_sp_2 == 3


def test_tenant_isolation_imported_records_belong_exclusively_to_target_tenant(
    db_session: Session, target_tenant: Tenant, secondary_tenant: Tenant
) -> None:
    """Test 4: Tenant isolation — imported records belong exclusively to target tenant_id."""
    # Import into target_tenant only
    import_assistant_ui_data(tenant_id=target_tenant.id, dry_run=False, db=db_session)

    # Verify secondary_tenant has zero records in any of the imported tables
    assert db_session.query(SmsPromptProfile).filter_by(tenant_id=secondary_tenant.id).count() == 0
    assert db_session.query(SmsKnowledgeEntry).filter_by(tenant_id=secondary_tenant.id).count() == 0
    assert db_session.query(CuratedMemory).filter_by(tenant_id=secondary_tenant.id).count() == 0
    assert db_session.query(Service).filter_by(tenant_id=secondary_tenant.id).count() == 0
    assert db_session.query(Provider).filter_by(tenant_id=secondary_tenant.id).count() == 0
    assert db_session.query(SmsBootcampSettings).filter_by(tenant_id=secondary_tenant.id).count() == 0
    assert db_session.query(ServiceProvider).filter_by(tenant_id=secondary_tenant.id).count() == 0

    # Now import into secondary_tenant and verify each tenant has isolated, distinct records
    import_assistant_ui_data(tenant_id=secondary_tenant.id, dry_run=False, db=db_session)

    target_provider = db_session.query(Provider).filter_by(tenant_id=target_tenant.id, name="Tori").first()
    secondary_provider = db_session.query(Provider).filter_by(tenant_id=secondary_tenant.id, name="Tori").first()

    assert target_provider is not None
    assert secondary_provider is not None
    assert target_provider.id != secondary_provider.id

    # Verify curated memories for target_tenant only reference target_tenant.id
    target_memories = db_session.query(CuratedMemory).filter_by(tenant_id=target_tenant.id).all()
    assert len(target_memories) == 180
    assert all(m.tenant_id == target_tenant.id for m in target_memories)
    assert all(m.provider_id == target_provider.id for m in target_memories)

    secondary_memories = db_session.query(CuratedMemory).filter_by(tenant_id=secondary_tenant.id).all()
    assert len(secondary_memories) == 180
    assert all(m.tenant_id == secondary_tenant.id for m in secondary_memories)
    assert all(m.provider_id == secondary_provider.id for m in secondary_memories)
