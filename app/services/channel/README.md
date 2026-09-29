# Channel-Neutral Messaging Module

## 1. Purpose & Scope

The **Channel-Neutral Messaging Module** introduces an omnichannel domain model and service foundation for FastAPI Bookings. It decouples the core booking and messaging infrastructure from SMS-specific transports, enabling first-class support for multiple communication channels (SMS, WhatsApp, Instagram, Messenger, WebChat, and Simulated test channels) through a unified data model and API surface.

### What it Owns
- Channel-neutral data models: `ChannelAccount`, `Conversation`, and `Message`.
- Channel and messaging domain enumerations: `ChannelType`, `MessageDirection`, `MessageSource`, `DeliveryStatus`.
- Omnichannel management service: `ChannelService` for account, conversation, and message lifecycles.
- Non-destructive compatibility facade: `ChannelCompatibilityFacade` providing bidirectional bridging between new channel-neutral endpoints and existing single-channel tables (`sms_conversations`, `sms_messages`, `sms_accounts`).
- Channel-neutral administrative API: `GET /api/admin/conversations`, `GET /api/admin/conversations/{id}`, and `POST /api/admin/conversations/{id}/messages`.

### What it Deliberately Avoids
- Does not modify, overwrite, or deprecate existing legacy SMS database tables (`sms_conversations`, `sms_messages`, `sms_bootcamp_settings`).
- Does not alter SMS bootcamp workflows, prompt builders, or background workers.
- Does not take direct ownership of Assistant UI internal state or messaging transport during the Bridge Phase.
- Does not couple channel routing to hardcoded external SMS providers.

---

## 2. Architecture & Key Files

```
app/
├── models/
│   └── conversation.py              # ChannelAccount, Conversation, Message models & enums
├── schemas/
│   ├── channel.py                   # ChannelAccount Pydantic schemas (Create, Update, Out)
│   └── conversation.py              # Conversation & Message schemas, Metadata Contract
├── services/
│   └── channel/
│       ├── __init__.py              # Exports ChannelService & ChannelCompatibilityFacade
│       ├── channel_service.py       # CRUD & business logic for omnichannel operations
│       ├── compatibility_facade.py  # Unified translation bridge between neutral & legacy SMS
│       └── README.md                # Living documentation (this document)
└── api/
    └── routers/
        └── conversations.py         # Admin REST endpoints for conversations & messages
```

### Core Entities

1. **`ChannelAccount` (Table: `channel_accounts`)**:
   Represents a configured inbound/outbound communication inbox (e.g., an SMS line, WhatsApp Business Account, or Instagram direct inbox) owned by a tenant and optionally scoped to a provider.
   - Credentials are encrypted at rest using Fernet with `credentials_encrypted`.
   - Links to optional external Chatwoot inboxes via `chatwoot_inbox_id`.

2. **`Conversation` (Table: `conversations`)**:
   A channel-agnostic conversational thread between a contact identifier (phone number, handle, or user ID) and a channel account.
   - Holds status (`active`, `archived`, `paused`).
   - Retains arbitrary structured integration context via `metadata_payload`.
   - Preserves external references such as `external_conversation_id` (Chatwoot conversation ID).

3. **`Message` (Table: `messages`)**:
   An individual communication item within a conversation.
   - Direction: `INBOUND` or `OUTBOUND`.
   - Source: `CLIENT`, `ASSISTANT`, `OPERATOR`, `SIMULATED`, or `CHATWOOT`.
   - Delivery Status: `PENDING`, `SENT`, `DELIVERED`, `READ`, or `FAILED`.
   - Tool calls and auxiliary metadata preserved in `tool_calls` and `metadata_payload`.

---

## 3. Setup, Configuration & Dependencies

### Environment Configuration
- `SECRET_KEY` / `PUBLIC_API_KEY`: Used as the symmetric encryption key for credential encryption (`Fernet`).
- Standard tenant and database settings configured in `app/core/config.py`.

### Database Tables
- `channel_accounts`
- `conversations`
- `messages`

No destructive migration is needed; tables are discovered by SQLAlchemy `Base.metadata` and can be created via Alembic migration or `Base.metadata.create_all(engine)` in tests.

---

## 4. Core Workflows & Contracts

### Inbound & Outbound Event Lifecycle
```
[Client on Any Channel]
          │
          ▼
   [Channel Inbox]
          │
          ▼
[ChannelService / Facade] ──► Persist `Message` / Update `Conversation`
          │
          ├── (If Legacy SMS) ──► Persists `SmsMessage` & notifies listeners
          └── (If Neutral)    ──► Emits outbox event / audit log
```

### API Contracts

- **List Conversations**: `GET /api/admin/conversations`
  - Query parameters: `provider_id` (optional), `channel` (optional enum), `status` (optional), `limit` (default 50), `offset` (default 0), `include_legacy` (default true).
  - Response: `List[ConversationOut]`
- **Retrieve Conversation Detail**: `GET /api/admin/conversations/{id}`
  - Query parameters: `include_legacy` (default true).
  - Response: `ConversationDetailOut` including ordered `messages: List[MessageOut]`.
- **Send/Record Outbound Message**: `POST /api/admin/conversations/{id}/messages`
  - Request body: `MessageCreate` (`content`, `direction`, `source`, `delivery_status`, `external_message_id`, `tool_calls`, `metadata_payload`).
  - Response: `MessageOut` (HTTP 201 Created).

### Metadata Contract (`ConversationMetadataContract`)
Preserves critical cross-system attributes across transports:
- `tenant_id`: Mandatory tenant isolation key.
- `provider_id`: Optional provider owner ID.
- `channel_type`: Active channel enum (`sms`, `whatsapp`, `instagram`, `messenger`, `webchat`, `simulated`).
- `chatwoot_inbox_id`: External Chatwoot inbox identifier.
- `external_conversation_id`: External Chatwoot or webhook conversation identifier.
- `external_message_id`: External provider message ID (e.g. Telnyx, Twilio, WhatsApp WAMID).
- `delivery_status`: Standardized delivery lifecycle status.
- `source`: Message author type (`client`, `assistant`, `operator`, `simulated`, `chatwoot`).

---

## 5. Data Safety & Isolation

1. **Multi-Tenant Boundaries**:
   Every query in `ChannelService`, `ChannelCompatibilityFacade`, and `conversations.py` is strictly partitioned by `tenant_id`. Cross-tenant lookups raise `404 Not Found` or return `None`.
2. **Credential Privacy**:
   Channel account credentials (`credentials_encrypted`) are encrypted at rest using AES/Fernet encryption derived from `SECRET_KEY`. Raw decrypted credentials are never exposed via API endpoints or logged in traces.
3. **Legacy Preservation**:
   Existing `SmsConversation` and `SmsMessage` rows remain unmodified in their native tables. The facade translates them on read, eliminating any data loss or breaking changes to existing SMS features.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Future Workstream 2 (Worker & Webhook Alignment)**:
  Ingress webhooks (e.g. Chatwoot agentbot, WhatsApp webhooks) currently write directly to `sms_*` tables. Workstream 2 will adapt the inbound webhook pipeline to write through `ChannelService` and `ChannelCompatibilityFacade`.
- **Dual-Write Synchronization**:
  During the Bridge Phase, new conversations created via the neutral API do not backfill into `sms_conversations` unless explicitly routed through SMS adapters.

---

## 7. Verification & Testing Commands

To run the unit and integration tests verifying channel-neutral models, schemas, and endpoints:
```bash
.\.venv\Scripts\python -m pytest tests/test_channel_neutral.py -v
```

To run the baseline SMS test suite and ensure no regressions occurred:
```bash
.\.venv\Scripts\python -m pytest tests/test_sms_foundation.py -v
```
