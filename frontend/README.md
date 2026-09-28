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
│   ├── context/                 # AuthContext, ClientPortalContext, TenantModulesContext
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

### Solo Provider & Primary Location Configuration — Settings > Business Profile (`/admin/settings/business`)
When either the **Multiple Service Providers** or **Multiple Locations** modules are disabled, the system provides dedicated configuration panels directly inside **Settings > Business Profile**:
- **Operator Name Field**: Labeled `"Business / Operator / Owner Name"` to reflect solo practitioner and business identity.
- **Solo Service Provider Panel** (active when `!multipleProvidersEnabled`):
  - Practitioner Name with instant `"Sync with Operator Name"` action.
  - Direct Email, Phone, and In-Call Studio physical address (with `"Use Business Address"` shortcut).
  - Bio / Professional Description for public appointment cards.
  - Delivery mode switches: **Allow In-Call Studio Bookings** and **Allow Out-Call Mobile Bookings**.
  - Out-Call travel parameters: Out-Call Radius (km), Base Surcharge ($), Per-KM Fee ($), and Turnaround / Travel Buffer (mins).
  - Directly saved to `PUT /api/admin/providers/{id}`.
- **Primary Location Panel** (active when `!locationsEnabled`):
  - Primary Location / Branch Name.
  - Structured Physical Address breakdown: Street Address, City / Suburb, State / Province, and Postal Code (with `"Use Business Address"` shortcut).
  - Timezone selector with comprehensive Australian and international IANA options.
  - **Discreet / Private Location Toggle** (`is_client_hidden`): Hides full street address from the public booking directory until appointment confirmation.
  - Directly saved to `PUT /api/admin/locations/{id}`.
- **Unified & Granular Persistence**: Changes can be saved individually via section buttons or in one atomic batch via the primary `"Save All Changes"` action.
- **Redundant Operating Hours Removed**: Business-level operating hours are removed from business settings to establish provider schedules and workdays as the single source of truth for availability.

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
