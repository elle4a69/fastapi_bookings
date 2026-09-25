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

## Development & Build Commands
```bash
# Start frontend development server on port 7070
npm run dev

# Run production TypeScript type-check and bundle build
npm run build

# Preview production build locally
npm run preview
```
