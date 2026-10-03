# Service Catalog & Capacity Management (`frontend/src/pages/admin/catalog`)

The catalog administration module provides comprehensive management of treatments, services, practitioners, facility branches, treatment packages, add-ons, and physical resources within **FastAPI Bookings**.

---

## 1. Purpose & Scope

The catalog module owns:
- **Services Management** (`services.tsx`): Treatment catalog, duration settings (15m–180m), base prices, deposit requirements, buffer times, and provider eligibility.
- **Locations & Branches** (`locations.tsx`): Physical clinics, rooms, operating addresses, geocoordinates, and client visibility toggles (`is_client_hidden`).
- **Providers & Staff Rostering** (`providers.tsx`): Practitioner profiles, assigned services, weekly shifts, turnaround buffers, and mobile radius capabilities.
- **Packages & Treatment Bundles** (`packages.tsx`): Multi-session treatment packages and phased redemption workflows.
- **Add-Ons & Retail Products** (`add-ons.tsx`, `products.tsx`): Ancillary services, equipment add-ons, and retail product inventories.
- **Scheduling & Capacity Constraints** (`scheduling.tsx`): Cross-provider concurrency limits, break rules, and buffer overrides.

This module deliberately avoids direct SQL manipulation from the browser or bypassing backend validation rules for slot boundaries and delivery modes.

---

## 2. Architecture & Key Files

```
frontend/src/pages/admin/catalog/
├── services.tsx         # Services list, pricing tiers, and duration configuration
├── providers.tsx        # Practitioner profiles, service assignments, and workdays
├── locations.tsx        # Clinic branches and physical room layouts
├── packages.tsx         # Multi-session treatment packages & step sequencing
├── add-ons.tsx          # Treatment add-ons and duration modifiers
├── products.tsx         # Inventory and retail product catalog
├── categories.tsx       # Hierarchical taxonomy for service organization
├── scheduling.tsx       # Cross-provider scheduling rules and buffer overrides
└── README.md            # Living documentation
```

### Key Files:
- [services.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/services.tsx): Full lifecycle CRUD table and drawer for service treatments, durations, and pricing.
- [providers.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/providers.tsx): Practitioner roster, shift schedules, delivery mode support, and location bindings.
- [locations.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/locations.tsx): Clinic locations, room configurations, and street address autocomplete integration.
- [scheduling.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/scheduling.tsx): Global and per-provider capacity limits and buffer rules.

---

## 3. Setup, Configuration & Dependencies

### Runtime Dependencies
- **React 18 & TypeScript**: Core UI component framework with strict typing.
- **Radix UI & Shadcn**: Accessible dialogs, drawers, accordions, and dropdown menus.
- **Axios HTTP Client**: Communicates with backend endpoints mounted at `/api/admin/services`, `/api/admin/providers`, `/api/admin/locations`.
- **AddressAutocomplete**: Reusable address lookup component using verified Australian postcode and geocoding services.

### Environment & Permissions
- Requires administrative authentication token (`Authorization: Bearer <token>`).
- Scoped automatically to the current active tenant via `X-Tenant` header.

---

## 4. Core Workflows & Contracts

### 4.1 Delivery Modes & Dynamic Pricing (In-Call vs. Out-Call)
- **Ergonomic Positioning**: In both the "Add New Service" creation view and the "Service Details" accordion editor, delivery mode toggles (**In-Call** and **Out-Call / Mobile**) are positioned directly underneath the Service Description.
- **Dynamic Conditional Sections**:
  - **In-Call Enabled**: Dynamically expands an In-Call section containing **In-Call Price ($)**, **Buffer Before (mins)**, and **Buffer After (mins)**.
  - **Out-Call Enabled**: Dynamically expands an Out-Call section containing **Out-Call Price ($)**, **Buffer Before (mins)**, and **Buffer After (mins)**.
  - **Dual Mode**: When both delivery modes are toggled on, both distinct pricing and buffer panels render sequentially.
  - **UI Streamlining**: Removed overly technical jargon from inputs and standardized labels (Price, Buffer Before, Buffer After) to ensure they sit on a balanced, uniform grid with matching heights.
- **Validation Guard**: At least one delivery mode must remain active at all times; disabling both is blocked with clear validation feedback.

### 4.2 Travel Pricing & Estimation
- **Provider Travel Settings**: Providers offering out-call services can configure their Travel Pricing Mode:
  - **Standard Base + Per-KM**: Charges a base out-call surcharge plus a per-km travel fee.
  - **Flat Fixed Fee**: Charges a fixed travel fee regardless of distance.
  - **Distance Tiers**: Dynamic distance-based tiers (e.g., Up to 10km: $20, Up to 20km: $40).
  - **Uber Pass-Through**: Client pays the estimated live Uber transit fare based on their address.
- **Checkout Estimation**: The public booking wizard dynamically calculates and displays estimated travel fees, physical distance, and driving transit times based on the client's destination. When "Uber Pass-Through" is selected, the travel estimate prominently features an Uber badge.

### 4.3 Mobile-First Ergonomics
- Replaced desktop-only dialog forms with responsive grids (`grid-cols-1 sm:grid-cols-2`).
- All form inputs, selects, and action buttons feature touch targets $\ge 44$px.
- Integrated `MobileBackButton` (`min-h-[44px] min-w-[44px]`) to provide seamless navigation on mobile devices.

---

## 5. Data Safety & Isolation

- **Tenant Isolation**: Every catalog request is strictly filtered by the authenticated user's `tenant_id`. Practitioners or services from other tenants cannot be inspected or linked.
- **Discreet Address Protection (`is_client_hidden`)**: Clinics with sensitive or private home-studio locations can enable `is_client_hidden`, which masks the full street address on public booking cards until appointment confirmation.
- **Atomic Deletions & Dependency Protection**: Attempting to delete a service or provider that is actively assigned to future bookings is safely blocked with a dependency conflict notice.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Bulk Service Reassignment**: Reassigning all services from a departing practitioner to a new practitioner currently requires updating individual provider profiles.
- **Multi-Currency Display**: While prices are saved as numeric amounts, international currency symbol formatting defaults to tenant locale settings.
- **Complex Room Resource Allocation**: Advanced room/chair scheduling constraints across overlapping providers are coordinated through booking slot availability checks.

---

## 7. Verification & Testing Commands

To verify catalog functionality, bundle compilation, and booking integration:

```powershell
# 1. Run frontend build to verify TypeScript and JSX compilation
npm run build

# 2. Run backend catalog and booking availability test suite
$env:PYTHONPATH='.'; .venv\Scripts\python.exe -m pytest tests/test_clean_numbered_data_and_scenarios.py -v
```
