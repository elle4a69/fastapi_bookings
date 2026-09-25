# Admin Management Portal & App Store

## Purpose & Scope
The `frontend/src/pages/admin/` directory implements the staff and administrative console for **FastAPI Bookings**. It serves business owners, operators, dispatchers, and practitioners. Key responsibilities include:
- Operational scheduling, calendar visualizer, and booking lifecycle control.
- Tenant configuration, modular app store, and tier entitlements.
- AI orchestration via the SMS Assistant and Resident Agent.
- Customer relationship management, client histories, and reviews.
- Enterprise compliance (GDPR, audit logging, system metrics, and telemetry).

The admin module deliberately leaves public-facing bookings and client self-service interactions to `/book`, `/site`, and `/portal`.

---

## Architecture & Key Files

### Directory Layout
```
frontend/src/pages/admin/
├── catalog/                     # Service catalog, providers, locations & bundles
│   ├── add-ons.tsx              # Add-on upsells
│   ├── categories.tsx           # Service categorization hierarchy
│   ├── locations.tsx            # Physical facilities & timezones
│   ├── packages.tsx             # Bundled multi-session packages
│   ├── products.tsx             # Inventory & retail items
│   ├── providers.tsx            # Staff & practitioner profiles
│   ├── scheduling.tsx           # Multi-provider scheduling rules
│   └── services.tsx             # Services definition & booking durations
├── compliance/
│   └── gdpr.tsx                 # Data subject export & erasure tools
├── configuration/
│   └── additional-fields.tsx    # Custom metadata fields configuration
├── finance/                     # Invoices, payments, taxes & processors
│   ├── invoices.tsx             # Invoicing management with PDF/email triggers
│   ├── payments.tsx             # Transactions history & refund tracking
│   ├── processors.tsx           # Stripe, Square, PayPal gateway settings
│   ├── promotions.tsx           # Coupon codes & promotional discounts
│   └── tax-rates.tsx            # Tax calculation rules & rates
├── notifications/
│   ├── messages.tsx             # Outbound communication history
│   ├── reminders.tsx            # Automated SMS/Email appointment triggers
│   └── templates.tsx            # Message content templates
├── provider/                    # Practitioner portal views
│   ├── my-jobs.tsx              # Assigned bookings and status controls
│   ├── my-profile.tsx           # Personal provider profile & bio
│   └── my-schedule.tsx          # Personal working hours & exceptions
├── schedule/
│   ├── exceptions.tsx           # Blocked dates & holiday overrides
│   └── workdays.tsx             # Weekly operating schedules
├── settings/
│   ├── business.tsx             # Tenant profile, logo, timezone & currency
│   ├── modules.tsx              # Modular App Store & tier quota management
│   ├── plugins.tsx              # Third-party extensions
│   └── webhooks.tsx             # Outbound webhook registrations
├── sms/                         # SMS Assistant suite (inbox, triage, arrivals, simulator)
├── audit.tsx                    # System audit trail viewer
├── booking-form-editor.tsx      # Drag-and-drop dynamic intake form designer
├── booking-forms.tsx            # Form template listing & publication status
├── bookings.tsx                 # Bookings tabular list, search & bulk operations
├── dashboard.tsx                # Configurable operational dashboard with customizable cards and deep module linking
├── calendar.tsx                 # Full interactive agenda & timeline calendar
├── clients.tsx                  # Client CRM, contact details & appointment notes
├── media.tsx                    # Media asset gallery & file uploader
├── relationships.tsx            # Graph overview of service-provider-location bindings
├── relationships-matrix.tsx     # Matrix editor for service/provider assignments
├── relationships-tree.tsx       # Hierarchical tree representation of relationships
├── resident-agent.tsx           # AI resident engineer & conversational coding studio
├── resources.tsx                # Facility rooms, chairs & equipment booking
├── reviews.tsx                  # Client testimonials, ratings & dispute approvals
├── sms-assistant.tsx            # Unified SMS command center shell
├── system.tsx                   # Health status, cache inspection & DB metrics
├── telemetry.tsx                # Real-time OpenTelemetry trace & span inspector
└── website.tsx                  # Public website layout builder & theme customizer
```

### Core Architecture Components
- **Dynamic Navigation Filtering ([`frontend/src/components/navigation.ts`](file:///F:/Projects/fastapi_bookings/frontend/src/components/navigation.ts))**: The sidebar navigation items declare optional `moduleKey` attributes. The function `filterNavigationByModules(sections, enabledModules)` strips disabled modules dynamically so staff only see features permitted by their tenant's plan.
- **Tenant Modules Context ([`frontend/src/context/tenant-modules-context.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/context/tenant-modules-context.tsx))**: Exposes `modulesData`, `enabledModules`, and API actions `toggleModule()` and `updateTier()`. Manages the optimistic UI updates and validation guards.
- **Modular App Store ([`frontend/src/pages/admin/settings/modules.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/settings/modules.tsx))**: Visual marketplace allowing tenant admins to enable or disable add-on capabilities (e.g., Resident Agent, Advanced Finance, Cal.com Scheduling). Enforces tier limits with an upgrade modal when add-on quotas are exceeded.
- **Responsive Layout Shell ([`frontend/src/layouts/admin-layout.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/layouts/admin-layout.tsx))**: Houses the collapsible `AppSidebar`, mobile topbar, tenant switch indicator, user profile dropdown, and child page routing outlet.

---

## Setup, Configuration & Dependencies

### Required Context Providers
The admin views depend on:
1. `AuthProvider` ([`src/context/auth-context.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/context/auth-context.tsx)): Injects current user info, roles (`isAdmin`, `isProvider`), and session token.
2. `TenantModulesProvider` ([`src/context/tenant-modules-context.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/context/tenant-modules-context.tsx)): Loads module licenses from `/api/admin/tenant/modules`.

### Key Backend Endpoints
- `GET /api/admin/tenant/modules`: Retrieves tenant tier (`starter`, `growth`, `pro`, `enterprise`, `unlimited`), quota metrics (`addon_quota`, `used_addons`), and array of registered modules.
- `POST /api/admin/tenant/modules/{key}/toggle`: Enables or disables a specific modular capability.
- `POST /api/admin/tenant/modules/tier`: Upgrades or modifies tenant plan entitlements.
- `GET /api/admin/bookings`, `GET /api/admin/clients`, `GET /api/admin/catalog/*`: Core business resource feeds.

---

## Core Workflows & Contracts

### 1. App Store & Entitlement Activation
```
[Admin Page: /admin/settings/modules]
                │
                ▼ (Toggle clicked on Add-On module)
        Check is_core flag?
         ├── Yes ──> Error: Core modules cannot be disabled
         └── No  ──> Check (used_addons < addon_quota)?
                       ├── No  ──> Open Quota Upgrade Modal
                       └── Yes ──> POST /api/admin/tenant/modules/{key}/toggle
                                     │
                                     ▼
                      Update TenantModulesContext state
                                     │
                                     ▼
                Sidebar automatically displays new navigation item
```

### 2. Provider Schedule Redirection
When a practitioner logs in who lacks full administrative rights (`isProvider = true`, `isAdmin = false`), `App.tsx` routes them automatically away from the main dashboard to `/admin/my-schedule`, restricting their navigation to assigned appointments and personal working hours.

---

## Data Safety, Multi-Tenancy & PII Isolation

- **Staff Authorization Boundaries**: All admin API requests pass `Authorization: Bearer <admin_token>`. The backend verifies the JWT role and rejects non-admin users with 403 Forbidden.
- **Tenant Separation**: Admin API endpoints scoped to a tenant cannot query or mutate data belonging to other tenants. The tenant context is pinned by the authenticated admin's session.
- **PII Scrubbing in Audit Logs**: The audit viewer ([`audit.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/audit.tsx)) masks passwords, payment tokens, and cryptographic salts before rendering log lines.

---

## Known Issues, Edge Cases & Outstanding Work

- **Initial Module Hydration**: Before `GET /api/admin/tenant/modules` returns, navigation falls back to `DEFAULT_FALLBACK_MODULES` to prevent visual flicker. If a network failure occurs, add-on features may remain hidden until a manual refresh.
- **Real-Time Calendar Websockets**: The calendar view ([`calendar.tsx`](file:///F:/Projects/fastapi_bookings/frontend/src/pages/admin/calendar.tsx)) polls on tab focus; WebSocket integration for concurrent multi-dispatcher schedule editing is slated for a future release.

---

## Verification & Testing Commands

To verify admin modules:
```bash
# Typecheck admin pages and build bundle
cd frontend
npm run build

# Lint admin TypeScript files
npx oxlint src/pages/admin
```
