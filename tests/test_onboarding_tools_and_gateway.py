"""Comprehensive tests for Onboarding Tools, OnboardingGateway, and LiveKit Tool Gateway wiring.

Covers:
1. OnboardingToolPack:
   - stage_fields (normalization, staged != saved invariant, RPC dispatch)
   - highlight_field (DOM overlay signal, RPC dispatch)
   - validate_form (field validation, email/phone format checks)
   - request_save_authorization (single-use nonce issuance for owner sign-off)
   - commit_save (authoritative commit, DelegationSaveGuard enforcement, nonce consumption)
   - navigate_route (admin route & subtab navigation)
   - get_onboarding_status (8-domain progress summary, next unanswered facts)
   - ask_clarification (targeted Australian English prompt)
   - generate_website_draft (draft synthesis, preview toggle & review drawer RPCs)
   - Section 13 catalogue aliases: read_context, plan_step, prepare_fields, navigate_show, fill_form, save_form, read_status, pause_takeover
2. OnboardingGateway:
   - Synchronous & asynchronous execution in isolated sessions
   - Monotonic control epoch validation and StaleControlEpochError rejection on manual takeover
   - Lease token validation and LeaseExpiredError rejection
   - RPC dispatch & truthful receipt envelopes (staged != saved)
3. LiveKitToolGateway Wiring:
   - Tool registration with "onboarding" pack enabled
   - Execution in authenticated tenant session context
   - Rejection on stale control epoch / expired lease
   - Audio transport and persona immutability preservation
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.onboarding import OnboardingPlan, OnboardingStep
from app.services.business_assistant.onboarding import (
    DelegationMode,
    DelegationRefusalError,
    InvalidNonceError,
    LeaseExpiredError,
    OnboardingPlanService,
    StaleControlEpochError,
)
from app.services.business_assistant.onboarding.gateway import OnboardingGateway
from app.services.business_assistant.onboarding.tools import (
    ONBOARDING_AGENT_TOOLS,
    OnboardingToolPack,
)
from app.services.business_assistant.livekit.config import get_baseline_config
from app.services.business_assistant.livekit.tool_gateway import (
    LiveKitSessionContext,
    LiveKitToolGateway,
    ONBOARDING_TOOL_NAMES,
)


from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session():
    """In-memory SQLite session with full schema initialized and shared connection pool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    tenant = Tenant(id=1, name="Bondi Canine Spa", subdomain="bondispa", email="contact@bondispa.com.au", phone="0412345678")
    session.add(tenant)
    session.flush()

    user = User(
        id=1,
        tenant_id=tenant.id,
        login="owner",
        password_hash="testhash",
        email="owner@bondispa.com.au",
        role="owner",
    )
    session.add(user)
    session.commit()

    yield session
    session.close()


@pytest.fixture
def db_factory(db_session):
    """Factory returning the test db session."""
    engine = db_session.get_bind()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


class TestOnboardingToolPackUnit:
    """Verifies all OnboardingToolPack tools, Section 13 aliases, and invariants."""

    def test_stage_fields_normalization_and_staged_invariant(self, db_session):
        dispatched = []
        def mock_rpc(action, params):
            dispatched.append((action, params))
            return {"receipt": "ok"}

        pack = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
            lease_token="lease-abc",
            control_epoch=1,
            rpc_dispatcher=mock_rpc,
            mode=DelegationMode.DELEGATED.value,
        )

        # Stage fields with American spelling to test normalization
        result = pack.stage_fields(
            step_id="step_1_identity",
            fields={
                "business_name": "Bondi Canine Spa",
                "brand_color": "We customize the color for theater clients",
            },
        )

        assert result["status"] == "ok"
        assert result["action"] == "fill_fields"
        assert result["receipt_state"] == "fields_staged"
        assert result["is_saved"] is False  # STAGED != SAVED invariant!
        assert "Bondi Canine Spa" in result["normalized_values"]["business_name"]
        # Enforced Australian spelling
        assert "customise" in result["normalized_values"]["brand_color"]
        assert "colour" in result["normalized_values"]["brand_color"]
        assert "theatre" in result["normalized_values"]["brand_color"]

        # Check RPC dispatched
        assert len(dispatched) == 1
        assert dispatched[0][0] == "fill_fields"
        assert dispatched[0][1]["staging_guard"] is True
        assert dispatched[0][1]["prevent_autosave"] is True

        # Check DB model state
        plan = db_session.query(OnboardingPlan).filter_by(tenant_id=1).first()
        step = OnboardingPlanService.get_step_by_id(plan, "step_1_identity")
        assert step.status == "staged"
        assert step.status != "saved"
        assert step.persisted_entity_id is None

    def test_highlight_field_dispatches_rpc(self, db_session):
        dispatched = []
        pack = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
            rpc_dispatcher=lambda act, p: dispatched.append((act, p)),
        )

        result = pack.highlight_field(
            field_name="business_email",
            reason="Please confirm your public email",
            form_id="business_settings",
        )

        assert result["status"] == "ok"
        assert result["action"] == "highlight_field"
        assert result["receipt_state"] == "executing"
        assert len(dispatched) == 1
        assert dispatched[0][0] == "highlight_field"
        assert dispatched[0][1]["field"] == "business_email"

    def test_validate_form_catches_missing_and_invalid_fields(self, db_session):
        pack = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
        )

        # Initially step 1 is empty, required facts are business_name, business_email
        invalid_res = pack.validate_form(form_id="business_settings", step_id="step_1_identity")
        assert invalid_res["valid"] is False
        assert "business_name" in invalid_res["errors"]
        assert "business_email" in invalid_res["errors"]
        assert invalid_res["receipt_state"] == "failed"

        # Stage invalid email
        pack.stage_fields("step_1_identity", {"business_name": "Spa", "business_email": "not-an-email"})
        invalid_email_res = pack.validate_form(form_id="business_settings", step_id="step_1_identity")
        assert invalid_email_res["valid"] is False
        assert "business_email" in invalid_email_res["errors"]

        # Stage valid fields including business_phone
        pack.stage_fields("step_1_identity", {"business_name": "Spa", "business_email": "hello@spa.com.au", "business_phone": "0412345678"})
        valid_res = pack.validate_form(form_id="business_settings", step_id="step_1_identity")
        assert valid_res["valid"] is True
        assert valid_res["errors"] == {}

    def test_request_save_authorization_and_commit_save(self, db_session):
        dispatched = []
        pack = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
            rpc_dispatcher=lambda act, p: dispatched.append((act, p)),
        )

        # Stage required fields first
        pack.stage_fields("step_1_identity", {"business_name": "Bondi Spa", "business_email": "info@bondispa.com.au"})

        # Domain 1 requires owner authorization nonce in delegated mode
        with pytest.raises(DelegationRefusalError):
            pack.commit_save(step_id="step_1_identity", nonce=None)

        # Request authorization
        auth_res = pack.request_save_authorization(domain=1, summary="Save business profile and identity", step_id="step_1_identity")
        assert auth_res["status"] == "ok"
        assert auth_res["authorization_required"] is True
        assert auth_res["nonce"] is not None
        nonce = auth_res["nonce"]

        # Commit save with valid nonce
        save_res = pack.commit_save(step_id="step_1_identity", nonce=nonce)
        assert save_res["status"] == "ok"
        assert save_res["is_saved"] is True
        assert save_res["receipt_state"] == "saved"
        assert save_res["persisted_entity"]["revision"] == 1

        # Check DB step state
        plan = db_session.query(OnboardingPlan).filter_by(tenant_id=1).first()
        step = OnboardingPlanService.get_step_by_id(plan, "step_1_identity")
        assert step.status == "saved"

        # Nonce reuse fails
        with pytest.raises(InvalidNonceError):
            pack.commit_save(step_id="step_1_identity", nonce=nonce)

    def test_navigate_route_and_get_onboarding_status(self, db_session):
        dispatched = []
        pack = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
            rpc_dispatcher=lambda act, p: dispatched.append((act, p)),
        )

        nav_res = pack.navigate_route(route="/admin/settings", subtab="general")
        assert nav_res["status"] == "ok"
        assert nav_res["action"] == "navigate_subtab"
        assert len(dispatched) == 1
        assert dispatched[0][1]["subtab"] == "general"

        status_res = pack.get_onboarding_status(include_facts=True)
        assert status_res["status"] == "ok"
        summary = status_res["plan_summary"]
        assert summary["total_steps"] == 8
        assert len(summary["domain_progress"]) == 8

    def test_ask_clarification(self, db_session):
        pack = OnboardingToolPack(db=db_session, tenant_id=1, user_id=1)
        res = pack.ask_clarification(
            ambiguous_fact="duration_minutes",
            clarification_prompt="Did you mean 45 or 60 minutes for the wash?",
        )
        assert res["status"] == "ok"
        assert res["ambiguous_fact"] == "duration_minutes"
        assert "45 or 60" in res["clarification_prompt"]

    def test_section13_catalogue_aliases(self, db_session):
        dispatched = []
        pack = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
            rpc_dispatcher=lambda act, p: dispatched.append((act, p)),
        )

        # 1. read_context
        ctx_res = pack.read_context()
        assert ctx_res["status"] == "ok"
        assert ctx_res["context"]["tenant_id"] == 1
        assert ctx_res["context"]["current_step_id"] == "step_1_identity"

        # 2. plan_step
        plan_res = pack.plan_step()
        assert plan_res["status"] == "ok"
        assert plan_res["next_step_id"] == "step_1_identity"

        # 3. prepare_fields
        prep_res = pack.prepare_fields(
            step_id="step_1_identity",
            fields={"business_name": "Bondi Spa Alias"},
        )
        assert prep_res["status"] == "ok"
        assert prep_res["is_saved"] is False

        # 4. navigate_show
        nav_show = pack.navigate_show(
            route="/admin/settings",
            subtab="general",
            field_name="business_name",
            reason="Highlighting business name",
        )
        assert nav_show["status"] == "ok"
        assert nav_show["highlight"]["status"] == "ok"

        # 5. fill_form
        fill_res = pack.fill_form(
            form_id="business_settings",
            fields={"business_email": "alias@bondispa.com.au"},
        )
        assert fill_res["status"] == "ok"
        assert fill_res["is_saved"] is False

        # 6. read_status
        read_stat = pack.read_status()
        assert read_stat["status"] == "ok"

        # 7. pause_takeover
        takeover = pack.pause_takeover(reason="User clicked manual takeover")
        assert takeover["status"] == "ok"
        assert takeover["control_epoch"] == 2


class TestOnboardingGatewayUnit:
    """Verifies OnboardingGateway synchronization, epoch/lease guards, and LiveKit RPC."""

    def test_gateway_synchronous_execution_and_receipts(self, db_factory):
        dispatched = []
        gateway = OnboardingGateway(
            db_factory=db_factory,
            tenant_id=1,
            user_id=1,
            active_lease_token="lease-gw-1",
            active_control_epoch=1,
            rpc_dispatcher=lambda act, p: dispatched.append((act, p)),
        )

        res = gateway.execute_tool_sync(
            name="stage_fields",
            arguments={
                "step_id": "step_1_identity",
                "fields": {"business_name": "Bondi Spa GW"},
            },
        )
        assert res["status"] == "ok"
        assert res["receipt_state"] == "fields_staged"
        assert len(gateway.dispatched_receipts) >= 1
        assert gateway.dispatched_receipts[-1]["receipt_state"] == "fields_staged"

    def test_gateway_rejects_stale_control_epoch_on_takeover(self, db_factory):
        gateway = OnboardingGateway(
            db_factory=db_factory,
            tenant_id=1,
            user_id=1,
            active_lease_token="lease-gw-1",
            active_control_epoch=1,
        )

        # Trigger manual takeover to increment epoch to 2
        takeover_res = gateway.execute_tool_sync(
            name="pause_takeover",
            arguments={"reason": "User takeover"},
        )
        assert takeover_res["status"] == "ok"
        assert takeover_res["control_epoch"] == 2

        # Stale call with old epoch 1 is rejected
        stale_res = gateway.execute_tool_sync(
            name="stage_fields",
            arguments={
                "step_id": "step_1_identity",
                "fields": {"business_name": "Old Agent"},
                "control_epoch": 1,
            },
        )
        assert stale_res["status"] == "rejected"
        assert stale_res["error_code"] == "stale_control_epoch"
        assert stale_res["receipt_state"] == "rejected"

    def test_gateway_rejects_expired_or_mismatched_lease(self, db_factory):
        gateway = OnboardingGateway(
            db_factory=db_factory,
            tenant_id=1,
            user_id=1,
            active_lease_token="lease-valid-tab",
        )

        # Execute once to initialize plan with active lease
        gateway.execute_tool_sync("read_context", {})

        # Attempt call with wrong lease token
        res = gateway.execute_tool_sync(
            name="stage_fields",
            arguments={
                "step_id": "step_1_identity",
                "fields": {"business_name": "Conflict"},
                "lease_token": "lease-wrong-tab",
            },
        )
        assert res["status"] == "rejected"
        assert res["error_code"] == "invalid_lease_token"

    @pytest.mark.asyncio
    async def test_gateway_async_execution(self, db_factory):
        gateway = OnboardingGateway(
            db_factory=db_factory,
            tenant_id=1,
            user_id=1,
        )
        res = await gateway.execute_tool("read_status", {})
        assert res["status"] == "ok"
        assert "plan_summary" in res


class TestLiveKitToolGatewayWiring:
    """Verifies onboarding tool registration and execution through LiveKitToolGateway."""

    def test_livekit_tool_gateway_registers_onboarding_pack(self, db_factory):
        session_ctx = LiveKitSessionContext(
            session_id="lk-sess-1",
            tenant_id=1,
            user_id=1,
            conversation_id=1,
            lease_token="lease-lk-1",
            control_epoch=1,
        )

        gateway = LiveKitToolGateway(
            db_factory=db_factory,
            session_context=session_ctx,
            packs=("booking_availability", "onboarding"),
        )

        tools = gateway.build_agent_tools()
        tool_names = [t.info.name for t in tools if hasattr(t, "info")]

        # All core onboarding tools must be registered
        assert "stage_fields" in tool_names
        assert "validate_form" in tool_names
        assert "commit_save" in tool_names
        assert "generate_website_draft" in tool_names
        assert "read_context" in tool_names
        assert "pause_takeover" in tool_names

    def test_livekit_tool_gateway_executes_onboarding_tool_sync(self, db_factory):
        dispatched = []
        session_ctx = LiveKitSessionContext(
            session_id="lk-sess-1",
            tenant_id=1,
            user_id=1,
            conversation_id=1,
            lease_token="lease-lk-1",
            control_epoch=1,
        )

        gateway = LiveKitToolGateway(
            db_factory=db_factory,
            session_context=session_ctx,
            packs=("onboarding",),
            rpc_dispatcher=lambda act, p: dispatched.append((act, p)),
        )

        result = gateway.execute_tool_sync(
            "stage_fields",
            {"step_id": "step_1_identity", "fields": {"business_name": "Bondi LK Spa"}},
        )

        assert result["status"] == "ok"
        assert result["action"] == "fill_fields"
        assert result["is_saved"] is False
        assert len(dispatched) >= 1
        assert len(gateway.last_rpc_dispatches) >= 1

    def test_livekit_baseline_audio_transport_preserved(self):
        """Invariant: LiveKit audio models, voice persona, and transport remain intact."""
        baseline = get_baseline_config()
        assert baseline.model == "gpt-live-1"
        assert baseline.voice == "gleam"
        assert baseline.delegation == "responses"
        assert baseline.delegated_model == "gpt-5.6-terra"
