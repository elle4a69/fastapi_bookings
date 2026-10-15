# Architecture Decision Record (ADR): Platform Ownership and Control-Plane Boundary

- **Status**: Accepted & Implemented
- **Date**: 2026-10-16
- **Context**: WP0 (Security Baseline and Control-Plane Contract)
- **Deciders**: Engineering Team, Security Review

---

## 1. Context & Problem Statement

FastAPI Bookings previously conflated the tenant-level administrative role (`role='owner'`) with platform-wide administrative privileges (`require_platform_owner`). In several endpoints:
1. A tenant owner could escalate privileges or access platform-level routes (e.g. modifying subscription tiers, accessing cross-tenant support tickets).
2. Tenant creation (`POST /api/tenants`) and tier mutations (`PUT /api/tenants/{id}/tier`) were not strictly gated behind platform-level authorization.
3. Google OAuth auto-provisioned the first user of any tenant as `role='owner'` or subsequent users as `role='admin'`, allowing unauthenticated or unintended users with valid Google accounts to claim tenant ownership without explicit authorization.
4. Tenant lifecycle states were undefined; there was no mechanism to suspend or reactivate tenants, and no guard in `get_current_tenant` to halt traffic to suspended tenants.
5. Insecure Direct Object Reference (IDOR) existed on `GET /api/tenants/{tenant_id}`, allowing any authenticated tenant user to inspect metadata of other tenants.

## 2. Decision & Architectural Principles

### 2.1 Separation of Platform Owner and Tenant Owner
- **Platform Owner (Control Plane)**: Explicitly identified via `User.is_platform_owner = True` or `User.is_superuser = True` or `User.role = 'platform_owner'`. Platform owners have `tenant_id = None` (or global scope) and can execute control-plane operations without supplying an `X-Tenant` header.
- **Tenant Owner (Data Plane)**: A customer with `role = 'owner'` within their specific `tenant_id`. Tenant owners have full administrative control **strictly within their tenant data plane**, but are strictly forbidden (`403 Forbidden`) from platform control-plane endpoints.

### 2.2 Control Plane vs Data Plane Boundary
- **Data Plane**:
  - Requires tenant context via hostname resolution or `X-Tenant` header.
  - Queries are strictly scoped: `query(Model).filter(Model.tenant_id == current_tenant.id)`.
  - Enforces tenant lifecycle: if `tenant.status == 'suspended'`, all data-plane access immediately returns `403 Forbidden` (`{"detail": "Tenant is suspended: <reason>"}`).
- **Control Plane**:
  - Gated via `require_platform_owner` (backed by `get_current_platform_owner`).
  - Does NOT require `X-Tenant` header.
  - Controls tenant provisioning (`POST /api/tenants`), tenant suspension/reactivation (`POST /api/tenants/{id}/suspend`, `POST /api/tenants/{id}/reactivate`), subscription tier mutation (`PUT /api/tenants/{id}/tier`), and cross-tenant observability/support queues.

### 2.3 Invitation-Based Onboarding & Elimination of Auto-Provisioning
- **Elimination of Auto-Provisioning**:
  - The insecure fallback (`role = "owner" if user_count == 0 else "admin"`) has been completely removed from `google_login`.
  - Uninvited Google OAuth logins are rejected with `403 Forbidden` (`{"detail": "No pending invitation found for email <email>. Please request an invitation from the tenant owner."}`).
- **Cryptographic Invitations (`TenantInvitation`)**:
  - Provisioning of initial tenant owners or additional tenant staff requires an invitation token generated via `secrets.token_urlsafe(32)`.
  - Tokens expire after 7 days and transition through `pending` -> `accepted` | `revoked` | `expired`.
  - Accepted via `POST /api/auth/invitations/accept`, creating the user and invalidating the token atomically.

### 2.4 Cross-Tenant IDOR Protection
- `GET /api/tenants/{tenant_id}` verifies that the authenticated caller is either:
  1. A verified Platform Owner (`is_platform_owner=True`), OR
  2. A verified member belonging to that specific tenant (`current_user.tenant_id == tenant_id`).
- Unauthorized callers receive `403 Forbidden`.

## 3. Database Schema Changes

Alembic revision `a2b3c4d5e6f8` introduces:
- `users`:
  - `is_platform_owner`: Boolean, default False, not null.
  - `is_superuser`: Boolean, default False, not null.
  - `tenant_id`: Made nullable (`nullable=True`) for platform-level operators.
- `tenants`:
  - `status`: String(32), default 'active', not null (`active` | `suspended`).
  - `suspended_at`: DateTime(timezone=True), nullable.
  - `suspension_reason`: Text, nullable.
- `tenant_invitations`:
  - `id`: Integer primary key.
  - `tenant_id`: Integer foreign key -> `tenants.id`.
  - `email`: String(255), not null, indexed.
  - `role`: String(64), default 'staff', not null.
  - `token`: String(128), unique, not null, indexed.
  - `status`: String(32), default 'pending', not null.
  - `invited_by_user_id`: Integer foreign key -> `users.id`, nullable.
  - `created_at`, `expires_at`, `accepted_at`: Timestamps.
- `audit_logs`:
  - `tenant_id`: Made nullable for platform-level audit events.

## 4. Consequences & Verification

- **Security Posture**: Multi-tenant isolation is strictly enforced. Privilege escalation from tenant owner to platform owner is impossible.
- **Backwards Compatibility**: Existing tenant user tokens remain valid within their respective tenants. Support ticket and platform administration tests are updated to authenticate with `is_platform_owner=True`.
- **Verification**: Verified with 47 passing tests including `test_wp0_security_contract.py` and `test_three_tenant_isolation.py`.
