# GPT-Live Business Assistant

## Purpose & scope

This isolated module creates authenticated GPT-Live WebRTC sessions for an existing Business Assistant conversation. It owns the server-side OpenAI request boundary and the immutable handoff configuration. It deliberately does not expose API keys, proxy media, create bookings, send SMS, or change the legacy Realtime voice integration.

## Architecture & key files

- `session_config.json` preserves the approved GPT-Live session configuration without server-added defaults.
- `runtime.py` validates bounded SDP, submits `POST /v1/live/sessions`, and returns only the opaque session ID and SDP answer.
- `router.py` exposes the tenant/user-scoped `POST /api/admin/gpt-live/conversations/{conversation_id}/sessions` boundary.

## Setup, configuration & dependencies

`OPENAI_API_KEY` is loaded only on the FastAPI server and must be a project-scoped OpenAI API key with GPT-Live access. The module reuses `BUSINESS_ASSISTANT_TURN_TIMEOUT_SECONDS` and `BUSINESS_ASSISTANT_REALTIME_SDP_MAX_BYTES` for request and SDP limits. It uses the existing Business Assistant conversation table solely to enforce tenant and owner scope; it adds no tables or migrations.

## Core workflows & contracts

The browser creates a WebRTC SDP offer and sends `{ "sdp": "..." }` to the authenticated route. The server sends exactly `{session, transport:{type:"webrtc",sdp}}` upstream and returns `{session_id, sdp}`. The browser applies the answer, waits for `session.started` on `oai-events`, and never repeats startup configuration. Session close occurs on the data channel; media remains attached until the terminal `session.closed` event.

## Data safety & isolation

The upstream key is held only in `GPTLiveRuntime`; it is neither accepted from nor returned to the browser, stored, traced, or logged. The route requires a tenant owner and confirms that the conversation belongs to that tenant and user before the upstream request. SDP is size-bounded and structurally checked before forwarding.

## Known issues, edge cases & outstanding work

The OpenAI Developers connector needs reauthentication before it can provision a project key in this workspace. Until the deployment environment supplies `OPENAI_API_KEY`, the route returns `GPT_LIVE_CONFIGURATION_REQUIRED`. No live provider request is made by tests.

## Verification & testing commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gpt_live.py -q
python scripts/verify_living_docs.py --path app/services/business_assistant/gpt_live/README.md
```
