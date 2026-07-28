# Main Context Document — FastAPI Bookings Frontend
Section 1: Product Overview

Working title: FastAPI Bookings Frontend

One-line description: A production-ready customer booking portal and admin/staff dashboard for the FastAPI Bookings backend.

Problem being solved: Customers need a clear way to discover services and request bookings, while staff need a reliable dashboard to approve, cancel, reschedule, and configure bookings without using raw backend tools.

Primary value proposition: The frontend turns the FastAPI Bookings backend into a usable, role-aware product with guided public booking, temporary slot holds, pending approval workflows, and safe admin operations.

Intended outcome: Customers can submit pending booking requests confidently, and staff can manage booking operations from a governed dashboard using backend-verified configuration and permissions.

Domain classification: SaaS booking and scheduling frontend; customer self-service portal plus internal operations dashboard.

Section 2: Problem Statement

Who has the problem: Service businesses, their customers, staff operators, and administrators using the FastAPI Bookings backend.

What is happening today: The backend exposes booking, hold, configuration, and admin endpoints, but users need a production UI to access them safely.

Why it is painful: Without a frontend, customers cannot self-serve booking requests, staff cannot efficiently approve or manage bookings, and configuration workflows remain too technical.

How often it happens: Every time a customer tries to book and every time staff need to approve, cancel, reschedule, or configure booking operations.

Current alternatives: Manual booking intake, direct API usage, custom admin scripts, spreadsheets, phone/email coordination, or ad hoc internal tools.

Why alternatives are insufficient: They increase operational errors, create duplicate booking risk, expose staff to raw API complexity, and fail to provide customer-facing booking confidence.

Business/user consequence of not solving it: Lower conversion from booking intent, slower staff response time, higher manual workload, and increased risk of stale availability or inconsistent booking state.

Section 3: Goals and Success Metrics
User Goals

Customers can discover available booking options by service, provider, location, category, or time.

Customers can place a 5-minute hold on a slot and submit booking details without duplicate submission risk.

Customers receive clear confirmation that the booking request is pending approval.

Staff can view pending bookings and confirm, cancel, or reschedule them.

Admins can configure services, providers, locations, categories, and enabled modules without exposing unavailable dimensions in the UI.

Business Goals

Increase completed booking-request submissions through guided discovery and slot-hold flows.

Reduce staff time spent interpreting backend state by providing dashboard-first operations.

Improve booking accuracy by aligning UI options with backend module configuration.

Reduce support load caused by unclear booking status or failed submissions.

Non-Goals

Rebuilding the FastAPI backend.

Implementing payment processing in v1.

Implementing real-time chat, SMS automation, or marketing automation in v1.

Allowing customers to self-confirm bookings without staff approval.

Exposing disabled module dimensions through hidden or unsupported UI paths.

Success Metrics

Primary metric: Public booking request completion rate: at least 55% of users who start availability search submit a pending booking request within 14 days after MVP launch, measured by availability_search_submitted to booking_request_submitted.

Activation metric: First-value action: at least 70% of first-time public visitors who select a service see available slot results within 5 minutes of first page load during the first 30 days after launch.

Engagement metric: Staff workflow engagement: at least 80% of active staff users open the pending approvals queue at least 3 times per week during the first 30 days after launch.

Quality metric: Booking submission error rate: fewer than 3 failed booking or hold submissions per 100 attempted submissions during the first 30 days after launch.

Retention metric: Admin/staff return usage: at least 65% of staff users return within 7 days of first dashboard login during the first 60 days after launch.

Section 4: Target Users
Primary User

Role/persona: Customer booking a service

Context of use: Public website or booking link on mobile, tablet, or desktop

Motivation: Find a suitable service time and submit a booking request quickly

Pain points: Unclear availability, too many irrelevant filters, uncertainty about whether a booking is confirmed

Skill level: Low to medium technical comfort

Device/platform: Mobile-first responsive web; desktop supported

Usage frequency: Occasional

Secondary User

Role/persona: Staff operator

Context of use: Admin dashboard during daily operations

Motivation: Approve, cancel, reschedule, and monitor bookings

Pain points: Manual tracking, unclear pending queues, risk of acting on stale state

Skill level: Medium technical comfort

Device/platform: Desktop-first web; tablet supported

Usage frequency: Daily

Admin/Operator Role

Role/persona: Business administrator

Context of use: Configuration and operational setup

Motivation: Manage services, providers, locations, categories, and module availability

Pain points: Configuration mistakes, exposing disabled booking dimensions, role-access mistakes

Skill level: Medium to high technical comfort

Device/platform: Desktop web

Usage frequency: Weekly or as needed

Section 5: Assumptions and Open Questions
Current Assumptions

ASSUMPTION: Staff roles are split into Admin and Staff: The repository evidence identifies admin/staff dashboard behavior but not final role names. | Risk: Permission copy or matrix may need adjustment if backend role names differ.

ASSUMPTION: Booking retention policy is 24 months: A booking product usually needs operational history for customer service and reporting. | Risk: Legal, privacy, or business retention requirements may require shorter or longer storage.

ASSUMPTION: Hold retention policy is 30 days for audit logs after expiry/release: Holds expire after 5 minutes, but short-term diagnostic history helps investigate booking conflicts. | Risk: Backend may delete holds immediately, limiting support diagnostics.

ASSUMPTION: Admin sessions persist until backend token expiry and are cleared on logout: Token expiry duration was not provided. | Risk: Session timeout copy and draft-restore behavior may need adjustment.

ASSUMPTION: Public auth token is required before public protected calls: Public token endpoint and X-Token header were provided. | Risk: Some public endpoints may be unauthenticated in practice and should avoid unnecessary token friction.

Open Questions

What exact role names and permissions does the backend return for admin users?: Needed to align protected routes, menu visibility, and unauthorized copy. | Impact: Section 13 matrix and permission-restricted flows may require role-name edits.

What are the exact CRUD configuration resources exposed in route-manifest and contract files?: Needed to specify every configuration screen. | Impact: Section 8, Section 9, and Section 16 may need endpoint expansion.

What is the backend token expiry duration?: Needed for precise timeout behavior. | Impact: Section 10 and Section 15 session-expiry rules may need timing changes.

Does POST /api/public/bookings duplicate or bypass hold confirmation?: Both direct booking creation and hold confirmation exist. | Impact: Customer journey may branch between hold-first and direct pending request modes.

Risks Created by Ambiguity

Risk: Role names differ from Admin/Staff — Mitigation: map backend role strings to UI permission groups during implementation.

Risk: Configuration CRUD resources are broader than the current MCD scope — Mitigation: generate admin configuration screens from route-manifest and contract metadata where possible.

Risk: Direct public booking and hold-confirm booking overlap — Mitigation: prioritize hold-first flow for slots and treat direct booking as fallback or non-slot request path until backend evidence confirms intent.

Section 6: Scope
Must Have (MVP-blocking)

Public authentication and bootstrap: Required to obtain public X-Token, load services, providers, locations, categories, booking rules, and timezone.

Module-aware UI configuration: Required to hide disabled modules and avoid unsupported discovery endpoint calls.

Flexible multi-entry discovery: Required so customers can start from location, provider, category, service, or time.

Availability search: Required to return candidate slots based on selected filters and date range.

Slot hold lifecycle: Required to create, show, confirm, expire, and release 5-minute slot holds.

Pending booking request submission: Required to create pending bookings and communicate approval status.

Admin authentication and dashboard bootstrap: Required for protected dashboard access and initial overview data.

Pending approvals queue: Required so staff can confirm or cancel pending bookings.

Calendar list and reschedule workflow: Required so staff can view operational booking schedules and move bookings.

Configuration CRUD dashboard: Required so admins can manage booking dimensions and service setup.

Role-scoped access control: Required to protect admin/staff actions and hide unauthorized UI.

Should Have (important but not MVP-blocking)

Unified UiError display system: Important for consistent user-facing error handling across standard API errors and FastAPI native exceptions.

Analytics instrumentation: Important to measure booking funnel, staff usage, errors, drop-offs, and activation.

Draft preservation for customer booking details: Important to recover from refresh, timeout, or network loss.

Optimistic UI guards for duplicate submissions: Important to prevent double holds and duplicate booking requests.

Could Have (future enhancement)

Calendar grid view: Valuable after list view is stable and staff need denser schedule visualization.

Customer booking lookup: Valuable when customers need to check pending/confirmed status.

Automated notifications: Valuable when email/SMS channels are integrated.

Payments: Valuable when confirmed bookings need deposit or full prepayment.

Localization: Valuable for multi-region businesses.

Out of Scope (explicitly excluded from v1)

Backend schema redesign: Excluded because the backend repository contracts are the source of truth.

Payment processing: Excluded because no payment endpoint evidence was supplied.

Customer self-confirmation: Excluded because public booking status is pending and staff approval is required.

Unsupported module entry flows: Excluded because disabled modules must be hidden and their discovery endpoints must not be called.

Native mobile applications: Excluded because MVP is responsive web.

Section 7: User Journeys
1. First-time onboarding — from landing to first success moment

Trigger: Customer opens the public booking portal.

Entry point: Public booking URL.

User intent: Find a service time and submit a booking request.

Steps:

System requests public token via POST /api/public/auth/token; feedback: loading indicator on initial booking shell.

System loads GET /api/public/ui-config; feedback: unavailable modules are hidden before discovery starts.

System loads GET /api/public/bootstrap; feedback: service, provider, location, category, rules, and timezone are shown.

User chooses an allowed entry point; feedback: selected path becomes active and irrelevant disabled paths remain hidden.

User searches availability; feedback: slot results appear with timezone context.

User selects a slot; feedback: hold countdown starts after successful hold creation.

User enters client details and confirms hold; feedback: booking request confirmation appears.

Decision points: Entry point selection; slot selection; whether to continue after no availability.

Success outcome: Customer sees: “Your booking request has been received and is awaiting confirmation.”

Drop-off risks: No availability, disabled expected filter, token failure, hold expiry, validation errors.

Recovery path: Show clear UiError, preserve filter selections, offer alternate dates or restart hold flow.

2. Primary repeated workflow — day-to-day use case

Trigger: Staff begins daily booking operations.

Entry point: Admin dashboard login.

User intent: Review pending booking requests.

Steps:

Staff signs in via POST /api/admin/auth; feedback: dashboard shell appears after token is stored.

System loads GET /api/admin/dashboard/bootstrap; feedback: overview cards and queue counts appear.

Staff opens pending approvals queue; feedback: pending rows appear with status labels.

Staff confirms or cancels a booking; feedback: action button disables during request.

System updates booking status; feedback: row moves out of pending queue.

Decision points: Confirm, cancel, reschedule, or leave pending.

Success outcome: Booking state changes to confirmed or cancelled.

Drop-off risks: Expired token, stale booking status, failed action request.

Recovery path: Preserve list position, show retry action, refresh row from server.

3. Edit / update flow — modifying existing work

Trigger: Staff needs to reschedule a booking.

Entry point: Calendar list or booking details action.

User intent: Move a booking to a new time.

Steps:

Staff selects “Reschedule”; feedback: reschedule panel opens.

Staff chooses new date/time and optional provider/location filters; feedback: availability search runs.

Staff submits POST /api/admin/bookings/{booking_id}/reschedule; feedback: action disables and progress appears.

System returns updated booking; feedback: calendar list updates.

Decision points: New slot selection; whether to cancel reschedule.

Success outcome: Booking appears in new slot.

Drop-off risks: No availability, booking already cancelled, permission lost.

Recovery path: Show specific UiError and keep current booking unchanged.

4. Delete / destructive action flow — with safety mechanisms

Trigger: Customer releases a hold or staff cancels a booking.

Entry point: Hold countdown panel or admin booking row.

User intent: Release a slot or cancel a booking.

Steps:

User chooses release/cancel; feedback: confirmation prompt appears for booking cancellation.

User confirms; feedback: button disables.

System calls DELETE /api/public/holds/{hold_id} or POST /api/admin/bookings/{booking_id}/cancel.

System updates UI state; feedback: hold removed or booking marked cancelled.

Decision points: Confirm or back out.

Success outcome: Slot hold is released or booking status is cancelled.

Drop-off risks: Network failure, stale state, accidental cancel.

Recovery path: No destructive action proceeds without confirmation for staff cancellation; failed requests preserve previous state.

5. Error recovery flow — what happens after failures

Trigger: API returns standard error envelope, FastAPI native detail, network timeout, or validation error.

Entry point: Any public or admin request.

User intent: Understand what went wrong and recover.

Steps:

Client parses response; feedback: no raw JSON exposed.

Client normalizes into UiError.

UI displays field error, inline message, banner, or modal depending on context.

User edits input or retries action.

Decision points: Retry, edit fields, refresh, sign in again.

Success outcome: User recovers without losing entered data where safe.

Drop-off risks: Ambiguous backend error, expired token, interrupted hold.

Recovery path: Preserve form state, show next action, require fresh hold when hold expiry is possible.

6. Permission-restricted flow

Trigger: Staff user attempts an admin-only configuration action.

Entry point: Admin dashboard route or direct deep link.

User intent: View or modify configuration.

Steps:

Client checks available user permissions from admin context.

Unauthorized navigation item is hidden or read-only.

If user deep-links, system blocks access.

UI shows access-denied message.

Decision points: Return to dashboard or sign in as different user.

Success outcome: Unauthorized action is prevented without exposing edit controls.

Drop-off risks: Backend role mismatch, stale permissions.

Recovery path: Refresh session, show “You do not have access to this action.”

Section 8: Core Feature Specifications

SECTION_8_FEATURES:

Public authentication and bootstrap

Module-aware UI configuration

Flexible multi-entry discovery

Availability search

Slot hold lifecycle

Pending booking request submission

Admin authentication and dashboard bootstrap

Pending approvals queue

Calendar list and reschedule workflow

Configuration CRUD dashboard

Role-scoped access control

Unified UiError display system

Analytics instrumentation

Draft preservation for customer booking details

Optimistic UI guards for duplicate submissions
TOTAL: 15 features to spec

Public authentication and bootstrap

Purpose: Establish public API access and load initial booking data.

User value: Customers see only valid services, providers, locations, categories, booking rules, and timezone.

Entry points: Public portal page load.

User actions: Open booking portal; retry loading when bootstrap fails.

System behavior: Call POST /api/public/auth/token, store token in memory/session storage, send X-Token, then call GET /api/public/ui-config and GET /api/public/bootstrap.

Inputs: company (string, required); key (string, required).

Outputs: access_token (string); token_type (bearer); modules; bookingFlow; services; providers; locations; categories; booking rules; timezone.

Business rules:

IF public token request succeeds THEN load UI config and bootstrap data ELSE show “We could not start booking. Please refresh and try again.”

IF bootstrap succeeds THEN render booking entry options ELSE show “Booking options could not be loaded. Please try again.”

IF timezone is returned THEN display all slots in that timezone ELSE use business timezone from booking rules.

Validation rules: company and key must be non-empty strings.

Success state: Booking portal displays available entry points and service data.

Failure state:

Token failure → “We could not start booking. Please refresh and try again.”

Bootstrap failure → “Booking options could not be loaded. Please try again.”

Missing data → “Booking setup is incomplete. Please contact the business.”

Empty state: “No bookable services are available right now.”

Loading state: Full-page skeleton with disabled discovery controls.

Disabled state: Discovery controls disabled until auth, UI config, and bootstrap complete.

Permissions impact: Public customer access only.

Edge cases:

Duplicate submission: Token request deduplicated during initial load.

Invalid/malformed input: Show startup failure message.

Session timeout mid-flow: Re-authenticate public token and preserve selected filters.

Slow or lost connection: Show retry banner after 10 seconds.

Partial completion / user abandons halfway: No booking is created.

Module-aware UI configuration

Purpose: Adapt UI to enabled modules.

User value: Customers are not shown filters or flows that cannot work.

Entry points: Public bootstrap, discovery, admin configuration screens.

User actions: Select entry point; navigate among discovery filters.

System behavior: Use GET /api/public/ui-config to resolve modules and bookingFlow.

Inputs: modules.locations (boolean); modules.categories (boolean); modules.resources (boolean); modules.products (boolean); modules.add_ons (boolean); bookingFlow.allowedEntryPoints (string[]); bookingFlow.defaultEntryPoint (string).

Outputs: Visible entry points, hidden filters, disabled endpoint calls.

Business rules:

IF locations is false THEN hide location selection and do not call location discovery endpoints ELSE show location entry points allowed by bookingFlow.

IF categories is false THEN hide category selection and do not submit category_id ELSE include category filters when selected.

IF defaultEntryPoint is not allowed THEN use first allowed entry point ELSE select defaultEntryPoint.

Validation rules: allowedEntryPoints must contain only service, provider, location, category, or time.

Success state: UI shows only enabled and allowed booking paths.

Failure state:

Config load failure → “Booking configuration could not be loaded. Please try again.”

No allowed entry points → “Online booking is not available right now.”

Disabled module deep link → “This booking option is not available.”

Empty state: “No booking paths are currently enabled.”

Loading state: Hide entry tabs until config resolves.

Disabled state: Disabled modules are not visible and cannot be selected.

Permissions impact: Public users see enabled public modules; admins manage configuration if authorized.

Edge cases:

Duplicate submission: Repeated config calls are cached per session.

Invalid/malformed input: Ignore unknown module keys and log client warning.

Session timeout mid-flow: Re-fetch config after token renewal.

Slow or lost connection: Show loading retry banner.

Partial completion / user abandons halfway: Selected path is discarded unless draft preservation has started.

Flexible multi-entry discovery

Purpose: Let customers begin booking from the dimension they know.

User value: Reduces friction by supporting service-first, provider-first, location-first, category-first, or time-first discovery.

Entry points: Public portal landing, deep links, booking widgets.

User actions: Choose location, provider, category, service, or time.

System behavior: Render only allowed entry points and progressively narrow filters.

Inputs: entry_point (string, required); selected service_id/provider_id/location_id/category_id/desired_time (UUID or ISO string, optional).

Outputs: Filter state and available next-step options.

Business rules:

IF selected entry point is disabled THEN redirect to default entry point ELSE render selected flow.

IF service is selected THEN constrain provider/location/category options to compatible records ELSE show all compatible options.

IF desired_time is selected THEN search availability using time-first filters ELSE wait for minimum required filters.

Validation rules: UUID filters must be valid UUID strings; desired_time must be ISO 8601.

Success state: Customer reaches availability search with valid filters.

Failure state:

Invalid entry point → “This booking path is not available.”

No compatible options → “No matching booking options are available.”

Malformed filter → “Please choose a valid option.”

Empty state: “Choose how you would like to start your booking.”

Loading state: Skeleton list for options.

Disabled state: Search disabled until required filters or date range are present.

Permissions impact: Public access.

Edge cases:

Duplicate submission: Repeated filter clicks only update local state once.

Invalid/malformed input: Clear invalid filter and show inline error.

Session timeout mid-flow: Preserve filters and renew token.

Slow or lost connection: Keep current filters and show retry.

Partial completion / user abandons halfway: No backend mutation occurs.

Availability search

Purpose: Find bookable slots from selected filters.

User value: Customers see real availability before committing.

Entry points: Discovery flow after sufficient filters.

User actions: Submit search, change filters, change date range.

System behavior: Call POST /api/public/search-availability.

Inputs: service_id (UUID, optional); provider_id (UUID, optional); location_id (UUID, optional); category_id (UUID, optional); desired_time (ISO datetime, optional); date_from (ISO date, required); date_to (ISO date, required).

Outputs: Slot results with slot identifiers, start/end time, provider, service, location, and availability metadata.

Business rules:

IF date_to is before date_from THEN block search and show “Choose an end date after the start date.” ELSE submit search.

IF a disabled module filter is present THEN remove that filter before request ELSE include selected filter.

IF no slots are returned THEN show alternate-date empty state ELSE show slot cards.

Validation rules: date_from and date_to required; date range max 31 days; UUID filters validated client-side.

Success state: Slot list appears.

Failure state:

Validation error → “Please check your search details.”

No slots → “No available times match your search.”

API failure → “Availability could not be loaded. Please try again.”

Empty state: “No available times match your search. Try another date or service.”

Loading state: Slot-card skeletons; search button disabled.

Disabled state: Search disabled while request is in flight.

Permissions impact: Public access with public token.

Edge cases:

Duplicate submission: In-flight search is cancelled or ignored when newer search starts.

Invalid/malformed input: Field-level error shown.

Session timeout mid-flow: Renew token and retry once.

Slow or lost connection: Show retry after timeout.

Partial completion / user abandons halfway: No backend mutation occurs.

Slot hold lifecycle

Purpose: Temporarily reserve a selected slot before final booking request.

User value: Customers have 5 minutes to complete details without losing the slot immediately.

Entry points: Slot result card.

User actions: Hold slot, confirm hold, release hold, restart after expiry.

System behavior: Call POST /api/public/holds; show 5-minute countdown; call POST /api/public/holds/{hold_id}/confirm or DELETE /api/public/holds/{hold_id}.

Inputs: slot details (required); hold_id (UUID, required for confirm/delete); client_details.name (string, required); client_details.email (string, required); client_details.phone (string, required).

Outputs: Hold record, expiry timestamp, pending booking after confirmation.

Business rules:

IF hold succeeds THEN start 5-minute countdown ELSE show “This time could not be held. Please choose another time.”

IF countdown reaches zero THEN mark hold expired and require new slot selection ELSE allow confirmation.

IF user releases hold THEN call delete endpoint and remove countdown ELSE keep hold active.

Validation rules: name required; email valid format; phone non-empty; hold_id UUID.

Success state: “Your booking request has been received and is awaiting confirmation.”

Failure state:

Hold failed → “This time could not be held. Please choose another time.”

Hold expired → “This hold has expired. Please choose a time again.”

Confirm failed → “We could not submit your booking request. Please try again.”

Empty state: “Select a time to hold your booking slot.”

Loading state: Hold button disabled; confirmation button shows progress.

Disabled state: Confirm disabled after expiry or while request is in flight.

Permissions impact: Public access with public token.

Edge cases:

Duplicate submission: Hold and confirm buttons disabled after first click.

Invalid/malformed input: Inline client detail errors shown.

Session timeout mid-flow: Renew token; if hold may have expired, re-check or require new hold.

Slow or lost connection: Preserve form and show retry.

Partial completion / user abandons halfway: Hold expires automatically or can be released.

Pending booking request submission

Purpose: Create booking requests with pending status.

User value: Customers can complete booking intent and understand approval is required.

Entry points: Hold confirmation or direct booking request form.

User actions: Submit client details and booking request.

System behavior: Call POST /api/public/bookings or confirm hold endpoint; display pending status copy.

Inputs: service_id (UUID); provider_id (UUID, optional); location_id (UUID, optional); category_id (UUID, optional); desired_time or slot details; client_details.

Outputs: Booking object with status pending.

Business rules:

IF booking creation succeeds THEN show pending confirmation ELSE show submission failure.

IF booking status is pending THEN display awaiting confirmation copy ELSE display returned status-specific copy.

IF duplicate submit is attempted THEN ignore second click ELSE submit request.

Validation rules: client name, email, and phone required; selected booking context must include service and time or backend-accepted equivalent.

Success state: “Your booking request has been received and is awaiting confirmation.”

Failure state:

Validation error → “Please check your booking details.”

Duplicate request → “This booking request is already being submitted.”

API failure → “We could not submit your booking request. Please try again.”

Empty state: “Complete your details to request this booking.”

Loading state: Submit button disabled with progress state.

Disabled state: Submit disabled until required fields are valid.

Permissions impact: Public access with public token.

Edge cases:

Duplicate submission: Idempotent UI guard and disabled submit.

Invalid/malformed input: Inline errors.

Session timeout mid-flow: Renew public token and retry once if safe.

Slow or lost connection: Show retry; do not clear form.

Partial completion / user abandons halfway: Draft details may be preserved locally.

Admin authentication and dashboard bootstrap

Purpose: Authenticate staff/admin and load dashboard overview.

User value: Staff get protected operational access.

Entry points: Admin login page.

User actions: Enter company, login, password.

System behavior: Call POST /api/admin/auth, store token, send X-Token, call GET /api/admin/dashboard/bootstrap.

Inputs: company (string, required); login (string, required); password (string, required).

Outputs: access_token, token_type, dashboard overview data.

Business rules:

IF auth succeeds THEN route to dashboard ELSE show “Sign in failed. Check your details and try again.”

IF dashboard bootstrap succeeds THEN render dashboard ELSE show retry state.

IF token is missing THEN redirect to login ELSE allow protected route load.

Validation rules: all login fields required; password masked.

Success state: Dashboard overview appears.

Failure state:

Auth failed → “Sign in failed. Check your details and try again.”

Bootstrap failed → “Dashboard data could not be loaded.”

Token missing → “Please sign in to continue.”

Empty state: “No dashboard activity yet.”

Loading state: Login button disabled; dashboard skeleton after auth.

Disabled state: Login disabled until all fields present.

Permissions impact: Admin/staff users only.

Edge cases:

Duplicate submission: Login button disabled during request.

Invalid/malformed input: Inline required-field errors.

Session timeout mid-flow: Redirect to login and preserve intended destination.

Slow or lost connection: Show retry.

Partial completion / user abandons halfway: No token stored.

Pending approvals queue

Purpose: Let staff process pending booking requests.

User value: Staff can quickly approve or reject customer requests.

Entry points: Dashboard pending count, sidebar approvals link.

User actions: View pending bookings, confirm, cancel, open details.

System behavior: Display pending records and call confirm/cancel endpoints.

Inputs: booking_id (UUID, required); optional cancel reason if backend supports it.

Outputs: Booking status transitions to confirmed or cancelled.

Business rules:

IF confirm succeeds THEN move booking from pending to confirmed ELSE show “Booking could not be confirmed.”

IF cancel succeeds THEN mark booking cancelled ELSE show “Booking could not be cancelled.”

IF booking is no longer pending THEN refresh row and show “This booking has already changed.”

Validation rules: booking_id must be valid UUID.

Success state: “Booking confirmed.” or “Booking cancelled.”

Failure state:

Confirm failed → “Booking could not be confirmed. Please try again.”

Cancel failed → “Booking could not be cancelled. Please try again.”

Stale status → “This booking has already changed. The list has been refreshed.”

Empty state: “No pending booking requests.”

Loading state: Row-level action spinner.

Disabled state: Confirm/cancel disabled while action is in flight or user lacks permission.

Permissions impact: Staff can confirm/cancel if authorized; public users cannot access.

Edge cases:

Duplicate submission: Action buttons disabled after click.

Invalid/malformed input: Refresh list and show generic action error.

Session timeout mid-flow: Redirect to login.

Slow or lost connection: Keep row pending and show retry.

Partial completion / user abandons halfway: No state change unless backend succeeds.

Calendar list and reschedule workflow

Purpose: Show operational booking list and support rescheduling.

User value: Staff can manage the schedule without a full calendar grid.

Entry points: Dashboard calendar list.

User actions: Filter list, open booking, reschedule booking.

System behavior: Load booking list from dashboard/bootstrap or calendar endpoint if present; call POST /api/admin/bookings/{booking_id}/reschedule.

Inputs: booking_id (UUID); new date/time; provider_id/location_id if needed.

Outputs: Updated booking date/time and status-preserving record.

Business rules:

IF reschedule succeeds THEN update booking row ELSE show “Booking could not be rescheduled.”

IF selected new time is unavailable THEN block submission ELSE submit reschedule.

IF booking is cancelled THEN disable reschedule ELSE allow authorized users.

Validation rules: new date/time required; booking_id UUID; date/time must be future.

Success state: “Booking rescheduled.”

Failure state:

Invalid time → “Choose a valid future time.”

API failure → “Booking could not be rescheduled. Please try again.”

Cancelled booking → “Cancelled bookings cannot be rescheduled.”

Empty state: “No bookings are scheduled for this view.”

Loading state: List skeleton; reschedule button spinner.

Disabled state: Reschedule disabled for cancelled bookings, unauthorized users, and invalid time.

Permissions impact: Staff/admin only.

Edge cases:

Duplicate submission: Submit disabled during request.

Invalid/malformed input: Inline validation.

Session timeout mid-flow: Redirect to login.

Slow or lost connection: Keep original booking displayed.

Partial completion / user abandons halfway: Close modal without saving.

Configuration CRUD dashboard

Purpose: Manage backend booking dimensions.

User value: Admins can configure services, providers, locations, categories, and module-driven booking dimensions.

Entry points: Admin configuration sidebar.

User actions: Create, read, update, archive/delete configuration records.

System behavior: Use backend CRUD endpoints defined in route-manifest and contract schemas.

Inputs: resource-specific fields for service, provider, location, category, resource, product, and add-on records.

Outputs: Updated configuration lists and detail records.

Business rules:

IF module is disabled THEN hide corresponding configuration tab from non-admin staff ELSE show if authorized.

IF create/update succeeds THEN show saved toast ELSE show validation errors.

IF delete/archive is requested THEN require confirmation ELSE do not mutate record.

Validation rules: required fields per contract schema; names non-empty; IDs UUID.

Success state: “Configuration saved.”

Failure state:

Validation error → “Please check the highlighted fields.”

Save failure → “Configuration could not be saved.”

Delete failure → “Configuration could not be removed.”

Empty state: “No records yet. Create the first item to enable this booking option.”

Loading state: Table skeleton and disabled save button.

Disabled state: Save disabled until required fields pass validation.

Permissions impact: Admin full access; staff view or none based on backend role.

Edge cases:

Duplicate submission: Save disabled during request.

Invalid/malformed input: Inline errors.

Session timeout mid-flow: Preserve draft and redirect to login.

Slow or lost connection: Show retry and keep draft.

Partial completion / user abandons halfway: Unsaved changes warning.

Role-scoped access control

Purpose: Enforce safe feature access.

User value: Users only see actions they can perform.

Entry points: Admin routes, nav, action buttons, configuration screens.

User actions: Navigate, view, create, edit, delete, approve, reschedule.

System behavior: Gate UI by authenticated admin/staff context and backend failures.

Inputs: access_token; user role/permissions from backend context; route metadata.

Outputs: Visible nav, enabled actions, access-denied states.

Business rules:

IF user lacks permission THEN hide action or show read-only state ELSE enable action.

IF backend returns unauthorized THEN clear session and redirect to login ELSE continue.

IF backend returns forbidden THEN show access denied ELSE show normal response.

Validation rules: protected routes require token.

Success state: Authorized users see appropriate UI.

Failure state:

Unauthorized → “Please sign in to continue.”

Forbidden → “You do not have access to this action.”

Unknown permission → “This action is not available for your account.”

Empty state: “No accessible tools are available for your role.”

Loading state: Protected route skeleton until permissions resolve.

Disabled state: Unauthorized actions disabled or hidden.

Permissions impact: Applies to all admin/staff features.

Edge cases:

Duplicate submission: Permission check cached per route load.

Invalid/malformed input: Treat unknown permission as denied.

Session timeout mid-flow: Redirect to login.

Slow or lost connection: Keep protected UI blocked until verified.

Partial completion / user abandons halfway: Clear pending mutations.

Unified UiError display system

Purpose: Normalize backend errors for consistent UX.

User value: Users receive clear messages instead of raw API payloads.

Entry points: All API calls.

User actions: Submit forms, search, retry, sign in.

System behavior: Parse standard error envelope and FastAPI native detail into UiError.

Inputs: {"ok": false, "error": {"code", "message", "field", "details"}} or {"detail": "string"}.

Outputs: UiError { code, message, field?, details? }.

Business rules:

IF response has ok false error THEN map code/message/field/details ELSE inspect detail.

IF response has detail string THEN set code to FASTAPI_ERROR and message to detail ELSE use fallback error.

IF UiError field is present THEN show field-level error ELSE show banner or toast.

Validation rules: message must be non-empty; fallback message required.

Success state: Errors are displayed consistently.

Failure state:

Unknown error → “Something went wrong. Please try again.”

Network error → “Connection lost. Check your internet and try again.”

Timeout → “This is taking longer than expected. Please try again.”

Empty state: No error displayed.

Loading state: Existing errors clear only after new request starts.

Disabled state: Retry disabled during retry request.

Permissions impact: Applies to public and admin users.

Edge cases:

Duplicate submission: Same error deduplicated within one request cycle.

Invalid/malformed input: Fallback UiError generated.

Session timeout mid-flow: Auth-specific message shown.

Slow or lost connection: Network UiError shown.

Partial completion / user abandons halfway: No additional error shown after unmount.

Analytics instrumentation

Purpose: Measure funnel health, adoption, errors, and drop-offs.

User value: Product team can improve UX based on real behavior.

Entry points: Public portal and admin dashboard.

User actions: Search, hold, submit booking, approve, reschedule, configure.

System behavior: Emit events with non-sensitive metadata.

Inputs: event name, timestamp, session_id, role, company, feature, result.

Outputs: Analytics events.

Business rules:

IF user submits availability search THEN emit search event ELSE do not emit search event.

IF API returns UiError THEN emit error event with code and context ELSE emit success event where configured.

IF client_details include PII THEN do not send PII to analytics ELSE send allowed metadata.

Validation rules: event names snake_case; PII excluded.

Success state: Events appear in analytics pipeline.

Failure state:

Analytics unavailable → “No user-facing message.”

Invalid event payload → “No user-facing message.”

Consent disabled → “No user-facing message.”

Empty state: No events before user action.

Loading state: Analytics send is non-blocking.

Disabled state: Tracking disabled when consent or environment disables analytics.

Permissions impact: Admin and public events scoped by role.

Edge cases:

Duplicate submission: Include request_id to deduplicate events.

Invalid/malformed input: Drop invalid analytics payload.

Session timeout mid-flow: Emit auth_expired event without token.

Slow or lost connection: Queue non-sensitive analytics where allowed.

Partial completion / user abandons halfway: Emit abandonment event after navigation/change.

Draft preservation for customer booking details

Purpose: Prevent loss of customer-entered details.

User value: Customers do not have to retype details after refresh, timeout, or recoverable error.

Entry points: Client details form after hold.

User actions: Enter name, email, phone; refresh; retry.

System behavior: Save non-sensitive booking draft locally until submission or expiry.

Inputs: name, email, phone, selected service/slot summary.

Outputs: Restored form draft.

Business rules:

IF form changes THEN save draft locally ELSE keep previous draft.

IF booking submits successfully THEN clear draft ELSE retain draft for retry.

IF hold expires THEN keep contact details but clear slot-specific hold ID ELSE allow new slot selection.

Validation rules: Do not persist access tokens in draft; clear draft after 24 hours.

Success state: Draft restored silently with unsaved indicator.

Failure state:

Storage unavailable → “Your details could not be saved on this device.”

Expired draft → “This saved booking draft has expired.”

Hold expired → “This hold has expired. Please choose a time again.”

Empty state: Blank form.

Loading state: Restore draft before showing form.

Disabled state: Restore disabled in private/browser-blocked storage.

Permissions impact: Public user only.

Edge cases:

Duplicate submission: Draft cleared only after confirmed success.

Invalid/malformed input: Invalid draft fields ignored.

Session timeout mid-flow: Draft remains available.

Slow or lost connection: Draft retained.

Partial completion / user abandons halfway: Draft expires after 24 hours.

Optimistic UI guards for duplicate submissions

Purpose: Prevent double holds, duplicate booking requests, and repeated admin actions.

User value: Users can click confidently without creating duplicate records.

Entry points: All mutating public/admin actions.

User actions: Submit, confirm, cancel, reschedule, save.

System behavior: Disable action, attach local request key where supported, ignore repeated clicks until response.

Inputs: action type, resource ID, request state.

Outputs: Single in-flight mutation per action/resource pair.

Business rules:

IF mutation is in flight THEN ignore duplicate click ELSE submit mutation.

IF mutation succeeds THEN clear in-flight state ELSE allow retry.

IF component unmounts during mutation THEN prevent stale UI update ELSE apply response.

Validation rules: Mutating buttons must have loading and disabled states.

Success state: One mutation result displayed.

Failure state:

Duplicate click → “This request is already being submitted.”

Request failure → “We could not complete this action. Please try again.”

Unknown state → “Refresh to confirm the latest status.”

Empty state: No active mutation.

Loading state: Button spinner and disabled state.

Disabled state: Button disabled during in-flight request.

Permissions impact: Applies to public and admin users.

Edge cases:

Duplicate submission: Ignored and message shown when helpful.

Invalid/malformed input: Request blocked before mutation.

Session timeout mid-flow: Mutation not retried automatically unless safe.

Slow or lost connection: Timeout message shown and retry enabled.

Partial completion / user abandons halfway: State refresh required on return.

Section 9: Screen-by-Screen UX Behavior
Public Booking Landing

Purpose: Start the booking flow.

Primary user goal: Choose how to discover a booking.

Primary action: “Find a time” → availability search.

Secondary actions: Switch entry point; retry loading; change filters.

Key components: Header, entry-point tabs, filter panel, service/provider/location/category/time selectors.

Information hierarchy: Booking purpose, enabled entry points, filters, helper text.

Default state: Loads UI config and bootstrap, then selects default entry point.

Empty state: “No bookable services are available right now.”

Loading state: Page skeleton.

Error state: Banner: “Booking options could not be loaded. Please try again.”

Validation behavior: On submit for search; inline for invalid dates.

Disabled conditions: Search disabled until required filters are valid.

Navigation behavior: Back returns to previous public page or resets current step.

Responsive behavior: Mobile uses stacked selectors; desktop uses tab/filter layout.

Accessibility notes: Entry tabs keyboard navigable; form labels explicit; focus moves to first error.

Availability Results

Purpose: Display available slots.

Primary user goal: Select a slot.

Primary action: “Hold this time” → create hold.

Secondary actions: Change filters; change date range.

Key components: Slot cards, timezone label, filters summary, empty state.

Information hierarchy: Date/time, service, provider/location, action button.

Default state: Shows results from latest valid search.

Empty state: “No available times match your search. Try another date or service.”

Loading state: Slot card skeletons.

Error state: Inline banner: “Availability could not be loaded. Please try again.”

Validation behavior: Date fields validate before search.

Disabled conditions: Hold disabled during hold request or for stale slot.

Navigation behavior: Back returns to discovery filters.

Responsive behavior: Mobile card list; desktop grouped by day.

Accessibility notes: Slot buttons include date/time in accessible label.

Hold and Client Details

Purpose: Collect customer details during 5-minute hold.

Primary user goal: Confirm booking request before hold expires.

Primary action: “Request booking” → confirm hold.

Secondary actions: Release hold; choose another time.

Key components: Hold countdown, slot summary, name/email/phone fields.

Information hierarchy: Countdown, selected slot, form, submit.

Default state: Countdown starts immediately after hold success.

Empty state: “Select a time to hold your booking slot.”

Loading state: Submit button spinner.

Error state: Field errors or banner from UiError.

Validation behavior: On blur and submit.

Disabled conditions: Submit disabled after hold expiry or invalid fields.

Navigation behavior: Back warns that selected hold may be released.

Responsive behavior: Mobile single-column form.

Accessibility notes: Countdown announced politely; errors linked to fields.

Public Confirmation

Purpose: Confirm booking request submission.

Primary user goal: Know what happens next.

Primary action: “Make another booking” → restart flow.

Secondary actions: Return to business website.

Key components: Success icon, pending copy, booking summary.

Information hierarchy: Status message, booking summary, next steps.

Default state: Shows pending status.

Empty state: Not used; page only appears after submission.

Loading state: None after confirmed response.

Error state: Not used; failures stay on previous form.

Validation behavior: None.

Disabled conditions: None.

Navigation behavior: Back does not resubmit booking.

Responsive behavior: Centered confirmation card.

Accessibility notes: Success status announced on route change.

Admin Login

Purpose: Authenticate staff/admin.

Primary user goal: Sign into dashboard.

Primary action: “Sign in” → dashboard.

Secondary actions: None in MVP.

Key components: Company, login, password fields.

Information hierarchy: Login form, error message, submit.

Default state: Empty form.

Empty state: Not applicable.

Loading state: Button spinner.

Error state: “Sign in failed. Check your details and try again.”

Validation behavior: Required fields on submit.

Disabled conditions: Submit disabled until required fields present.

Navigation behavior: Successful login redirects to intended protected route.

Responsive behavior: Centered form.

Accessibility notes: Password field labelled; errors announced.

Admin Dashboard Overview

Purpose: Show operational overview.

Primary user goal: See pending work and schedule status.

Primary action: “Review pending” → approvals queue.

Secondary actions: Open calendar list; open configuration.

Key components: Overview cards, queue counts, recent bookings.

Information hierarchy: Pending count, today’s bookings, navigation.

Default state: Dashboard bootstrap data.

Empty state: “No dashboard activity yet.”

Loading state: Dashboard skeleton.

Error state: “Dashboard data could not be loaded.”

Validation behavior: None.

Disabled conditions: Restricted links hidden or disabled.

Navigation behavior: Sidebar routes.

Responsive behavior: Desktop card grid; tablet stacked.

Accessibility notes: Cards have headings and meaningful labels.

Pending Approvals Queue

Purpose: Process pending booking requests.

Primary user goal: Confirm or cancel bookings.

Primary action: “Confirm” → confirm endpoint.

Secondary actions: Cancel; reschedule; open details.

Key components: Pending table/list, status tags, row actions.

Information hierarchy: Customer/service/time, status, actions.

Default state: Pending bookings sorted by request time.

Empty state: “No pending booking requests.”

Loading state: Table skeleton.

Error state: “Pending bookings could not be loaded.”

Validation behavior: Action confirmation for cancel.

Disabled conditions: Actions disabled during request or without permission.

Navigation behavior: Detail drawer retains queue position.

Responsive behavior: Desktop table; tablet cards.

Accessibility notes: Row action labels include booking identifier.

Calendar List

Purpose: Show scheduled booking list.

Primary user goal: Review and manage upcoming bookings.

Primary action: “Reschedule” → reschedule panel.

Secondary actions: Filter, confirm, cancel if available.

Key components: Date filters, booking list, status tags.

Information hierarchy: Date/time, client/service, status, actions.

Default state: Today and upcoming bookings.

Empty state: “No bookings are scheduled for this view.”

Loading state: List skeleton.

Error state: “Bookings could not be loaded.”

Validation behavior: Filter date validation.

Disabled conditions: Reschedule disabled for cancelled bookings.

Navigation behavior: Filters reflected in URL query where practical.

Responsive behavior: List layout across devices.

Accessibility notes: Status text not color-only.

Reschedule Panel

Purpose: Change booking time.

Primary user goal: Choose a valid new slot.

Primary action: “Save new time” → reschedule endpoint.

Secondary actions: Cancel, search availability.

Key components: Current booking summary, date/time selector, available alternatives.

Information hierarchy: Current time, new options, save action.

Default state: Current booking shown; new date empty.

Empty state: “No alternative times found.”

Loading state: Availability skeleton.

Error state: “Booking could not be rescheduled. Please try again.”

Validation behavior: Submit and inline date validation.

Disabled conditions: Save disabled until new valid time selected.

Navigation behavior: Cancel closes panel without saving.

Responsive behavior: Modal on desktop; full-screen sheet on mobile/tablet.

Accessibility notes: Focus trapped in modal; Escape closes after confirmation if unsaved.

Configuration Dashboard

Purpose: Manage booking setup.

Primary user goal: Create or update configuration records.

Primary action: “Save” → resource-specific endpoint.

Secondary actions: Create new, archive/delete, search records.

Key components: Resource tabs, table, form drawer, module-aware visibility.

Information hierarchy: Resource tab, records, edit form.

Default state: First authorized config resource.

Empty state: “No records yet. Create the first item to enable this booking option.”

Loading state: Table and form skeleton.

Error state: “Configuration could not be loaded.”

Validation behavior: On blur and submit.

Disabled conditions: Save disabled until required fields valid.

Navigation behavior: Unsaved changes warning on tab change.

Responsive behavior: Desktop split view; tablet full-screen drawer.

Accessibility notes: Form fields labelled; destructive actions require confirmation.

Access Denied

Purpose: Block unauthorized routes/actions.

Primary user goal: Understand lack of access.

Primary action: “Back to dashboard” → dashboard.

Secondary actions: “Sign in again” → login.

Key components: Status message, safe navigation.

Information hierarchy: Access message, available action.

Default state: Rendered after permission failure.

Empty state: Not applicable.

Loading state: None.

Error state: “You do not have access to this action.”

Validation behavior: None.

Disabled conditions: Restricted action unavailable.

Navigation behavior: Avoids loop back to denied route.

Responsive behavior: Simple centered card.

Accessibility notes: Error heading receives focus.

Section 10: Interaction Rules

Confirmation rules: Staff booking cancellation and configuration delete/archive require confirmation. Public hold release may use a lightweight confirmation if client details are already entered.

Undo rules: Public filter changes are reversible through back/edit controls. Confirm/cancel/reschedule mutations are not undone client-side; reversal requires another authorized backend action.

Destructive action behavior: Admin destructive actions use modal confirmation with copy: “This action changes booking availability and cannot be undone here.”

Save behavior: Public booking details use local draft preservation; admin configuration uses manual save; booking approvals are immediate explicit actions.

Retry behavior: GET and search failures allow manual retry; auth token renewal may retry once; mutating requests do not retry automatically unless proven safe.

Notification/toast behavior: Success toasts last 4 seconds; warning/error banners remain until dismissed or corrected.

Form validation timing: Required fields validate on blur and submit; cross-field date validation occurs before submit.

Session behavior: Admin protected routes require token; expired token redirects to login with intended route preserved. Public token renewal happens silently when safe.

Back button behavior: Unsaved admin configuration changes trigger warning. Public booking back navigation preserves filters and form draft when safe.

Keyboard behaviors: Tab follows visual order; Enter submits active form when valid; Escape closes modal/drawer after unsaved-change handling.

Section 11: Content and Messaging Guidelines

Tone of voice: Professional, direct, calm, and supportive.

CTA style: Short action verbs: “Find a time,” “Hold this time,” “Request booking,” “Confirm,” “Cancel booking,” “Save.”

Error message principles: State what went wrong and what to do next. Never show raw JSON. Never blame the user.

Empty state principles: Explain the area and suggest the next action.

Helper text principles: One sentence maximum per field.

Trust/safety messaging: Public confirmation must say: “Your booking request has been received and is awaiting confirmation.” Admin cancellation must warn that the action changes booking state.

Prohibited language: “Oops,” “invalid payload,” “bad request,” “failed silently,” “unknown object,” “click here,” “N/A,” “TBD,” “placeholder.”

Section 12: Data Model and Core Objects
Company
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	auto-generated
name	VARCHAR(255)	NOT NULL	Business display name
slug	VARCHAR(120)	UNIQUE, NOT NULL	Used as company identifier in auth
timezone	VARCHAR(64)	NOT NULL	Booking display timezone
created_at	TIMESTAMP	NOT NULL	Creation timestamp

Relationships: Company has many services, providers, locations, categories, bookings, holds, and users.

Lifecycle states: active → suspended → archived.

Retention policy: Retain company records for 24 months after account closure.

Who can access/modify: Admin can view/edit; staff can view; public can only receive safe display data.

Service
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	auto-generated
company_id	UUID	FK → company.id, NOT NULL	Owning company
name	VARCHAR(255)	NOT NULL	Public service name
duration_minutes	INTEGER	NOT NULL	Booking duration
active	BOOLEAN	NOT NULL, DEFAULT true	Public availability flag
created_at	TIMESTAMP	NOT NULL	Creation timestamp

Relationships: Service belongs to company; service has many bookings.

Lifecycle states: draft → active → inactive → archived.

Retention policy: Retain for 24 months after archival.

Who can access/modify: Admin full access; staff view; public view when active.

Provider
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	auto-generated
company_id	UUID	FK → company.id, NOT NULL	Owning company
display_name	VARCHAR(255)	NOT NULL	Provider display label
active	BOOLEAN	NOT NULL, DEFAULT true	Whether provider is bookable
created_at	TIMESTAMP	NOT NULL	Creation timestamp

Relationships: Provider belongs to company; provider has many bookings.

Lifecycle states: active → inactive → archived.

Retention policy: Retain for 24 months after archival.

Who can access/modify: Admin full access; staff view; public view when module and provider are active.

Location
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	auto-generated
company_id	UUID	FK → company.id, NOT NULL	Owning company
name	VARCHAR(255)	NOT NULL	Public location name
address_text	TEXT	NULL	Display address
active	BOOLEAN	NOT NULL, DEFAULT true	Whether location is bookable

Relationships: Location belongs to company; location has many bookings.

Lifecycle states: active → inactive → archived.

Retention policy: Retain for 24 months after archival.

Who can access/modify: Admin full access; staff view; public view only when locations module is enabled.

Category
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	auto-generated
company_id	UUID	FK → company.id, NOT NULL	Owning company
name	VARCHAR(255)	NOT NULL	Category label
sort_order	INTEGER	NOT NULL, DEFAULT 0	Display order
active	BOOLEAN	NOT NULL, DEFAULT true	Whether category is visible

Relationships: Category belongs to company; category groups services.

Lifecycle states: active → inactive → archived.

Retention policy: Retain for 24 months after archival.

Who can access/modify: Admin full access; staff view; public view only when categories module is enabled.

Booking
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	auto-generated
company_id	UUID	FK → company.id, NOT NULL	Owning company
service_id	UUID	FK → service.id, NOT NULL	Booked service
provider_id	UUID	FK → provider.id, NULL	Assigned provider
location_id	UUID	FK → location.id, NULL	Assigned location
category_id	UUID	FK → category.id, NULL	Selected category
status	VARCHAR(32)	NOT NULL	pending, confirmed, cancelled
starts_at	TIMESTAMP	NOT NULL	Booking start
ends_at	TIMESTAMP	NOT NULL	Booking end
client_details	JSONB	NOT NULL	name, email, phone
created_at	TIMESTAMP	NOT NULL	Request timestamp

Relationships: Booking belongs to company and service; optionally belongs to provider, location, and category.

Lifecycle states: pending → confirmed → cancelled; pending → cancelled; confirmed → rescheduled confirmed.

Retention policy: Retain bookings for 24 months after final status.

Who can access/modify: Public can create pending requests; staff/admin can confirm, cancel, and reschedule.

Hold
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	auto-generated
company_id	UUID	FK → company.id, NOT NULL	Owning company
slot_key	VARCHAR(255)	NOT NULL	Backend slot identifier or composite slot key
expires_at	TIMESTAMP	NOT NULL	5 minutes after creation
status	VARCHAR(32)	NOT NULL	active, confirmed, released, expired
created_at	TIMESTAMP	NOT NULL	Hold creation timestamp

Relationships: Hold may become one booking after confirmation.

Lifecycle states: active → confirmed; active → released; active → expired.

Retention policy: Retain hold audit data for 30 days after expiry/release.

Who can access/modify: Public can create, confirm, and release own hold; staff/admin can view resulting booking state if exposed by backend.

AdminUser
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	auto-generated
company_id	UUID	FK → company.id, NOT NULL	Owning company
login	VARCHAR(255)	NOT NULL	Admin login identifier
role	VARCHAR(64)	NOT NULL	admin or staff planning role
active	BOOLEAN	NOT NULL, DEFAULT true	Whether login is usable

Relationships: AdminUser belongs to company.

Lifecycle states: invited → active → disabled.

Retention policy: Retain admin user audit record for 24 months after deactivation.

Who can access/modify: Admin manages; staff can view own profile if backend supports it.

UiConfig
Field	Type	Constraints	Notes
id	UUID	PK, NOT NULL	frontend-derived virtual object
company_id	UUID	FK → company.id, NOT NULL	Owning company
modules	JSONB	NOT NULL	locations, categories, resources, products, add_ons booleans
allowed_entry_points	JSONB	NOT NULL	service, provider, location, category, time
default_entry_point	VARCHAR(64)	NOT NULL	Initial discovery path

Relationships: UiConfig belongs to company and controls visible public UI dimensions.

Lifecycle states: loaded → applied → refreshed.

Retention policy: Cache in frontend session only; backend retention follows configuration records.

Who can access/modify: Public can read safe config; admin can modify underlying backend configuration if authorized.

erDiagram
    Company ||--o{ Service : "has many"
    Company ||--o{ Provider : "has many"
    Company ||--o{ Location : "has many"
    Company ||--o{ Category : "has many"
    Company ||--o{ Booking : "has many"
    Company ||--o{ Hold : "has many"
    Company ||--o{ AdminUser : "has many"
    Service ||--o{ Booking : "booked as"
    Provider ||--o{ Booking : "assigned to"
    Location ||--o{ Booking : "hosted at"
    Category ||--o{ Booking : "classifies"
    Hold ||--o| Booking : "promotes to"
Section 13: Roles and Permissions
Public Customer

Role name: Public Customer

Description: Unauthenticated or public-token user booking a service.

Can view: Public booking portal, enabled services, enabled providers, enabled locations, enabled categories, availability slots.

Can create: Holds and pending booking requests.

Can edit: Own in-progress local draft before submission.

Can delete: Own active hold by releasing it.

Cannot do: Confirm bookings, cancel bookings after submission, reschedule bookings, access admin dashboard, edit configuration.

Approval workflows: Booking requests remain pending until staff/admin confirms.

Staff

Role name: Staff

Description: Operational user managing bookings.

Can view: Dashboard overview, pending bookings, calendar list, booking details.

Can create: Reschedule actions if authorized by backend.

Can edit: Booking status through confirm/cancel/reschedule actions if authorized.

Can delete: No permanent deletes; can cancel bookings where permitted.

Cannot do: Manage all configuration unless granted, bypass backend permissions, access disabled modules.

Approval workflows: Can confirm or cancel pending bookings.

Admin

Role name: Admin

Description: Business administrator with configuration and operational authority.

Can view: All admin dashboard areas for the company.

Can create: Configuration records, booking operations, admin-supported resources.

Can edit: Configuration records and booking state.

Can delete: Archive/delete configuration records where backend supports it; cancel bookings.

Cannot do: Access another company’s data, expose disabled modules to public users, bypass backend validation.

Approval workflows: Can confirm, cancel, and reschedule bookings.

Feature	Public Customer	Staff	Admin
Public portal discovery	✅ Full	✅ View	✅ View
Availability search	✅ Full	✅ View	✅ View
Create hold	✅ Full	❌ None	❌ None
Confirm hold into pending booking	✅ Full	❌ None	❌ None
Direct pending booking request	✅ Full	❌ None	❌ None
Admin dashboard bootstrap	❌ None	✅ Full	✅ Full
Pending approvals queue	❌ None	✅ Full	✅ Full
Confirm booking	❌ None	✅ Full if permitted	✅ Full
Cancel booking	❌ None	✅ Full if permitted	✅ Full
Reschedule booking	❌ None	✅ Full if permitted	✅ Full
Configuration CRUD	❌ None	👁️ View if permitted	✅ Full
Role/permission management	❌ None	❌ None	✅ Full if backend supports it
Section 14: Non-Functional Requirements
Performance

Public portal initial usable load: under 2.5 seconds on broadband and under 4 seconds on mobile 4G.

Availability search visible response: under 2 seconds for p95 successful requests, excluding backend cold starts.

Admin dashboard bootstrap visible response: under 2.5 seconds p95.

Concurrent users target: 100 public booking sessions and 20 admin/staff users during MVP pilot.

Data freshness: availability and pending queue data must be refreshed after every mutating action and on manual refresh.

Accessibility

WCAG level: WCAG 2.1 AA.

Keyboard navigation: All forms, tabs, modals, date selectors, and row actions must be keyboard accessible.

Screen reader support: Form fields, errors, status changes, countdown, and confirmation messages must be announced.

Color contrast: Text and status labels meet AA contrast.

Focus states: Visible focus rings on all interactive controls.

Reliability

Uptime target: 99.5% frontend availability during MVP pilot.

Save integrity: Mutating actions must not be shown as successful until backend success response is received.

Retry behavior: GET/search failures can retry; unsafe POST/DELETE requests require explicit user retry.

Data backup: Backend-owned; frontend stores only temporary drafts and tokens.

Security and Privacy

Authentication method: X-Token: <access_token> for protected admin and public calls.

Authorization model: Backend role and token enforcement; frontend mirrors permissions for usability but does not rely on UI-only security.

Sensitive data handling: Client name, email, and phone are collected only for booking request submission.

Audit logging: Backend-owned; frontend emits non-PII analytics events.

Data retention: Booking 24 months after final status; hold audit 30 days; local customer drafts 24 hours; session token until logout or expiry.

Offline / Poor Network

Offline booking submission is not supported.

Public form draft can persist locally for recovery.

Mutating actions fail gracefully and require retry.

Availability and admin dashboard show connection error banners.

No offline queue for booking mutations in v1.

Scalability

Expected user growth: 100 public sessions and 20 admin users at launch; 500 public sessions and 50 admin users by 6 months; 2,000 public sessions and 150 admin users by 12 months.

Data volume growth: Up to 10,000 bookings per company in first 12 months.

Geographic distribution: Single-region frontend deployment for MVP; timezone display follows backend bootstrap timezone.

Section 15: Edge Cases and Failure Scenarios Matrix
Scenario	Trigger	User Impact	System Behavior	User-Facing Message
Two users try to hold same slot	Race condition	One customer cannot hold slot	Backend rejects one hold; UI refreshes availability	“This time is no longer available. Please choose another time.”
API times out after UI shows progress	Server exceeds timeout threshold	User unsure if complete	Stop spinner; do not mark success; allow refresh/retry	“This is taking longer than expected. Please try again.”
Session expires mid-flow	Token lapses during task	Action blocked	Admin redirects to login; public renews token where safe	“Please sign in to continue.”
User loses internet mid-flow	Network dropped	Save/search fails	Detect network failure; keep local state	“Connection lost. Check your internet and try again.”
User refreshes during submission	Browser refresh mid-POST	Duplicate or lost request risk	Restore draft; do not auto-resubmit mutation	“Your details were restored. Please check and submit again.”
User submits same form twice	Double-tap / impatient re-submit	Potential duplicate	Disable button on first click	“This request is already being submitted.”
Hold expires while customer enters details	5-minute countdown ends	Slot no longer reserved	Disable submit; clear hold ID; keep contact draft	“This hold has expired. Please choose a time again.”
User confirms expired hold	Backend rejects confirm	Booking not created	Normalize UiError; require new hold	“This hold has expired. Please choose a time again.”
Disabled module appears in URL	Deep link to disabled location/category path	User sees unsupported path	Redirect to default allowed entry point	“This booking option is not available.”
Backend returns FastAPI native detail	{"detail": "string"}	Potential raw error exposure	Normalize to UiError	Backend message if safe; fallback: “Something went wrong. Please try again.”
Backend returns standard error envelope	ok:false response	Action fails	Normalize code/message/field/details	Show field or banner message
User invited but account exists	Admin auth/account edge case	Login confusion	Show normalized backend error	“Sign in failed. Check your details and try again.”
Deep-link to deleted content	Booking/config record removed	User sees stale route	Show not found and safe navigation	“This item could not be found.”
User loses permission mid-session	Role changed after login	Action no longer allowed	Backend 403; hide action after refresh	“You do not have access to this action.”
Payment succeeds but confirmation fails	Payment not in v1	Not applicable to MVP	Payment excluded from v1	“Payments are not available in this booking flow.”
File upload exceeds size limit	File upload not in v1	Not applicable	Upload UI not present	“File uploads are not available in this version.”
Imported data contains invalid records	Import not in v1	Not applicable	Import UI not present	“Data import is not available in this version.”
Reschedule target unavailable	Staff selects stale slot	Booking not moved	Backend rejects; UI preserves original booking	“That time is no longer available. Choose another time.”
Admin cancels already confirmed booking	Valid destructive action if backend allows	Booking becomes cancelled	Confirmation modal required	“Booking cancelled.”
Public booking creates pending status	Customer expects instant confirmation	Misunderstanding risk	Show pending copy prominently	“Your booking request has been received and is awaiting confirmation.”
Section 16: Technical Architecture

Platform: Responsive web frontend.

Frontend: TypeScript application using generated contracts/types.ts and contracts/client.ts as API contract references.

Backend: Existing FastAPI Bookings backend.

Database: Backend-owned.

Authentication: Admin and public token endpoints; protected calls use X-Token.

Storage: Frontend session storage for tokens; local storage/session storage for public draft details where safe.

Deployment: Static frontend deployment connected to backend base URL.

Third-party integrations: None required for MVP.

Notification channels: In-app messages only for MVP.

Analytics: Client-side event tracking without PII.

Localization: English only for MVP.

Admin tooling: Admin dashboard, approval queue, calendar list, configuration CRUD.

graph TD
    PublicCustomer[Public Customer Browser] --> PublicFrontend[Public Booking Portal]
    StaffUser[Staff/Admin Browser] --> AdminFrontend[Admin Dashboard]
    PublicFrontend --> ApiClient[Typed API Client + UiError Normalizer]
    AdminFrontend --> ApiClient
    ApiClient --> FastAPI[FastAPI Bookings Backend]
    FastAPI --> Contracts[openapi.json + route-manifest + contract schemas]
    FastAPI --> Database[(Backend Database)]
API contracts
POST /api/public/auth/token
Request:  { "company": "string (required)", "key": "string (required)" }
Response 200: { "ok": true, "data": { "access_token": "string", "token_type": "bearer" } }
Response 400: { "ok": false, "error": { "code": "AUTH_FAILED", "message": "Public authentication failed.", "field": null, "details": null } }
Response 422: { "detail": "Validation error." }

POST /api/admin/auth
Request:  { "company": "string (required)", "login": "string (required)", "password": "string (required)" }
Response 200: { "ok": true, "data": { "access_token": "string", "token_type": "bearer" } }
Response 400: { "ok": false, "error": { "code": "AUTH_FAILED", "message": "Sign in failed.", "field": null, "details": null } }
Response 422: { "detail": "Validation error." }

GET /api/public/ui-config
Request:  X-Token: public access token
Response 200: { "modules": { "locations": "boolean", "categories": "boolean", "resources": "boolean", "products": "boolean", "add_ons": "boolean" }, "bookingFlow": { "allowedEntryPoints": "string[]", "defaultEntryPoint": "string" } }
Response 401: { "ok": false, "error": { "code": "UNAUTHORIZED", "message": "Public session expired.", "field": null, "details": null } }
Response 500: { "detail": "Internal server error." }

GET /api/public/bootstrap
Request:  X-Token: public access token
Response 200: { "ok": true, "data": { "services": "array", "providers": "array", "locations": "array", "categories": "array", "booking_rules": "object", "timezone": "string" }, "meta": {} }
Response 401: { "ok": false, "error": { "code": "UNAUTHORIZED", "message": "Public session expired.", "field": null, "details": null } }
Response 500: { "detail": "Internal server error." }

POST /api/public/search-availability
Request:  { "service_id": "uuid optional", "provider_id": "uuid optional", "location_id": "uuid optional", "category_id": "uuid optional", "desired_time": "ISO datetime optional", "date_from": "ISO date required", "date_to": "ISO date required" }
Response 200: { "ok": true, "data": [ { "slot_id": "string", "service_id": "uuid", "provider_id": "uuid nullable", "location_id": "uuid nullable", "starts_at": "ISO datetime", "ends_at": "ISO datetime" } ], "meta": { "page": 1, "page_size": 25, "total": 100 } }
Response 400: { "ok": false, "error": { "code": "INVALID_SEARCH", "message": "Please check your search details.", "field": null, "details": null } }
Response 422: { "detail": "Validation error." }

POST /api/public/holds
Request:  { "slot_id": "string required", "service_id": "uuid required", "provider_id": "uuid optional", "location_id": "uuid optional", "starts_at": "ISO datetime required", "ends_at": "ISO datetime required" }
Response 200: { "ok": true, "data": { "hold_id": "uuid", "expires_at": "ISO datetime", "status": "active" }, "meta": {} }
Response 409: { "ok": false, "error": { "code": "SLOT_UNAVAILABLE", "message": "This time is no longer available.", "field": null, "details": null } }
Response 422: { "detail": "Validation error." }

POST /api/public/holds/{hold_id}/confirm
Request:  { "client_details": { "name": "string required", "email": "string required", "phone": "string required" } }
Response 200: { "ok": true, "data": { "booking_id": "uuid", "status": "pending" }, "meta": {} }
Response 400: { "ok": false, "error": { "code": "HOLD_EXPIRED", "message": "This hold has expired.", "field": null, "details": null } }
Response 422: { "detail": "Validation error." }

DELETE /api/public/holds/{hold_id}
Request:  X-Token: public access token
Response 200: { "ok": true, "data": { "hold_id": "uuid", "status": "released" }, "meta": {} }
Response 404: { "ok": false, "error": { "code": "HOLD_NOT_FOUND", "message": "This hold could not be found.", "field": null, "details": null } }
Response 422: { "detail": "Validation error." }

POST /api/public/bookings
Request:  { "service_id": "uuid required", "provider_id": "uuid optional", "location_id": "uuid optional", "category_id": "uuid optional", "desired_time": "ISO datetime optional", "client_details": { "name": "string required", "email": "string required", "phone": "string required" } }
Response 200: { "ok": true, "data": { "booking_id": "uuid", "status": "pending" }, "meta": {} }
Response 400: { "ok": false, "error": { "code": "BOOKING_FAILED", "message": "We could not submit your booking request.", "field": null, "details": null } }
Response 422: { "detail": "Validation error." }

GET /api/admin/dashboard/bootstrap
Request:  X-Token: admin access token
Response 200: { "ok": true, "data": { "overview": "object", "pending_bookings": "array", "calendar_items": "array", "permissions": "object" }, "meta": {} }
Response 401: { "ok": false, "error": { "code": "UNAUTHORIZED", "message": "Please sign in to continue.", "field": null, "details": null } }
Response 403: { "ok": false, "error": { "code": "FORBIDDEN", "message": "You do not have access to this action.", "field": null, "details": null } }

POST /api/admin/bookings/{booking_id}/confirm
Request:  X-Token: admin access token
Response 200: { "ok": true, "data": { "booking_id": "uuid", "status": "confirmed" }, "meta": {} }
Response 404: { "ok": false, "error": { "code": "BOOKING_NOT_FOUND", "message": "This booking could not be found.", "field": null, "details": null } }
Response 409: { "ok": false, "error": { "code": "BOOKING_STATE_CHANGED", "message": "This booking has already changed.", "field": null, "details": null } }

POST /api/admin/bookings/{booking_id}/cancel
Request:  X-Token: admin access token
Response 200: { "ok": true, "data": { "booking_id": "uuid", "status": "cancelled" }, "meta": {} }
Response 404: { "ok": false, "error": { "code": "BOOKING_NOT_FOUND", "message": "This booking could not be found.", "field": null, "details": null } }
Response 409: { "ok": false, "error": { "code": "BOOKING_STATE_CHANGED", "message": "This booking has already changed.", "field": null, "details": null } }

POST /api/admin/bookings/{booking_id}/reschedule
Request:  { "starts_at": "ISO datetime required", "ends_at": "ISO datetime required", "provider_id": "uuid optional", "location_id": "uuid optional" }
Response 200: { "ok": true, "data": { "booking_id": "uuid", "status": "confirmed", "starts_at": "ISO datetime", "ends_at": "ISO datetime" }, "meta": {} }
Response 400: { "ok": false, "error": { "code": "RESCHEDULE_FAILED", "message": "Booking could not be rescheduled.", "field": null, "details": null } }
Response 422: { "detail": "Validation error." }
Section 17: Analytics and Tracking
Event	Trigger	Data Captured	Purpose
public_portal_loaded	Public portal shell loads	company, session_id, timestamp	Measure entry volume
ui_config_loaded	UI config successfully applied	enabled_modules, allowed_entry_points, default_entry_point	Validate module-aware behavior
discovery_entry_selected	Customer selects entry point	entry_point, enabled_modules	Understand discovery preferences
availability_search_submitted	Customer searches availability	selected_filter_types, date_range_days	Measure search funnel
availability_results_viewed	Search returns results	result_count, date_range_days	Measure inventory availability
slot_hold_created	Hold succeeds	service_present, provider_present, location_present, expires_in_seconds	Measure hold conversion
hold_expired	Hold countdown expires	elapsed_seconds, current_step	Identify drop-off
booking_request_submitted	Booking request succeeds	booking_status, source_flow	Measure conversion
booking_request_failed	Booking request fails	ui_error_code, field, source_flow	Diagnose errors
admin_login_succeeded	Admin auth succeeds	role_group, company	Measure staff activation
pending_queue_opened	Staff opens approvals queue	pending_count, role_group	Measure operational usage
booking_confirmed	Staff confirms booking	booking_status_before, booking_status_after	Measure approval throughput
booking_cancelled	Staff cancels booking	booking_status_before, booking_status_after	Measure cancellation rate
booking_rescheduled	Staff reschedules booking	date_delta_days, role_group	Measure schedule changes
config_record_saved	Admin saves configuration	resource_type, action_type	Measure configuration usage
access_denied_shown	User hits forbidden route/action	route_id, role_group	Detect permission friction
Section 18: QA Acceptance Criteria
Public authentication and bootstrap

Happy path:

Given valid company and key, When the portal loads, Then the token is stored and booking options appear.

Failure cases:

Given invalid public credentials, When token request fails, Then “We could not start booking. Please refresh and try again.” appears.

Given bootstrap API fails, When loading finishes, Then “Booking options could not be loaded. Please try again.” appears.

Permission case:

Given no public token, When protected public data is requested, Then the client obtains a token before retrying.

Edge cases:

Given UI config disables categories, When bootstrap includes categories, Then category entry is hidden.

Given slow network, When bootstrap exceeds timeout threshold, Then retry UI appears.

Module-aware UI configuration

Happy path:

Given locations and categories are enabled, When UI config loads, Then both entry points appear if allowed.

Failure cases:

Given config request fails, When portal loads, Then “Booking configuration could not be loaded. Please try again.” appears.

Given no allowed entry points, When config is applied, Then “Online booking is not available right now.” appears.

Permission case:

Given public user opens disabled location path, When locations is disabled, Then user is redirected to default entry point.

Edge cases:

Given unknown module key appears, When config is parsed, Then known modules still apply.

Given defaultEntryPoint is disabled, When config applies, Then first allowed entry point is selected.

Flexible multi-entry discovery

Happy path:

Given service entry is enabled, When customer selects service and date range, Then search becomes available.

Failure cases:

Given malformed provider ID, When search is attempted, Then “Please choose a valid option.” appears.

Given no compatible options, When customer filters, Then “No matching booking options are available.” appears.

Permission case:

Given disabled module, When user deep-links to its entry path, Then “This booking option is not available.” appears.

Edge cases:

Given user switches entry points, When filters are incompatible, Then incompatible filters clear safely.

Given desired_time is selected first, When search runs, Then request includes desired_time.

Availability search

Happy path:

Given valid filters and date range, When customer searches, Then slot results appear.

Failure cases:

Given end date before start date, When customer searches, Then “Choose an end date after the start date.” appears.

Given API fails, When search returns error, Then “Availability could not be loaded. Please try again.” appears.

Permission case:

Given public token expired, When search is submitted, Then token renewal occurs or startup error appears.

Edge cases:

Given zero slots, When search succeeds, Then “No available times match your search. Try another date or service.” appears.

Given newer search starts before old search returns, When old response returns, Then old response is ignored.

Slot hold lifecycle

Happy path:

Given available slot, When customer clicks “Hold this time,” Then hold is created and 5-minute countdown starts.

Failure cases:

Given slot is unavailable, When hold request fails, Then “This time could not be held. Please choose another time.” appears.

Given hold expires, When customer submits, Then “This hold has expired. Please choose a time again.” appears.

Permission case:

Given no public token, When hold request is made, Then token is renewed before safe retry.

Edge cases:

Given customer double-clicks hold, When first request is in flight, Then second click is ignored.

Given customer releases hold, When delete succeeds, Then countdown is removed.

Pending booking request submission

Happy path:

Given valid held slot and client details, When customer submits, Then booking is created with pending status and pending confirmation copy appears.

Failure cases:

Given invalid email, When customer submits, Then “Please check your booking details.” appears.

Given server error, When customer submits, Then “We could not submit your booking request. Please try again.” appears.

Permission case:

Given expired public token, When submission starts, Then token renewal occurs if safe.

Edge cases:

Given duplicate click, When request is in flight, Then “This request is already being submitted.” appears.

Given customer refreshes before submit, When page reloads, Then draft details restore.

Admin authentication and dashboard bootstrap

Happy path:

Given valid admin credentials, When user signs in, Then dashboard loads.

Failure cases:

Given wrong password, When user signs in, Then “Sign in failed. Check your details and try again.” appears.

Given dashboard bootstrap fails, When auth succeeds, Then “Dashboard data could not be loaded.” appears.

Permission case:

Given no token, When user opens dashboard route, Then redirect to login.

Edge cases:

Given user double-clicks sign in, When first request is in flight, Then second click is ignored.

Given token expires after login, When dashboard request returns unauthorized, Then user is redirected to login.

Pending approvals queue

Happy path:

Given pending booking, When staff clicks Confirm, Then booking status becomes confirmed and row leaves pending queue.

Failure cases:

Given backend rejects confirm, When staff confirms, Then “Booking could not be confirmed. Please try again.” appears.

Given backend rejects cancel, When staff cancels, Then “Booking could not be cancelled. Please try again.” appears.

Permission case:

Given user lacks confirm permission, When approvals queue renders, Then Confirm action is hidden or disabled.

Edge cases:

Given booking already changed, When staff confirms, Then “This booking has already changed. The list has been refreshed.” appears.

Given network failure, When confirm is attempted, Then row remains pending.

Calendar list and reschedule workflow

Happy path:

Given confirmed booking, When staff selects valid new time and saves, Then booking row updates with new time.

Failure cases:

Given past time, When staff saves, Then “Choose a valid future time.” appears.

Given reschedule API fails, When staff saves, Then “Booking could not be rescheduled. Please try again.” appears.

Permission case:

Given user lacks reschedule permission, When booking row renders, Then reschedule action is hidden or disabled.

Edge cases:

Given cancelled booking, When row renders, Then reschedule is disabled.

Given selected target becomes unavailable, When save occurs, Then original booking remains unchanged.

Configuration CRUD dashboard

Happy path:

Given admin edits valid service configuration, When Save succeeds, Then “Configuration saved.” appears.

Failure cases:

Given required field is blank, When admin saves, Then “Please check the highlighted fields.” appears.

Given save API fails, When admin saves, Then “Configuration could not be saved.” appears.

Permission case:

Given staff lacks config permission, When staff opens config URL, Then access denied appears.

Edge cases:

Given unsaved changes, When admin changes tab, Then unsaved warning appears.

Given disabled module, When config loads, Then corresponding public discovery path is hidden.

Role-scoped access control

Happy path:

Given admin has full permission, When dashboard loads, Then all authorized admin sections appear.

Failure cases:

Given backend returns 401, When protected call runs, Then “Please sign in to continue.” appears.

Given backend returns 403, When action is attempted, Then “You do not have access to this action.” appears.

Permission case:

Given staff lacks configuration permission, When nav renders, Then configuration link is hidden or read-only.

Edge cases:

Given permission changes mid-session, When next request returns 403, Then UI refreshes permissions.

Given unknown role string, When permissions map loads, Then default access is denied.

Unified UiError display system

Happy path:

Given ok:false error envelope, When API client parses it, Then UiError contains code, message, field, details.

Failure cases:

Given malformed error response, When parsing fails, Then “Something went wrong. Please try again.” appears.

Given network failure, When request rejects, Then “Connection lost. Check your internet and try again.” appears.

Permission case:

Given 401 error, When normalized, Then auth-specific recovery runs.

Edge cases:

Given FastAPI detail, When parsed, Then UiError message uses detail if safe.

Given field error, When displayed, Then message appears beside matching field.

Analytics instrumentation

Happy path:

Given customer submits availability search, When request starts, Then availability_search_submitted fires.

Failure cases:

Given analytics endpoint unavailable, When event send fails, Then user flow continues.

Given event includes PII, When sanitizer runs, Then PII is removed before send.

Permission case:

Given admin event fires, When payload builds, Then role_group is included without token.

Edge cases:

Given duplicate submit, When duplicate event fires, Then request_id supports dedupe.

Given user abandons hold, When countdown expires, Then hold_expired fires.

Draft preservation for customer booking details

Happy path:

Given customer enters details, When page refreshes before submit, Then details restore.

Failure cases:

Given storage blocked, When draft save attempts, Then “Your details could not be saved on this device.” appears.

Given draft is older than 24 hours, When restore runs, Then “This saved booking draft has expired.” appears.

Permission case:

Given public token expires, When draft restores, Then token renewal does not erase draft.

Edge cases:

Given hold expires, When draft restores, Then contact fields remain but slot hold clears.

Given booking succeeds, When confirmation appears, Then draft is cleared.

Optimistic UI guards for duplicate submissions

Happy path:

Given user submits once, When request is in flight, Then button disables and spinner appears.

Failure cases:

Given user clicks twice, When second click occurs, Then “This request is already being submitted.” appears.

Given request fails, When error returns, Then retry is enabled.

Permission case:

Given unauthorized action, When user tries to click, Then button is hidden or disabled.

Edge cases:

Given component unmounts mid-request, When response returns, Then stale UI update is prevented.

Given request times out, When spinner stops, Then “This is taking longer than expected. Please try again.” appears.

Section 19: MVP Definition and Release Notes

MVP definition: The smallest releasable frontend that lets customers discover availability, hold a slot, submit a pending booking request, and lets staff/admin authenticate, review pending bookings, confirm/cancel/reschedule bookings, and manage configuration with role-scoped access.

MVP must include:

Public auth token flow

Public UI config and bootstrap

Module-aware public discovery

Availability search

5-minute slot hold creation, confirmation, expiry, and release

Pending booking request copy and status handling

Admin authentication

Dashboard bootstrap

Pending approvals queue

Confirm/cancel booking actions

Calendar list and reschedule workflow

Configuration CRUD dashboard

Role-scoped access control

Unified UiError normalization

Core analytics events

MVP explicitly excludes:

Payment processing

Customer self-confirmation

Native mobile apps

SMS/email automation

Calendar grid view

Customer booking lookup

Bulk import/export

File uploads

Launch risks:

Backend role names may differ from planning roles.

Direct public booking and hold-confirm booking may overlap and require final route-specific UX branching.

Configuration CRUD resource list may expand once full route-manifest is reviewed.

Token expiry duration may require precise timeout copy changes.

Availability race conditions may cause hold failures during busy periods.

Staged rollout strategy:

Internal smoke test: 10 staff-created test bookings with zero uncaught errors.

Pilot release: 1 company, 50 public booking attempts, booking submission error rate under 5%.

Public release: Booking submission error rate under 3%, staff approval success rate over 95%, no critical permission leaks.

Feedback collection:

Public post-submission feedback prompt.

Staff dashboard feedback link.

Analytics funnel review weekly during first 30 days.

Error-code review from UiError analytics twice weekly during pilot.

Definition of Done:

All MVP features implemented against generated contracts.

Disabled modules hidden and not called.

Public booking request copy exactly states pending approval.

Admin protected calls use X-Token.

UiError normalization covers standard error envelope and FastAPI detail.

Duplicate submission guards exist on all mutating actions.

QA scenarios in Section 18 pass.

Accessibility smoke test passes for keyboard navigation, focus states, labels, and error announcements.

No placeholders, “TBD,” “N/A,” or raw backend errors appear in user-facing UI.

The full draft is complete as a first MCD pass. Remaining highest-risk validation items are role-name precision, token expiry duration, exact configuration CRUD endpoint list, and whether direct public booking should be a separate non-hold flow or a fallback to hold confirmation.
