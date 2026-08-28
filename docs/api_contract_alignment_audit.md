# Frontend-to-Backend API Contract Alignment Audit

**Audit Date**: 2026-08-28  
**Branch**: `telemetry/observability-baseline`  
**OpenAPI Total Paths**: 209 paths / 305 operations  
**Frontend Total Callers Scanned**: 242 `apiClient` callers across 34 TypeScript/React files  
**Baseline Match Rate Before Repair**: 216 / 242 (89.3%)  
**Match Rate After Category A Repair**: 230 / 242 (95.0%) (remaining 12 are Category B/C or parameterized dynamic dispatch)

---

## 1. Classification Methodology

Every identified mismatch between frontend caller paths and backend FastAPI OpenAPI routes is classified strictly into one of three tiers:

- **Category A (Safe Path-Only Correction)**: The route exists canonically on the backend under a different path prefix with identical HTTP method, matching payload/parameter requirements, and compatible response structures. Safe for direct frontend path alignment.
- **Category B (Schema / Payload / Domain Ambiguity)**: A route exists or is attempted, but there is a payload structure mismatch, response model discrepancy, missing query parameters, domain model misalignment, or commented-out stubbing. Left untouched in code to prevent silent runtime errors; decisions documented for review.
- **Category C (External / Financial / Side-Effecting Operation)**: An operation involving financial transactions (refunds, payments), cancellations, SMS dispatch, or third-party AI mutations where backend logic or safety guarantees do not exist. Left untouched in code under mandatory operating rules.

---

## 2. Complete Inventory of Mismatches

| # | Frontend File & Line | Method & Called Path | Canonical Backend Route | Class | Corrected? | Evidence & Caveats |
|---|---|---|---|:---:|:---:|---|
| 1 | `frontend/src/pages/admin/finance/invoices.tsx:71` | `GET /api/admin/finance/invoices` | `GET /api/admin/invoices` | **A** | **Yes** | Declared in `app/api/routers/checkout.py:311` (`list_admin_invoices`). Returns `InvoiceListResponse` (`{ ok: true, data: [...], meta: {...} }`). |
| 2 | `frontend/src/pages/admin/finance/payments.tsx:35` | `GET /api/admin/finance/payments` | `GET /api/admin/payments` | **A** | **Yes** | Declared in `app/api/routers/payments.py:22` (`list_payments`). Returns `PaymentListResponse` (`{ ok: true, data: [...], meta: {...} }`). |
| 3 | `frontend/src/pages/admin/finance/payments.tsx:51` | `POST /api/admin/finance/payments/${paymentId}/refund` | *None* | **C** | **No** | **Financial side effect**: No refund route exists in `payments.py` or Stripe router. Requires formal refund workflow with idempotency and audit logs. |
| 4 | `frontend/src/pages/admin/finance/processors.tsx:43` | `GET /api/admin/finance/processors` | `GET /api/admin/payment-processor/configs` | **B** | **No** | **Schema Mismatch**: Backend returns `list[PaymentProcessorConfigOut]`, while frontend expects `{ currency: string, processors: { stripe, paypal, offline } }`. |
| 5 | `frontend/src/pages/admin/finance/processors.tsx:62` | `PUT /api/admin/finance/processors` | `PUT /api/admin/payment-processor/configs/{id}` | **B** | **No** | **Schema / Method Mismatch**: Backend expects ID in URL and single processor object, frontend sends composite nested dictionary to root path. |
| 6 | `frontend/src/pages/admin/finance/promotions.tsx:47` | `GET /api/admin/finance/promotions` | `GET /api/admin/promotions` | **A** | **Yes** | Declared in `app/api/routers/checkout.py:360` (`list_promotions`). Returns `list[PromotionCodeOut]`. |
| 7 | `frontend/src/pages/admin/finance/promotions.tsx:98` | `PUT /api/admin/finance/promotions/${selectedPromoId}` | `PUT /api/admin/promotions/{promotion_id}` | **A** | **Yes** | Declared in `app/api/routers/checkout.py:390` (`update_promotion`). Accepts `PromotionCodeUpdate`. |
| 8 | `frontend/src/pages/admin/finance/promotions.tsx:101` | `POST /api/admin/finance/promotions` | `POST /api/admin/promotions` | **A** | **Yes** | Declared in `app/api/routers/checkout.py:369` (`create_promotion`). Accepts `PromotionCodeCreate`. |
| 9 | `frontend/src/pages/admin/finance/tax-rates.tsx:35` | `GET /api/admin/finance/tax-rates` | `GET /api/admin/tax-rates` | **A** | **Yes** | Declared in `app/api/routers/checkout.py:428` (`list_tax_rates`). Returns `list[TaxRateOut]`. |
| 10 | `frontend/src/pages/admin/finance/tax-rates.tsx:72` | `PUT /api/admin/finance/tax-rates/${selectedRate.id}` | `PUT /api/admin/tax-rates/{tax_rate_id}` | **A** | **Yes** | Declared in `app/api/routers/checkout.py:453` (`update_tax_rate`). Accepts `TaxRateUpdate`. |
| 11 | `frontend/src/pages/admin/finance/tax-rates.tsx:75` | `POST /api/admin/finance/tax-rates` | `POST /api/admin/tax-rates` | **A** | **Yes** | Declared in `app/api/routers/checkout.py:437` (`create_tax_rate`). Accepts `TaxRateCreate`. |
| 12 | `frontend/src/pages/admin/notifications/messages.tsx:25` | `GET /api/admin/notifications/messages` | `GET /api/admin/notifications` | **A** | **Yes** | Declared in `app/api/routers/notifications.py:37` (`list_notifications`). Returns paginated notification logs. |
| 13 | `frontend/src/pages/admin/notifications/reminders.tsx:41` | `GET /api/admin/notifications/templates` | `GET /api/admin/notification-templates` | **A** | **Yes** | Declared in `app/api/routers/notifications.py:91` (`list_notification_templates`). Returns `NotificationTemplateListResponse`. |
| 14 | `frontend/src/pages/admin/notifications/templates.tsx:34` | `GET /api/admin/notifications/templates` | `GET /api/admin/notification-templates` | **A** | **Yes** | Declared in `app/api/routers/notifications.py:91` (`list_notification_templates`). Returns `NotificationTemplateListResponse`. |
| 15 | `frontend/src/pages/admin/notifications/templates.tsx:51` | `POST /api/admin/notifications/templates` | `POST /api/admin/notification-templates` | **A** | **Yes** | Declared in `app/api/routers/notifications.py:104` (`create_notification_template`). Accepts `NotificationTemplateCreate`. |
| 16 | `frontend/src/pages/admin/notifications/templates.tsx:53` | `PUT /api/admin/notifications/templates/${selectedTemplate.id}` | `PUT /api/admin/notification-templates/{template_id}` | **A** | **Yes** | Declared in `app/api/routers/notifications.py:128` (`update_notification_template`). Accepts `NotificationTemplateUpdate`. |
| 17 | `frontend/src/pages/admin/relationships-matrix.tsx:329` | `PUT /api/admin/${plural}/${item.id}` | `PUT /api/admin/{entities}/{id}` | **Dynamic** | **No change** | Evaluates at runtime to canonical entity routes (`/api/admin/locations/{id}`, `/api/admin/providers/{id}`, `/api/admin/services/{id}`, etc.). |
| 18 | `frontend/src/pages/admin/relationships-matrix.tsx:330` | `PATCH /api/admin/${plural}/${item.id}` | `PATCH /api/admin/{entities}/{id}` | **Dynamic** | **No change** | Fallback path for entities supporting PATCH. |
| 19 | `frontend/src/pages/admin/relationships-matrix.tsx:356` | `PUT /api/admin/${plural}/${item.id}` | `PUT /api/admin/{entities}/{id}` | **Dynamic** | **No change** | Evaluates at runtime to canonical entity routes. |
| 20 | `frontend/src/pages/admin/relationships-matrix.tsx:357` | `PATCH /api/admin/${plural}/${item.id}` | `PATCH /api/admin/{entities}/{id}` | **Dynamic** | **No change** | Fallback path for entities supporting PATCH. |
| 21 | `frontend/src/pages/admin/relationships-matrix.tsx:381` | `DELETE /api/admin/${plural}/${item.id}` | `DELETE /api/admin/{entities}/{id}` | **Dynamic** | **No change** | Evaluates at runtime to canonical DELETE endpoints. |
| 22 | `frontend/src/pages/admin/relationships-matrix.tsx:515` | `PUT /api/admin/${colDef.plural}/${item.id}` | `PUT /api/admin/{entities}/{id}` | **Dynamic** | **No change** | Evaluates at runtime to canonical entity routes. |
| 23 | `frontend/src/pages/admin/relationships-matrix.tsx:516` | `PATCH /api/admin/${colDef.plural}/${item.id}` | `PATCH /api/admin/{entities}/{id}` | **Dynamic** | **No change** | Fallback path for entities supporting PATCH. |
| 24 | `frontend/src/pages/admin/reviews.tsx:84` | `PUT /api/admin/management-reviews/${review.id}` | `PUT /api/admin/management-reviews/{id}/resolve` | **B** | **No** | **Domain/Payload Mismatch**: Page is a mock customer star ratings table (`{ is_approved }`), whereas backend endpoint is for restricted-client booking reviews (`{ state: "approved" | "rejected", resolution_notes }`). |
| 25 | `frontend/src/pages/admin/settings/plugins.tsx:41` | `GET /api/admin/ui-config` | `GET /api/public/ui-config/admin` | **A** | **Yes** | Declared in `app/api/routers/ui_config.py:79` (`get_admin_ui_config`). Returns admin UI modules config `{ modules: {...} }`. |
| 26 | `frontend/src/pages/admin/settings/plugins.tsx:67` | `POST /api/admin/plugins/${id}/toggle` | *None* | **B** | **No** | **Commented Stub**: Line is commented out in TypeScript (`// await ...`); no plugin toggle route exists. |

---

## 3. Decisions & Recommendations for Untouched Items (Categories B & C)

### A. Payment Refund Endpoint (`frontend/src/pages/admin/finance/payments.tsx:51`) — Category C
- **Current State**: Frontend attempts `POST /api/admin/finance/payments/${paymentId}/refund`.
- **Reason Left Untouched**: In accordance with `AGENTS.md` Rule 3 ("A payment/refund feature requires an approved provider integration, idempotency, audit trail, and explicit user authorization"), no backend refund route exists.
- **Decision Required**: When refund functionality is prioritized, create an explicit Stripe/gateway refund service with idempotency keying and an audit log table before attaching a frontend action.

### B. Payment Processors Configuration (`frontend/src/pages/admin/finance/processors.tsx:43, 62`) — Category B
- **Current State**: Frontend expects `{ currency: string, processors: { stripe, paypal, offline } }`. Backend stores records in `payment_processor_configs` table (`GET/POST/PUT /api/admin/payment-processor/configs`).
- **Reason Left Untouched**: Simply changing the URL would produce schema mapping errors and prevent saving.
- **Decision Required**: Update `processors.tsx` to map its form state to the `PaymentProcessorConfig` entity schema or introduce a typed frontend adapter.

### C. Reviews Management (`frontend/src/pages/admin/reviews.tsx:84`) — Category B
- **Current State**: `reviews.tsx` renders a 5-star customer rating UI and calls `PUT /api/admin/management-reviews/${id}` with `{ is_approved: boolean }`.
- **Reason Left Untouched**: Backend `management-reviews` is dedicated to restricted-client booking policy approval (`state: 'approved' | 'rejected'`), not customer testimonials/star ratings.
- **Decision Required**: Determine whether customer testimonials are in scope for a new `CustomerReview` model or if `reviews.tsx` should be adapted to display restricted-client booking review requests.
