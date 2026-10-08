# Shared frontend libraries

## Purpose & Scope

This directory contains shared browser utilities, including the authenticated
API client and tenant-host resolver in `api.ts`. It does not own backend
authentication, tenant membership, booking mutations or Cloudflare configuration.

## Architecture & Key Files

- `api.ts`: same-origin HTTP requests, tenant headers, token handling and safe
  session/error navigation.
- `api.test.ts`: regression tests for hostname classification, header selection,
  local-only bypass, logout and error handling.
- The login page and client portal reuse `getActiveTenantFromHost`; admin requests
  reuse `getAuthenticatedAdminHeaders`.

## Setup, Configuration & Dependencies

Use the existing frontend Node/TypeScript toolchain and `package.json` commands.
API traffic is same-origin; the existing Vite development proxy forwards `/api`
to the configured backend. This fix introduces no environment variables,
dependencies, credentials or tunnel configuration changes.

## Core Workflows & Contracts

Tenant-style hosts such as `tenant.localhost` and `tenant.example.com` retain
their existing tenant-label interpretation. Cloud Run and exact
`*.trycloudflare.com` routing hostnames are not interpreted as tenant slugs.
Quick tunnels therefore reach the already-existing `simplydemo` development
fallback used by the login page and admin request headers, instead of requesting
a tenant named after Cloudflare's random hostname.

The suffix comparison uses a domain boundary, not a substring: a host such as
`tenant.trycloudflare.com.example.com` retains its normal tenant interpretation.
Case and a trailing DNS dot are normalised by the existing resolver.

## Data Safety & Isolation

A tenant selector is not authentication or authorisation. Backend token,
tenant-membership and role checks remain authoritative and unchanged. Quick
tunnels do not receive the localhost development bypass: absent a stored token,
admin requests remain unauthenticated. Do not log tokens or request credentials.

## Known Issues, Edge Cases & Outstanding Work

- The existing quick-tunnel development fallback targets `simplydemo`; this is
  not a general multi-business tenant chooser or production custom-domain map.
- Google sign-in still requires the exact public origin registered on the
  existing OAuth client. Temporary tunnel URLs can change on restart.
- This change does not modify backend forwarded-host handling, OAuth settings,
  passwords, account creation or any unrelated authentication code.

## Verification & Testing Commands

From `frontend/`:

```powershell
node --experimental-strip-types --test src/lib/api.test.ts
npm test
npm run build
```

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/verify_living_docs.py --path frontend/src/lib/README.md
```

Runtime checks use the existing tunnel and backend: confirm the served resolver
excludes the quick-tunnel hostname, the login page displays `simplydemo`, and
an anonymous `/api/admin/auth/me` request with that tenant remains HTTP 401.
Do not use real account credentials or create business records for this check.
