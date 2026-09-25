# Data Models & Persistence Architecture

## Purpose & Scope
The `app/models/` directory defines the SQLAlchemy ORM models representing the complete domain model for **FastAPI Bookings**.

Key entities:
- **Tenancy**: `Tenant`, `TenantWebsite`, `User` (roles: `owner`, `manager`, `provider`).
- **Catalog**: `Service`, `Provider`, `Location`, `Category`, `AddOn`, `Product`, `Package`.
- **Operations & Scheduling**: `Booking`, `BookingSlotAllocation`, `CalendarNote`, `Client`, `ClientDispute`.
- **Messaging & Outbox**: `SmsConversation`, `SmsMessage`, `SmsOutboundJob`, `SmsAiJob`, `SmsConversationEvent`, `SmsNote`, `SmsChatwootBinding`, `SmsQuickTool`.
- **Financial**: `Invoice`, `Payment`, `TaxRate`, `Promotion`.
- **Intelligence & Bootcamp**: `CuratedMemory`, `KnowledgeProposal`, `LearningEvent`, `SmsBootcampSettings`, `SmsBootcampRun`, `SmsBootcampConversation`, `SmsBootcampMessage`, `AuditLog`.

---

## Architecture & Key Files

```
app/models/
├── __init__.py               # Re-exports all models and registers metadata
├── tenant.py                 # Multi-tenant account, tiers ('starter', 'growth', 'unlimited'), addon quotas
├── tenant_website.py         # Website builder templates, color palettes, and custom sections
├── user.py                   # User auth, hashed password, role hierarchy ('owner', 'manager', 'provider')
├── provider.py               # Staff practitioner, bio, skills, assigned services
├── service.py                # Treatments, durations, pricing, buffer rules
├── booking.py                # Appointment lifecycle, start/end timestamps, status enum
├── calendar_note.py          # Calendar notes, tenant_id partition, provider notes
├── client.py                 # Customer directory, contact details, notes
├── client_dispute.py         # Self-service client disputes, photos, resolutions
├── sms_conversation.py       # SMS thread tracking, autoresponder state, Chatwoot sync
├── sms_outbox.py             # Outbound SMS jobs, AI jobs, conversation events, notes (tenant_id isolated)
├── sms_bootcamp.py           # Bootcamp runs, conversations, messages, settings with composite tenant/provider unique constraint
├── curated_memory.py         # CuratedMemory (active durable facts) and KnowledgeProposal (quarantined/review queue)
└── learning_event.py         # Unified LearningEvent capturing human-in-the-loop signals & diffs
```

---

## Multi-Tenant Partitioning Rules
1. **Mandatory `tenant_id`**: Every business entity table has a foreign key to `tenants.id` with `ondelete="CASCADE"`. All jobs, calendar notes, events, proposals, and bootcamp entities are strictly partitioned by `tenant_id`.
2. **Compound Indexes**: Standard tables feature compound indexes on `(tenant_id, created_at)` or `(tenant_id, status)` for fast tenant-scoped queries.
3. **Discrete Slot Allocations**: `booking_slot_allocations` enforces an explicit unique constraint on `(tenant_id, provider_id, slot_time)` to guarantee 100% double-booking prevention.
4. **Bootcamp Settings Isolation**: `sms_bootcamp_settings` enforces a composite unique constraint on `(tenant_id, provider_id)` allowing both tenant-default and provider-specific assistant personas.

---

## Verification & Migration Commands
```bash
# Verify schema and row parity between source (5432) and dedicated database (5433)
.venv\Scripts\python.exe scripts/verify_db_parity.py

# Apply pending Alembic migrations
.venv\Scripts\python.exe -m alembic upgrade head
```
