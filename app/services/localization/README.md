# Dynamic Wording & Industry Translations Engine (`app/services/localization`)

## 1. Purpose & Architectural Mandate

The **Dynamic Wording & Industry Translations Engine** provides multi-industry adaptability across medical/health, automotive, salons/wellness, and professional services without requiring schema churn, column proliferation, or parallel models.

Following the **SimplyBook.me Dynamic Translation Model**, core operational concepts (`client`, `provider`, `service`, `booking`, `location`) are represented uniformly in database models while terminology is dynamically resolved and mapped per tenant for both public booking portals and administrative dashboards.

---

## 2. Architecture & Key Files

```
app/services/localization/
├── __init__.py           # Public exports for presets and resolution helpers
├── presets.py            # Pre-packaged industry presets and layer merging logic
└── README.md             # This living documentation

Related Subsystems:
├── app/models/tenant_translation.py  # SQLAlchemy ORM model for tenant_translations
├── app/schemas/translation.py       # Pydantic request/response schemas
├── app/api/routers/translations.py  # Public and Admin HTTP endpoints
└── frontend/src/context/TranslationContext.tsx # React Context provider & useTranslation hook
```

---

## 3. Pre-Packaged Industry Presets

The engine comes with four canonical presets defined in [app/services/localization/presets.py](file:///f:/Projects/fastapi_bookings/app/services/localization/presets.py):

| Entity / Key | Default (Fallback) | `allied_health` | `automotive` | `wellness_salon` | `professional_services` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `client` | Client | Patient | Customer | Client | Client |
| `clients` | Clients | Patients | Customers | Clients | Clients |
| `provider` | Provider | Practitioner | Technician | Stylist | Consultant |
| `providers` | Providers | Practitioners | Technicians | Stylists | Consultants |
| `booking` | Booking | Appointment | Booking | Appointment | Session |
| `bookings` | Bookings | Appointments | Bookings | Appointments | Sessions |
| `service` | Service | Consultation | Service/Repair | Treatment | Advisory |
| `services` | Services | Consultations | Services | Treatments | Advisories |
| `location` | Location | Clinic | Workshop | Salon | Office |
| `locations` | Locations | Clinics | Workshops | Salons | Offices |

---

## 4. Resolution Layering Precedence

When retrieving terminology for any tenant (public or admin), terms are resolved via three strict cascading layers in `resolve_terminology`:

$$\text{System Defaults} \longrightarrow \text{Selected Industry Preset} \longrightarrow \text{Tenant Custom Overrides}$$

1. **System Defaults (`DEFAULT_TERMINOLOGY`)**: Base fallbacks ensuring no missing labels.
2. **Industry Preset**: Applied if specified by the tenant configuration.
3. **Custom Overrides**: Direct per-key adjustments stored in `tenant_translations.terminology`.

---

## 5. Database Schema & Migration

The engine persists tenant customization in the `tenant_translations` table (migration `e5g7i9k1m3o5_tenant_translations.py`):

* `id`: Integer primary key.
* `tenant_id`: Foreign key referencing `tenants.id` (1-to-1 unique mapping, `CASCADE` delete).
* `locale`: ISO language/locale string (default: `"en"`).
* `terminology`: JSON dictionary containing tenant terminology overrides.
* `created_at` / `updated_at`: Timezone-aware timestamps.

---

## 6. REST API Endpoints

Mounted in [app/api/routers/translations.py](file:///f:/Projects/fastapi_bookings/app/api/routers/translations.py):

* **`GET /api/public/translations`**:
  - Scoped via host subdomain or `X-Tenant` header (`get_public_tenant`).
  - Returns `{ "locale": "...", "terminology": { ... } }` with all fallbacks resolved.
  - Zero authentication required; used by public booking portals and mobile intake.

* **`GET /api/admin/translations`**:
  - Requires tenant admin authentication (`get_current_tenant`, `get_current_admin`).
  - Returns current tenant translation record, catalog of all available industry presets, and resolved terminology dictionary.

* **`PUT /api/admin/translations`**:
  - Requires tenant admin authentication.
  - Accepts `locale`, `preset`, and `terminology` override dictionary.
  - Validates presets and enforces strict tenant isolation: changes only affect the authenticated tenant.

---

## 7. Frontend Integration

Provided by `TranslationProvider` in [frontend/src/context/TranslationContext.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/context/TranslationContext.tsx):

```tsx
import { useTranslation } from "@/context/TranslationContext";

function MyComponent() {
  const { t } = useTranslation();
  return (
    <div>
      <h1>{t("clients", "Clients")}</h1>
      <button>New {t("client", "Client")}</button>
    </div>
  );
}
```

The hook automatically pulls the active tenant wording from `/api/public/translations` and falls back gracefully to `DEFAULT_TERMINOLOGY` while offline or loading.

---

## 8. Verification & Test Suite

Comprehensive tests in [tests/test_tenant_translations.py](file:///f:/Projects/fastapi_bookings/tests/test_tenant_translations.py) verify:
1. Public endpoint defaults and custom wording.
2. Admin endpoint retrieval and preset catalog completeness.
3. Preset application (`allied_health`, `automotive`, `wellness_salon`, `professional_services`).
4. Custom override priority over preset defaults.
5. Invalid preset validation (HTTP 400).
6. Strict cross-tenant isolation (Tenant B cannot read or modify Tenant A translations).
7. Cascade deletion upon tenant removal.
