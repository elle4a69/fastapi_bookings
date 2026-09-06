# Chatwoot outbound contract — 4.15.1 synthetic fixture

Package D supports the smallest FastAPI-to-Chatwoot handoff only. It is not a
provider-delivery engine and it does not provide direct-provider fallback.

The contract is exercised solely with an in-process synthetic HTTP boundary.
It must not be pointed at a user-run or production Chatwoot installation.

## Request

For a locally owned intent, FastAPI makes one bounded-timeout request:

```text
POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/messages
api_access_token: <connection-scoped write-only token>
```

The JSON body is exactly:

```json
{
  "content": "message content",
  "message_type": "outgoing",
  "private": false,
  "content_attributes": {
    "fastapi_bookings": {
      "outbound_correlation_id": "opaque-uuid"
    }
  }
}
```

`source_id` is prohibited. In Chatwoot 4.15.1, a caller-populated source ID
can be treated as a channel-originated echo and suppress actual delivery.

The marker is correlation only, not idempotency. It contains no tenant,
customer, booking, channel, or message information.

## Validation and outcomes

The response, signed echo, and bounded `GET .../messages?after=<cursor>`
fixture must retain the exact opaque marker and prove the configured account,
inbox, conversation, outgoing/public/text shape, configured Chatwoot API
`User` sender ID,
and one positive Chatwoot message ID.

An API 4xx marks the intent failed. Timeout, disconnect, redirect, 5xx,
malformed output, or any mismatch becomes terminal `OUTCOME_UNKNOWN`; Package
D never automatically posts it again. It performs at most one authenticated,
bounded GET after the stored pre-send cursor. One match reconciles, zero leaves
it unknown, and multiple matches quarantine it.

The API response and early signed webhook race reconcile by remote message ID.
A conflicting second remote ID quarantines the intent. A copied marker, staff
reply, private note, or AgentBot event is never a FastAPI echo.

## Operational restriction

The observed Chatwoot build was 4.15.1. Before production use, pin the
Chatwoot image/version and rerun this full synthetic contract against that
pinned build. Any Chatwoot version change requires a new contract review and
fixture run before outbound is enabled. No live token, message, webhook, or
production endpoint is part of Package D validation.
