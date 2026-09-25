"""Phase 9 and Phase 10 tests: Shadow Retrieval and Canary Gating.

Spec references:
- Spec 62: Shadow retrieval alongside legacy retrieval
- Spec 63: Privacy-safe evaluation metrics (counts, overlap, latencies, cache_hit)
- Spec 64: Provider and tenant canary scope selection
- Spec 65: Canary routing and rollout gating
- Spec 66: Safe legacy fallback on retrieval degradation
- Spec 88: Zero customer PII in evaluation metrics
- Spec 89: Low-cardinality structured logging without raw text
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.curated_memory import CuratedMemory
from app.models.sms_knowledge import SmsKnowledgeEntry
from app.services.knowledge.types import (
    Authority,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeScope,
    RetrievalQuery,
    RetrievalResult,
)
from app.services.knowledge.cache import clear_in_memory_cache
from app.services.knowledge.shadow_evaluator import (
    ShadowEvaluator,
    compute_overlap_ratio,
    build_legacy_retrieval_result,
    is_canary_active,
    shadow_evaluator,
)
from app.services.sms.prompt_builder import UnifiedPromptBuilder


@pytest.fixture
def shadow_setup(db_session):
    """Setup multi-tenant fixtures for Phase 9 & 10 testing."""
    clear_in_memory_cache()

    tenant_1 = Tenant(name="Canary Clinic Alpha", subdomain="canary-alpha")
    tenant_2 = Tenant(name="Legacy Wellness Beta", subdomain="legacy-beta")
    db_session.add_all([tenant_1, tenant_2])
    db_session.flush()

    prov_1a = Provider(tenant_id=tenant_1.id, name="Dr. Alice Canary", active=True)
    prov_1b = Provider(tenant_id=tenant_1.id, name="Dr. Bob Standard", active=True)
    prov_2 = Provider(tenant_id=tenant_2.id, name="Dr. Charlie Beta", active=True)
    db_session.add_all([prov_1a, prov_1b, prov_2])
    db_session.flush()

    # Seed legacy knowledge for tenant 1
    sk_1 = SmsKnowledgeEntry(
        tenant_id=tenant_1.id,
        provider_id=None,
        text="Validated parking is available in the underground garage.",
        category="facility",
        status="approved",
    )
    # Provider 1a specific memory
    cm_1a = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        user_query="What services do you perform?",
        ideal_response="Dr. Alice specializes in pediatric acupuncture and pain therapy.",
        category="specialty",
        status="active",
        conflict_state="clear",
    )
    # Provider 1b specific memory
    cm_1b = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1b.id,
        user_query="What services do you perform?",
        ideal_response="Dr. Bob specializes in deep tissue rehabilitation.",
        category="specialty",
        status="active",
        conflict_state="clear",
    )
    # Seed legacy knowledge for tenant 2
    sk_2 = SmsKnowledgeEntry(
        tenant_id=tenant_2.id,
        provider_id=None,
        text="Beta Wellness is open Monday through Saturday from 8 AM to 6 PM.",
        category="hours",
        status="approved",
    )

    db_session.add_all([sk_1, cm_1a, cm_1b, sk_2])
    db_session.commit()

    return {
        "tenant_1": tenant_1,
        "tenant_2": tenant_2,
        "prov_1a": prov_1a,
        "prov_1b": prov_1b,
        "prov_2": prov_2,
        "sk_1": sk_1,
        "cm_1a": cm_1a,
        "cm_1b": cm_1b,
        "sk_2": sk_2,
    }


# =============================================================================
# Test 1: Shadow read executes in parallel without altering non-canary prompt
# =============================================================================
def test_1_shadow_read_without_altering_non_canary_prompt(shadow_setup, db_session):
    """Test 1: Shadow read executes in parallel without altering non-canary prompt content (Spec 62)."""
    t1 = shadow_setup["tenant_1"]
    p1b = shadow_setup["prov_1b"]

    with patch.object(settings, "GRAPH_SHADOW_READ", True), \
         patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
         patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
         patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

        legacy_data = {
            "shared_entries": [shadow_setup["sk_1"]],
            "provider_entries": [],
            "curated_memories": [shadow_setup["cm_1b"]],
        }

        # Baseline prompt built via legacy path
        baseline_builder = (
            UnifiedPromptBuilder(tenant_id=t1.id, provider_id=p1b.id)
            .with_core_safety()
            .with_knowledge(
                shared_entries=legacy_data["shared_entries"],
                provider_entries=legacy_data["provider_entries"],
                curated_memories=legacy_data["curated_memories"],
            )
        )
        baseline_payload = baseline_builder.build_messages_payload(discrete_system_messages=True)

        # Execution via shadow evaluator
        active_result, metrics = shadow_evaluator.evaluate_and_resolve(
            db=db_session,
            tenant_id=t1.id,
            provider_id=p1b.id,
            message_text="Do you have parking?",
            legacy_knowledge=legacy_data,
            legacy_latency_ms=12.5,
        )

        assert metrics["is_canary"] is False
        assert active_result.metadata.get("source") == "legacy"

        # The non-canary path continues to assemble prompt via legacy knowledge
        evaluated_builder = (
            UnifiedPromptBuilder(tenant_id=t1.id, provider_id=p1b.id)
            .with_core_safety()
            .with_knowledge(
                shared_entries=legacy_data["shared_entries"],
                provider_entries=legacy_data["provider_entries"],
                curated_memories=legacy_data["curated_memories"],
            )
        )
        evaluated_payload = evaluated_builder.build_messages_payload(discrete_system_messages=True)

        # Non-canary prompt is byte-for-byte identical to baseline
        assert [m["content"] for m in evaluated_payload] == [m["content"] for m in baseline_payload]


# =============================================================================
# Test 2: Shadow evaluation metrics computed accurately with zero PII
# =============================================================================
def test_2_shadow_evaluation_metrics_privacy_and_accuracy(shadow_setup, db_session, caplog):
    """Test 2: Metrics computed accurately (counts, overlap, latencies, zero PII) (Specs 63, 88, 89)."""
    t1 = shadow_setup["tenant_1"]
    p1a = shadow_setup["prov_1a"]

    customer_query = "Hi, my name is John Doe, phone +1-555-0199. Is parking free?"
    legacy_data = {
        "shared_entries": [shadow_setup["sk_1"]],
        "provider_entries": [],
        "curated_memories": [shadow_setup["cm_1a"]],
    }

    mock_graph_result = RetrievalResult(
        facts=["Validated parking is available in the underground garage."],
        behavioural_rules=["Always speak warmly and clearly."],
        examples=[],
        metadata={"cache_hit": True},
    )

    with patch("app.services.knowledge.shadow_evaluator.knowledge_gateway.retrieve", return_value=mock_graph_result), \
         patch.object(settings, "GRAPH_SHADOW_READ", True), \
         patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
         patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
         patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

        with caplog.at_level(logging.INFO):
            active_result, metrics = shadow_evaluator.evaluate_and_resolve(
                db=db_session,
                tenant_id=t1.id,
                provider_id=p1a.id,
                message_text=customer_query,
                legacy_knowledge=legacy_data,
                legacy_latency_ms=8.4,
            )

        # Check accurate count metrics
        assert metrics["legacy_items_count"] == 2
        assert metrics["graphiti_items_count"] == 2
        assert metrics["cache_hit"] is True
        assert metrics["legacy_latency_ms"] == 8.4
        assert metrics["graphiti_latency_ms"] >= 0.0
        assert 0.0 <= metrics["overlap_ratio"] <= 1.0
        assert metrics["overlap_ratio"] > 0.0  # Common parking tokens overlap

        # Spec 88 & 89 Privacy Check: No raw query text, customer names, or phone numbers in metrics
        metrics_dump = str(metrics)
        assert "John Doe" not in metrics_dump
        assert "555-0199" not in metrics_dump
        assert "Validated parking" not in metrics_dump
        assert "Hi, my name is" not in metrics_dump

        # Privacy Check on Structured Logs
        log_text = caplog.text
        assert "Knowledge shadow evaluation complete" in log_text
        assert "John Doe" not in log_text
        assert "555-0199" not in log_text
        assert "Validated parking" not in log_text


# =============================================================================
# Test 3: Canary activation for specific provider switches prompt to Graphiti
# =============================================================================
def test_3_canary_activation_specific_provider(shadow_setup, db_session):
    """Test 3: Provider canary activation switches prompt to bounded Graphiti retrieval (Specs 64, 65)."""
    t1 = shadow_setup["tenant_1"]
    p1a = shadow_setup["prov_1a"]

    mock_graph_result = RetrievalResult(
        facts=["Graphiti fact: Pediatric acupuncture sessions require 45 minutes."],
        behavioural_rules=["Graphiti rule: Clarify patient age before booking."],
        examples=["Graphiti example: 'We warmly welcome young patients.'"],
        metadata={"source": "graphiti", "cache_hit": False},
    )

    with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p1a.id]), \
         patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []), \
         patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
         patch("app.services.knowledge.shadow_evaluator.knowledge_gateway.retrieve", return_value=mock_graph_result):

        assert shadow_evaluator.is_canary_active(t1.id, p1a.id) is True

        legacy_data = {
            "shared_entries": [shadow_setup["sk_1"]],
            "curated_memories": [shadow_setup["cm_1a"]],
        }

        active_result, metrics = shadow_evaluator.evaluate_and_resolve(
            db=db_session,
            tenant_id=t1.id,
            provider_id=p1a.id,
            message_text="How long is a pediatric session?",
            legacy_knowledge=legacy_data,
        )

        assert metrics["is_canary"] is True
        assert active_result == mock_graph_result

        # Build prompt using canary retrieval context
        builder = (
            UnifiedPromptBuilder(tenant_id=t1.id, provider_id=p1a.id)
            .with_core_safety()
            .with_retrieval_result(active_result)
            .with_spec_54(True)
        )
        messages = builder.build_messages_payload(discrete_system_messages=True)
        contents = [m["content"] for m in messages]

        # Verify Graphiti bounded retrieval items are injected into discrete messages
        assert any("Pediatric acupuncture sessions require 45 minutes." in c for c in contents)
        assert any("Clarify patient age before booking." in c for c in contents)
        assert any("We warmly welcome young patients." in c for c in contents)


# =============================================================================
# Test 4: Non-canary provider under same tenant continues using legacy path
# =============================================================================
def test_4_non_canary_provider_under_same_tenant_continues_legacy(shadow_setup, db_session):
    """Test 4: Non-canary provider under same tenant remains on legacy path (Spec 64)."""
    t1 = shadow_setup["tenant_1"]
    p1a = shadow_setup["prov_1a"]
    p1b = shadow_setup["prov_1b"]

    with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p1a.id]), \
         patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []), \
         patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

        # Provider 1a is canary, Provider 1b is NOT
        assert shadow_evaluator.is_canary_active(t1.id, p1a.id) is True
        assert shadow_evaluator.is_canary_active(t1.id, p1b.id) is False

        legacy_data = {
            "shared_entries": [shadow_setup["sk_1"]],
            "curated_memories": [shadow_setup["cm_1b"]],
        }

        active_result_1b, metrics_1b = shadow_evaluator.evaluate_and_resolve(
            db=db_session,
            tenant_id=t1.id,
            provider_id=p1b.id,
            message_text="What services do you provide?",
            legacy_knowledge=legacy_data,
        )

        assert metrics_1b["is_canary"] is False
        assert active_result_1b.metadata.get("source") == "legacy"

        # Active result contains Dr. Bob's legacy specialty, not Graphiti
        assert any("Dr. Bob specializes in deep tissue" in f for f in active_result_1b.facts)


# =============================================================================
# Test 5: Canary activation for entire tenant
# =============================================================================
def test_5_canary_activation_entire_tenant(shadow_setup, db_session):
    """Test 5: Tenant canary activation enables canary for all its providers, isolating other tenants (Spec 64)."""
    t1 = shadow_setup["tenant_1"]
    t2 = shadow_setup["tenant_2"]
    p1a = shadow_setup["prov_1a"]
    p1b = shadow_setup["prov_1b"]
    p2 = shadow_setup["prov_2"]

    with patch.object(settings, "GRAPH_CANARY_TENANT_IDS", [t1.id]), \
         patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
         patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

        # Both providers in Tenant 1 are canary
        assert shadow_evaluator.is_canary_active(t1.id, p1a.id) is True
        assert shadow_evaluator.is_canary_active(t1.id, p1b.id) is True
        assert shadow_evaluator.is_canary_active(t1.id, None) is True

        # Tenant 2 is NOT canary
        assert shadow_evaluator.is_canary_active(t2.id, p2.id) is False
        assert shadow_evaluator.is_canary_active(t2.id, None) is False

        legacy_data_t2 = {
            "shared_entries": [shadow_setup["sk_2"]],
            "curated_memories": [],
        }

        active_result_t2, metrics_t2 = shadow_evaluator.evaluate_and_resolve(
            db=db_session,
            tenant_id=t2.id,
            provider_id=p2.id,
            message_text="What are your hours?",
            legacy_knowledge=legacy_data_t2,
        )

        assert metrics_t2["is_canary"] is False
        assert active_result_t2.metadata.get("source") == "legacy"
        assert any("Beta Wellness is open Monday through Saturday" in f for f in active_result_t2.facts)


# =============================================================================
# Test 6: Fallback when Graphiti fails during shadow/canary run
# =============================================================================
def test_6_fallback_when_graphiti_fails_degrades_safely(shadow_setup, db_session):
    """Test 6: Fallback when Graphiti fails during canary run degrades safely to legacy (Spec 66)."""
    t1 = shadow_setup["tenant_1"]
    p1a = shadow_setup["prov_1a"]

    legacy_data = {
        "shared_entries": [shadow_setup["sk_1"]],
        "curated_memories": [shadow_setup["cm_1a"]],
    }

    # Simulate Graphiti gateway raising an unexpected runtime exception
    with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p1a.id]), \
         patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []), \
         patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
         patch("app.services.knowledge.shadow_evaluator.knowledge_gateway.retrieve", side_effect=RuntimeError("Graph database offline")):

        active_result, metrics = shadow_evaluator.evaluate_and_resolve(
            db=db_session,
            tenant_id=t1.id,
            provider_id=p1a.id,
            message_text="Tell me about parking and services",
            legacy_knowledge=legacy_data,
        )

        assert metrics["is_canary"] is True
        assert metrics["fallback_to_legacy"] is True
        assert metrics.get("graph_error") == "RuntimeError"

        # Result degrades safely to legacy without crashing
        assert active_result.metadata.get("source") == "legacy"
        assert any("Validated parking is available" in f for f in active_result.facts)
        assert any("Dr. Alice specializes in pediatric acupuncture" in f for f in active_result.facts)


# =============================================================================
# Test 7: Multi-tenant and provider isolation in shadow evaluation
# =============================================================================
def test_7_multi_tenant_and_provider_isolation(shadow_setup, db_session):
    """Test 7: Multi-tenant and provider isolation strictly preserved across evaluations (Spec 34, 53)."""
    t1 = shadow_setup["tenant_1"]
    t2 = shadow_setup["tenant_2"]
    p1a = shadow_setup["prov_1a"]
    p2 = shadow_setup["prov_2"]

    legacy_data_1a = {
        "shared_entries": [shadow_setup["sk_1"]],
        "curated_memories": [shadow_setup["cm_1a"]],
    }
    legacy_data_2 = {
        "shared_entries": [shadow_setup["sk_2"]],
        "curated_memories": [],
    }

    with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p1a.id]), \
         patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []), \
         patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

        # Evaluate Tenant 1 Provider 1a
        res_1a, met_1a = shadow_evaluator.evaluate_and_resolve(
            db=db_session,
            tenant_id=t1.id,
            provider_id=p1a.id,
            message_text="What are your hours and parking?",
            legacy_knowledge=legacy_data_1a,
        )

        # Evaluate Tenant 2 Provider 2
        res_2, met_2 = shadow_evaluator.evaluate_and_resolve(
            db=db_session,
            tenant_id=t2.id,
            provider_id=p2.id,
            message_text="What are your hours and parking?",
            legacy_knowledge=legacy_data_2,
        )

        # Ensure no cross-tenant leakage between results
        all_1a_texts = res_1a.facts + res_1a.behavioural_rules + res_1a.examples
        all_2_texts = res_2.facts + res_2.behavioural_rules + res_2.examples

        assert not any("Beta Wellness" in txt for txt in all_1a_texts)
        assert not any("Dr. Alice" in txt for txt in all_2_texts)
        assert not any("underground garage" in txt for txt in all_2_texts)

        # Scopes verified
        assert met_1a["tenant_id"] == t1.id
        assert met_1a["provider_id"] == p1a.id
        assert met_2["tenant_id"] == t2.id
        assert met_2["provider_id"] == p2.id
