# Client Self-Service Portal & Dispute Center (`frontend/src/pages/portal`)

The `frontend/src/pages/portal/` directory implements the customer-facing, passwordless self-service portal (`/portal`) for **FastAPI Bookings**.

---

## 1. Purpose & Scope

The Client Self-Service Portal owns:
- Fast OTP phone or email authentication for friction-free customer access without passwords.
- Viewing upcoming and historical appointments with real-time status.
- 1-tap appointment reschedule and cancellation adhering to tenant cancellation policies.
- Digital invoice review and payment status tracking.
- Guided Dispute & Quality Resolution Center allowing clients to lodge service issues, submit photographic evidence, and track resolutions.

This module deliberately avoids granting administrative privileges, exposing provider contact details beyond public profiles, or allowing unauthenticated access to appointment details.

---

## 2. Architecture & Key Files

```
frontend/src/pages/portal/
├── portal-login.tsx         # OTP request and verification form with 1-click quick-fill demo buttons
├── portal-dashboard.tsx     # Master portal hub: Upcoming Appointments, Receipts, and Dispute Center
└── README.md                # Living documentation
```

### Key Files:
- [portal-login.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/portal/portal-login.tsx): Passwordless intake form handling phone/email OTP requests and token exchange.
- [portal-dashboard.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/portal/portal-dashboard.tsx): Responsive customer dashboard displaying upcoming visits, past appointments, receipts, and dispute intake forms.
- [frontend/src/context/client-portal-context.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/context/client-portal-context.tsx): Client-side React context storing the client JWT token and handling authenticated portal API interactions.
- [app/api/routers/client_portal.py](file:///f:/Projects/fastapi_bookings/app/api/routers/client_portal.py): Backend REST endpoints mounted at `/api/portal/*`.

---

## 3. Setup, Configuration & Dependencies

### Runtime Dependencies
- **React 18 & TypeScript**: Core UI rendering and state management.
- **ClientPortalContext**: Dedicated client context separate from administrative `AuthContext`.
- **Lucide Icons**: Responsive icons for appointments, calendar, receipts, alerts, and upload triggers.
- **Backend Endpoints**: Communicates with `/api/portal/auth/send-otp`, `/api/portal/auth/verify-otp`, `/api/portal/bookings`, and `/api/portal/disputes`.

### Environment & Authentication
- Authenticates via client-specific JWT token stored in `localStorage` under `client_token`.
- Scope is strictly validated per tenant using the `X-Tenant` header or domain host.

---

## 4. Core Workflows & Contracts

### 4.1 Passwordless OTP Login
1. Client enters phone or email on `/portal/login`.
2. Calls `POST /api/portal/auth/send-otp`.
3. Client inputs 6-digit code -> `POST /api/portal/auth/verify-otp`.
4. Backend issues a signed client access token stored in `localStorage` under `client_token`.

### 4.2 Appointment Reschedule & Cancellation
- **Reschedule**: Modal allows selecting a new date/time; backend validates slot availability before committing.
- **Cancel**: 1-tap confirmation updates status to `cancelled` and releases reserved slot allocations immediately.

### 4.3 Lodging a Dispute
- Client selects appointment, selects reason (`incomplete_work`, `late_arrival`, `quality_concern`, `billing_dispute`), enters notes, and uploads photo evidence.
- Submits to `POST /api/portal/disputes`, creating a tracked dispute in `submitted` state visible to admins on `/admin`.

---

## 5. Data Safety & Isolation

- **Client Scoping**: The client token only authorizes access to records where `client_id == current_client.id`.
- **Privacy Isolation**: Clients are strictly barred from viewing other clients' appointments, notes, or disputes. Cross-client query attempts return `403 Forbidden` or `404 Not Found`.
- **Photo Evidence Sanitization**: Uploaded dispute attachments are screened for file type and size before persisting to storage.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Late Cancellation Lockout**: If an appointment falls within the tenant's non-refundable cancellation window (e.g. < 24 hours), the cancel button requires staff contact rather than self-service cancellation.
- **Multiple Phone Numbers**: If a customer changes phone numbers, past bookings associated with the older phone number require administrative client profile merging.
- **Push Notification Integration**: Browser push notifications for reminder chime alerts on portal devices are planned for upcoming releases.

---

## 7. Verification & Testing Commands

To run client portal backend tests and frontend validation:

```powershell
# 1. Run client portal backend tests
.venv\Scripts\python.exe -m pytest tests/test_client_portal.py -v

# 2. Verify frontend compilation
npm run build
```
