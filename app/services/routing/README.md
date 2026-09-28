# Routing & Geospatial Services (`app/services/routing`)

## 1. Purpose & Scope

The **Routing & Geospatial Services** module provides decoupled dual-route calculations and address resolution for FastAPI Bookings:
- **Commercial Travel Calculation (Chargeable Travel)**: Determines what the client pays for an out-call booking based on tenant policy (`ALWAYS_FROM_BASE` vs. `ACTUAL_ORIGIN`), provider base out-call surcharge, per-kilometer fee, and out-call radius bounds.
- **Physical Transit Calculation (Operational Travel)**: Calculates physical driving duration (minutes) and distance (km) between itinerary waypoints to schedule provider arrival times and calendar turnaround buffers.
- **Geocoding & Centroid Estimation**: Resolves exact addresses or suburb/postcode centroids into geographic coordinates using a high-performance local SQLite dataset of Australian postcodes (<1ms lookup), with external Mapbox API and deterministic offline fallback protection.
- **Locality Autocomplete**: Provides instant typeahead locality/postcode matching for client booking forms without incurring third-party API latency or costs.
- **Canonical Travel Ownership**: Guarantees that the destination appointment owns its inbound travel leg; creating or shifting subsequent bookings does not alter preceding booking charges or allocated inbound travel buffers.

### Deliberate Non-Goals
- Calendar slot-allocation mutations and dynamic itinerary event hooks belong to subsequent phases (Phase 3 & 4) and are strictly excluded from this service layer.
- Direct database writes to booking records are not performed within this service; it produces pure, immutable calculation DTOs (`ChargeableTravelQuote` and `OperationalTravelSegment`).

---

## 2. Architecture & Key Files

```
app/
├── schemas/
│   └── travel.py                   # Pydantic DTOs (ChargeableTravelQuote, OperationalTravelSegment, SuburbAutocompleteItem, Requests)
├── services/
│   └── routing/
│       ├── __init__.py             # Public exports for routing module
│       ├── data/
│       │   └── au_postcodes.db     # Indexed local SQLite database of 15,500+ Australian suburbs & postcodes
│       ├── distance_calculator.py  # Low-level OSRM client & Haversine distance calculator
│       ├── distance.py             # Re-export compatibility shim
│       ├── geocoding.py            # GeocodingService with local AU fast-path, autocomplete, & API fallback
│       ├── travel_service.py       # TravelCalculationService (Dual-Route engine & domain methods)
│       └── README.md               # Living module documentation
└── api/
    └── routers/
        └── travel.py               # REST API endpoints for quotes, estimates, transit, and autocomplete
```

### Primary Components:
- **`TravelCalculationService`** (`travel_service.py`):
  - `calculate_chargeable_travel(tenant, provider, client_destination, is_estimate, previous_location)`: Evaluates tenant policy, resolves base or actual origin, computes chargeable distance and fee, validates radius.
  - `calculate_operational_travel(origin_waypoint, destination_waypoint)`: Evaluates physical driving transit (minutes + km) and identifies the method used (`osrm`, `haversine`, `direct`).
  - `estimate_suburb_travel(tenant, provider, suburb, postcode)`: Computes an estimated quote using suburb/postcode centroid coordinates with `is_estimate=True` and client-facing disclaimer.
  - `verify_canonical_travel_ownership(destination_address, quote)`: Verifies destination ownership of inbound leg.
- **`GeocodingService` & Local Helpers** (`geocoding.py`):
  - `lookup_au_postcode(suburb, postcode)`: Fast-path local indexed lookup against `data/au_postcodes.db` (<1ms execution).
  - `search_au_suburbs(query, limit)`: Instant prefix search for suburb names or postcode numbers.
  - `resolve_coordinates(location_query)`: Multi-tier resolver (literals -> local db -> centroids -> Mapbox -> deterministic fallback).
  - `estimate_suburb_centroid(suburb, postcode)`: Fast centroid lookup using the local database.
- **`DistanceCalculator`** (`distance_calculator.py`):
  - Known-good baseline for OSRM driving calculations and Haversine formula with road winding (1.25x) and average speed (50 km/h).

---

## 3. Setup, Configuration & Dependencies

### Environment Variables & Settings
- `OSRM_BASE_URL`: Base URL for the OSRM routing engine (default: `https://router.project-osrm.org`).
- `MAPBOX_ACCESS_TOKEN`: Mapbox access token for forward geocoding fallback (optional; falls back to built-in local database and offline deterministic resolution if empty or unreachable).

### Local Dataset & Database Dependencies
- `app/services/routing/data/au_postcodes.db`: Local indexed SQLite database derived from the community-maintained Australian postcodes dataset (`schappim/australian-postcodes`), indexing all Australian postcodes, suburbs, states, and coordinates with zero runtime network requirements.
- `tenants`:
  - `travel_charge_origin`: String enum (`ALWAYS_FROM_BASE`, `ACTUAL_ORIGIN`).
  - `address`, `latitude`, `longitude`: Default base location fallback.
- `providers`:
  - `allow_out_call`: Boolean capability flag.
  - `in_call_address`: Primary base address for mobile providers.
  - `out_call_radius_km`: Maximum serviceable radius (default: 25.0 km).
  - `base_outcall_surcharge`: Flat fee component (Numeric).
  - `per_km_fee`: Distance rate per km (Numeric).
  - `turnaround_buffer_mins`: Buffer minutes between appointments (default: 15 mins).

---

## 4. Core Workflows & Contracts

### Inbound Leg Calculation Flow
```
Client Request (Address or Suburb/Postcode)
               │
               ▼
   [TravelCalculationService]
               │
       ┌───────┴───────────────────────┐
       ▼                               ▼
Commercial Chargeable           Operational Transit
- Check tenant policy:          - Resolve physical coords:
  ALWAYS_FROM_BASE vs ACTUAL      origin & destination
- Select origin:                - Call OSRM / Haversine
  Base address vs Previous loc  - Return duration (mins)
- Validate provider radius        and physical distance (km)
- Compute fee: Base + km_rate   - Feed availability buffers
- Return ChargeableTravelQuote  - Return OperationalTravelSegment
```

### API Contracts
- `GET /api/public/travel/suburbs?q=...&limit=10`:
  - Output: List of `SuburbAutocompleteItem` (`suburb`, `postcode`, `state`, `latitude`, `longitude`) matching prefix.
- `POST /api/public/travel/estimate`:
  - Input: `{"provider_id": 1, "suburb": "Bondi", "postcode": "2026"}`
  - Output: `ChargeableTravelQuote` with `is_estimate: true`, `within_radius: true`, `distance_km`, `travel_fee`, `base_surcharge`, `distance_fee`, and `disclaimer`.
- `POST /api/public/travel/quote`:
  - Input: `{"provider_id": 1, "service_address": "123 Ocean St, Bondi", "previous_booking_address": null}`
  - Output: `ChargeableTravelQuote` with `is_estimate: false`, exact calculation details.
- `POST /api/public/travel/transit`:
  - Input: `{"origin": "Sydney CBD", "destination": "Bondi Beach"}`
  - Output: `OperationalTravelSegment` with `duration_minutes`, `distance_km`, and `method`.

---

## 5. Data Safety & Isolation

- **Tenant Scoping**: All public and admin endpoints enforce tenant isolation. Provider lookups verify `provider.tenant_id == active_tenant.id`.
- **Offline / Guarded Execution**: Outbound network requests are guarded. The primary fast-path operates 100% locally from `au_postcodes.db` without network calls. In automated test environments (`PYTEST_CURRENT_TEST`), mock transports ensure tests never open unpermitted sockets or hang on external API latency.
- **Fail-Closed Capability**: If a provider or tenant has `allow_out_call == False`, travel quotes return `within_radius: false` and `travel_fee: 0.0` with explicit rejection reasons, preventing accidental out-call scheduling.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Edge Case - Island / Water Separations**: Haversine fallback calculates great-circle distance with a 1.25x road-winding factor, which may underestimate travel across bodies of water without bridges when OSRM is offline.
- **Phase 3 Integration**: The operational travel duration will be integrated into the availability engine (`scheduling_service.py`) to dynamically insert travel buffers before out-call slots.
- **Phase 4 Booking Flow**: The checkout intake flow will persist `chargeable_travel_distance_km` and `chargeable_travel_fee` on the `Booking` record.

---

## 7. Verification & Testing Commands

Run the Phase 2 test suite and regression tests:

```bash
# Run Phase 2 Dual-Route Travel tests (including local AU postcodes fast-path & autocomplete)
.venv\Scripts\python -m pytest tests/test_travel_service_phase2.py -v

# Run full routing and capability regression suite
.venv\Scripts\python -m pytest tests/test_distance_calculator.py tests/test_domain_contracts_phase1.py tests/test_travel_service_phase2.py -v
```
