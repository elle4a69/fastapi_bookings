# FastAPI Bookings — Frontend Application & PWA

## Purpose & Scope
The `frontend/` directory contains the modern Single Page Application (SPA) and Progressive Web App (PWA) for **FastAPI Bookings**.

It serves multiple user surfaces:
1. **Admin Workspace** (`/admin`, `/admin/dashboard`, `/admin/calendar`, `/admin/bookings`, etc.): Staff control center.
2. **Practitioner Portal** (`/admin/my-schedule`, `/admin/my-jobs`, `/admin/my-profile`): Role-scoped self-service.
3. **Client Self-Service Portal** (`/portal`): Passwordless appointment reschedule, cancellation, and dispute lodging.
4. **Public Single-Page Website** (`/site`): Multi-theme tenant website with embedded booking and chat widget.
5. **Umbrella Directory & Geo-Radius Marketplace** (`/directory`): Search and triage nearby clinics.
6. **Messaging Operations Workspace** (`/admin/sms-assistant`): Tenant-scoped SMS inbox, draft moderation, arrivals, synthetic simulator, line configuration, and diagnostics. FastAPI Bookings remains authoritative for clients, availability, and bookings.

---

## Architecture & Key Files

```
frontend/
├── public/                      # PWA icons, manifest, favicon, apple-touch-icon
├── src/
│   ├── components/              # App header, sidebar, navigation, iOS install prompt
│   │   └── ui/                  # Shadcn primitives, MobilePageShell, ResponsiveDataTable
│   ├── context/                 # AuthContext, ClientPortalContext, TenantModulesContext, TranslationContext
│   ├── layouts/                 # AdminLayout with responsive padding & safe-area insets
│   ├── lib/                     # Axios API client, utils, auth tokens
│   ├── pages/                   # Admin, Portal, and Public route components
│   ├── App.tsx                  # Main router and lazy route configurations
│   ├── main.tsx                 # React entrypoint & PWA service worker registration
│   └── index.css                # Tailwind base styles and theme tokens
├── vite.config.ts               # Vite build config with vite-plugin-pwa
└── package.json                 # Dependencies and build scripts
```

---

## Mobile-First & PWA Standards
- **Standalone PWA**: Configured with `display: 'standalone'` in `manifest.webmanifest`. Includes automatic update service worker (`sw.js`).
- **44x44px Touch Targets**: All buttons, inputs, switches, and navigation triggers adhere to the 44px minimum tap height in standard touch views.
- **Traditional Hamburger Menu**: The mobile header explicitly renders a visible, touch-safe `Menu` icon with direct sidebar toggle.
- **Column Visibility Picker**: `ResponsiveDataTable` lets users customize displayed columns on small screens to eliminate horizontal scrolling.
- **Compact Density Mode (`density="compact"`)**:
  - `MobilePageShell`: Supports `density="compact"` to reduce vertical margins (`space-y-2 sm:space-y-2.5`), header gap (`space-y-1 sm:space-y-1.5`), title scale (`text-lg sm:text-xl`), description line-clamp, and action buttons gap.
  - `ResponsiveDataTable`: Supports `density="compact"` to reduce control bar vertical padding (`py-1.5`), header height/padding (`h-8 py-1 text-xs`), and body cell padding (`py-1.5 sm:py-2 px-2.5 sm:px-3 text-xs`), increasing above-the-fold record density by ~50%.
- **Calendar & Scheduling Viewport Optimization**:
  - `CalendarPage` consolidates 3 stacked header tiers (~174px) into 2 clean, high-density bars (~76px total):
    1. **Top Bar**: Date navigation cluster, view switcher segmented control (`Month`, `Work Week`, `Week`, `Day`), and primary action buttons (`Add Note`, `New Booking`).
    2. **Filter & Secondary Toolbar**: Compact Provider & Location selectors, Filter toggle, and secondary operational links (`Edit schedules`, `Manage bookings`, `Transactions`, `Notes`).
  - Reclaims 80px–100px of vertical space, displaying calendar grids and appointments immediately above the fold.

## Messaging Operations Boundary

The SMS operations workspace is native to this frontend and uses the same authenticated tenant boundary as the rest of FastAPI Bookings. Conversation controls and draft lifecycle actions are persisted by backend APIs; browser-local state is never treated as the source of truth. The workspace links operators to the existing client, booking, and arrival surfaces and does not implement a second booking form or calendar authority.

Features whose backend audit contract is not yet available—such as escalation reasons, resolution notes, internal notes, AI correction evidence, and CSV/audit export—must remain visibly unavailable rather than making speculative API calls.

---

## Dynamic Industry Terminology (`TranslationContext` & `useTranslation`)

The application implements dynamic terminology customization to adapt across health/medical, automotive, spa/wellness, and professional services without hardcoding terms.

- **Provider**: `TranslationProvider` is mounted at the root in `App.tsx`, providing `useTranslation()` (and alias `useTerminology()`).
- **Hook API**: `const { t, locale, terminology, updateTranslations, refreshTranslations } = useTranslation();`
- **Usage**:
  ```tsx
  // Dynamic lookup with graceful default fallback
  <h1>{t("clients", "Clients")}</h1>
  <Button>New {t("client", "Client")}</Button>
  ```
- **Adoption**:
  - `AppSidebar`: Dynamically translates main and child navigation items (`Clients`, `Providers`, `Bookings`, `Services`, `Locations`) based on the active tenant's terminology preset.
  - `ClientsPage`: Dynamic page titles, action buttons, mobile card triggers, and profile drawers.

---

## Phase 5: Autonomous Booking & Delivery Mode Features

### 1. Public Customer Booking Experience (`/book/:slug`)
- **Delivery Mode Selector**: Dynamic In-Call vs. Out-Call toggle. Auto-locks mode when a service/provider only supports a single delivery mode; defaults to `"in_call"` when both are available.
- **Dynamic Pricing**: Seamlessly updates price display across service selection and confirmation based on `outcall_price` vs. base price.
- **Suburb & Postcode Estimator**: Debounced query to `GET /api/public/travel/suburbs` and estimate calculation via `POST /api/public/travel/estimate` with transit fee breakdown, max-radius compliance badge, and estimation disclaimer.
- **Checkout & Snapshots**: Requires street address on out-call, calls `POST /api/public/travel/quote` for canonical quote, and submits full snapshot attributes (`service_mode`, `service_address`, `client_suburb`, `client_postcode`, `chargeable_travel_distance_km`, `chargeable_travel_fee`).

### 2. Admin Operations UI
- **Services Editor (`/admin/catalog/services`)**: In-Call and Out-Call toggles, `outcall_price`, `outcall_buffer_before`, `outcall_buffer_after` inputs, and mobile indicator badges in service catalog list.
- **Providers Editor (`/admin/catalog/providers`)**: Provider-level In-Call and Out-Call capability switches with automated persistence.
- **Locations Editor (`/admin/catalog/locations` & `/admin/catalog/providers`)**: `is_client_hidden` toggle allowing clinics to designate discreet/private locations where the street address is hidden from public booking cards until appointment confirmation.
- **Admin Bookings & Calendar (`/admin/bookings`, `/admin/calendar`)**: Real-time itinerary conflict indicators (`has_itinerary_conflict`), transit warning banners, and out-call destination badges across list, month grid, week timegrid, and appointment inspection dialogs.

---

## Simplified Module Controls — Settings > Modules (`/admin/settings/modules`)

`Settings > Modules` serves as the authoritative single location where optional features are toggled for each tenant. Disabling a module cleanly removes its controls, filters, accordions, and workflows across the entire application while preserving underlying data.

### 5 Standardized Core Module Controls
1. **Multiple Service Providers (`multiple_providers`)** (alias: `providers`):
   - **Enabled (Multi-Provider)**: Displays provider navigation, staff selectors, calendar provider filters, workday staff selector sidebars, exception assignment dropdowns, service provider assignment accordions, and SMS provider instruction tabs.
   - **Disabled (Solo Mode)**: Exactly one default provider remains active. Multi-provider UI elements disappear across catalog, calendar, workday schedule, exceptions, service editor, and SMS settings. Public booking auto-selects the default provider and skips the provider selection tab.
2. **Multiple Locations (`locations`)**:
   - **Enabled (Multi-Location)**: Full branch management, location filter dropdowns in calendar, location selectors in booking and exception forms.
   - **Disabled (Single Location)**: Exactly one default location remains active. Location filters and selectors are removed from calendar, exceptions, and booking intake forms.
3. **Categories (`categories`)**:
   - **Enabled**: Service grouping with category tabs, category management in navigation, and category assignment accordions.
   - **Disabled**: Flat service list without category chips, category accordions, or category navigation.
4. **Products (`products`)**:
   - **Enabled**: Products catalog, service product assignment, and upsells in checkout.
   - **Disabled**: Completely hidden from navigation, service forms, and booking intake.
5. **Add-ons (`addons`)** (alias: `packages`):
   - **Enabled**: Service add-ons and extra options during service booking.
   - **Disabled**: Hidden from navigation, service forms, and booking intake wizard tabs.

### Relationship Matrix Module (`relationship_matrix`) & Multi-Provider Guard
- **Visual Dependency Mapping**: 6-column interactive matrix mapping connections between providers, locations, services, add-ons, products, and categories.
- **Strict Multi-Provider Requirement**:
  - In solo/single-practitioner mode, the 6-column matrix is overkill. The module is strictly dependent on `multiple_providers`.
  - In **Settings > Modules (`/admin/settings/modules`)**: When `multiple_providers` is OFF, the Relationship Matrix card is locked with an amber warning badge, callout ("Requires Multiple Service Providers to be enabled"), and its switch is disabled and locked OFF.
  - In **Context (`TenantModulesContext`)**: Exposes `relationshipMatrixEnabled = isModuleEnabled('relationship_matrix') && multipleProvidersEnabled`.
  - In **Navigation (`filterNavigationByModules`)**: "Relationships" menu item and its children (Matrix, Bulk Editor, Tree View) declare `moduleKey: "relationship_matrix"`. If either `relationship_matrix` or `multiple_providers` is OFF, the entire section is omitted from the sidebar.
  - In **Backend (`/api/admin/tenant/modules/toggle`)**: Attempting to enable `relationship_matrix` without `multiple_providers` active raises `400 Bad Request`.

### Solo Provider & Primary Location Configuration — Settings > Business Profile (`/admin/settings/business`)
When either the **Multiple Service Providers** or **Multiple Locations** modules are disabled, the system provides dedicated configuration panels directly inside **Settings > Business Profile**:
- **Balanced Side-by-Side Responsive Layout**:
  - Replaced oversized full-width stacked cards with a balanced 2-column grid (`grid-cols-1 lg:grid-cols-2`).
  - Column 1 contains **Business Contact Details** and **Primary Location Details**; Column 2 contains **Solo Service Provider Details**, providing a balanced, compact dashboard appearance without horizontal stretching.
- **Operator Name Field**: Labeled `"Business / Operator / Owner Name"` to reflect solo practitioner and business identity.
- **Solo Service Provider Panel** (active when `!multipleProvidersEnabled`):
  - Compact **Provider Photo / Avatar Dropzone**: In-browser client-side WebP thumbnail optimization (<120KB) with preview, change, and remove controls.
  - Practitioner Name with `"Copy Contact Info"` action (syncs operator name, email, and phone).
  - Direct Email and Phone (providers operate from their assigned location(s) and do not own an address field on their profile).
  - Bio / Professional Description for public appointment cards.
  - Delivery mode switches: **Allow In-Call Studio Bookings** and **Allow Out-Call Mobile Bookings** (with automatic tenant capability alignment).
  - Out-Call travel parameters: Out-Call Radius (km), Base Surcharge ($), Per-KM Fee ($), and Turnaround / Travel Buffer (mins).
  - Directly saved to `PUT /api/admin/providers/{id}`.
- **Primary Location Panel** (active when `!locationsEnabled`):
  - Primary Location / Branch Name and Timezone selector with comprehensive Australian and international IANA options.
  - Compact **Location Studio Photo Dropzone**: WebP thumbnail optimization (<120KB) with preview and remove actions.
  - Structured Physical Address via `AddressAutocomplete` with notice callout and detailed breakdown (Street, Suburb, State, Postcode) with zero corrupting string-split syncs.
  - **Discreet / Private Location Toggle** (`is_client_hidden`): Positioned directly beneath the address field with an explanatory callout.
  - **Live Google Map Preview**: Embedded interactive Google Map dynamically rendered and centered on the verified location address.
  - Directly saved to `PUT /api/admin/locations/{id}`.
- **Save on Change (Debounced Auto-Save & Manual Buttons Removed)**:
  - All fields on the Business Profile page save automatically on change (600ms debounce for text/numbers, immediate execution for image uploads, capability toggles, timezone, private location, and address autocomplete).
  - Visual `AutoSaveStatus` badge indicator (`Saving...` / `✓ Saved` / `Save failed` with retry) in the page header.
  - All manual save buttons ("Save All Changes", "Save Business Details", "Save Provider Details", "Save Location Details") and error-prone "Use Business Address" sync shortcuts have been cleanly removed.
- **Redundant Operating Hours Removed**: Business-level operating hours are removed from business settings to establish provider schedules and workdays as the single source of truth for availability.

### Standardized Address Verification & Autocomplete (`AddressAutocomplete`)
- **Component**: `src/components/ui/address-autocomplete.tsx`
- **Multi-Tier Resolution**: Queries `GET /api/public/travel/addresses` (Mapbox Places API → OpenStreetMap Nominatim → Local AU Postcodes fast-path) with instant debounced typeahead suggestions.
- **Verification Metadata & Badges**:
  - `[✓ Verified via Address Search]`: Visual emerald badge displayed when an address is chosen from standardized lookup.
  - `[Manual Entry / Unverified]`: Amber badge when an address is manually edited or overridden.
- **Location Travel Calculation Notice**: Displays standard explanatory callout beneath location address fields:
  *"This is the location that will be used to calculate outcall travel times and travel requirements."*
- **5-Segment Operational Travel & Buffer Clarification**:
  - **Dynamic Travel Time**: Calculated and reserved dynamically based on real road driving distance to/from the location base address.
  - **Dedicated Buffer Times**: Turnaround cooldown, Pre-Service Prep (parking, building entry, unpacking) and Post-Service Pack-up (sanitation, repacking, departure) are reserved **in addition to travel time**, preventing double-buffering or appointment clashes.
- **Universal Application**:
  - **Business Profile**: Business HQ Physical Address.
  - **Solo Provider Settings**: Clean practitioner details (Name, Email, Phone, Bio, Capabilities, Buffers); provider address field removed as providers operate from assigned Locations.
  - **Primary Location Settings**: Physical address autocomplete with travel origin notice, auto-sync to street, suburb, state, and postcode breakdown.
  - **Multi-Provider Editor (`/admin/catalog/providers`)**: Turnaround buffer, out-call radius, and delivery capabilities; provider address removed as providers operate from assigned Locations.
  - **Location Catalog (`/admin/catalog/locations` & provider location modal)**: Standardized address autocomplete with travel origin notice for all physical branches.

---

## Assistant Studio — Knowledge Curator UI (`/admin/assistant-studio`)

The **Knowledge Curator** tab (`src/pages/admin/assistant-studio/tabs/knowledge-curator-tab.tsx`) provides staff with end-to-end governance and visual inspection of autonomous learning and epistemic graphs across 4 dedicated interfaces:

### 1. Screen A: Autonomous Learning Pipeline Flow (`learning-pipeline-flow.tsx`)
- **6-Stage Interactive Visualizer**: Models the epistemic lifecycle from customer interactions to runtime prompt injection:
  1. *Raw Conversation Turns* (SMS turns, drafts, bootcamp answers)
  2. *Ingested Learning Events* (PII-scrubbed transactional queue)
  3. *Autonomous Curator Decision* (Dynamic operational data rejection, policy guards)
  4. *Authoritative Curated Memory* (PostgreSQL durable fact store)
  5. *Canonical Graph Projection* (Outbox queue to Neo4j/Graphiti)
  6. *Runtime Prompt Retrieval* (Bounded multi-channel context assembly)
- **Live Metrics & Counters**: Displays live queue depths, cache hit ratios, dead letters, and node counts from `GET /api/admin/assistant-studio/curator/pipeline-status`.
- **Interactive Filtering**: Clicking any stage filters the knowledge ledger below to relevant items.

### 2. Screen B: Interactive Epistemic Graph Canvas (`epistemic-graph-canvas.tsx`)
- **Visual Ontological Graph**: Scalable Vector Graphics (SVG) node-link diagram rendering active knowledge relationships:
  - Directed Edge Types: `PREFERS`, `AVOIDS`, `SUPERSEDES`, `APPLIES_WHEN`, `HAS_BOUNDARY`, `SUPPORTED_BY`.
  - Node Types: Central Provider, Category Clusters (policy, scheduling, location, amenities, pricing, general), and discrete Curated Facts.
- **Scope & Partition Badges**: Explicitly renders partition boundaries (`tenant:{id}:shared` vs `tenant:{id}:provider:{id}`) with color-coded nodes.
- **Canvas Controls**: Interactive zoom in/out, fit-to-canvas, reset, and edge type filtering.
- **Node Inspector Trigger**: Clicking any node opens the provenance lifecycle drawer directly.

### 3. Screen C: Knowledge Ledger & Admin Management Table (`knowledge-ledger-table.tsx`)
- **Full Operational CRUD Table**: Paginated, sortable, and searchable index of curated knowledge linked to Graphiti projection state.
- **Add Fact Modal**: Add durable facts with instant client-side and server-side leak detection (`classify_text`), PII scrubbing, and category classification.
- **Edit Supersession Modal**: Enforces immutable knowledge revisioning: editing an active fact marks the prior version as `superseded` and creates a new `CuratedMemory` pointing to `supersedes_id`.
- **Administrative Actions**: Quarantine/Activate toggle, Retract (soft-delete/archive), and manual Reproject trigger (`POST /reproject`).

### 4. Screen D: End-to-End Provenance & Lifecycle Drawer (`provenance-lifecycle-drawer.tsx`)
- **Radix Sheet Drawer**: Deep inspection of memory lineage across 5 audit sections:
  1. *Overview & Scope*: Partition badges, kinds (`durable_fact`, `response_guidance`, `style_example`), status, and timestamps.
  2. *Source Context & Scrubbing Audit*: Original trigger type, conversation turn references, and proof of automated PII sanitization.
  3. *Epistemic Graph Details & Outbox Status*: Ontological classifications, projection ledger status (`pending`, `projected`, `retry`, `dead_letter`), attempt counters, and Graphiti episode UUIDs.
  4. *Redis Cache & Dual-Epoch Invalidation*: Visual representation of cache keys (`fb:tenant:{t}:provider:{p}:knowledge:{epoch}:{query_hash}`) and composite epoch invalidation status.
  5. *Spec 54 Precedence Preview*: Live demonstration showing that Layer 2 Real-Time Calendar/Tool Truth takes precedence over Layer 6 Curated Factual Knowledge in system prompts.

### Zero-Mock Rule Compliance
In strict adherence to **AGENTS.md Rule 3**, no mock data, synthetic timeouts, or fake states exist in the Knowledge Curator UI. Every button, filter, and modal calls authenticated, tenant-scoped FastAPI endpoints (`/api/admin/assistant-studio/curator/*`) and updates real database/cache state.

---

## Development & Build Commands
```bash
# Start frontend development server on port 7070
npm run dev

# Run unit tests via Node test runner
npm test
node --experimental-strip-types --test src/components/navigation-modules.test.ts

# Run production TypeScript type-check and bundle build
npm run build

# Preview production build locally
npm run preview
```
