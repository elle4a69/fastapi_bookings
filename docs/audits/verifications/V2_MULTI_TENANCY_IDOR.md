# Forensic Verification Report: Multi-Tenancy & IDOR Audit (V2)

- **Auditor**: Auditor 2 (Multi-Tenancy & IDOR Forensic Auditor)
- **Target Repository**: `f:\Projects\fastapi_bookings`
- **Reference Document**: `docs/audits/SYSTEM_AUDIT_REPORT.md` (Section 4)
- **Audit Date**: October 2026
- **Status**: Complete & Verified

---

## 1. Executive Summary & Verification Census

An independent forensic inspection was conducted across the database schema, SQLAlchemy ORM metadata, API routing layer, and cryptographic utilities of **FastAPI Bookings** to verify Section 4 of `SYSTEM_AUDIT_REPORT.md`.

### 1.1 Summary of Findings
1. **8 IDOR Vulnerabilities**: All 8 reported vulnerabilities (IDOR-01 through IDOR-08) were inspected line-by-line against current codebase files and are **CONFIRMED**. Every finding represents a genuine, exploitable flaw allowing unauthorized cross-tenant data enumeration, modification, denial-of-service, or secret compromise.
2. **Table Census**: The audit report cited 63 tables (52 with direct `tenant_id`, 11 without). A recursive import of all packages under `app.models` revealed **97 total database tables**.
   - **86 tables** possess a direct `tenant_id` column.
   - **11 child tables** lack a direct `tenant_id` column. The audit report's identification of the 11 child tables is **100% ACCURATE**, though its total table count of 63 was an undercount resulting from a partial module reflection (omitting newer subsystems such as `business_assistant_*`, `sms_bootcamp_*`, and `knowledge_*`).
3. **Global Unique Constraint Collisions**:
   - `invoices.idempotency_key`: **CONFIRMED**. Marked `unique=True` globally rather than scoped to `(tenant_id, idempotency_key)`.
   - `clients.chatwoot_contact_id`: **CONFIRMED**. Marked `unique=True` globally rather than scoped to `(tenant_id, chatwoot_contact_id)`.
   - Additional discovered global uniqueness collisions:
     * `providers.chatwoot_inbox_id`: Marked `unique=True` globally.
     * `device_tokens.token`: Marked `unique=True` globally without mandatory tenant scoping.
     * `webhook_deliveries.idempotency_key`: Marked `unique=True` globally without tenant scoping.
     * `outbox_events.idempotency_key`: Marked `unique=True` globally without tenant scoping.

---

## 2. Database Models & Child Table Architecture Census

### 2.1 Reflection Census Output
A full inspection script walked `app.models` and reflected all tables registered in `Base.metadata.tables`:
- **Total Tables**: 97
- **Tables WITH direct `tenant_id`**: 86
- **Tables WITHOUT direct `tenant_id`**: 11

### 2.2 Forensic Inspection of the 11 Child Tables Lacking Direct `tenant_id`

| Table Name | Model Class | Parent Entity / Foreign Key Chain | Tenant Boundary Derivation | Audit Report Verdict | Forensic Assessment & Notes |
|---|---|---|---|---|---|
| `tenants` | `Tenant` | Root entity | N/A (`id`, `name`, `subdomain`) | N/A (Root) | **CONFIRMED**. Platform root entity. |
| `additional_field_responses` | `AdditionalFieldResponse` | `booking_id -> bookings.id`, `field_id -> additional_fields.id` | Via `bookings.tenant_id` or `additional_fields.tenant_id` | **MEDIUM** | **CONFIRMED**. `app/api/routers/additional_fields.py:166` joins `AdditionalField` for admin reads; however, public submission endpoint does not verify `booking_id`/`client_id` tenant match. |
| `booking_events` | `BookingEvent` | `booking_id -> bookings.id` | Via `bookings.tenant_id` | **LOW** | **CONFIRMED**. Internal booking audit log; accessed only in association with parent booking. |
| `booking_resource_allocations` | `BookingResourceAllocation` | `booking_id -> bookings.id`, `resource_id -> resources.id` | Via `bookings.tenant_id` or `resources.tenant_id` | **MEDIUM** | **CONFIRMED**. Handled inside scheduling services; lacks direct tenant key. |
| `notification_logs` | `NotificationLog` | `booking_id -> bookings.id`, `client_id -> clients.id`, `notification_id -> notifications.id` | Via `bookings.tenant_id` / `notifications.tenant_id` | **LOW** | **CONFIRMED**. Audit log entity for dispatched notifications. |
| `notification_preferences` | `NotificationPreference` | `client_id -> clients.id` | Via `clients.tenant_id` | **MEDIUM** | **CONFIRMED**. Has unique constraint on `client_id`; relies strictly on `Client.tenant_id`. |
| `package_steps` | `PackageStep` | `package_id -> service_packages.id`, `service_id -> services.id` | Via `service_packages.tenant_id` | **HIGH** | **CONFIRMED**. Exploited in **IDOR-04**. Routers execute PK lookups without joining `service_packages`. |
| `service_resource_requirements` | `ServiceResourceRequirement` | `service_id -> services.id`, `resource_id -> resources.id` | Via `services.tenant_id` | **HIGH** | **CONFIRMED**. Exploited in **IDOR-05**. Routers execute PK lookups without joining `services`. |
| `sms_arrival_sessions` | `SmsArrivalSession` | `booking_id -> bookings.id` (Unique), `conversation_id -> sms_conversations.id` | Via `bookings.tenant_id` | **LOW** | **CONFIRMED**. Unique constraint on `booking_id` prevents multi-tenant drift. |
| `sms_delivery_receipts` | `SmsDeliveryReceipt` | `message_id -> sms_messages.id` | Via `sms_messages.tenant_id` | **LOW** | **CONFIRMED**. Telco delivery receipt idempotency tracking. |
| `sms_inbound_receipts` | `SmsInboundReceipt` | `sms_account_id -> sms_accounts.id` | Via `sms_accounts.tenant_id` | **LOW** | **CONFIRMED**. Webhook deduplication log bound to `sms_accounts`. |

---

## 3. Global Unique Constraint Collisions & Tenant Isolation Hazards

### 3.1 `invoices.idempotency_key` Collision Hazard
- **Model**: `app/models/checkout.py:43`
- **Definition**:
  ```python
  idempotency_key = Column(String, unique=True, nullable=True, index=True)
  ```
- **Hazard**: The single-column `unique=True` creates a global unique index `ix_invoices_idempotency_key`. In a multi-tenant platform where different organizations send standard idempotency tokens (e.g., `checkout_101`, payment gateway event IDs, or deterministic checkout session hashes), Tenant B's invoice creation will crash with `IntegrityError` if Tenant A used the same idempotency key.
- **Remediation**:
  Remove `unique=True` from the column and declare a compound table argument:
  ```python
  __table_args__ = (
      UniqueConstraint("tenant_id", "idempotency_key", name="uq_invoices_tenant_idempotency_key"),
  )
  ```

### 3.2 `clients.chatwoot_contact_id` Collision Hazard
- **Model**: `app/models/client.py:34`
- **Definition**:
  ```python
  chatwoot_contact_id = Column(Integer, unique=True, nullable=True)
  ```
- **Hazard**: Chatwoot contact IDs are sequential integers (`1, 2, 3...`) scoped per Chatwoot account. In a multi-tenant deployment where tenants map to separate Chatwoot accounts or shared inboxes, Tenant A will have a Contact ID #12, and Tenant B will also have a Contact ID #12. The second tenant's client sync will trigger an unhandled database unique constraint crash.
- **Remediation**:
  Remove `unique=True` from the column and declare:
  ```python
  __table_args__ = (
      UniqueConstraint("tenant_id", "chatwoot_contact_id", name="uq_clients_tenant_chatwoot_contact_id"),
  )
  ```

### 3.3 Discovered Collisions in Other Tables
1. **`providers.chatwoot_inbox_id`** (`app/models/provider.py`):
   - Defined as `Column(Integer, unique=True, nullable=True)`.
   - When different tenants operate on different Chatwoot accounts, inbox ID numbers will collide globally. Must be scoped with `(tenant_id, chatwoot_inbox_id)`.
2. **`device_tokens.token`** (`app/models/notification.py:119`):
   - `UniqueConstraint("token", name="uq_device_tokens_token")`.
   - Because `tenant_id` is nullable and unauthenticated devices can register tokens, one tenant's user registering a token replaces or collides with another tenant's device.

---

## 4. Line-by-Line Forensic Inspection of 8 IDOR Vulnerabilities

### IDOR-01: Un-scoped Schedule Probing in Public Timeline
- **File**: `app/api/routers/public_timeline.py`
- **Vulnerable Lines**: 74–101 (`/slots`) and 103–126 (`/first-available-day`)
- **Verbatim Code**:
  ```python
  74: @router.get("/slots")
  75: def get_available_slots(
  76:     service_id: DatabaseId,
  77:     provider_id: Optional[int] = None,
  78:     date_from: Optional[date] = None,
  79:     date_to: Optional[date] = None,
  80:     db: Session = Depends(get_db),
  81: ) -> dict:
  82:     """Return available slots for a service over an optional date range."""
  83:     service = db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
  84:     if not service:
  85:         raise HTTPException(status_code=404, detail="Service not found")
  86:     provider = None
  87:     if provider_id:
  88:         provider = db.query(ProviderModel).filter(ProviderModel.id == provider_id).first()
  89:         if not provider:
  90:             raise HTTPException(status_code=404, detail="Provider not found")
  ...
  103: @router.get("/first-available-day")
  104: def get_first_available_day(
  105:     service_id: DatabaseId,
  106:     provider_id: Optional[int] = None,
  107:     db: Session = Depends(get_db),
  108: ) -> dict:
  109:     """Return the first date that has at least one available slot."""
  110:     service = db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
  ```
- **Contrast With Secure Route in Same File**:
  Lines 29–43 of `public_timeline.py` properly enforce tenant boundaries:
  ```python
  @router.get("/schedule/{provider_id}")
  def get_provider_schedule(
      provider_id: DatabaseId,
      db: Session = Depends(get_db),
      current_tenant: Tenant = Depends(get_public_tenant),
  ):
      provider = db.query(ProviderModel).filter(
          ProviderModel.id == provider_id,
          ProviderModel.tenant_id == current_tenant.id,
      ).first()
  ```
- **Forensic Assessment**:
  `get_available_slots` and `get_first_available_day` completely omit `current_tenant: Tenant = Depends(get_public_tenant)`. Any unauthenticated caller on the public internet can enumerate `service_id` and `provider_id` integers across the entire database to harvest competitor provider schedules, working days, and real-time appointment availability.
- **Verdict**: **CONFIRMED** (High Severity IDOR & Information Disclosure).
- **Remediation**:
  Inject `current_tenant: Tenant = Depends(get_public_tenant)` and append `.filter(ServiceModel.tenant_id == current_tenant.id)` and `.filter(ProviderModel.tenant_id == current_tenant.id)`.

---

### IDOR-02: Unauthenticated Cross-Tenant Push Device Overwrites
- **File**: `app/api/routers/devices.py`
- **Vulnerable Lines**: 11–46
- **Verbatim Code**:
  ```python
  11: @router.post("/register", response_model=DeviceTokenResponse)
  12: def register_device(
  13:     device_in: DeviceTokenCreate,
  14:     db: Session = Depends(get_db)
  15: ) -> dict:
  16:     """Register or update a user device token for push notifications."""
  17:     # Check if token already exists
  18:     token_record = db.query(DeviceTokenModel).filter(DeviceTokenModel.token == device_in.token).first()
  19:     
  20:     if token_record:
  21:         # Update existing
  22:         token_record.client_id = device_in.client_id
  23:         token_record.user_id = device_in.user_id
  24:         token_record.platform = device_in.platform
  25:         token_record.device_id = device_in.device_id
  26:         token_record.enabled = device_in.enabled
  27:         token_record.last_seen_at = datetime.utcnow()
  28:         token_record.updated_at = datetime.utcnow()
  29:     else:
  30:         # Create new
  31:         token_record = DeviceTokenModel(
  32:             client_id=device_in.client_id,
  33:             user_id=device_in.user_id,
  34:             token=device_in.token,
  35:             platform=device_in.platform,
  36:             device_id=device_in.device_id,
  37:             enabled=device_in.enabled,
  38:             last_seen_at=datetime.utcnow(),
  39:             created_at=datetime.utcnow(),
  40:             updated_at=datetime.utcnow()
  41:         )
  42:         db.add(token_record)
  ```
- **Forensic Assessment**:
  The route has **zero authentication** and **no tenant dependency**. The model `DeviceToken` has a `tenant_id` column, but `register_device` never populates it (it remains `NULL`). Furthermore, an unauthenticated attacker can submit a device registration payload with an arbitrary `user_id` (admin/staff) or `client_id` belonging to any tenant. If push notifications are dispatched to that user, the notifications will be delivered to the attacker's device.
- **Verdict**: **CONFIRMED** (Critical Severity IDOR & Push Notification Hijack).
- **Remediation**:
  Require either authenticated user context (`get_current_user`), client portal OTP session, or public tenant resolution, and validate that `client_id` / `user_id` belongs to `current_tenant.id`. Always set `token_record.tenant_id = current_tenant.id`.

---

### IDOR-03: Cross-Tenant Denial of Service via Notification Templates
- **File**: `app/api/routers/notifications.py`
- **Vulnerable Lines**: 104–126
- **Verbatim Code**:
  ```python
  104: @router.post("/notification-templates", response_model=NotificationTemplateResponse, tags=["notification-templates"])
  105: def create_notification_template(
  106:     template_in: NotificationTemplateCreate,
  107:     tenant: Tenant = Depends(get_current_tenant),
  108:     db: Session = Depends(get_db),
  109:     current_user = Depends(get_current_admin),
  110: ) -> dict:
  111:     """Create a new notification template."""
  112:     existing = db.query(TemplateModel).filter(TemplateModel.code == template_in.code).first()
  113:     if existing:
  114:         raise HTTPException(
  115:             status_code=status.HTTP_409_CONFLICT,
  116:             detail=f"Notification template code '{template_in.code}' already exists",
  117:         )
  118: 
  119:     tmpl_data = template_in.model_dump()
  120:     tmpl_data["tenant_id"] = tenant.id
  121:     template = TemplateModel(**tmpl_data)
  ```
- **Forensic Assessment**:
  `NotificationTemplate` in `app/models/notification.py:41` defines a compound unique constraint:
  `UniqueConstraint("tenant_id", "code", name="uq_notification_templates_tenant_code")`.
  The database schema is properly designed for multi-tenancy. However, the application-level pre-check at line 112 queries `TemplateModel.code == template_in.code` **globally**, completely omitting `TemplateModel.tenant_id == tenant.id`.
  If Tenant A creates template `"BOOKING_CONFIRMATION"`, any attempt by Tenant B to create a template with code `"BOOKING_CONFIRMATION"` will be rejected with `HTTP 409 Conflict`.
- **Verdict**: **CONFIRMED** (High Severity Cross-Tenant DoS & Code Squatting).
- **Remediation**:
  Change line 112 to:
  ```python
  existing = db.query(TemplateModel).filter(
      TemplateModel.code == template_in.code,
      TemplateModel.tenant_id == tenant.id,
  ).first()
  ```

---

### IDOR-04: IDOR Modification and Deletion of Package Steps
- **File**: `app/api/routers/packages.py`
- **Vulnerable Lines**: 117–145
- **Verbatim Code**:
  ```python
  117: @router.put("/steps/{step_id}", response_model=PackageStepOut)
  118: def update_package_step(
  119:     step_id: DatabaseId,
  120:     step_in: PackageStepUpdate,
  121:     db: Session = Depends(get_db),
  122:     current_user = Depends(get_current_admin),
  123: ) -> PackageStepOut:
  124:     step = db.query(StepModel).filter(StepModel.id == step_id).first()
  125:     if not step:
  126:         raise HTTPException(status_code=404, detail="Package step not found")
  127:     for field, value in step_in.model_dump(exclude_unset=True).items():
  128:         setattr(step, field, value)
  129:     db.commit()
  130:     db.refresh(step)
  131:     return PackageStepOut.model_validate(step)
  132: 
  133: 
  134: @router.delete("/steps/{step_id}", response_model=PackageStepOut)
  135: def delete_package_step(
  136:     step_id: DatabaseId,
  137:     db: Session = Depends(get_db),
  138:     current_user = Depends(get_current_admin),
  139: ) -> PackageStepOut:
  140:     step = db.query(StepModel).filter(StepModel.id == step_id).first()
  141:     if not step:
  142:         raise HTTPException(status_code=404, detail="Package step not found")
  143:     db.delete(step)
  144:     db.commit()
  145:     return PackageStepOut.model_validate(step)
  ```
- **Forensic Assessment**:
  `StepModel` (`package_steps`) is one of the 11 child tables that does not possess a direct `tenant_id` column. Its tenant boundary is derived via its parent package (`package_steps.package_id -> service_packages.id`).
  Lines 124 and 140 query `StepModel` strictly by `StepModel.id == step_id` without joining `ServicePackage`.
  Any authenticated admin belonging to Tenant A can modify or delete package steps belonging to Tenant B simply by passing Tenant B's `step_id`.
- **Verdict**: **CONFIRMED** (High Severity Cross-Tenant Tampering & Deletion).
- **Remediation**:
  Join `PackageModel` and enforce tenant ownership:
  ```python
  step = (
      db.query(StepModel)
      .join(PackageModel, StepModel.package_id == PackageModel.id)
      .filter(
          StepModel.id == step_id,
          PackageModel.tenant_id == current_user.tenant_id,
      )
      .first()
  )
  if not step:
      raise HTTPException(status_code=404, detail="Package step not found")
  ```

---

### IDOR-05: IDOR Deletion and Cross-Tenant Creation of Service Resource Requirements
- **File**: `app/api/routers/resources.py`
- **Vulnerable Lines**: 111–134
- **Verbatim Code**:
  ```python
  111: @router.post("/requirements", response_model=ServiceResourceRequirementOut)
  112: def create_service_resource_requirement(
  113:     requirement_in: ServiceResourceRequirementCreate,
  114:     db: Session = Depends(get_db),
  115:     current_user = Depends(get_current_admin),
  116: ) -> ServiceResourceRequirementOut:
  117:     requirement = SRRModel(**requirement_in.model_dump())
  118:     db.add(requirement)
  119:     db.commit()
  120:     db.refresh(requirement)
  121:     return ServiceResourceRequirementOut.model_validate(requirement)
  122: 
  123: 
  124: 
  125: @router.delete("/requirements/{requirement_id}", response_model=None, status_code=204)
  126: def delete_requirement(
  127:     requirement_id: DatabaseId,
  128:     db: Session = Depends(get_db),
  129:     current_user = Depends(get_current_admin),
  130: ) -> None:
  131:     requirement = db.query(SRRModel).filter(SRRModel.id == requirement_id).first()
  132:     if requirement:
  133:         db.delete(requirement)
  134:         db.commit()
  ```
- **Forensic Assessment**:
  `SRRModel` (`service_resource_requirements`) lacks a direct `tenant_id` column.
  - In `create_service_resource_requirement`: There is no verification that `requirement_in.service_id` or `requirement_in.resource_id` belongs to `current_user.tenant_id`. An admin of Tenant A can link their resources to Tenant B's services or link Tenant B's resources to Tenant A's services.
  - In `delete_requirement`: Line 131 looks up `SRRModel.id == requirement_id` without joining `ServiceModel` or `ResourceModel`. Any admin of Tenant A can delete resource requirement mappings belonging to any other tenant.
- **Verdict**: **CONFIRMED** (High Severity Cross-Tenant Tampering & Deletion).
- **Remediation**:
  1. On create, verify that both the referenced service and resource belong to `current_user.tenant_id`:
     ```python
     service = db.query(ServiceModel).filter(
         ServiceModel.id == requirement_in.service_id,
         ServiceModel.tenant_id == current_user.tenant_id,
     ).first()
     resource = db.query(ResourceModel).filter(
         ResourceModel.id == requirement_in.resource_id,
         ResourceModel.tenant_id == current_user.tenant_id,
     ).first()
     if not service or not resource:
         raise HTTPException(status_code=404, detail="Service or Resource not found")
     ```
  2. On delete, join `ServiceModel` to verify tenant ownership:
     ```python
     requirement = (
         db.query(SRRModel)
         .join(ServiceModel, SRRModel.service_id == ServiceModel.id)
         .filter(
             SRRModel.id == requirement_id,
             ServiceModel.tenant_id == current_user.tenant_id,
         )
         .first()
     )
     if not requirement:
         raise HTTPException(status_code=404, detail="Requirement not found")
     db.delete(requirement)
     db.commit()
     ```

---

### IDOR-06: Cross-Tenant Package Attachment in Checkout
- **File**: `app/api/routers/checkout.py`
- **Vulnerable Lines**: 135–144
- **Verbatim Code**:
  ```python
  111:     for add_on_id in payload.add_on_ids:
  112:         add_on = db.query(AddOn).filter(
  113:             AddOn.id == add_on_id,
  114:             AddOn.active.is_(True),
  115:             AddOn.tenant_id == tenant_id,
  116:         ).first()
  ...
  123:     for product_id in payload.product_ids:
  124:         product = db.query(Product).filter(
  125:             Product.id == product_id,
  126:             Product.active.is_(True),
  127:             Product.tenant_id == tenant_id,
  128:         ).first()
  ...
  135:     if payload.package_id:
  136:         package = db.query(ServicePackage).filter(
  137:             ServicePackage.id == payload.package_id,
  138:             ServicePackage.active.is_(True)
  139:         ).first()
  140:         if not package:
  141:             raise HTTPException(status_code=404, detail="Package not found")
  142:         amount = float(package.price) if package.price is not None else sum(float(step.price or 0.0) for step in package.steps if step.active)
  143:         lines.append({"line_type": "package", "item_id": package.id, "description": package.name, "quantity": 1, "unit_price": amount, "amount": amount})
  144:         subtotal += amount
  ```
- **Forensic Assessment**:
  In `calculate_checkout_total`, `AddOn` (line 115) and `Product` (line 127) explicitly check `tenant_id == tenant_id`.
  However, at line 136, `ServicePackage` queries only `ServicePackage.id == payload.package_id` and `ServicePackage.active.is_(True)`.
  It completely omits `ServicePackage.tenant_id == tenant_id`. A client purchasing items under Tenant A can pass `package_id` belonging to Tenant B, causing Tenant B's package name and pricing to be added to Tenant A's invoice and totals.
- **Verdict**: **CONFIRMED** (Medium-High Severity Cross-Tenant Catalog Tampering).
- **Remediation**:
  Add `ServicePackage.tenant_id == tenant_id` to the query:
  ```python
  package = db.query(ServicePackage).filter(
      ServicePackage.id == payload.package_id,
      ServicePackage.tenant_id == tenant_id,
      ServicePackage.active.is_(True),
  ).first()
  ```

---

### IDOR-07: Global Business Volume Leak in Admin Diagnostics
- **File**: `app/api/routers/diagnostics.py`
- **Vulnerable Lines**: 58–85
- **Verbatim Code**:
  ```python
  58: @router.get("/diagnostics", response_model=DiagnosticsResponse)
  59: def get_system_diagnostics(
  60:     current_admin = Depends(get_current_admin),
  61:     db: Session = Depends(get_db),
  62: ) -> Dict[str, Any]:
  63:     """Return minimal system entity counts and module flags."""
  64:     diagnostics: Dict[str, Any] = {
  65:         "counts": {
  66:             "services": db.query(Service).count(),
  67:             "providers": db.query(Provider).count(),
  68:             "clients": db.query(Client).count(),
  69:             "bookings": db.query(Booking).count(),
  70:             "resources": db.query(Resource).count(),
  71:             "waitlist_entries": db.query(WaitlistEntry).count(),
  72:             "outbox_events": db.query(OutboxEvent).filter(OutboxEvent.processed == False).count(),
  73:         },
  74:         "modules": { ... }
  ```
- **Forensic Assessment**:
  While the endpoint requires admin credentials via `Depends(get_current_admin)`, all 7 table count queries are issued **without tenant filtering**. Because `Service`, `Provider`, `Client`, `Booking`, `Resource`, `WaitlistEntry`, and `OutboxEvent` all have a `tenant_id` column, querying `count()` globally leaks the total platform-wide volume of competitors, total appointment bookings, total customer counts, and pending system jobs to any registered tenant admin.
- **Verdict**: **CONFIRMED** (Medium Severity Cross-Tenant Business Intelligence Leak).
- **Remediation**:
  Filter counts by `current_admin.tenant_id` (unless the user has a global platform superadmin role):
  ```python
  tenant_id = current_admin.tenant_id
  diagnostics: Dict[str, Any] = {
      "counts": {
          "services": db.query(Service).filter(Service.tenant_id == tenant_id).count(),
          "providers": db.query(Provider).filter(Provider.tenant_id == tenant_id).count(),
          "clients": db.query(Client).filter(Client.tenant_id == tenant_id).count(),
          "bookings": db.query(Booking).filter(Booking.tenant_id == tenant_id).count(),
          "resources": db.query(Resource).filter(Resource.tenant_id == tenant_id).count(),
          "waitlist_entries": db.query(WaitlistEntry).filter(WaitlistEntry.tenant_id == tenant_id).count(),
          "outbox_events": db.query(OutboxEvent).filter(OutboxEvent.tenant_id == tenant_id, OutboxEvent.processed == False).count(),
      },
  ```

---

### IDOR-08: Cryptographic Key Misuse for Database Token Encryption
- **File**: `app/models/sms_chatwoot.py`
- **Vulnerable Lines**: 11–23
- **Verbatim Code**:
  ```python
  11: def _chatwoot_token_cipher():
  12:     """Build a stable cipher from the application's configured key.
  13: 
  14:     The previous implementation read ``os.getenv`` directly. That bypassed
  15:     Pydantic's ``.env`` loading and meant a manually launched server could use
  16:     a different key from the application that saved the binding.
  17:     """
  18:     from cryptography.fernet import Fernet
  19: 
  20:     secret = settings.PUBLIC_API_KEY or settings.SECRET_KEY or "fallback-default-secret-key-change-me"
  21:     key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
  22:     return Fernet(base64.urlsafe_b64encode(key_bytes))
  ```
- **Context in `app/core/config.py:85`**:
  ```python
  PUBLIC_API_KEY: str = Field(
      "local-public-key-change-me",
      description="API key used by the public widget to obtain a token",
  )
  ```
- **Forensic Assessment**:
  `PUBLIC_API_KEY` is explicitly documented and distributed to the frontend client booking widget.
  In `_chatwoot_token_cipher()`, `secret = settings.PUBLIC_API_KEY or settings.SECRET_KEY ...` evaluates `PUBLIC_API_KEY` **first**.
  As a result, whenever `PUBLIC_API_KEY` is populated, the Fernet symmetric encryption key for all stored Chatwoot API tokens and webhook secrets is derived from a key distributed publicly in client-side code!
  Anyone with access to the public booking widget or frontend network traffic can derive the Fernet key and decrypt all tenant Chatwoot tokens stored in `sms_chatwoot_bindings`.
  While categorized under Section 4 as an IDOR, it is fundamentally a **Critical Cryptographic Key Derivation Vulnerability** that destroys multi-tenant isolation for Chatwoot integrations.
- **Verdict**: **CONFIRMED** (Critical Severity Cryptographic Key Misuse / Secret Disclosure).
- **Remediation**:
  Never include `settings.PUBLIC_API_KEY` in cipher key derivation. Use a dedicated `settings.CHATWOOT_ENCRYPTION_KEY` or fallback strictly to `settings.SECRET_KEY`:
  ```python
  secret = getattr(settings, "CHATWOOT_ENCRYPTION_KEY", None) or settings.SECRET_KEY
  if not secret or secret in ("changeme", "local-public-key-change-me"):
      raise RuntimeError("A secure SECRET_KEY or CHATWOOT_ENCRYPTION_KEY must be configured for token encryption")
  key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
  return Fernet(base64.urlsafe_b64encode(key_bytes))
  ```

---

## 5. Synthesis Verdict Table & Risk Scoring

| Finding ID | Router / Model File | Primary Defect | Impact Classification | Forensic Verdict |
|---|---|---|---|---|
| **IDOR-01** | `app/api/routers/public_timeline.py:74-126` | Missing `get_public_tenant` on `/slots` & `/first-available-day` | Cross-Tenant Schedule & Availability Enumeration | **CONFIRMED** |
| **IDOR-02** | `app/api/routers/devices.py:11-46` | Unauthenticated route, un-scoped device token registration | Cross-Tenant Push Notification Hijacking | **CONFIRMED** |
| **IDOR-03** | `app/api/routers/notifications.py:104-126` | Global uniqueness pre-check on notification template code | Cross-Tenant Denial of Service / Template Squatting | **CONFIRMED** |
| **IDOR-04** | `app/api/routers/packages.py:117-145` | Un-joined PK lookup on un-scoped `PackageStep` | Cross-Tenant Package Step Modification & Deletion | **CONFIRMED** |
| **IDOR-05** | `app/api/routers/resources.py:111-134` | Un-joined PK lookup on un-scoped `ServiceResourceRequirement` | Cross-Tenant Resource Requirement Deletion/Tampering | **CONFIRMED** |
| **IDOR-06** | `app/api/routers/checkout.py:135-144` | Omission of `tenant_id` in `ServicePackage` filter | Cross-Tenant Package Attachment & Checkout Tampering | **CONFIRMED** |
| **IDOR-07** | `app/api/routers/diagnostics.py:58-74` | Unfiltered `.count()` on 7 tenant-scoped entities | Platform-Wide Business Volume & Metric Leakage | **CONFIRMED** |
| **IDOR-08** | `app/models/sms_chatwoot.py:11-23` | Fernet key derivation using client-facing `PUBLIC_API_KEY` | Platform-Wide Chatwoot Token Decryption & Takeover | **CONFIRMED** |
| **COLL-01** | `app/models/checkout.py:43` | Global `unique=True` on `invoices.idempotency_key` | Cross-Tenant Invoice Creation Integrity Crash | **CONFIRMED** |
| **COLL-02** | `app/models/client.py:34` | Global `unique=True` on `clients.chatwoot_contact_id` | Cross-Tenant Client Chatwoot Sync Collision Crash | **CONFIRMED** |
| **COLL-03** | `app/models/provider.py` | Global `unique=True` on `providers.chatwoot_inbox_id` | Cross-Tenant Provider Chatwoot Sync Collision Crash | **CONFIRMED** |

---

## 6. Recommendations & Implementation Plan

1. **Phase 1: Remediation of IDOR-01 through IDOR-08**:
   - Apply tenant filtering to all 8 router and model locations identified above.
   - For child tables (`package_steps`, `service_resource_requirements`), always enforce joins to parent tables (`service_packages`, `services`).
2. **Phase 2: Database Migration for Global Unique Constraints**:
   - Write an Alembic migration converting single-column unique constraints on `invoices.idempotency_key`, `clients.chatwoot_contact_id`, and `providers.chatwoot_inbox_id` into compound unique constraints scoped by `tenant_id`:
     * `uq_invoices_tenant_idempotency_key`: `(tenant_id, idempotency_key)`
     * `uq_clients_tenant_chatwoot_contact_id`: `(tenant_id, chatwoot_contact_id)`
     * `uq_providers_tenant_chatwoot_inbox_id`: `(tenant_id, chatwoot_inbox_id)`
3. **Phase 3: Cryptographic Cipher Hardening**:
   - Update `_chatwoot_token_cipher()` to eliminate `PUBLIC_API_KEY` from key derivation and require `SECRET_KEY` or a dedicated secret.
4. **Phase 4: Automated Multi-Tenancy Regression Suite**:
   - Introduce automated tests that attempt cross-tenant access for each of the 8 routes to guarantee no regressions in future refactors.
