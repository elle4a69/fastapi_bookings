# Dynamic Wording & Industry Translations Engine (`app/services/localization`)

The **Dynamic Wording & Industry Translations Engine** provides multi-industry adaptability across medical/health, automotive, salons/wellness, and professional services without requiring schema churn, column proliferation, or parallel models.

Following the **SimplyBook.me Dynamic Translation Model**, core operational concepts (`client`, `provider`, `service`, `booking`, `location`) are represented uniformly in database models while terminology is dynamically resolved and mapped per tenant for both public booking portals and administrative dashboards.

---

## 1. Purpose & Scope

The Localization and Translation Engine owns:
- Multi-industry vocabulary adaptability across Allied Health, Automotive, Salons/Wellness, and Professional Services.
- Three-tier cascading terminology resolution: System Defaults -> Industry Preset -> Tenant Custom Overrides.
- Public dynamic terminology resolution for anonymous booking widgets and client portals (`GET /api/public/translations`).
- Authenticated tenant administration endpoints for inspecting and updating tenant wording and selecting presets (`GET / PUT /api/admin/translations`).
- Frontend runtime caching and fallback integration via `TranslationContext` and `useTranslation`.

This module deliberately avoids schema-level table/column renames per tenant, parallel industry-specific database tables, or storing static UI text strings that bypass the fallback cascading hierarchy.

---

## 2. Architecture & Key Files

```
app/services/localization/
├── __init__.py           # Public exports for presets and resolution helpers
├── presets.py            # Pre-packaged industry presets and layer merging logic
└── README.md             # This living documentation

Related Subsystems:
├── app/models/tenant_translation.py  # SQLAlchemy ORM model for tenant_translations
├── app/schemas/translations.py      # Pydantic request/response schemas (also app/schemas/translation.py)
├── app/api/routers/translations.py  # Public and Admin HTTP endpoints
└── frontend/src/context/TranslationContext.tsx # React Context provider & useTranslation hook
```

### Key Files:
- [presets.py](file:///f:/Projects/fastapi_bookings/app/services/localization/presets.py): Contains canonical definitions of `DEFAULT_TERMINOLOGY`, `INDUSTRY_PRESETS` (`allied_health`, `automotive`, `wellness_salon`, `professional_services`), and the `resolve_terminology()` layered merge engine.
- [app/models/tenant_translation.py](file:///f:/Projects/fastapi_bookings/app/models/tenant_translation.py): Defines the `TenantTranslation` SQLAlchemy model mapped to the `tenant_translations` database table.
- [app/schemas/translations.py](file:///f:/Projects/fastapi_bookings/app/schemas/translations.py): Pydantic contracts for updating and retrieving translation records and preset options.
- [app/api/routers/translations.py](file:///f:/Projects/fastapi_bookings/app/api/routers/translations.py): FastAPI router implementing public resolution and authenticated admin CRUD endpoints.
- [frontend/src/context/TranslationContext.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/context/TranslationContext.tsx): React hook (`useTranslation`) providing client-side translation interpolation and caching.

---

## 3. Setup, Configuration & Dependencies

### Database Table & Migration
- Backed by the `tenant_translations` table (Alembic revision `e5g7i9k1m3o5_tenant_translations.py`):
  - `id`: Integer primary key.
  - `tenant_id`: Foreign key referencing `tenants.id` (1-to-1 unique mapping, `CASCADE` delete).
  - `locale`: ISO language/locale string (default: `"en"`).
  - `terminology`: JSON dictionary containing tenant custom terminology overrides.
  - `created_at` / `updated_at`: Timezone-aware timestamps.

### Environment & System Dependencies
- No external 3rd-party translation API (e.g. Google Cloud Translation) is required; resolution is handled entirely within Python memory and SQLite/PostgreSQL JSON structures.
- Integrates directly with SQLAlchemy 2.0 and Pydantic v2.

---

## 4. Core Workflows & Contracts

### 4.1 Industry Presets Catalog
Defined in [presets.py](file:///f:/Projects/fastapi_bookings/app/services/localization/presets.py):

| Entity / Key | Default (Fallback) | `allied_health` | `automotive` | `wellness_salon` | `professional_services` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `client` | Client | Patient | Customer | Client | Client |
| `clients` | Clients | Patients | Customers | Clients | Clients |
| `provider` | Provider | Practitioner | Technician | Stylist | Consultant |
| `providers` | Providers | Practitioners | Technicians | Stylists | Consultants |
| `booking` | Booking | Consultation | Service | Appointment | Appointment |
| `bookings` | Bookings | Consultations | Services | Appointments | Appointments |
| `service` | Service | Treatment | Service/Repair | Treatment | Session |
| `services` | Services | Treatments | Services/Repairs | Treatments | Sessions |
| `location` | Location | Clinic | Workshop/Bay | Salon/Studio | Office |
| `locations` | Locations | Clinics | Workshops/Bays | Salons/Studios | Offices |

### 4.2 Cascading Terminology Resolution
Resolution follows a strict 3-tier waterfall:
```text
System Defaults (DEFAULT_TERMINOLOGY)
       │
       ▼
Selected Industry Preset (e.g. allied_health)
       │
       ▼
Tenant Custom Overrides (tenant_translations.terminology)
```

### 4.3 REST API Endpoints
- **`GET /api/public/translations`**:
  - Scoped via host subdomain or `X-Tenant` header (`get_public_tenant`).
  - Returns `{ "locale": "...", "terminology": { ... } }` with all fallbacks resolved.
  - Zero authentication required; used by public booking portals and mobile intake.
- **`GET /api/admin/translations`**:
  - Requires tenant admin authentication (`get_current_tenant`, `get_current_admin`).
  - Returns current tenant translation record, catalog of all available industry presets, and resolved terminology dictionary.
- **`PUT /api/admin/translations`**:
  - Requires tenant admin authentication.
  - Accepts `locale`, `preset`, and `terminology` override dictionary.
  - Validates presets and enforces strict tenant isolation: changes only affect the authenticated tenant.

---

## 5. Data Safety & Isolation

- **Tenant Isolation**: `tenant_translations` records are strictly bound to `tenant_id` with a 1-to-1 unique constraint. Admin endpoints access records exclusively through `current_tenant.id` resolved by authentication tokens.
- **Tenant Deletion Cascades**: Foreign key `tenant_id` specifies `ON DELETE CASCADE`, guaranteeing zero orphaned translation records if a tenant account is removed.
- **Sanitization & Validation**: All terminology keys are validated against an allowlist of supported operational concepts to prevent arbitrary JSON bloat or injection.
- **Public Fallback Safety**: Unauthenticated public requests never leak sensitive tenant configuration or internal database keys; only the resolved string dictionary is returned.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Pluralization Grammar Rules**: The engine currently stores explicit singular and plural forms (`client` vs `clients`). Complex irregular pluralization across non-English locales requires explicit key definition.
- **Multi-lingual Locale Switching**: Dynamic switching across multiple languages simultaneously for a single tenant (e.g., English and Spanish bilingual support) is currently bounded to single-locale tenant records (`locale="en"`).
- **Future Work**: Integration with the SMS and Chatwoot assistants to dynamically rewrite agent prompts using tenant-selected terminology keys.

---

## 7. Verification & Testing Commands

To run the complete test suite for localization and tenant translations:

```powershell
python -m pytest tests/test_tenant_translations.py -v
```
