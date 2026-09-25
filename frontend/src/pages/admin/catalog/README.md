# Service Catalog & Capacity Management

## Purpose & Scope
The `frontend/src/pages/admin/catalog/` directory houses the service catalog, practitioner rosters, facility locations, and inventory components in **FastAPI Bookings**.

Key entities:
- **Services** (`services.tsx`): Treatment catalog, durations (15m–180m), base prices, buffer times, and provider eligibility.
- **Locations** (`locations.tsx`): Physical clinics, rooms, operating addresses, and geocoordinates.
- **Providers** (`providers.tsx`): Practitioners, assigned services, weekly shifts, and credentials.
- **Packages** (`packages.tsx`): Multi-service treatment bundles and phased redemption steps.
- **Add-Ons & Products** (`add-ons.tsx`, `products.tsx`): Ancillary services, equipment, and retail items.
- **Scheduling Rules** (`scheduling.tsx`): Multi-provider availability constraints and capacity limits.

---

## Architecture & Key Files

```
frontend/src/pages/admin/catalog/
├── services.tsx         # Services list, pricing tiers, and duration configuration
├── providers.tsx        # Practitioner profiles, service assignments, and workdays
├── locations.tsx        # Clinic branches and physical room layouts
├── packages.tsx         # Multi-session treatment packages & step sequencing
├── add-ons.tsx          # Treatment add-ons and duration modifiers
├── products.tsx         # Inventory and retail product catalog
├── categories.tsx       # Hierarchical taxonomy for service organization
└── scheduling.tsx       # Cross-provider scheduling rules and buffer overrides
```

---

## Mobile-First & Ergonomics
- Replaced desktop-only dialog forms with responsive grids (`grid-cols-1 sm:grid-cols-2`).
- All form inputs, selects, and action buttons feature touch targets $\ge 44$px.
- Integrated `MobileBackButton` (`min-h-[44px] min-w-[44px]`) to provide seamless navigation on mobile devices.

---

## Verification & Testing Commands
```bash
# Verify frontend bundle builds cleanly
npm run build

# Run catalog and booking availability tests
$env:PYTHONPATH='.'; .venv\Scripts\python.exe -m pytest tests/test_clean_numbered_data_and_scenarios.py -v
```
