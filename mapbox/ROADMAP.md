# Master Implementation Roadmap: FastAPI Bookings Front-End

**STATUS: 100% COMPLETE**

Based on the provided Main Context Document (MCD), the application has been broken down into logical, dependency-ordered modules to ensure strict API contract enforcement, type safety, and iterative progress without monolithic degradation. All modules have been successfully executed.

## [x] Module 0: Project Setup & Core Infrastructure
*   **Dependencies:** None
*   **FastAPI Endpoints Consumed:** None (Foundation only)
*   **Key Components/Files to Generate:**
    *   `types.ts` (Global interfaces mirroring Pydantic schemas: `Tenant`, `User`, `UiError`, etc.)
    *   `services/apiClient.ts` (Axios/Fetch wrapper with interceptors for auth and error normalization)
    *   `store/tenantStore.ts` (State management for resolved tenant)
    *   `components/Layout.tsx` (Base application shell)

## [x] Module 1: Tenant Routing, Bootstrap & Auth
*   **Dependencies:** Module 0
*   **FastAPI Endpoints Consumed:**
    *   `POST /api/admin/auth`
    *   `POST /api/public/auth/token`
    *   `GET /api/public/bootstrap`
    *   `GET /api/public/ui-config`
*   **Key Components/Files to Generate:**
    *   `services/authService.ts`
    *   `components/auth/AdminLogin.tsx`
    *   `components/auth/AuthGuard.tsx`
    *   `store/authStore.ts` (Role and permission management)

## [x] Module 2: Public Booking Discovery (Service, Provider, Time)
*   **Dependencies:** Module 1
*   **FastAPI Endpoints Consumed:**
    *   `POST /api/public/search-availability`
*   **Key Components/Files to Generate:**
    *   `components/public/DiscoveryShell.tsx`
    *   `components/public/ServiceCard.tsx`
    *   `components/public/ProviderCard.tsx`
    *   `components/public/TimeSelector.tsx`
    *   `components/public/AddOnSelector.tsx`
    *   `store/bookingFlowStore.ts`

## [x] Module 3: Public Booking Checkout & Review
*   **Dependencies:** Module 2
*   **FastAPI Endpoints Consumed:**
    *   `POST /api/public/management-review-requests`
    *   `POST /api/public/bookings/checkout`
    *   `POST /api/public/bookings`
*   **Key Components/Files to Generate:**
    *   `components/public/ClientDetailsForm.tsx`
    *   `components/public/CheckoutReview.tsx`
    *   `components/public/BookingOutcome.tsx`
    *   `services/bookingService.ts`

## [x] Module 4: Admin Dashboard & Calendar
*   **Dependencies:** Module 1
*   **FastAPI Endpoints Consumed:**
    *   `POST /api/admin/bookings/:booking_id/confirm`
    *   `POST /api/admin/bookings/:booking_id/reschedule`
    *   (Implied GET endpoints for dashboard queues and calendar events)
*   **Key Components/Files to Generate:**
    *   `components/admin/Dashboard.tsx`
    *   `components/admin/CalendarView.tsx`
    *   `components/admin/BookingList.tsx`
    *   `components/admin/BookingDrawer.tsx`

## [x] Module 5: Admin Entity Management (Catalogue)
*   **Dependencies:** Module 1, Module 4
*   **FastAPI Endpoints Consumed:**
    *   `GET/POST/PUT/DELETE /api/admin/services`
    *   `GET/POST/PUT/DELETE /api/admin/providers`
    *   `GET/POST/PUT/DELETE /api/admin/locations`
*   **Key Components/Files to Generate:**
    *   `components/admin/ServiceManager.tsx`
    *   `components/admin/ProviderManager.tsx`
    *   `components/admin/LocationManager.tsx`
    *   `components/admin/RelationshipAccordion.tsx`

## [x] Module 6: Admin Scheduling (Hours & Availability)
*   **Dependencies:** Module 5
*   **FastAPI Endpoints Consumed:**
    *   `PUT /api/admin/providers/:provider_id/availability`
    *   (Implied endpoints for Company Hours)
*   **Key Components/Files to Generate:**
    *   `components/admin/BusinessHours.tsx`
    *   `components/admin/ProviderAvailability.tsx`
    *   `components/admin/IntervalGrid.tsx`

## [x] Module 7: Admin Client Management & Settings
*   **Dependencies:** Module 1
*   **FastAPI Endpoints Consumed:**
    *   `PATCH /api/admin/clients/:client_id/management-approval`
    *   (Implied endpoints for Notifications and Business Profile)
*   **Key Components/Files to Generate:**
    *   `components/admin/ClientManager.tsx`
    *   `components/admin/NotificationSettings.tsx`
    *   `components/admin/BusinessProfile.tsx`

## [x] Module 8: Admin Categories & Locations
*   **Dependencies:** Module 5
*   **FastAPI Endpoints Consumed:**
    *   `GET/POST/PUT /api/admin/categories`
    *   `GET/POST/PUT /api/admin/locations`
*   **Key Components/Files to Generate:**
    *   `components/admin/CategoryManager.tsx`
    *   `components/admin/LocationManager.tsx`

## [x] Module 9: Admin Add-ons
*   **Dependencies:** Module 5
*   **FastAPI Endpoints Consumed:**
    *   `GET/POST/PUT /api/admin/add-ons`
*   **Key Components/Files to Generate:**
    *   `components/admin/AddOnManager.tsx`

## [x] Module 10: Background Operational Freshness (Feature 18)
*   **Dependencies:** Module 4
*   **FastAPI Endpoints Consumed:** Existing Dashboard/Booking endpoints
*   **Key Components/Files to Generate:**
    *   `hooks/usePolling.ts` (Custom hook for background refresh and stale-state handling)
    *   Updates to `Dashboard.tsx`, `BookingList.tsx`, and `CalendarView.tsx`
