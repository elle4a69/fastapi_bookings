# Authentication, Google OIDC & Chatwoot SSO Service

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

### 4.1 Google SSO Login Workflow
```
Client (Google ID Token) 
  --> POST /api/admin/auth/google 
  --> verify_google_id_token() 
  --> Resolve/Create User (tenant_id, email, google_sub)
  --> sync_user_to_chatwoot_platform()
  --> generate_chatwoot_sso_url()
  --> Returns { access_token, token_type, user, chatwoot_sso_url }
```

### 4.2 RBAC Role Alignment Matrix
| FastAPI Bookings Role | Chatwoot Account Role | Permissions |
|---|---|---|
| `owner` | `administrator` | Full tenant settings, inboxes, users, billing |
| `admin` | `administrator` | Account settings, inboxes, macros, integrations |
| `manager` | `agent` | Inboxes, conversation triage, reporting |
| `provider` | `agent` | Assigned provider inbox and schedule |
| `staff` | `agent` | Assigned inboxes |

---

## 5. Data Safety & Isolation

1. **Mandatory Tenant Claim Isolation**: All JWT access tokens minted by the auth service embed `"tenant_id": user.tenant_id`. Dependencies reject cross-tenant tokens even if a user ID matches across tenants.
2. **Ephemeral Single-Use SSO Tokens**: Chatwoot SSO URLs use 32-byte cryptographic hex tokens (`USER_SSO_AUTH_TOKEN`) stored in Redis with a 300-second (5-minute) TTL, invalidated immediately upon use.
3. **Synthetic Password Complexity**: Generated Chatwoot user passwords meet uppercase, lowercase, numeric, and special character constraints (`generate_compliant_password`), preventing unauthenticated local password access.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Google Client ID Verification**: When `GOOGLE_CLIENT_ID` is omitted in staging or local development, Google certificates and issuer are verified while audience matching is bypassed.
- **PlatformApp Permissibles**: Account users must belong to accounts that are enrolled under the active `PlatformApp`. Newly provisioned tenants via `provision_chatwoot_tenant` are registered automatically.

---

## 7. Verification & Testing Commands

Execute targeted authentication and SSO test suites:
```powershell
# Run authentication contract tests
.\.venv\Scripts\python.exe -m pytest tests/test_auth_contract.py -v

# Run SSO and Chatwoot integration tests
.\.venv\Scripts\python.exe -m pytest tests/test_sso_chatwoot.py -v
```
