"""Multi-tenant security isolation test across three distinct tenants (Alpha, Beta, Gamma).

Verifies:
1. Complete tenant boundary isolation across 3 separate tenants.
2. Cross-tenant credential and resource containment.
3. Selective suspension isolation: suspending Tenant Beta completely blocks Beta without
   affecting Alpha or Gamma.
4. Reactivation restores Beta without impacting Alpha or Gamma.
5. Platform owner control plane visibility across all tenants.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.models.service import Service


def _create_tenant_with_data(db_session: Session, name: str, slug: str) -> tuple[Tenant, User, dict[str, str], Service]:
    tenant = Tenant(
        name=name,
        subdomain=slug,
        subscription_tier="growth",
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        login=f"admin@{slug}.test",
        email=f"admin@{slug}.test",
        password_hash=get_password_hash("SecretPassword123!"),
        role="owner",
        is_platform_owner=False,
        is_superuser=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    service = Service(
        tenant_id=tenant.id,
        name=f"Exclusive Service for {name}",
        duration=60,
        price=100.0,
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }
    return tenant, user, headers, service


def _create_platform_owner(db_session: Session) -> tuple[User, dict[str, str]]:
    owner = User(
        login="global_admin@controlplane.internal",
        password_hash=get_password_hash("MasterKey123!"),
        role="platform_owner",
        is_platform_owner=True,
        is_superuser=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    headers = {"X-Token": create_access_token({"sub": str(owner.id)})}
    return owner, headers


def test_three_tenant_boundary_and_suspension_containment(client: TestClient, db_session: Session):
    """Rigorous 3-tenant isolation test."""
    t_alpha, u_alpha, h_alpha, s_alpha = _create_tenant_with_data(db_session, "Tenant Alpha", "alpha-tenant")
    t_beta, u_beta, h_beta, s_beta = _create_tenant_with_data(db_session, "Tenant Beta", "beta-tenant")
    t_gamma, u_gamma, h_gamma, s_gamma = _create_tenant_with_data(db_session, "Tenant Gamma", "gamma-tenant")
    p_owner, h_platform = _create_platform_owner(db_session)

    # 1. Verify all 3 tenants can view their own profiles and services
    res_a = client.get("/api/admin/services", headers=h_alpha)
    assert res_a.status_code == 200
    assert any(s["id"] == s_alpha.id for s in res_a.json()["data"])
    assert not any(s["id"] in (s_beta.id, s_gamma.id) for s in res_a.json()["data"])

    res_b = client.get("/api/admin/services", headers=h_beta)
    assert res_b.status_code == 200
    assert any(s["id"] == s_beta.id for s in res_b.json()["data"])
    assert not any(s["id"] in (s_alpha.id, s_gamma.id) for s in res_b.json()["data"])

    res_c = client.get("/api/admin/services", headers=h_gamma)
    assert res_c.status_code == 200
    assert any(s["id"] == s_gamma.id for s in res_c.json()["data"])
    assert not any(s["id"] in (s_alpha.id, s_beta.id) for s in res_c.json()["data"])

    # 2. Cross-Tenant IDOR: Alpha trying to access Beta's tenant profile
    res_cross_ab = client.get(f"/api/tenants/{t_beta.id}", headers=h_alpha)
    assert res_cross_ab.status_code == 403

    # Beta trying to access Gamma's tenant profile
    res_cross_bg = client.get(f"/api/tenants/{t_gamma.id}", headers=h_beta)
    assert res_cross_bg.status_code == 403

    # Gamma trying to access Alpha's tenant profile
    res_cross_ga = client.get(f"/api/tenants/{t_alpha.id}", headers=h_gamma)
    assert res_cross_ga.status_code == 403

    # 3. Platform owner suspends Tenant Beta ONLY
    res_suspend_beta = client.post(
        f"/api/tenants/{t_beta.id}/suspend",
        json={"reason": "Payment overdue"},
        headers=h_platform,
    )
    assert res_suspend_beta.status_code == 200
    assert res_suspend_beta.json()["data"]["status"] == "suspended"

    # 4. Assert Beta is strictly blocked
    res_beta_blocked = client.get("/api/admin/services", headers=h_beta)
    assert res_beta_blocked.status_code == 403
    assert "suspended" in res_beta_blocked.json()["detail"].lower()

    # 5. Assert Alpha and Gamma remain COMPLETELY unaffected and active
    res_alpha_still_active = client.get("/api/admin/services", headers=h_alpha)
    assert res_alpha_still_active.status_code == 200
    assert any(s["id"] == s_alpha.id for s in res_alpha_still_active.json()["data"])

    res_gamma_still_active = client.get("/api/admin/services", headers=h_gamma)
    assert res_gamma_still_active.status_code == 200
    assert any(s["id"] == s_gamma.id for s in res_gamma_still_active.json()["data"])

    # 6. Platform owner reactivates Tenant Beta
    res_reactivate_beta = client.post(f"/api/tenants/{t_beta.id}/reactivate", headers=h_platform)
    assert res_reactivate_beta.status_code == 200
    assert res_reactivate_beta.json()["data"]["status"] == "active"

    # 7. Beta is restored
    res_beta_restored = client.get("/api/admin/services", headers=h_beta)
    assert res_beta_restored.status_code == 200
    assert any(s["id"] == s_beta.id for s in res_beta_restored.json()["data"])
