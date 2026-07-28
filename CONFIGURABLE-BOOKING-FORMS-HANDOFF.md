# Configurable Booking Forms and Admin Relationships — Handoff Brief

## Project

- Local project: `F:\Projects\fastapi_bookings`
- Backend: FastAPI
- Local API: `http://127.0.0.1:8000`
- Use the VS Code MCP tools to inspect and modify the project directly.
- Do not ask the user to upload files that already exist in this project unless VS Code access genuinely fails.

## Current backend testing baseline

A full authenticated/stateful Newman sweep has been completed successfully.

Latest verified report:

`F:\Projects\fastapi_bookings\tools\postman-sweep\reports\run-20260712-203358`

Results:

- Total requests: 209
- 200: 178
- 201: 16
- 204: 13
- Unexpected 404: 0
- Unexpected 409: 0
- 422: 0
- 500+: 0
- Newman exit code: 0

The only two non-2xx responses are deliberate Stripe negative tests:

- Checkout Commit: fake checkout session
- Stripe Webhook: unsigned invalid payload

Do not redo the completed generic sweep work unless a new change requires regression testing.

## Primary implementation objective

Implement a configurable, dynamic booking-form/widget system.

The five configurable booking modules are:

1. Location
2. Category
3. Service
4. Provider
5. Time

Each business must be able to create multiple booking-form/widget configurations with:

- arbitrary module order
- optional modules
- predefined location
- predefined category
- predefined service
- predefined provider
- provider-selection modes
- generated embed/widget code
- live preview
- separate configurations for different pages and use cases

## Critical dynamic behaviour

A predefined selection can remove more than its own step.

The widget must perform iterative constraint propagation.

Example:

- Service is predefined.
- That service belongs to one category.
- It is available at one location.
- Only one provider at that location performs it.

The resulting visible flow must be:

`Time → Client details`

The category, location and provider are inferred and hidden.

The algorithm must:

1. Load the booking-form configuration.
2. Apply predefined values.
3. Validate them against the tenant and relationship graph.
4. Calculate compatible records for unresolved modules.
5. Infer any module with exactly one valid option.
6. Recalculate all dependent options.
7. Repeat until no further values can be inferred.
8. Hide predefined, inferred, automatic and disabled modules.
9. Return unresolved modules in the configured order.

Each resolved value should track its source:

- `predefined`
- `customer_selected`
- `inferred`
- `automatic`
- `unresolved`
- `disabled`

Provider-selection modes should include:

- `required`
- `optional`
- `automatic`
- `predefined`

## Booking-flow examples confirmed by screenshots and discussion

### Nothing predefined

Visible flow:

`Location → Category → Service → Provider → Time → Client`

### Location predefined

Visible flow:

`Category → Service → Provider → Time → Client`

All later options must be constrained to that location.

### Location and category predefined

Visible flow:

`Service → Provider → Time → Client`

### Location, category and provider predefined

Visible flow:

`Service → Time → Client`

### Provider predefined

If the provider has one inferred location:

`Category → Service → Time → Client`

If the provider operates at multiple locations, location may remain visible unless also predefined.

### Location, service and provider predefined

Visible flow:

`Time → Client`

### Service predefined with a unique path

If that service resolves to one category, one location and one provider:

`Time → Client`

This is the key correction: one preselection may remove multiple modules through inference.

## Universal-by-default relationship semantics

Relationships must follow this rule:

- No explicit links means universally available.
- Once one or more links exist, availability becomes restricted to the explicitly linked records.

Examples:

- A service with no provider links is available to all otherwise eligible providers.
- Once linked to one or more providers, it is available only to those providers.
- A product with no service links is available to all services.
- Once linked, it is available only to those services.

This rule must be implemented centrally and consistently in both directions.

Do not materialise “universal” by creating rows to every record. The absence of explicit rows is the universal state.

## Admin creation panels and related records

Throughout the admin system:

> Wherever a user can select or connect a record, they must also be able to create a new record immediately and connect it without leaving the current workflow.

Examples:

- Create a service from a provider editor and connect it immediately.
- Create a service from a product editor and connect it immediately.
- Create a client when a telephone search finds no match.
- Edit provider schedules and related records from the provider panel.

Relevant selectable records include:

- clients
- locations
- categories
- providers
- services
- service add-ons
- products

Create-and-connect operations should be transactional so a failed link does not leave an orphaned newly created record.

## Required relationships by module

- **Location** — categories, providers and products
- **Category** — services
- **Provider** — schedule, locations, categories and services
- **Service** — add-ons, products and providers
- **Product** — services

## Existing backend relationship coverage already observed

Existing or substantially present:

- service ↔ provider
- service ↔ category
- service ↔ product
- location ↔ provider
- location ↔ service
- location ↔ category
- provider schedule editing

Likely missing or incomplete:

- persisted booking-form/widget definitions
- arbitrary per-form module order
- per-form optional modules
- per-form predefined values
- dynamic inference/constraint propagation engine
- provider ↔ category
- location ↔ product
- reusable many-to-many service ↔ add-on relationship
- consistent tenant scoping on products/add-ons/associations
- universal-by-default filtering across public selectors
- atomic create-and-connect workflows
- aggregate admin editor endpoints
- widget embed generation

## Existing static UI configuration

`app/api/routers/ui_config.py` currently returns static, tenant-wide configuration. It exposes module flags and booking entry points but does not persist multiple booking forms or per-widget settings.

This should not be stretched into the final design. Introduce a real tenant-scoped booking-form/widget entity.

## Recommended data model

Add a tenant-scoped `BookingForm` model with fields similar to:

```text
id
tenant_id
name
slug
description
active
module_order_json
enabled_modules_json
predefined_values_json
provider_selection_mode
clear_session_on_start
allow_switch_to_ada
widget_type
appearance_json
settings_json
created_at
updated_at
```

A form should support values such as:

```json
{
  "module_order": ["location", "category", "service", "provider", "time"],
  "enabled_modules": {
    "location": true,
    "category": true,
    "service": true,
    "provider": true,
    "time": true
  },
  "predefined_values": {
    "location_id": null,
    "category_id": null,
    "service_id": 12,
    "provider_id": null
  },
  "provider_selection_mode": "automatic"
}
```

## Recommended booking-form endpoints

### Admin

```text
GET    /api/admin/booking-forms
POST   /api/admin/booking-forms
GET    /api/admin/booking-forms/{form_id}
PUT    /api/admin/booking-forms/{form_id}
DELETE /api/admin/booking-forms/{form_id}
POST   /api/admin/booking-forms/{form_id}/duplicate
GET    /api/admin/booking-forms/{form_id}/preview
GET    /api/admin/booking-forms/{form_id}/embed
```

### Public

```text
GET  /api/public/booking-forms/{slug}
POST /api/public/booking-forms/{slug}/resolve
GET  /api/public/booking-forms/{slug}/embed-config
```

The frontend should not reproduce the constraint logic independently. It should render the `visible_modules` and options returned by the resolver.

## Public resolver contract

Example request:

```json
{
  "selections": {
    "location_id": null,
    "category_id": null,
    "service_id": 12,
    "provider_id": null
  }
}
```

Example response:

```json
{
  "ok": true,
  "data": {
    "resolved_context": {
      "location_id": 3,
      "category_id": 4,
      "service_id": 12,
      "provider_id": 7
    },
    "resolution_source": {
      "location": "inferred",
      "category": "inferred",
      "service": "predefined",
      "provider": "inferred"
    },
    "visible_modules": ["time", "client"],
    "options": {}
  }
}
```

When a module remains unresolved, return its valid options.

## Provider modes

### `required`

Provider remains visible unless only one valid provider exists.

### `optional`

Provider remains visible and offers an “Anyone available” option.

### `automatic`

Provider is hidden and assigned from eligible providers during availability or booking confirmation.

### `predefined`

Provider is fixed by the widget configuration.

## Relationship resolver

Create a central service, for example:

`app/services/booking_relationship_resolver.py`

Likely core functions:

```python
get_valid_locations(...)
get_valid_categories(...)
get_valid_services(...)
get_valid_providers(...)
get_valid_products(...)
get_valid_addons(...)
```

All should accept the current context and return only records compatible with every active constraint.

The universal-default rule must live here, not be reimplemented differently in multiple routers.

## Add-on restructuring

The current add-on model belongs directly to one service. That conflicts with reusable selectable add-ons and universal-by-default semantics.

Preferred structure:

```text
add_ons
- id
- tenant_id
- name
- description
- price
- duration
- active

service_add_ons
- id
- tenant_id
- service_id
- add_on_id
```

Migration must preserve existing add-on/service assignments.

## Tenant scoping to verify or add

At minimum, inspect and correct tenant ownership for:

```text
products.tenant_id
add_ons.tenant_id
service_products.tenant_id
service_add_ons.tenant_id
provider_categories.tenant_id
location_products.tenant_id
```

All association routes must verify both records belong to the current tenant.

## Missing relationship tables likely required

```text
provider_categories
location_products
service_add_ons
```

Potential provider ↔ product should only be added if actual product availability needs provider-specific restriction.

## Inline create-and-connect backend support

The frontend can call create then link, but the backend should expose transactional support.

Examples:

```text
POST /api/admin/providers/{provider_id}/services/create-and-link
POST /api/admin/products/{product_id}/services/create-and-link
POST /api/admin/locations/{location_id}/categories/create-and-link
POST /api/admin/locations/{location_id}/products/create-and-link
```

A generic internal service such as:

`app/services/related_record_service.py`

should:

1. validate tenant ownership
2. create the target record
3. flush to obtain the ID
4. create the relationship
5. commit once
6. roll back everything on failure

Avoid arbitrary dynamic table access from client-supplied model names. Whitelist supported source/target combinations.

## Aggregate admin editor responses

Useful endpoints may include:

```text
GET /api/admin/providers/{provider_id}/editor
GET /api/admin/services/{service_id}/editor
GET /api/admin/locations/{location_id}/editor
GET /api/admin/categories/{category_id}/editor
GET /api/admin/products/{product_id}/editor
GET /api/admin/clients/{client_id}/editor
```

These can return the current record, its relationships, schedule where applicable, and available records for connection.

## Existing SimplyBook widget reference

The extracted widget examples are located at:

`F:\Projects\fastapi_bookings\SimplyBook-Widget-Code-Extract.md`

This file has already been successfully read through VS Code.

Useful configuration patterns found include:

```json
{
  "app_config": {
    "clear_session": 0,
    "allow_switch_to_ada": 0,
    "predefined": {
      "location": "1",
      "category": "1"
    }
  }
}
```

The file also contains:

- iframe widget examples
- button widgets
- reviews widgets
- React widget loading via `runtime.js` and `app.js`
- container IDs
- theme settings
- timeline settings
- datepicker settings
- predefined-value configuration
- generated embed-code patterns

The linked SimplyBook JavaScript is external. Do not copy proprietary/minified code blindly. Use the configuration and behavioural patterns as a reference for this project’s own implementation.

## Validation requirements

Reject booking-form configurations when:

- module order contains duplicates
- an unknown module is supplied
- time is disabled
- a preset ID belongs to another tenant
- a preset combination is incompatible
- provider mode is `predefined` without a provider
- provider cannot perform the predefined service
- location/provider/service combination is invalid
- a disabled module remains unresolved and is required
- slug duplicates another form in the same tenant

Preview should surface warnings such as:

```text
This configuration resolves to no valid providers.
This service is offered at multiple locations, but the location module is disabled.
Provider selection is required, but multiple valid providers remain.
```

## Required tests

### Relationship resolver unit tests

- zero links returns all eligible records
- first explicit link restricts results
- restrictions apply bidirectionally
- multiple constraints intersect correctly
- cross-tenant records are excluded

### Constraint propagation tests

- nothing predefined → all modules visible
- location predefined → location hidden
- service predefined and unique path → only time visible
- service predefined with multiple providers → provider remains visible
- provider predefined with one location → location inferred
- provider predefined with multiple locations → location remains visible
- category inferred from service
- automatic provider mode hides provider
- optional provider mode includes “Anyone available”

### Postman workflow folder

Add a dedicated folder such as:

`Configurable Booking Forms`

It should prove:

1. No presets
2. Predefined location
3. Predefined location and category
4. Predefined service with a unique provider/location/category path
5. Predefined service with multiple providers
6. Automatic provider mode
7. Universal-default behaviour with no links
8. Explicit restriction after adding the first link
9. Inline create-and-connect

After implementation, rerun the full authenticated regression sweep.

## Recommended implementation sequence

1. Audit existing models, schemas, routers, services and migrations.
2. Produce a precise present/partial/missing matrix based on the actual code.
3. Add the persisted booking-form/widget model and migration.
4. Add admin CRUD, duplicate, preview and embed endpoints.
5. Complete missing relationship models and tenant scoping.
6. Build one central universal-default relationship resolver.
7. Build the iterative booking-context constraint-propagation engine.
8. Add public widget bootstrap and resolve endpoints.
9. Integrate availability and automatic-provider assignment.
10. Add transactional create-and-connect backend workflows.
11. Add unit and integration tests.
12. Add dedicated Postman workflows and rerun the regression sweep.

## Instruction for the next chat

Do not merely provide another conceptual plan.

Start by opening this file and inspecting the existing implementation through VS Code. Produce the exact present/partial/missing matrix from the current codebase, then proceed with implementation in controlled stages. Preserve tenant isolation and keep the existing passing regression baseline intact.
