# Identity & Logto Foundation Service (`app/services/identity`)

## 1. Purpose & Scope

The `identity` module owns external OAuth2/OIDC identity management, Logto integration, multi-tenant organization linking, and asynchronous tenant provisioning for the native SaaS control plane.

### Responsibilities
- **External Identity Mapping**: Mapping external OAuth2/OIDC subject identifiers (`sub`) from Logto to internal `User` records via `ExternalIdentityLink`.
- **External Organization Mapping**: Mapping external organization IDs (`org_id` / `urn:logto:organization:id`) from Logto to internal `Tenant` records via `ExternalOrganizationLink`.
- **Cryptographic Token Verification**: Enforcing local RS256 public key signature validation against Logto's JSON Web Key Set (JWKS), with in-memory caching and offline test support.
- **Invitation-Based Identity Linking**: Linking external subjects to new or existing tenant users upon valid tenant invitation redemption (`TenantInvitation`).
- **Asynchronous Organization Provisioning**: Queuing retry-safe `IdentityOutboxEvent` records for background synchronization of Logto organizations when tenants are registered.
- **Organization-Scoped Access Guard**: Strictly rejecting access when an organization token targets an unlinked tenant or when a user's membership has been revoked.

### Deliberate Exclusions
- Does not store raw passwords or external secrets.
- Does not perform uninvited auto-provisioning (strict WP0/WP1 security invariant).
- Does not replace internal authorization roles or database permissions.

---

## 2. Architecture & Key Files

```
app/services/identity/
├── __init__.py                # Package exports (LogtoTokenValidator, LogtoClient, IdentityProvisioningService)
├── jwt_validator.py           # RS256 signature verification, claims normalization, JWKS caching
├── logto_client.py            # Logto Management API client for org & membership synchronization
├── provisioning_service.py    # Idempotent identity & org linking, outbox processing, invitation linking
└── README.md                  # This living module documentation
```

### Key Models and Schemas
- **[`ExternalIdentityLink`](file:///f:/Projects/fastapi_bookings/app/models/external_identity.py)**: `(provider, external_subject_id)` -> `user_id`. Unique on provider + external_subject_id.
- **[`ExternalOrganizationLink`](file:///f:/Projects/fastapi_bookings/app/models/external_identity.py)**: `(provider, external_organization_id)` -> `tenant_id`. Unique on provider + external_organization_id and provider + tenant_id.
- **[`IdentityOutboxEvent`](file:///f:/Projects/fastapi_bookings/app/models/external_identity.py)**: Durable, retry-safe queue for provisioning and sync tasks with unique `idempotency_key`.
- **[`LogtoTokenExchangeRequest`](file:///f:/Projects/fastapi_bookings/app/schemas/identity.py)**: Request schema for token exchange and invitation-based account linking.
- **[`IdentityMeResponse`](file:///f:/Projects/fastapi_bookings/app/schemas/identity.py)**: Identity state, subject mapping, and accessible tenant organizations.

---

## 3. Setup, Configuration & Dependencies

### Configuration Settings (`app/core/config.py`)
- `LOGTO_ENDPOINT`: Base URL for the Logto instance (e.g. `https://auth.example.com` or local container).
- `LOGTO_APP_ID`: Client ID for the web/portal application.
- `LOGTO_APP_SECRET`: Client secret for the web application.
- `LOGTO_API_RESOURCE`: Resource indicator / audience expected in organization access tokens (e.g. `https://api.fastapibookings.com`).
- `LOGTO_M2M_APP_ID`: Machine-to-machine application ID for Management API access.
- `LOGTO_M2M_APP_SECRET`: M2M application secret for Management API.
- `LOGTO_JWKS_URI`: Optional explicit URI for JWKS (defaults to `{LOGTO_ENDPOINT}/oidc/jwks`).
- `LOGTO_ISSUER`: Optional explicit issuer claim (defaults to `{LOGTO_ENDPOINT}/oidc`).
- `LOGTO_CACHE_TTL_SECONDS`: In-memory caching duration for public keys (default: 3600 seconds).
- `LOGTO_PUBLIC_KEYS_JSON`: Optional pre-seeded JWKS JSON for hermetic/offline environments.

### Core Dependencies
- `python-jose[cryptography]`: For RS256 JWT decoding, header inspection, and JWK translation.
- `cryptography`: High-performance asymmetric cryptographic primitives.
- `httpx`: Async and sync HTTP clients with explicit timeouts for JWKS fetching and Management API interactions.

---

## 4. Core Workflows & Contracts

### Workflow 1: Token Exchange on Invitation Redemption (`POST /api/identity/exchange`)
1. Client presents a signed Logto OIDC token (`id_token` or `access_token`) and a single-use `invitation_token`.
2. `LogtoTokenValidator` validates RS256 signature, expiry, issuer, and audience against cached JWKS.
3. System verifies `TenantInvitation` exists in the database with status `pending` and not expired.
4. If no user exists for that email within the invited tenant, an internal `User` is created with the invitation's role.
5. `ExternalIdentityLink` is recorded mapping `(provider='logto', external_subject_id=sub)` to `user.id`.
6. Invitation transitions to status `accepted` with timestamp `accepted_at`.
7. Internal access token is returned in the response alongside user and tenant metadata.

### Workflow 2: Organization-Scoped Request Authentication (`get_current_user`)
1. Inbound request delivers `Authorization: Bearer <token>` or `X-Token: <token>`.
2. `get_current_user` attempts validation via `LogtoTokenValidator`.
3. If RS256 token is valid, external subject `sub` is looked up via `ExternalIdentityLink`.
4. If an organization claim (`org_id` / `urn:logto:organization:id`) is present, the mapped internal tenant is resolved via `ExternalOrganizationLink`.
5. Access is strictly rejected with `403 Forbidden` if:
   - The token's organization is not linked to any tenant.
   - The token's organization does not match the active request tenant (`X-Tenant` / host subdomain).
   - The user does not hold an active membership in the resolved tenant.
6. If the token is not an RS256 Logto token, falls back cleanly to internal HS256 JWT verification.

### Workflow 3: Asynchronous Organization Provisioning (`IdentityOutboxEvent`)
1. Tenant creation enqueues an `IdentityOutboxEvent` with type `organization.provision` and idempotency key `provision:logto:tenant:{tenant_id}`.
2. Background outbox worker (`process_identity_outbox`) claims pending events with optimistic locking.
3. Worker calls Logto Management API (`get_or_create_organization`) to provision the organization.
4. Idempotently creates or updates `ExternalOrganizationLink`.
5. Event status transitions to `SUCCEEDED` with `processed_at`.

---

## 5. Data Safety & Isolation

- **Tenant Isolation**: Users can only execute actions within tenants where an explicit membership or ownership record exists. Organization tokens for Tenant A cannot be used to query or manipulate Tenant B.
- **No Auto-Provisioning**: Uninvited external users presenting valid Logto tokens are strictly rejected with `403 Forbidden`. Accounts can only be established via explicit tenant invitations or pre-existing linked internal profiles.
- **Immediate Revocation**: Deactivating a `User` (`is_active = False`) or suspending a `Tenant` immediately revokes all API access on subsequent requests, regardless of unexpired token TTL.
- **Zero Secret Exposure**: Tokens, private keys, M2M client secrets, and raw request payloads are never logged or reflected in error messages. All validation exceptions emit sanitized structural error codes (`TOKEN_EXPIRED`, `INVALID_SIGNATURE`, etc.).

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Full Control Plane Integration**: WP1 through WP5 are fully implemented and verified. Production deployment topology is documented in [`docs/operations/DEPLOYMENT_TOPOLOGY_LOGTO_FLEXPRICE.md`](file:///f:/Projects/fastapi_bookings/docs/operations/DEPLOYMENT_TOPOLOGY_LOGTO_FLEXPRICE.md), operational runbooks in [`docs/runbooks/SAAS_CONTROL_PLANE_RUNBOOK.md`](file:///f:/Projects/fastapi_bookings/docs/runbooks/SAAS_CONTROL_PLANE_RUNBOOK.md), and platform security review in [`docs/security/SAAS_CONTROL_PLANE_SECURITY_REVIEW.md`](file:///f:/Projects/fastapi_bookings/docs/security/SAAS_CONTROL_PLANE_SECURITY_REVIEW.md).
- **Edge Case - Concurrent Linking**: Handled via database unique constraints on `(provider, external_subject_id)` and catch-rollback retry in `link_identity`.
- **Edge Case - Clock Skew**: `python-jose` decode handles standard leeway; expiration validation enforces strict timestamp comparison.
- **Provider Liveness Check**: Validated via deep readiness probe (`GET /api/platform/health/readiness` and `/health/ready`).

---

## 7. Verification & Testing Commands

Execute the following commands to verify identity foundation implementation, cryptographic token validation, and multi-tenant access control.

### Verification Tests
Run the comprehensive Logto identity contract suite:
```powershell
python -m pytest tests/test_wp1_logto_identity_contract.py -v
```

### Full Multi-Tenant Security & Operational Hardening Suite
Execute the full security, identity, billing, entitlements, and operational hardening verification suites:
```powershell
python -m pytest tests/test_wp0_security_contract.py tests/test_wp1_logto_identity_contract.py tests/test_wp2_flexprice_billing_contract.py tests/test_wp3_entitlements_contract.py tests/test_wp4_ux_api_contract.py tests/test_wp5_operational_hardening.py -v
```

### Documentation Verification Gate
Verify living documentation compliance against AGENTS.md Rule 10:
```powershell
python scripts/verify_living_docs.py --path app/services/identity/README.md
```
