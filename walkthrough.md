# Walkthrough: Backend Fixes for CORS, Database Timeout, and Server-Side Crash

We have successfully resolved the database connection timeout, CORS `MissingAllowOriginHeader` error, and server-side crash when hitting the `/api/admin/services` endpoint.

## Changes Made

1. **Switched Local Database to SQLite**:
   - Modified [.env](file:///f:/Projects/fastapi_bookings/.env) to point the local development environment `DATABASE_URL` to the pre-seeded SQLite database file:
     ```ini
     DATABASE_URL=sqlite:///./fastapi_bookings.db
     ```
   - This bypasses the PostgreSQL service on port `5433` (which is offline due to Docker Desktop being closed), removing the 30-second connection timeout instantly.

2. **Added CORS Protection to Exception Handlers**:
   - Added a helper utility `add_cors_headers` to [main.py](file:///f:/Projects/fastapi_bookings/app/main.py).
   - Wrapped the responses returned by all three custom exception handlers (`http_exception_handler`, `validation_exception_handler`, and `global_exception_handler`) to ensure that even if the server crashes or validation/authentication fails, the browser still receives correct `Access-Control-Allow-*` headers from the list of allowed frontend origins (e.g. `http://localhost:7070`).

---

## Validation and Verification Results

### 1. Integration Test Suite
- Ran all integration tests using `.venv\Scripts\python.exe run_integration_tests.py`.
- **Status**: **PASS** (100% of integration tests succeeded, verifying complete SQLite dialect compatibility).

### 2. Manual Verification
- Hipped `/api/admin/services` with PowerShell requesting origin `http://localhost:7070` and admin token:
  ```powershell
  $r = Invoke-WebRequest -Uri http://localhost:8000/api/admin/services -Headers @{ "X-Token" = "mock-admin-token"; "X-Tenant" = "simplydemo"; "Origin" = "http://localhost:7070" } -Method Get -SkipHttpErrorCheck
  ```
  - **HTTP Status**: `200 OK` (Returned instantly in <1 second)
  - **CORS Headers**:
    - `Access-Control-Allow-Origin`: `http://localhost:7070`
    - `Access-Control-Allow-Credentials`: `true`
  - **Data Payload**: Successfully fetched 11 services.

### 3. Error Case CORS Validation
- Hipped `/api/admin/services` with a non-existent tenant to verify CORS headers on error paths (triggers a `404 NOT FOUND` exception):
  ```powershell
  $r = Invoke-WebRequest -Uri http://localhost:8000/api/admin/services -Headers @{ "X-Token" = "mock-admin-token"; "X-Tenant" = "non-existent-tenant"; "Origin" = "http://localhost:7070" } -Method Get -SkipHttpErrorCheck
  ```
  - **HTTP Status**: `404 Not Found`
  - **CORS Headers**:
    - `Access-Control-Allow-Origin`: `http://localhost:7070`
    - `Access-Control-Allow-Credentials`: `true`
    - `Access-Control-Allow-Methods`: `*`
    - `Access-Control-Allow-Headers`: `*`
  - **Error Payload**: Correctly formatted error payload was successfully parsed by the browser request context.

---

## Service Cards Layout Redesign (Radix Themes size="1" surface variant)

We updated the visual design and layout of the service management tiles in [services.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/services.tsx) to match the Radix Themes card specification:

1. **Radix Themes size="1" Density**:
   - Spacing & Padding: Set padding to compact `p-3` (equivalent to Radix space 3, which is 12px).
   - Corner Radius: Set corner radius to `rounded-lg` (equivalent to Radix default size 1 card radius).
   - Typography: Reduced heading scale to `text-xs` (semi-bold) and price/duration labels to `text-[10px]` to match size 1 layout density.
   - Images: Scaled down service images to a compact `48px` x `48px` (1:1 aspect ratio) with `rounded` corners.

2. **Radix Themes variant="surface" Style**:
   - Replaced old card styles with `bg-card/50 border-border hover:bg-muted/30 hover:border-border/60` to mimic the transparent-background inset border styling of Radix UI "surface" cards.
   - Active/Selected state utilizes primary colored subtle glow borders and background (`border-primary bg-primary/5 ring-1 ring-primary/20`).

3. **Drag Handle & Controls Grouping**:
   - Positioned the `GripVertical` handle at the top-right corner of each card.
   - Placed the **Active** toggle (filled green circle `Circle` or red slash circle `CircleSlash`) and the **Visibility** eye button (`Eye` / `EyeOff`) side-by-side horizontally directly underneath the drag handle.
   - Visibility toggle is disabled and grayed out (`opacity-30 cursor-not-allowed`) when deactivated.

---

## Catalog Header Simplification & Edit Pane Cleanup

We simplified the catalog page layout to reduce visual noise and improve form structure:

1. **List View Default**:
   - Set the catalog sidebar's default view mode to a clean vertical **List View** instead of Grid View.
   - Removed the outer "Services" section title and layout toggles.
   - Positioned the compact icon-only "Add Service" (`Plus` icon) button directly next to the search input.

2. **Detail/Edit Pane Header Cleanups**:
   - Replaced the dynamic service name title/heading from the top card header with a generic static header: **"Service Details"**.
   - Removed the Active status switch and Visible on booking page switch from the top card header area.

3. **Service Name Field Relocation**:
   - Moved the **Service Name** input field down into the **"1. Basic Info"** accordion details form section directly below the header.

4. **Add New Service View Cleanups**:
   - Removed the redundant "Add Service" button from the top-right corner of the creation header.
   - Removed the "Active Status" toggle card/switch from the creation content form.
   - Updated the creation footer to be identical to the edit view: aligned to the bottom-right corner with a standard-themed **Cancel** (outlined) and **Save** (filled) button row.

5. **Right Pane Card Spacer Alignment (Header Flush Fix)**:
   - Added `py-0 gap-0` classes to both the Creation Card and the Edit/Details Card components in the right pane.
   - This overrides the default vertical padding (`py-(--card-spacing)`) and layout gap (`gap-(--card-spacing)`) of the Radix/Shadcn Card container, ensuring the sticky `CardHeader` sits perfectly flush at the very top of the right pane without an unwanted background spacer or gap above it.

---

## Persistent Image Saving, Accordion Refactoring & Checklist Cleanups

We added database column persistence for service image uploads, consolidated form sections, and redesigned the catalog lists:

1. **Persistent Service Image Column**:
   - Added the `image` string column to the `Service` SQLAlchemy model in [service.py](file:///f:/Projects/fastapi_bookings/app/models/service.py).
   - Added the `image` field to the Pydantic schemas in [service.py](file:///f:/Projects/fastapi_bookings/app/schemas/service.py).
   - Generated and executed Alembic database migrations (`2f379fcbe18c_add_image_to_service`) to add the column to the development SQLite database, enabling image uploads to save persistently.

2. **Basic Info Consolidation & Scheduling Accordion Removal**:
   - Moved the **Duration**, **Buffer Before**, and **Buffer After** input fields from the "Scheduling" accordion section into the **"1. Basic Info"** details form section.
   - Deleted the "2. Scheduling" accordion item completely.

3. **Checklists Layout ("One Per Line")**:
   - Replaced all 2-column grid layouts for checking Categories, Providers, Add-ons, and Products with a clean vertical list layout (one item per line) wrapped in a custom card layout with dividing borders.
   - **Providers Checklist Note**: Added a descriptive note explaining matching logic: *"If no providers are selected, this service will be available with all providers by default."*
   - **Add-ons Checklist Columns**: Organized rows in a dual-column layout displaying the checkbox and name on the left, additional duration (e.g. `+15 mins`) in the middle column, and the addon price on the far right.
   - **Products Checklist Columns**: Formatted rows to show the checkbox and name on the left and the product price on the far right.

4. **Creation Modals Integration**:
   - Integrated quick-creation triggers for **Categories**, **Providers**, **Add-ons**, and **Products** within each checklist section using clean **"Add Category"**, **"Add Provider"**, etc. buttons which open entity creation modals.

5. **Resource Requirements List Selector**:
   - Replaced the free-text input field for "Resource Type" inside the Resource Requirements accordion section with a clean `<Select>` dropdown list component.
   - Fetched the list of available physical/logical resources from `/api/admin/resources` on initialization.
   - Derived the distinct list of resource groups (types) from configured database assets.
   - If no resource groups are defined, display a friendly help alert requesting the user to configure groups on the Resources page first.

6. **Catalog Wizard Navigation Redirect Flow**:
   - Replaced simplified entity name-only creation dialogs inside the Services details page with a robust redirect wizard flow:
     - **Save Current Progress**: Clicking **"Add [Entity]"** (Category, Provider, Add-on, Product) first automatically saves the current service details progress (via `handleSave()`).
     - **Redirect with State**: Navigates the browser directly to the full catalog creation module (e.g. `/admin/catalog/products`) passing the current service ID and originating accordion section in React Router location state.
     - **Auto-Open Form & Pre-Check**: Upon loading the target page, if redirect state is present, the interface automatically triggers the full creation panel (`isCreating(true)`), prepopulating any fields (like pre-checking the originating service inside the new Add-on / Product `service_ids` list).
     - **Wizard Return**: Clicking **Save** or **Cancel** on the target page automatically redirects the user back to the originating service's detail page, puts them back in Edit mode, and opens the exact accordion section tab they came from.

7. **Service Array Parsing & Null Safety Fix**:
   - Fixed a `TypeError: services.map is not a function` crash on the Add-ons, Products, and Providers pages.
   - The crash occurred because `/api/admin/services` returns a paginated metadata envelope `{"ok": true, "data": [...]}`. The components were setting the `services` state directly to the entire object instead of the array.
   - Refactored `fetchData` in [add-ons.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/add-ons.tsx), [products.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/products.tsx), and [providers.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/providers.tsx) to check `Array.isArray(servicesData) ? servicesData : servicesData?.data ?? []`.
   - Updated component map renders to use null-safe syntax `(services || []).map(...)` to prevent runtime crashes.

8. **Locations Array Parsing & Null Safety Fix**:
   - Fixed an `Uncaught TypeError: locations.map is not a function` crash on the Products page.
   - The crash occurred because the locations API `/api/admin/locations` also returns the standard paginated envelope `{"ok": true, "data": [...]}`.
   - Updated `fetchData` in [products.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/products.tsx) and [providers.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/providers.tsx) to check and unwrap `locationsData` safely using `Array.isArray(locationsData) ? locationsData : (locationsData?.data ?? [])`.
   - Modified the map renders to use null-safe checking: `(locations || []).map(...)`.

9. **Redesigned Resources Management (Resource Groups & Quantities)**:
   - Redesigned the entire Resources Page ([resources.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/resources.tsx)) to match the requested nested group quantity manager.
   - **Left Sidebar Grouping**: Resources are grouped under their "Resource Group" (`type`), with a caret control to expand and display individual physical assets (e.g., `Massage Room 1`, `Massage Room 2`) underneath.
   - **Accordion Details Panel**:
     - *Name of resource group*: Form binds to "Name of resource type", allowing selection of *One per booking* vs *Shared* (using a capacity-based toggle), *Qty of resources*, and target *Location/Branch*. Saving automatically syncs the list of physical assets in the database by adding/removing resources to match the target quantity.
     - *Connected services*: Lists all catalog services with a checkbox. Checked services show a field to configure the quantity of resources required per booking, which automatically creates/updates the `ServiceResourceRequirement` records in the database.
   - **Backend Schema & Router Sync**:
     - Added nested `requirements` serialization/update Pydantic schemas in `app/schemas/service.py`.
     - Updated `sync_service_relationships` helper and service routes in `app/api/routers/services.py` to sync resource requirements dynamically.
     - Added GET and DELETE endpoints for requirements in `app/api/routers/resources.py` to support full requirements CRUD from the frontend.
10. **Reorganized Left Navigation Sidebar Menu**:
    - Restructured the sidebar menu inside [navigation.ts](file:///f:/Projects/fastapi_bookings/frontend/src/components/navigation.ts) to match the requested layout.
    - Moved **Scheduling** out of the Main menu and placed it directly under **Providers** in the *Catalog* section.
    - Moved **Resources** out of the *Operations* section and placed it directly under **Add-ons** in the *Catalog* section.
    - Swapped **Categories** and **Services** in the *Catalog* menu order.
    - The final *Catalog* menu order is: **Locations**, **Providers**, **Scheduling**, **Services**, **Categories**, **Add-ons**, **Resources**, **Products**, and **Packages**.

11. **Redesigned Locations Details Accordion**:
    - Re-ordered the location details accordion panels to mirror the sidebar layout exactly.
    - Renamed all headers to describe relationship constraints explicitly: **Location Providers**, **Provider Scheduling**, **Location Services**, **Service Categories**, **Service Add-ons**, **Service Resources**, **Service Products**, and **Service Packages**.
    - Implemented layout height overrides (`h-[calc(100vh-65px)]`) with zero container padding to eliminate card-nesting space bugs.
    - Added a smooth scroll mechanism using `scrollBy()` relative to the detail pane scroll container bounds to center and scroll opened sections smoothly to the top of the viewport when clicked.
    - Consolidated vertical padding and reduced panel gap spacing (`space-y-2`) to keep accordion items compact and aesthetic.


