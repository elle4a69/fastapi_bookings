# Client Self-Service Portal & Dispute Center

## Purpose & Scope
The `frontend/src/pages/portal/` directory implements the customer-facing, passwordless self-service portal (`/portal`).

Key responsibilities:
- Fast OTP phone or email authentication.
- Viewing upcoming and historical appointments.
- 1-tap appointment reschedule and cancellation.
- Digital invoice review and payment status tracking.
- Guided Dispute & Quality Resolution Center allowing clients to lodge service issues, submit photographic evidence, and track resolutions.

---

## Architecture & Key Files

```
frontend/src/pages/portal/
├── portal-login.tsx         # OTP request and verification form with 1-click quick-fill demo buttons
├── portal-dashboard.tsx     # Master portal hub: Upcoming Appointments, Receipts, and Dispute Center
└── README.md                # Living documentation
```

Supporting files:
- `frontend/src/context/client-portal-context.tsx`: Manages client JWT auth session and API calls.
- `app/api/routers/client_portal.py`: Backend REST endpoints (`/api/portal/*`).

---

## Core Workflows & Contracts

### 1. Passwordless OTP Login
1. Client enters phone or email on `/portal/login`.
2. Calls `POST /api/portal/auth/send-otp`.
3. Client inputs 6-digit code -> `POST /api/portal/auth/verify-otp`.
4. Backend issues a signed client access token stored in `localStorage` under `client_token`.

### 2. Appointment Reschedule & Cancellation
- **Reschedule**: Modal allows selecting a new date/time; backend validates slot availability before committing.
- **Cancel**: 1-tap confirmation updates status to `cancelled` and releases reserved slot allocations immediately.

### 3. Lodging a Dispute
- Client selects appointment, selects reason (`incomplete_work`, `late_arrival`, `quality_concern`, `billing_dispute`), enters notes, and uploads photo evidence.
- Submits to `POST /api/portal/disputes`, creating a tracked dispute in `submitted` state visible to admins on `/admin`.

---

## Data Safety & Isolation
- The client token only authorizes access to records where `client_id == current_client.id`.
- Clients are strictly barred from viewing other clients' appointments, notes, or disputes.

---

## Verification & Testing Commands
```bash
# Run client portal backend tests
.venv\Scripts\python.exe -m pytest tests/test_client_portal.py -v
```
