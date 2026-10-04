# GPT-Live Admin Page

## Purpose & scope

This isolated admin page starts and closes the native GPT-Live Business Assistant voice experience. It owns browser WebRTC media, event-channel captions, and close finalisation feedback. It does not hold API keys, alter bookings, send SMS, or replace the existing Realtime voice page.

## Architecture & key files

- `index.tsx` creates a real authenticated Business Assistant conversation and renders its live caption timeline.
- `use-gpt-live.ts` negotiates WebRTC, plays the remote audio track, waits for `session.started`, and retains transport until `session.closed`.
- `protocol.ts` appends exact transcript deltas into timestamp-based speaker intervals.

## Setup, configuration & dependencies

The page requires an authenticated admin session, microphone permission, browser WebRTC support, and the server-side `OPENAI_API_KEY` setup documented in the backend module. It calls only `/api/admin/business-assistant/conversations` and `/api/admin/gpt-live/conversations/{id}/sessions`.

## Core workflows & contracts

The browser creates a local SDP offer, sends it to FastAPI, applies the returned SDP answer, and receives remote audio through WebRTC. It uses the `oai-events` data channel, waits for `session.started`, and sends no startup configuration. `session.input_transcript.delta` and `session.output_transcript.delta` text is appended exactly as received and rendered according to `start_ms`/`end_ms`; it is not paired into turns. Ending a session sends `session.close` and waits for `session.closed`, reporting a timeout or disconnect as incomplete finalisation.

## Data safety & isolation

No OpenAI credential enters browser code. Captions remain in component memory for the active session; the page does not write transcript content to logs, telemetry, or an unrelated customer record. Existing tenant/user authentication controls the session-creation route.

## Known issues, edge cases & outstanding work

The page is intentionally reachable directly at `/admin/gpt-live` while it remains isolated and is not added to the main navigation. Browser autoplay policies can require the user to permit remote audio playback. If the terminal `session.closed` event is not delivered within ten seconds, the page explicitly reports incomplete finalisation.

## Verification & testing commands

```powershell
npm test -- --test-name-pattern="GPT-Live"
npm run build
python scripts/verify_living_docs.py --path frontend/src/pages/admin/gpt-live/README.md
```
