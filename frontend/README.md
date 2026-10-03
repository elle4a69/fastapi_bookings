# FastAPI Bookings — Frontend Application & PWA

The `frontend/` directory contains the modern Single Page Application (SPA) and Progressive Web App (PWA) for **FastAPI Bookings** built with React 18, TypeScript, Vite, Tailwind CSS, and Radix UI / Shadcn primitives.

---

## 1. Purpose & Scope

The frontend provides the complete client and administrative interface across multiple operational surfaces:
1. **Admin Workspace** (`/admin`, `/admin/dashboard`, `/admin/calendar`, `/admin/bookings`, etc.): Comprehensive staff and management control center.
2. **Practitioner Portal** (`/admin/my-schedule`, `/admin/my-jobs`, `/admin/my-profile`): Role-scoped self-service for individual providers.
3. **Client Self-Service Portal** (`/portal`): Passwordless appointment reschedule, cancellation, and dispute lodging.
4. **Public Single-Page Website** (`/site`): Multi-theme tenant website with embedded booking and chat widget.
5. **Umbrella Directory & Geo-Radius Marketplace** (`/directory`): Search and triage nearby clinics with geospatial discovery.
6. **Messaging Operations Workspace** (`/admin/sms-assistant`): Tenant-scoped SMS inbox, draft moderation, arrivals chime, synthetic simulator, and diagnostics.
7. **Assistant Studio** (`/admin/assistant-studio`): Unified prompt lab, model orchestration, and knowledge curation governance.

This module deliberately avoids direct SQL or database mutations, mock network fallbacks in production paths (Rule 3), or treating client-side browser state as the authority for availability or bookings.

---

## 2. Architecture & Key Files

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
│   │   ├── admin/               # Admin dashboard, calendar, catalog, SMS, assistant studio
│   │   ├── portal/              # Client self-service portal
│   │   └── public/              # Public booking flow and directory
│   ├── App.tsx                  # Main router and lazy route configurations
│   ├── main.tsx                 # React entrypoint & PWA service worker registration
│   └── index.css                # Tailwind base styles and theme tokens
├── vite.config.ts               # Vite build config with vite-plugin-pwa
└── package.json                 # Dependencies and build scripts
```

### Key Files:
- [src/App.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/App.tsx): Root application routing tree, providers setup (`ThemeProvider`, `TranslationProvider`, `TenantModulesContext`, `AuthContext`), and lazy-loaded page routes.
- [src/lib/api.ts](file:///f:/Projects/fastapi_bookings/frontend/src/lib/api.ts): Axios API client configured with request interceptors for JWT injection, multi-tenant headers (`X-Tenant`), and global error handling.
- [src/context/AuthContext.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/context/AuthContext.tsx): Manages authentication tokens, tenant administrative profiles, and permission roles.
- [src/context/TranslationContext.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/context/TranslationContext.tsx): Dynamic industry terminology resolution hook (`useTranslation` / `useTerminology`).
- [src/context/TenantModulesContext.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/context/TenantModulesContext.tsx): Single source of truth for modular tenant feature switches.
- [src/components/ui/address-autocomplete.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/components/ui/address-autocomplete.tsx): Standardized typeahead address resolution with geocoding badges.

---

## 3. Setup, Configuration & Dependencies

### Prerequisites & Installation
- **Node.js**: Version 18+ LTS or 20+ LTS
- **Package Manager**: `npm` (v9+) or `pnpm`

```bash
cd frontend
npm install
```

### Environment Configuration
The frontend uses Vite environment variables defined in `.env` or `.env.local`:
```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_ANALYTICS=false
VITE_MAPBOX_TOKEN=pk.eyJ1I...
```

### Build Tooling & Core Libraries
- **Vite 5**: Blazing-fast HMR and ESM bundling.
- **React 18 & React Router 6**: Component architecture and declarative routing.
- **Tailwind CSS & PostCSS**: Utility-first CSS styling with custom theme CSS variables.
- **Lucide React & Radix UI**: Accessible UI component primitives and iconography.
- **Axios**: HTTP communication layer with backend FastAPI services.

---

## 4. Core Workflows & Contracts

### 4.1 Mobile-First & PWA Standards
- **Standalone PWA**: Configured with `display: 'standalone'` in `manifest.webmanifest`. Includes automatic update service worker (`sw.js`).
- **44x44px Touch Targets**: All buttons, inputs, switches, and navigation triggers adhere to the 44px minimum tap height in standard touch views.
- **Traditional Hamburger Menu**: The mobile header explicitly renders a visible, touch-safe `Menu` icon with direct sidebar toggle.
- **Column Visibility Picker**: `ResponsiveDataTable` lets users customize displayed columns on small screens to eliminate horizontal scrolling.
- **Compact Density Mode (`density="compact"`)**:
  - `MobilePageShell`: Supports `density="compact"` to reduce vertical margins, header gap, and title scale.
  - `ResponsiveDataTable`: Reduces padding and header height, increasing above-the-fold record density by ~50%.
- **Calendar Viewport Optimization**:
  - `CalendarPage` consolidates 3 stacked header tiers (~174px) into 2 clean, high-density bars (~76px total), reclaiming 80px–100px of vertical space.

### 4.2 Multi-Palette Luxury Themes & Glassmorphism
- **Midnight Executive (`midnight`)**: Deep navy-slate background (`oklch(0.12 0.025 258)`), cold slate cards, electric blue accents (`#3b82f6`).
- **Emerald Luxe (`emerald`)**: Obsidian black base with dark forest undertones, cold obsidian-slate cards, vibrant jewel emerald accents (`oklch(0.66 0.20 155)`).
- **BookMe Crimson (`crimson`)**: Velvet crimson and magenta styling (`oklch(0.52 0.24 350)` light / `oklch(0.62 0.24 350)` dark).
- **Glassmorphic Utilities**: `.glass-panel` (16px backdrop blur, subtle borders), `.glass-card` (12px blur), `.glass-surface` (translucent background).

### 4.3 Modular Tenant Feature Controls (`/admin/settings/modules`)
Authority for optional tenant capabilities:
1. `multiple_providers`: Toggle between Solo Practitioner mode and Multi-Provider staff operations.
2. `locations`: Toggle between Single Studio and Multi-Location branch management.
3. `categories`: Hierarchical service categories vs. flat catalog.
4. `products`: Retail products and checkout upsells.
5. `addons`: Additional service options and packages.
6. `relationship_matrix`: 6-column interactive matrix strictly requiring `multiple_providers` to be active.

### 4.4 Assistant Studio Governance (`/admin/assistant-studio`)
The Knowledge Curator UI (`knowledge-curator-tab.tsx`) provides 4 dedicated interfaces for AI oversight:
- **Screen A (Learning Pipeline Flow)**: 6-stage interactive visualizer tracking events from raw conversation turns to runtime prompts.
- **Screen B (Epistemic Graph Canvas)**: Scalable Vector Graphics (SVG) ontological node-link diagram rendering active knowledge relationships (`PREFERS`, `AVOIDS`, `SUPERSEDES`).
- **Screen C (Knowledge Ledger)**: Paginated administrative CRUD table enforcing immutable fact supersession.
- **Screen D (Provenance Lifecycle Drawer)**: Radix sheet drawer for deep inspection of memory lineage, PII sanitization audits, and Graphiti projection states.

---

## 5. Data Safety & Isolation

- **Zero-Mock Rule Compliance (Rule 3)**: In strict adherence to AGENTS.md Rule 3, no fake states, synthetic delays, or mock data exist in production UI code. Every action connects directly to real backend API endpoints.
- **Tenant Scope Enforcement**: All API requests transmit the authenticated tenant context via JWT bearer tokens and `X-Tenant` headers. Route guards prevent cross-tenant access.
- **Client Storage Sanitization**: Auth tokens stored in `localStorage` or session cookies are cleared on logout, 401 unauthorized responses, or tenant switching.
- **PII Leakage Prevention**: Customer input fields (phone numbers, addresses) are validated client-side and sanitized before rendering in public views.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Mobile Safari Safe Area Insets**: iOS notch areas require `env(safe-area-inset-top)` and `env(safe-area-inset-bottom)` tuning on deep bottom sheet dialogs.
- **High Latency Graph Rendering**: On large knowledge graphs (>500 nodes), SVG rendering in the epistemic canvas should be transitioned to HTML5 Canvas or WebGL.
- **Bundle Size Optimization**: Heavy third-party dependencies (Mapbox GL, Lucide React icons) benefit from ongoing route-level code splitting and dynamic imports.

---

## 7. Verification & Testing Commands

To verify and test the frontend application:

```bash
# 1. Run Node.js unit tests for frontend navigation modules
npm test

# 2. Run TypeScript strict type-check without emitting output
npx tsc --noEmit

# 3. Run production build bundle verification
npm run build

# 4. Preview local production build
npm run preview
```
