# Chatwoot Messaging & Human Handoff Service (`app/services/messaging`)

This module provides external HTTP client capabilities for transitioning Chatwoot conversations to human agents and dispatching outbound bot messages via the Chatwoot REST API v1.

---

## 1. Purpose & Scope

The `app/services/messaging` package owns:
- Headless asynchronous API calls to external Chatwoot instances for human escalation (`handoff_to_human`).
- Direct outbound bot message delivery into active Chatwoot conversation threads (`send_bot_message`).
- Private internal context notes attached during agent handoffs.

This module deliberately avoids local database mutation, session lifecycle management, or SMS transport operations. It acts purely as a stateless external API client invoked by the Chatwoot AgentBot router (`app/api/routers/chatwoot_agentbot.py`).

---

## 2. Architecture & Key Files

```
app/services/messaging/
├── __init__.py           # Package exports: handoff_to_human, send_bot_message
├── chatwoot_handoff.py   # Asynchronous HTTP operations against Chatwoot REST API
└── README.md             # This living architecture and contracts documentation
```

### Key Files & Components
- [`chatwoot_handoff.py`](file:///f:/Projects/fastapi_bookings/app/services/messaging/chatwoot_handoff.py):
  - `handoff_to_human()`: Issues `PATCH /api/v1/accounts/{account_id}/conversations/{conversation_id}` setting status to `"open"` and optionally `POST /messages` with `private=True` to append staff context notes.
  - `send_bot_message()`: Issues `POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/messages` with `message_type="outgoing"` and `content` text.

---

## 3. Setup, Configuration & Dependencies

### External Dependencies
- **httpx**: Asynchronous HTTP client with connection pooling and configurable request timeouts (`timeout=10.0s`).
- **Chatwoot Server**: Live Chatwoot instance accessible over HTTP/HTTPS (default: `http://localhost:4000` or `https://app.chatwoot.com`).

### Configuration Parameters
The service methods accept connection credentials passed down from caller context (such as resolved `SmsChatwootBinding` or `settings`):
- `chatwoot_base_url`: Target Chatwoot endpoint URL.
- `api_access_token`: Account or AgentBot API token.
- `account_id`: Chatwoot account identifier.
- `conversation_id`: Chatwoot conversation identifier.

---

## 4. Core Workflows & Contracts

### 4.1 Human Agent Handoff (`handoff_to_human`)
1. **Status Update**: Calls `PATCH /api/v1/accounts/{account_id}/conversations/{conversation_id}` with `{"status": "open"}` to move the conversation into the human agent queue.
2. **Private Note**: If `note` is provided, issues `POST /messages` with `{"content": note, "private": True, "message_type": "outgoing"}` visible only to staff agents in the Chatwoot dashboard.
3. **Response Envelope**:
   ```python
   {
       "status": "success",
       "conversation_id": conversation_id,
       "account_id": account_id,
       "conversation_status": "open",
       "note_sent": True,
       "conversation": {...},
       "note_details": {...}
   }
   ```

### 4.2 Outbound Bot Message Dispatch (`send_bot_message`)
1. Calls `POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/messages` with `{"content": content, "message_type": "outgoing"}`.
2. Returns parsed Chatwoot message entity payload or raises `httpx.HTTPStatusError` / `httpx.RequestError`.

---

## 5. Data Safety & Isolation

- **Token Protection**: API access tokens are passed via headers (`api_access_token`) and never echoed in log output or error strings.
- **Multi-Tenant Boundaries**: Calls are parameterized with explicit `account_id` resolved from the tenant's authenticated binding.
- **Fail-Safe Exception Handling**: Callers are expected to handle HTTP failures gracefully without aborting database transactions.

---

## 6. Known Issues, Edge Cases & Outstanding Work

1. **Transient Network Errors**: Requests use direct `httpx` calls without automated exponential backoff retries. Network blips raise `httpx.RequestError`.
2. **Rate Limiting**: High-volume burst replies are subject to Chatwoot's API rate limits; callers should debounce turns prior to dispatch.
3. **Orphaned Parallel Service**: Notice that a redundant legacy `app/services/chatwoot.py` exists in the repository root service directory. All new handoff operations use `app/services/messaging/chatwoot_handoff.py`.

---

## 7. Verification & Testing Commands

Execute unit and integration tests verifying Chatwoot messaging and handoff behaviors:
```powershell
# Run AgentBot handoff and messaging tests
python -m pytest tests/test_chatwoot_agentbot.py -k "handoff" -v

# Run full Chatwoot agentbot suite
python -m pytest tests/test_chatwoot_agentbot.py -v
```
