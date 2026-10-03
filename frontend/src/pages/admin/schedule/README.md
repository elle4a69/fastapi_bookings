# Admin Schedule Module (`frontend/src/pages/admin/schedule`)

The Admin Schedule module (`frontend/src/pages/admin/schedule/`) manages practitioner workdays, working hour templates, date-specific overrides/exceptions, blocked time blocks, and reservation holds in **FastAPI Bookings**.

---

## 1. Purpose & Scope

The Admin Schedule module owns:
- Weekly recurring working hours template configuration per provider (`weekly_schedule`).
- Date-specific special day overrides (`ProviderSpecialDay` via `/api/admin/providers/{id}/special-days` and `/api/admin/schedule/special-days`).
- Seamless, debounced on-the-fly auto-saving for all mutations (slot selections, Day Off toggles, Recurring decoupling, and advance notice constraints) with live `AutoSaveStatus` indicators, eliminating manual save buttons.
- Consolidated single source of truth for all time-off records and exceptions in `exceptions.tsx`, displaying unified `ProviderSpecialDay` time-off entries and `BlockedTime` blocks.
- Bi-directional synchronization: any time-off created or deleted on the Schedule page is immediately reflected in Exceptions, and deleting an exception immediately deletes the underlying record and reverts the schedule.
- Mobile-responsive schedule editor with 7-day single-row navigation, date-specific override status indicators (amber badges & dots), 4-column compact time slot grids, full 24-hour range (`00:00` - `23:30`), and stacked day/date controls.
- Advance booking threshold configuration ("Time in Advance" / `maxDaysAhead`) auto-saved to tenant business profile (`max_advance_days`).
- Active booking hold management (`/api/admin/schedule/reserved-times`).

This module deliberately avoids:
- Live customer SMS messaging or conversational booking negotiations (owned by SMS Assistant).
- External calendar syncing protocols (owned by sync engines).
- Client checkout and invoice generation (owned by Finance module).

---

## 2. Architecture & Key Files

```
frontend/src/pages/admin/schedule/
├── workdays.tsx                  # Practitioner weekly operating schedules, recurring/one-off slot management, auto-saving
├── exceptions.tsx                # Consolidated time-off and schedule exception management sharing underlying records
├── weekly-schedule-editor.tsx    # Shared weekly schedule and special day component
└── README.md                     # Living documentation
```

### Key Files & UI Features:
- [workdays.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/schedule/workdays.tsx): Practitioner weekly operating schedules, recurring/one-off slot management, fixed start times, advance notice constraints, and seamless auto-saving.
- [exceptions.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/schedule/exceptions.tsx): Consolidated, synchronized time-off and schedule exception management sharing the exact same underlying records as the schedule.
- **Auto-Save Status Header**: Replaced redundant manual "Save Schedule" button with an ambient `<AutoSaveStatus state={saveState} onRetry={handleRetry} />` badge in the header, rendering real-time states (`saving`, `saved`, `failed`, `idle`).
- **7-Day Selector Bar**: Single-row 7-column grid displaying weekday initials (SUN, MON, TUE...) with prominent bold date numbers and amber indicator dots when a date-specific override is active.
- **4-Column Time Slot Grid**: Clean 4 columns on mobile (`grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10`) with compact `h-8` tiles and standard application typography.
- **Full 24-Hour Range**: 48 slots (`00:00` to `23:30`) with quick-selection helpers (`9-5`, `All`, `Clear`).

---

## 3. Setup, Configuration & Dependencies

### Endpoints & APIs
- `GET /api/admin/providers`: Loads practitioner list.
- `GET /api/admin/providers/{id}/special-days`: Loads existing date-specific exceptions for the provider.
- `PUT /api/admin/providers/{id}`: Persists recurring weekly template in `weekly_schedule`.
- `POST /api/admin/providers/{id}/special-days`: Saves date-specific non-recurring overrides.
- `DELETE /api/admin/providers/{id}/special-days/{date_str}`: Deletes reverted date overrides.
- `GET /api/admin/schedule/special-days`: Lists all tenant special day overrides for the consolidated Exceptions view.
- `DELETE /api/admin/schedule/special-days/{id}`: Deletes special day override by primary key.
- `GET/POST/DELETE /api/admin/schedule/blocked-times`: Manages blocked time ranges.
- `GET /api/admin/schedule/reserved-times`: Manages temporary booking holds.
- `GET/PUT /api/admin/business-profile`: Loads and saves tenant booking horizon (`max_advance_days`).

### Dependencies & UI Components
- Lucide icons, Tailwind CSS, Shadcn UI primitives (`Button`, `Card`, `Switch`, `Input`, `Label`, `ScrollArea`, `Table`, `Tabs`, `Dialog`, `Select`), Sonner toasts.

---

## 4. Core Workflows & Contracts

### 4.1 On-the-Fly Auto-Save Mechanics (`workdays.tsx`)
1. **Recurring Weekly Hours (`weeklyScheduleTemplate`)**:
   - Modifications to slot grids or recurring Day Off switches update React state instantaneously.
   - Triggers debounced save (500ms) to `PUT /api/admin/providers/{id}` with `{ weekly_schedule }`.
2. **Date-Specific Decoupling ("Recurring" Toggle OFF)**:
   - When toggling Recurring OFF on a specific date, creates/updates date override in `specialDaysMap`.
   - Persists to `POST /api/admin/providers/{id}/special-days` with `is_working`, `active_slots`, and reason.
   - Dispatches `schedule-exceptions-updated` DOM event.
3. **Reverting to Recurring ("Recurring" Toggle ON)**:
   - Purges date from `specialDaysMap` and immediately reverts UI to the recurring template.
   - Persists deletion to `DELETE /api/admin/providers/{id}/special-days/{dateStr}`.
   - Dispatches `schedule-exceptions-updated` DOM event.
4. **Time in Advance (`maxDaysAhead`)**:
   - Fetched on mount from `GET /api/admin/business-profile`.
   - Changes trigger debounced save (500ms) to `PUT /api/admin/business-profile` with `{ max_advance_days }`.

### 4.2 Consolidated Exceptions Model (`exceptions.tsx`)
- **Shared Underlying Store**:
  - The Exceptions page queries `GET /api/admin/schedule/special-days` (table `provider_special_days`) and `GET /api/admin/schedule/blocked-times` (table `blocked_times`).
  - Entries created on the Schedule Workdays page (`ProviderSpecialDay` where `is_working: false` or custom hours) appear directly in the consolidated list alongside time blocks.
- **Unified Deletion**:
  - Clicking **Delete** beside a special day calls `DELETE /api/admin/schedule/special-days/{id}`.
  - The underlying record in `provider_special_days` is permanently deleted.
  - When switching back to the Schedule page, that day automatically reverts to its baseline recurring schedule.
- **Real-Time Cross-Component Synchronization**:
  - Both pages emit and listen to the `schedule-exceptions-updated` custom event and `focus` window events.
  - Mutations on one page update the other immediately without stale caches.

---

## 5. Data Safety & Isolation

- **Multi-Tenant Isolation**: All API calls pass through `apiClient` which automatically injects multi-tenant scoping headers (`X-Tenant`) and session tokens.
- **Server-Side Validation**: The backend validates provider ownership and tenant boundaries. Client-side mutations cannot reach cross-tenant or unassigned provider records.
- **Template Protection**: One-off date overrides are strictly isolated from the generic weekday recurring schedule to avoid unintentional schedule drift.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Midday Break Multi-Segment Shifts**: Providers with split shifts (e.g. 9am–1pm and 4pm–8pm) configure them via discrete 15-minute slot blocks rather than split shift time pickers.
- **Daylight Saving Time Boundary Transitions**: Overrides spanning DST cutover days calculate slot intervals in location local time to prevent 1-hour display drift.
- **High Concurrency Auto-Saves**: Rapid consecutive slot toggles are debounced to 500ms to avoid out-of-order race conditions on the provider record.

---

## 7. Verification & Testing Commands

To run the schedule tests and frontend compilation:

```powershell
# 1. Frontend Typecheck & Build
cd frontend
npm run build

# 2. Backend Scheduling Tests
.venv\Scripts\python.exe -m pytest tests/test_scheduling_edge_cases.py tests/test_scheduling_constraints.py -v
```
