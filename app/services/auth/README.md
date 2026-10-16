# Authentication, Google OIDC & Chatwoot SSO Service

### Persisted platform-owner authority

`platform_owner_authority.py` owns status, preview, grant, and revoke behavior
for the cross-tenant platform capability. Mutations require a fresh session,
serialize through a PostgreSQL transaction advisory lock or SQLite
`BEGIN IMMEDIATE`, enforce the last-active-owner invariant, and commit the user
change with one structural `AuditLog`. Unsupported database dialects fail
closed. No login, email, token, or customer data is accepted or emitted.

The service deliberately does not own tenant RBAC, public HTTP routes, user
deactivation, or initial provisioning. Callers use numeric tenant/user IDs and
the offline CLI; future deactivation/deletion support must reuse this guard.

## 1. Purpose & Scope

The `app/services/auth` module acts as the central identity broker and Single Sign-On (SSO) gateway for FastAPI Bookings. It owns:
- Cryptographic verification of third-party Identity Provider tokens (Google OAuth2 / OpenID Connect).
- Secure user synchronization and account-user role binding with Chatwoot Enterprise Platform API (`/platform/api/v1/`).
- Exchange of authenticated sessions for single-use Chatwoot `sso_auth_token` URLs (5-minute TTL).
- Multi-tenant JWT access token minting and tenant boundary validation (`tenant_id` claim verification).

This module deliberately avoids managing external customer passwords or storing unencrypted provider credentials.

---

## 2. Architecture & Key Files

- [`__init__.py`](file:///f:/Projects/fastapi_bookings/app/services/auth/__init__.py): Public service exports.
- [`google_oidc.py`](file:///f:/Projects/fastapi_bookings/app/services/auth/google_oidc.py): Google OAuth2/OIDC ID token verification via `google.oauth2.id_token` and `google.auth.transport.requests`.
- [`chatwoot_sso.py`](file:///f:/Projects/fastapi_bookings/app/services/auth/chatwoot_sso.py): Chatwoot Platform API client managing user provisioning, RBAC role alignment, and single-use SSO link generation.

---

## 3. Setup, Configuration & Dependencies

### External Dependencies
- `google-auth>=2.0.0`: Cryptographic certificate retrieval and signature verification.
- `httpx>=0.25.0`: Asynchronous HTTP client for Chatwoot Platform API.
- `PyJWT`: HMAC-SHA256 token minting and verification.

### Environment Configuration (`app/core/config.py`)
- `GOOGLE_CLIENT_ID`: Google OAuth2 Web Client ID (optional, audience verified when configured).
- `CHATWOOT_BASE_URL`: Chatwoot base URL (default: `http://localhost:4000`).
- `CHATWOOT_PLATFORM_API_TOKEN` / `CHATWOOT_PLATFORM_ACCESS_TOKEN`: Platform app token for automated user provisioning and SSO link generation.
- `SECRET_KEY`: Signs tenant-scoped JWT tokens (`HS256`).

---

## 4. Core Workflows & Contracts

### 4.1 Google SSO Login Workflow & Invitation Requirement
```
Client (Google ID Token) 
  --> POST /api/admin/auth/google 
  --> verify_google_id_token() 
  --> Check existing User or pending TenantInvitation
      * If user exists: authenticate
      * If pending TenantInvitation exists: redeem invitation, provision user with invited role
      * If uninvited: REJECT with 403 Forbidden (Auto-provisioning eliminated in WP0)
  --> sync_user_to_chatwoot_platform()
  --> generate_chatwoot_sso_url()
  --> Returns { access_token, token_type, user, chatwoot_sso_url }
```

### 4.2 Invitation Token Redemption Workflow
```
Client (Invitation Token + Credentials)
  --> POST /api/auth/invitations/accept
  --> Verify token status == 'pending' and expires_at > now()
  --> Atomically create User with invitation.role and invitation.tenant_id
  --> Mark invitation status = 'accepted', accepted_at = now()
  --> Return JWT access_token and user profile
```

### 4.3 RBAC Role Alignment Matrix
| FastAPI Bookings Role | Chatwoot Account Role | Permissions |
|---|---|---|
| `platform_owner` | `administrator` | Global control-plane, cross-tenant management, tier mutation |
| `owner` | `administrator` | Full tenant settings, inboxes, users, billing (Data Plane only) |
| `admin` | `administrator` | Account settings, inboxes, macros, integrations |
| `manager` | `agent` | Inboxes, conversation triage, reporting |
| `provider` | `agent` | Assigned provider inbox and schedule |
| `staff` | `agent` | Assigned inboxes |

---

## 5. Data Safety & Isolation

1. **Mandatory Tenant Claim Isolation**: All JWT access tokens minted by the auth service embed `"tenant_id": user.tenant_id`. Dependencies reject cross-tenant tokens even if a user ID matches across tenants.
2. **Platform Owner Control-Plane Separation**: Platform owners (`is_platform_owner=True`) are strictly distinguished from tenant owners (`role='owner'`). Tenant owners attempting to access platform control-plane endpoints receive `403 Forbidden`.
3. **Elimination of Auto-Provisioning**: Uninvited Google OAuth logins cannot self-promote to `owner` or `admin`. Every new user must possess a valid, pending `TenantInvitation`.
4. **Suspension Containment**: Authenticated users of suspended tenants are blocked at the dependency layer (`get_current_tenant`) with `403 Forbidden`.
5. **Ephemeral Single-Use SSO Tokens**: Chatwoot SSO URLs use 32-byte cryptographic hex tokens (`USER_SSO_AUTH_TOKEN`) stored in Redis with a 300-second (5-minute) TTL, invalidated immediately upon use.
6. **Synthetic Password Complexity**: Generated Chatwoot user passwords meet uppercase, lowercase, numeric, and special character constraints (`generate_compliant_password`), preventing unauthenticated local password access.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Google Client ID Verification**: When `GOOGLE_CLIENT_ID` is omitted in staging or local development, Google certificates and issuer are verified while audience matching is bypassed.
- **PlatformApp Permissibles**: Account users must belong to accounts that are enrolled under the active `PlatformApp`. Newly provisioned tenants via `provision_chatwoot_tenant` are registered automatically.
- **Timezone Awareness in Invitation Expiry**: When running tests against SQLite (naive datetimes) vs PostgreSQL (offset-aware datetimes), the helper `_is_expired(dt)` normalizes both representations to UTC for accurate expiry checks.

---

## 7. Verification & Testing Commands

Execute targeted authentication, security baseline, and SSO test suites:
```powershell
# Run WP0 security contract tests
.\.venv\Scripts\python.exe -m pytest tests/test_wp0_security_contract.py -v

# Run 3-tenant isolation and suspension tests
.\.venv\Scripts\python.exe -m pytest tests/test_three_tenant_isolation.py -v

# Run authentication contract tests
.\.venv\Scripts\python.exe -m pytest tests/test_auth_contract.py -v

# Run role hierarchy tests
.\.venv\Scripts\python.exe -m pytest tests/test_role_hierarchy.py -v

# Run SSO and Chatwoot integration tests
.\.venv\Scripts\python.exe -m pytest tests/test_sso_chatwoot.py -v
```
