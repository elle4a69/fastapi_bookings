# Form & Autosave Audit: Business Settings & Catalog Services

**Target Application:** `F:\Projects\fastapi_bookings`  
**Governing Specification:** `E:\Projects\Playground\VOICE_FIRST_ONBOARDING_IMPLEMENTATION_SPEC.md` (Stage 1 / Task S1)  
**Target Forms Inspected:**
1. Business Settings: `frontend/src/pages/admin/settings/business.tsx`
2. Catalog Services: `frontend/src/pages/admin/catalog/services.tsx`
3. Supporting Architecture: `frontend/src/hooks/use-auto-save.ts`, `frontend/src/components/ui/auto-save-status.tsx`, `frontend/src/components/ui/address-autocomplete.tsx`

---

## 1. Executive Summary & Purpose

This audit establishes the concrete contracts, validation rules, field hierarchies, state management patterns, and autosave trigger mechanics of the real frontend forms used during tenant onboarding in **FastAPI Bookings**.

The voice-first onboarding assistant operates the application visibly. Instead of bypassing the UI or directly mutating database tables via backdoor endpoints, the assistant drives the registered frontend form adapters using the same state mutation and validation pathways as manual users. 

Understanding how controlled React states, debounced timers, and autosave endpoints function in `business.tsx` and `services.tsx` is essential to prevent race conditions, premature persisting of partial speech transcripts, and concurrency conflicts during manual takeover.

---

## 2. Business Settings Form Audit (`settings/business.tsx`)

### 2.1 Component Architecture & Layout

- **Source File:** `frontend/src/pages/admin/settings/business.tsx` (Lines 1–1451)
- **Component:** `export default function BusinessSettings()` (Lines 213–1450)
- **Shell Wrapper:** Wrapped in `<MobilePageShell title="Business Profile" ... actions={<AutoSaveStatus ... />}>` (Lines 1424–1449).
- **Tenant Modular Composition:** Evaluated dynamically via `useTenantModules()` (Line 214):
  - `multipleProvidersEnabled`: When `false`, renders the **Solo Provider Details Card** (`hasSoloProvider = !multipleProvidersEnabled`, Lines 590, 689–1082).
  - `locationsEnabled`: When `false`, renders the **Primary Location Details Card** (`hasPrimaryLocation = !locationsEnabled`, Lines 591, 1088–1420).
  - When both modular flags are enabled (multi-provider, multi-location business), the page only renders the **Business Profile Card** (`renderBusinessProfileCard`, Lines 596–684). In default single-operator / solo studio mode, all three cards are rendered in a responsive 2-column grid (Lines 1434–1446).

### 2.2 State Management Paradigm

- **Form Library:** None. The form operates entirely on **raw controlled React state** (`useState`) paired with multiple lifecycle refs (`useRef`). No Formik, React Hook Form, or TanStack Form is used.
- **Core Entities & State Hooks:**
  1. `profile`: `BusinessProfile | null` (Line 217):
     ```ts
     interface BusinessProfile {
       name: string;
       email: string;
       phone: string;
       address: string;
     }
     ```
  2. `soloProvider`: `SoloProvider | null` (Line 220):
     ```ts
     interface SoloProvider {
       id: number | string;
       name: string;
       email?: string;
       phone?: string;
       description?: string;
       image?: string;
       avatar?: string;
       allow_in_call: boolean;
       allow_out_call: boolean;
       out_call_radius_km: number;
       base_outcall_surcharge: number;
       per_km_fee: number;
       turnaround_buffer_mins: number;
     }
     ```
  3. `primaryLocation`: `PrimaryLocation | null` (Line 224):
     ```ts
     interface PrimaryLocation {
       id: number | string;
       name: string;
       address?: string;
       image?: string;
       timezone?: string;
       is_client_hidden?: boolean;
     }
     ```
  4. Granular Location Address Sub-fields:
     - `locStreet` (Line 226), `locCity` (Line 227), `locState` (Line 228), `locPostalCode` (Line 229).
     - Decomposed from `primaryLocation.address` on load via `parseAddressParts` (Lines 154–195).
     - Composed back into full comma-separated address on save via `composeAddress` (Lines 197–211).
  5. UI & Save State:
     - `loading`: `boolean` (Line 231).
     - `saveState`: `SaveState` (`"idle" | "saving" | "saved" | "failed"`, Line 232).

### 2.3 Autosave Triggers, Timers & Network Operations

The autosave architecture in `business.tsx` does **not** use a unified hook; instead, it implements three separate debounced save loops with a shared concurrent request counter (`activeSaveCountRef`):

1. **Debounce Timers (`600ms`):**
   - Profile: `profileDebounceRef` (Lines 235, 293–300).
   - Provider: `providerDebounceRef` (Lines 236, 342–349).
   - Location: `locationDebounceRef` (Lines 237, 378–385).
   - Typing in any text input calls the corresponding trigger, which clears the previous timeout, sets `setSaveState("saving")`, and schedules execution in **600ms**.
2. **Immediate Saves (Bypassing Debounce):**
   - Address selection in `AddressAutocomplete`: Calls `executeSaveProfile(updated)` (Line 676) or `executeSaveLocation(...)` (Line 1279) directly.
   - Switch toggles (`allow-in-call`, `allow-out-call`, `loc-is-client-hidden`): Directly invoke `executeSaveProvider(updated)` (Lines 930, 951) or `executeSaveLocation(...)` (Line 1392).
   - Timezone Select: Directly invokes `executeSaveLocation(updated, ...)` on `onValueChange` (Line 1231).
   - Image upload or deletion: Directly invokes `executeSaveProvider(...)` (Lines 772, 797) or `executeSaveLocation(...)` (Lines 1156, 1181).
3. **Absence of Blur Triggers:**
   - There are **no `onBlur` listeners** on inputs in `business.tsx`. Autosaves trigger purely from `onChange` after 600ms of inactivity or immediately on discrete control changes.
4. **Network Endpoints & Payloads:**
   - Business Profile: `PUT /api/admin/business-profile` (Lines 274–291).
     - Payload: `{ name: string, email: string | null, phone: string | null, address: string | null }`.
   - Solo Provider: `PUT /api/admin/providers/{id}` (Lines 305–340).
     - Side Effect: If `allow_in_call` or `allow_out_call` is enabled, it first executes a `PUT /api/admin/business-profile` call (Lines 312–316) to ensure tenant-level capabilities permit the provider capabilities.
     - Payload: `{ name, email, phone, description, allow_in_call, allow_out_call, out_call_radius_km, base_outcall_surcharge, per_km_fee, turnaround_buffer_mins, image }`.
   - Primary Location: `PUT /api/admin/locations/{id}` (Lines 354–376).
     - Payload: `{ name, address, timezone, is_client_hidden, image }`.
5. **Save State Coordination:**
   - `activeSaveCountRef` (Line 240) tracks concurrent in-flight requests.
   - Upon completion, `handleSaveSuccess` (Lines 252–261) decrements `activeSaveCountRef`. When the count reaches `0`, `saveState` transitions to `"saved"`, and a 2500ms timeout (`savedTimerRef`, Line 257) resets it to `"idle"`.
   - On error, `handleSaveFailure` (Lines 263–269) sets `saveState = "failed"` and displays a `toast.error(errorMsg)`.
   - `<AutoSaveStatus state={saveState} onRetry={handleRetry} />` (Line 1427) exposes a retry button that re-submits all active entities (Lines 388–395).

### 2.4 Complete Business Settings Field Specification

| Field Name / Control ID | Target Entity & Key | React State Binding | Data Type | Validation Rules (Frontend & Backend) | Save Trigger | API Route & Method |
|---|---|---|---|---|---|---|
| `name` (`#name`) | `Tenant.name` | `profile.name` | `string` | Required, non-empty. Unique across tenants (Backend HTTP 409 collision check). | Debounce 600ms | `PUT /api/admin/business-profile` |
| `email` (`#email`) | `Tenant.email` | `profile.email` | `string \| null` | Optional. Email format if present (`type="email"`). | Debounce 600ms | `PUT /api/admin/business-profile` |
| `phone` (`#phone`) | `Tenant.phone` | `profile.phone` | `string \| null` | Optional. Valid telephone string. | Debounce 600ms | `PUT /api/admin/business-profile` |
| `address` (`#address`) | `Tenant.address` | `profile.address` | `string \| null` | Optional. Triggers background address geocoding on backend if changed. | Immediate on Autocomplete select | `PUT /api/admin/business-profile` |
| `solo-provider-name` (`#solo-provider-name`) | `Provider.name` | `soloProvider.name` | `string` | Required by backend (`ProviderBase.name`). Cannot be blank. | Debounce 600ms | `PUT /api/admin/providers/{id}` |
| `solo-provider-email` (`#solo-provider-email`) | `Provider.email` | `soloProvider.email` | `string \| null` | Optional direct practitioner email. | Debounce 600ms | `PUT /api/admin/providers/{id}` |
| `solo-provider-phone` (`#solo-provider-phone`) | `Provider.phone` | `soloProvider.phone` | `string \| null` | Optional direct practitioner phone. | Debounce 600ms | `PUT /api/admin/providers/{id}` |
| `solo-provider-bio` (`#solo-provider-bio`) | `Provider.description` | `soloProvider.description` | `string \| null` | Optional practitioner biography / specialties. | Debounce 600ms | `PUT /api/admin/providers/{id}` |
| `solo-provider-image-input` | `Provider.image` | `soloProvider.image` | `string (base64) \| null` | Client-side canvas compression: WebP, max 400x400px, max 120KB. | Immediate on upload/delete | `PUT /api/admin/providers/{id}` |
| `allow-in-call` (`#allow-in-call`) | `Provider.allow_in_call` | `soloProvider.allow_in_call` | `boolean` | Boolean flag. Synchronizes tenant capabilities first. | Immediate on change | `PUT /api/admin/providers/{id}` |
| `allow-out-call` (`#allow-out-call`) | `Provider.allow_out_call` | `soloProvider.allow_out_call` | `boolean` | Boolean flag. Enables mobile travel parameters below. | Immediate on change | `PUT /api/admin/providers/{id}` |
| `out-call-radius` (`#out-call-radius`) | `Provider.out_call_radius_km` | `soloProvider.out_call_radius_km` | `number` | Float, `min=0`, step 1. Out-call travel radius in km. Default: 25. | Debounce 600ms | `PUT /api/admin/providers/{id}` |
| `out-call-surcharge` (`#out-call-surcharge`) | `Provider.base_outcall_surcharge` | `soloProvider.base_outcall_surcharge` | `number` | Float, `min=0`, step 0.01. Currency amount. | Debounce 600ms | `PUT /api/admin/providers/{id}` |
| `out-call-per-km` (`#out-call-per-km`) | `Provider.per_km_fee` | `soloProvider.per_km_fee` | `number` | Float, `min=0`, step 0.01. Per-km travel fee. | Debounce 600ms | `PUT /api/admin/providers/{id}` |
| `out-call-buffer` (`#out-call-buffer`) | `Provider.turnaround_buffer_mins` | `soloProvider.turnaround_buffer_mins` | `number` | Integer, `min=0`, step 5. Turnaround buffer between bookings in minutes. | Debounce 600ms | `PUT /api/admin/providers/{id}` |
| `primary-location-name` (`#primary-location-name`) | `Location.name` | `primaryLocation.name` | `string` | Required by backend (`LocationBase.name`). | Debounce 600ms | `PUT /api/admin/locations/{id}` |
| `primary-location-timezone` (`#primary-location-timezone`) | `Location.timezone` | `primaryLocation.timezone` | `string` | Valid IANA timezone string. Default: `"Australia/Melbourne"`. | Immediate on select | `PUT /api/admin/locations/{id}` |
| `loc-autocomplete` / `loc-street`, `city`, `state`, `postcode` | `Location.address` | `locStreet`, `locCity`, `locState`, `locPostalCode` | `string` | Physical studio address used for outcall distance matrix calculations. | Immediate on Autocomplete, 600ms on manual inputs | `PUT /api/admin/locations/{id}` |
| `loc-is-client-hidden` (`#loc-is-client-hidden`) | `Location.is_client_hidden` | `primaryLocation.is_client_hidden` | `boolean` | Boolean flag. Hides exact street address on public booking card until confirmed. | Immediate on change | `PUT /api/admin/locations/{id}` |

### 2.5 Staging Guard Points Needed for Voice Assistant Integration

1. **Premature Auto-save Prevention During Spoken Turn:**
   - When the user is answering a question verbally (e.g., rambling about business description or address), partial transcripts or interim interpretations must **never** be injected directly into inputs while autosave is live.
   - If an assistant stages candidate text into `profile.name` or `soloProvider.description`, the 600ms debounce timer would immediately commit half-spoken or unconfirmed sentences to the production database.
   - Immediate controls (switches, selects) commit instantaneously with zero delay.
2. **Adapter Staging Buffer:**
   - The Stage 2 `BusinessSettingsAdapter` must intercept commands in a distinct `staged` state.
   - While the agent is proposing or editing values, the debounce timers (`profileDebounceRef`, `providerDebounceRef`, `locationDebounceRef`) must be suspended or cancelled.
   - Staged values are rendered visibly in the UI (with a distinctive assistant staging visual cue/highlight) without initiating `PUT` network calls until:
     - The user verbally accepts or doesn't contest the entered details.
     - An explicit `save_form` RPC action is dispatched under valid session delegation.
3. **Multi-Entity Synchronization:**
   - Because `business.tsx` spans three distinct backend tables (`tenants`, `providers`, `locations`), a high-level intent like "Set up my studio Elena Nails in Sydney with mobile services" requires sequencing:
     - Update Profile (`name`, `address`).
     - Update Solo Provider (`name`, `allow_out_call`, `out_call_radius_km`).
     - Update Primary Location (`name`, `address`, `timezone`).
   - The adapter must coordinate these three calls sequentially or via a unified batch save command to avoid partial persistence failures.

---

## 3. Catalog Services Form Audit (`catalog/services.tsx`)

### 3.1 Component Architecture & Master-Detail Layout

- **Source File:** `frontend/src/pages/admin/catalog/services.tsx` (Lines 1–1871)
- **Component:** `export default function ServicesPage()` (Lines 147–1870)
- **Split-Pane Architecture:**
  - **Left Pane (Master List):** (Lines 591–919)
    - Search input (`search`, Line 157) filtering service list (Line 568).
    - Grouped by Category when `categoriesEnabled` is `true` (Lines 716–834) or rendered as a flat list when `categoriesEnabled` is `false` (Lines 644–713).
    - Quick action controls on list items:
      - Active toggle (`handleToggleActive`, Lines 428–436): Green `Circle` vs red `CircleSlash`.
      - Public visibility toggle (`is_visible`, Lines 696–708): `Eye` vs `EyeOff`.
      - Drag-and-drop reordering: Services (`handleDropService`, Lines 503–519) and Categories (`handleDropCategory`, Lines 526–541).
  - **Right Pane (Detail / Edit / Create):** (Lines 921–1850)
    - Discriminated by `rightPaneType`: `"service" | "category"` (Line 165).
    - Handles Service Creation vs Existing Service Editing.

### 3.2 Dual Operational Modes: Creation Mode vs. Autosave Edit Mode

A crucial architectural distinction exists in `services.tsx` between **creation** and **editing**:

1. **Service Creation Mode (`isCreating === true`):** (Lines 1021–1211)
   - Triggered by clicking the "+" button (`handleCreateNew`, Lines 296–305).
   - Resets state to `defaultFormData` (Lines 219–246).
   - **AUTOSAVE IS COMPLETELY DISABLED.**
   - No `useAutoSave` calls are made. State updates strictly mutate local `formData`.
   - Persistence happens **exclusively** when the user clicks the explicit "Save" button in the footer (Lines 1209, 358–398):
     - Validates name: `!formData.name.trim()` -> `toast.error('Name is required')`.
     - Validates delivery mode: `!formData.allow_in_call && !formData.allow_out_call` -> `toast.error('At least one delivery mode (In-Call or Out-Call) must be enabled')`.
     - Calls `POST /api/admin/services`.
     - On success: Appends to `services` list, shows success toast, and transitions automatically into Edit Mode via `handleSelectService(newSvc)` (Line 384).
2. **Existing Service Edit Mode (`selectedServiceId !== null`, `isCreating === false`):** (Lines 1213–1849)
   - Triggered by selecting a service from the master list (`handleSelectService`, Lines 307–343).
   - **AUTOSAVE IS ACTIVELY ENABLED** via the `useAutoSave` hook (Lines 187–202).
   - Every modification to `formData` triggers `useAutoSave`:
     - Text inputs trigger `triggerSave(next)` with a **500ms debounce** (Line 201).
     - Switch toggles, dropdowns, and image changes trigger `triggerSave(next, true)` for **immediate persistence**.
   - Network Operation: `PUT /api/admin/services/{selectedServiceId}`.
   - Header displays `<AutoSaveStatus state={saveState} onRetry={retry} />` (Line 1225).

### 3.3 Accordion Sections in Service Details

The service edit form is organized into collapsible Radix Accordion items controlled by `openSection` state (`details`, `fixed_times`, `categories`, `providers`, `products`, `addons`):

1. **`acc-details` ("Service Details"):** (Lines 1241–1541)
   - `service_name`: Text input (Lines 1247–1257). Required.
   - `image`: Drag-and-drop / upload component (`ImageUpload`, Lines 96–145, 1261–1274). Max 5MB.
   - `description`: Textarea (Lines 1279–1289).
   - `allow_in_call` / `allow_out_call`: Delivery mode switches (Lines 1298–1339). At least one must remain active.
   - Conditional In-Call block: `price`, `buffer_before`, `buffer_after` (Lines 1344–1398).
   - Conditional Out-Call block: `outcall_price` (defaults to `price` if null), `outcall_buffer_before`, `outcall_buffer_after` (Lines 1401–1473).
   - General pricing/duration: `duration` (mins, required), `deposit_amount` ($), `tax_rate_id` (Select: `"none"`, `"gst_10"`, `"gst_free"`, `"pst_5"`, `"hst_13"`).
2. **`acc-fixed_times` ("Service Schedule"):** (Lines 1544–1653)
   - `fixed_start_times`: Comma-separated string of 24h times (e.g., `"09:00, 13:30"`). Rendered as an interactive 48-slot half-hour pill grid (`HALF_HOUR_SLOTS`, Lines 62–73). Selecting/clearing pills immediately autosaves.
   - `has_groups`: Switch toggling group booking.
   - `min_group_size` / `max_group_size`: Integer inputs for group constraints.
3. **`acc-categories` ("Service Categories"):** (Lines 1656–1705)
   - Visible only when `categoriesEnabled` is `true`.
   - Renders available categories with individual `Switch` components. Toggling updates `formData.category_ids` array and immediately autosaves (`triggerSave(next, true)`).
4. **`acc-providers` ("Service Providers"):** (Lines 1709–1761)
   - Visible only when `multipleProvidersEnabled` is `true`.
   - Renders practitioner cards with individual `Switch` components.
   - If `!multipleProvidersEnabled`, the form automatically binds to the primary solo provider (`[String(providers[0].id)]`, Lines 300–302, 312–314, 374–376).
5. **`acc-products` ("Products") & `acc-addons` ("Add-ons"):** (Lines 1764–1838)
   - Enabled conditionally via tenant modules (`productsEnabled`, `addonsEnabled`).
   - Renders item lists with switches mapping to `formData.product_ids` and `formData.addon_ids`.

### 3.4 Complete Catalog Services Field Specification

| Field Name / Control ID | Target Model Key | React State Key | Data Type | Validation Rules (Frontend & Backend) | Save Trigger (Edit Mode) | Save Trigger (Create Mode) |
|---|---|---|---|---|---|---|
| `service_name` (`#service_name`) | `Service.name` | `formData.name` | `string` | Required. Non-empty string. Toast error if blank. | Debounce 500ms | Manual "Save" button |
| `description` (`#description`) | `Service.description` | `formData.description` | `string` | Optional detailed service overview. | Debounce 500ms | Manual "Save" button |
| `image` (ImageUpload) | `Service.image` | `formData.image` | `string \| null` | Optional. Base64 or URL. File upload limit: max 5MB. | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `allow_in_call` (`#allow_in_call`) | `Service.allow_in_call` | `formData.allow_in_call` | `boolean` | Must have at least one mode active (`allow_in_call \|\| allow_out_call`). | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `allow_out_call` (`#allow_out_call`) | `Service.allow_out_call` | `formData.allow_out_call` | `boolean` | Must have at least one mode active. Enables mobile travel buffers. | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `price` (`#price`) | `Service.price` | `formData.price` | `number` | Float / Decimal $\ge 0$. Base price for in-call booking. | Debounce 500ms | Manual "Save" button |
| `buffer_before` (`#buffer_before`) | `Service.buffer_before` | `formData.buffer_before` | `number` | Integer $\ge 0$. Pre-appointment setup/prep buffer in minutes. | Debounce 500ms | Manual "Save" button |
| `buffer_after` (`#buffer_after`) | `Service.buffer_after` | `formData.buffer_after` | `number` | Integer $\ge 0$. Post-appointment clean/pack buffer in minutes. | Debounce 500ms | Manual "Save" button |
| `outcall_price` (`#outcall_price`) | `Service.outcall_price` | `formData.outcall_price` | `number \| null` | Optional. Float $\ge 0$. Defaults to `price` if null when outcall enabled. | Debounce 500ms | Manual "Save" button |
| `outcall_buffer_before` (`#outcall_buffer_before`) | `Service.outcall_buffer_before` | `formData.outcall_buffer_before` | `number` | Integer $\ge 0$. Dedicated mobile travel prep buffer (in addition to road driving time). | Debounce 500ms | Manual "Save" button |
| `outcall_buffer_after` (`#outcall_buffer_after`) | `Service.outcall_buffer_after` | `formData.outcall_buffer_after` | `number` | Integer $\ge 0$. Dedicated mobile pack-up buffer. | Debounce 500ms | Manual "Save" button |
| `duration` (`#duration`) | `Service.duration` | `formData.duration` | `number` | Required. Integer $\ge 1$ minute. Appointment duration. Default: 60. | Debounce 500ms | Manual "Save" button |
| `deposit_amount` (`#deposit_amount`) | `Service.deposit_amount` | `formData.deposit_amount` | `number` | Decimal $\ge 0$. Upfront deposit required to book. Default: 0. | Debounce 500ms | Manual "Save" button |
| `tax_rate_id` (`#tax_rate_id`) | `Service.tax_rate_id` | `formData.tax_rate_id` | `string \| null` | Select dropdown. Values: `none`, `gst_10`, `gst_free`, `pst_5`, `hst_13`. | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `fixed_start_times` | `Service.fixed_start_times` | `formData.fixed_start_times` | `string` | Stored as comma-separated 24h string (`"09:00, 14:00"`). | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `has_groups` | `Service.has_groups` | `formData.has_groups` | `boolean` | Enables group booking constraints (`min_group_size`, `max_group_size`). | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `min_group_size` (`#min_group_size`) | `Service.min_group_size` | `formData.min_group_size` | `number` | Integer $\ge 1$. Minimum attendees required. Default: 1. | Debounce 500ms | Manual "Save" button |
| `max_group_size` (`#max_group_size`) | `Service.max_group_size` | `formData.max_group_size` | `number` | Integer $\ge 1$. Maximum spot limit. Default: 1. | Debounce 500ms | Manual "Save" button |
| `category_ids` | `Service.category_ids` | `formData.category_ids` | `string[]` | Array of category UUIDs/IDs linked to this service. | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `provider_ids` | `Service.provider_ids` | `formData.provider_ids` | `string[]` | Array of provider IDs. In solo mode, defaults to `[String(providers[0].id)]`. | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `product_ids` | `Service.product_ids` | `formData.product_ids` | `string[]` | Array of product IDs attached to service. | Immediate (`triggerSave(next, true)`) | Manual "Save" button |
| `addon_ids` | `Service.addon_ids` | `formData.addon_ids` | `string[]` | Array of add-on IDs attached to service. | Immediate (`triggerSave(next, true)`) | Manual "Save" button |

### 3.5 Modal Dialogs & Sub-Navigation Lifecycle

1. **Inline Entity Creation Dialog (`newEntityDialog`):** (Lines 1852–1866)
   - `<Dialog open={newEntityDialog.open} ...>` allows quick modal creation of categories, providers, add-ons, and products directly without leaving the service editor.
   - Endpoint: `POST /api/admin/{categories|providers|add-ons|products}` (Lines 547–550).
   - Upon creation, the newly created entity is appended to the local collection and selected immediately.
2. **Deep-Link Navigation (`handleSaveAndNavigate`):** (Lines 400–415)
   - When user clicks "Add Category" or "Add Provider" button in accordion tabs (Lines 1701, 1756):
   - First enforces that the service name is valid.
   - Calls `handleSave()` to persist the service state to ensure changes are not lost.
   - Navigates to the dedicated catalog route (`/admin/catalog/categories`, `/admin/catalog/providers`), setting `location.state = { returnToServiceId: savedService.id, section }`.
   - Upon returning, `useEffect` (Lines 253–268) inspects `location.state.selectServiceId`, reselects the service, and expands the relevant accordion section (`setOpenSection(targetSection)`).

### 3.6 Concurrency Conflict Prevention & Manual User Takeover

When a voice assistant is guiding service creation or modification, race conditions can occur if the user simultaneously touches controls:

1. **Keystroke Preemption:**
   - If the user begins typing into an input (e.g. altering price from $120 to $150) while the assistant has an action queued, the user's keystrokes trigger `triggerSave` with a 500ms debounce.
   - Any pending agent commands targeting that field must be cancelled immediately.
   - The field must be tagged with `user-owned` status to prevent subsequent agent overwrite.
2. **Lifecycle State Invalidation:**
   - If the user clicks "Cancel", selects a different service from the left list, or closes the creation card, the active instance context is destroyed.
   - Any agent command bound to the prior `serviceId` or creation draft must fail with `stale_context` or `target_unavailable`.
3. **Out-of-Order Network Request Guarding:**
   - The `useAutoSave` hook maintains `activeRequestIdRef` (Lines 16, 38, 42 of `use-auto-save.ts`). If an earlier request finishes after a later request, its outcome is ignored.
   - The Stage 2 adapter must provide the same request sequencing and reject late responses or older entity revisions.

---

## 4. TypeScript Schemas for Stage 2 Form Adapters

The following schemas provide the exact contracts for the upcoming Stage 2 adapters (`BusinessSettingsAdapter` and `CatalogServicesAdapter`):

```ts
/**
 * Stage 2 Onboarding Form Adapter Contract Schemas
 * Grounded in F:\Projects\fastapi_bookings audit
 */

// ============================================================================
// 1. Common Adapter Infrastructure Types
// ============================================================================

export type FormFieldOrigin = 'user' | 'agent' | 'initial';

export interface FieldMetadata<T> {
  value: T;
  origin: FormFieldOrigin;
  dirty: boolean;
  revision: number;
  lastUpdatedTimestamp: number;
}

export type FormReadinessStatus = 'ready' | 'loading' | 'saving' | 'blocked' | 'unmounted';

export interface FormReadiness {
  status: FormReadinessStatus;
  formId: string;
  activeInstanceId: string | null;
  activeMode: 'view' | 'create' | 'edit';
  errorMessage?: string;
}

export interface StagingGuardState {
  isStagingActive: boolean;
  stagedFields: Record<string, unknown>;
  suspendedDebounceCount: number;
}

// ============================================================================
// 2. Business Settings Adapter Contract (`settings/business.tsx`)
// ============================================================================

export type BusinessSettingsFieldKey =
  | 'business_name'
  | 'business_email'
  | 'business_phone'
  | 'business_address'
  | 'solo_provider_name'
  | 'solo_provider_email'
  | 'solo_provider_phone'
  | 'solo_provider_bio'
  | 'allow_in_call'
  | 'allow_out_call'
  | 'out_call_radius_km'
  | 'base_outcall_surcharge'
  | 'per_km_fee'
  | 'turnaround_buffer_mins'
  | 'primary_location_name'
  | 'primary_location_timezone'
  | 'primary_location_address'
  | 'primary_location_street'
  | 'primary_location_city'
  | 'primary_location_state'
  | 'primary_location_postcode'
  | 'is_client_hidden';

export interface BusinessSettingsState {
  profile: {
    name: FieldMetadata<string>;
    email: FieldMetadata<string>;
    phone: FieldMetadata<string>;
    address: FieldMetadata<string>;
  };
  soloProvider: {
    id: number | string | null;
    name: FieldMetadata<string>;
    email: FieldMetadata<string>;
    phone: FieldMetadata<string>;
    description: FieldMetadata<string>;
    allow_in_call: FieldMetadata<boolean>;
    allow_out_call: FieldMetadata<boolean>;
    out_call_radius_km: FieldMetadata<number>;
    base_outcall_surcharge: FieldMetadata<number>;
    per_km_fee: FieldMetadata<number>;
    turnaround_buffer_mins: FieldMetadata<number>;
  } | null;
  primaryLocation: {
    id: number | string | null;
    name: FieldMetadata<string>;
    address: FieldMetadata<string>;
    timezone: FieldMetadata<string>;
    is_client_hidden: FieldMetadata<boolean>;
    street: FieldMetadata<string>;
    city: FieldMetadata<string>;
    state: FieldMetadata<string>;
    postalCode: FieldMetadata<string>;
  } | null;
}

export interface BusinessSettingsFieldCommand {
  fields: Partial<{
    business_name: string;
    business_email: string;
    business_phone: string;
    business_address: string;
    solo_provider_name: string;
    solo_provider_email: string;
    solo_provider_phone: string;
    solo_provider_bio: string;
    allow_in_call: boolean;
    allow_out_call: boolean;
    out_call_radius_km: number;
    base_outcall_surcharge: number;
    per_km_fee: number;
    turnaround_buffer_mins: number;
    primary_location_name: string;
    primary_location_timezone: string;
    primary_location_address: string;
    is_client_hidden: boolean;
  }>;
  stageOnly?: boolean;
}

// ============================================================================
// 3. Catalog Services Adapter Contract (`catalog/services.tsx`)
// ============================================================================

export type CatalogServicesFieldKey =
  | 'service_name'
  | 'description'
  | 'allow_in_call'
  | 'allow_out_call'
  | 'price'
  | 'buffer_before'
  | 'buffer_after'
  | 'outcall_price'
  | 'outcall_buffer_before'
  | 'outcall_buffer_after'
  | 'duration'
  | 'deposit_amount'
  | 'tax_rate_id'
  | 'fixed_start_times'
  | 'has_groups'
  | 'min_group_size'
  | 'max_group_size'
  | 'category_ids'
  | 'provider_ids'
  | 'product_ids'
  | 'addon_ids';

export interface CatalogServicesState {
  mode: 'list' | 'create' | 'edit';
  selectedServiceId: string | null;
  activeAccordionSection: 'details' | 'fixed_times' | 'categories' | 'providers' | 'products' | 'addons';
  formData: {
    name: FieldMetadata<string>;
    description: FieldMetadata<string>;
    allow_in_call: FieldMetadata<boolean>;
    allow_out_call: FieldMetadata<boolean>;
    price: FieldMetadata<number>;
    buffer_before: FieldMetadata<number>;
    buffer_after: FieldMetadata<number>;
    outcall_price: FieldMetadata<number | null>;
    outcall_buffer_before: FieldMetadata<number>;
    outcall_buffer_after: FieldMetadata<number>;
    duration: FieldMetadata<number>;
    deposit_amount: FieldMetadata<number>;
    tax_rate_id: FieldMetadata<string | null>;
    fixed_start_times: FieldMetadata<string>;
    has_groups: FieldMetadata<boolean>;
    min_group_size: FieldMetadata<number>;
    max_group_size: FieldMetadata<number>;
    category_ids: FieldMetadata<string[]>;
    provider_ids: FieldMetadata<string[]>;
    product_ids: FieldMetadata<string[]>;
    addon_ids: FieldMetadata<string[]>;
  };
  availableCategories: Array<{ id: string; name: string }>;
  availableProviders: Array<{ id: string; name: string }>;
}

export interface CatalogServicesFieldCommand {
  serviceId?: string; // null if creating
  section?: 'details' | 'fixed_times' | 'categories' | 'providers' | 'products' | 'addons';
  fields: Partial<{
    service_name: string;
    description: string;
    allow_in_call: boolean;
    allow_out_call: boolean;
    price: number;
    buffer_before: number;
    buffer_after: number;
    outcall_price: number | null;
    outcall_buffer_before: number;
    outcall_buffer_after: number;
    duration: number;
    deposit_amount: number;
    tax_rate_id: string | null;
    fixed_start_times: string;
    has_groups: boolean;
    min_group_size: number;
    max_group_size: number;
    category_ids: string[];
    provider_ids: string[];
  }>;
  stageOnly?: boolean;
}
```

---

## 5. Audit Conclusions & Stage 2 Implementation Guidelines

1. **Staging Guard Implementation:**
   - In Stage 2, both form adapters must wrap the underlying React states with an explicit `isStagingGuardActive` ref.
   - When an assistant batch field command arrives, the adapter stages the values into state while suppressing debounced network saves.
   - Only upon receiving an authorized `save_form` command or explicit user confirmation does the adapter trigger the live `executeSaveProfile` / `executeSaveProvider` / `executeSaveLocation` or `handleSave` / `triggerSave` calls.
2. **Delivery Modes Invariant:**
   - In both forms, service delivery parameters require at least one delivery mode (`allow_in_call` or `allow_out_call`) to be active. The adapter must validate this invariant before staging values to prevent server rejection.
3. **Category & Provider Binding Invariant:**
   - For solo operators (`!multipleProvidersEnabled`), service creation must automatically bind `provider_ids: [String(providers[0].id)]` exactly as the manual UI does at lines 300–302 and 374–376.
4. **Accordion & Modal Navigation:**
   - In `services.tsx`, fields in collapsed accordion sections are still mounted in the DOM, but their section header should be visually expanded (`handleAccordionOpen`) when the assistant highlights or edits those fields to preserve visible user awareness.
