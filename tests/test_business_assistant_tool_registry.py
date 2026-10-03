"""Real native read-tool registry tests without provider-response simulation."""

from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.adapters import BusinessAssistantReadAdapters
from app.services.business_assistant.tool_registry import ProductHelpToolRegistry


def test_product_help_tools_return_only_scoped_native_reads(db_session):
    tenant = Tenant(name="Tool Tenant", subdomain="tool-tenant", enabled_modules=["locations"])
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login="tool-owner", password_hash="test", role="owner")
    db_session.add(user)
    db_session.commit()
    registry = ProductHelpToolRegistry(BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=user.id))

    product_help = registry.execute("read_product_help", {})
    onboarding = registry.execute("read_onboarding_progress", {})
    rejected = registry.execute("read_product_help", {"tenant_id": 999})
    unavailable = registry.execute("not_a_tool", {})

    assert product_help["status"] == "ok"
    assert "locations" in product_help["product_help"]["enabled_modules"]
    assert onboarding["onboarding"]["status"] == "not_started"
    assert rejected["status"] == "rejected"
    assert unavailable["status"] == "rejected"
