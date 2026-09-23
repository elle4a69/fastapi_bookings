# AI Gateway Services

## Purpose & Scope

The gateway package is the server-side boundary for model policy selection,
tenant budget enforcement, and OpenAI-compatible response generation. It does
not own SMS lifecycle decisions, customer-facing send authorization, booking
actions, or durable conversation knowledge.

## Architecture & Key Files

- `responses_client.py` validates the tenant/model policy, constructs the
  provider request, performs the bounded external call, and returns the parsed
  provider response to the caller.
- `policy_router.py` selects the configured model policy and applies tenant
  budget checks.
- `rule_compiler.py` compiles local response rules used outside the external
  provider path.

The SMS responder applies its independent prompt, credential, output, and
lifecycle gates before and after this gateway.

## Setup, Configuration & Dependencies

The caller should pass the already selected server-side API credential. The
legacy settings/environment fallback remains for other existing callers but
must never be exposed in responses, logs, events, or telemetry. External calls
use `httpx` with the provider URL and a 30-second timeout.

## Core Workflows & Contracts

`generate_response` validates the requested policy, sends the supplied bounded
message array to the provider, parses the response, and applies the existing
tenant budget accounting. Failures propagate to the caller so the owning
workflow can enter its fail-closed review state.

Provider exceptions are replaced by the stable `AiGatewayError` and logged
only as a fixed structural failure message. Original exception text and
traceback output are deliberately excluded because they may contain response
content, credentials, prompts, or customer data.

## Data Safety & Isolation

- The explicit tenant identifier is passed to policy and budget controls.
- API credentials remain server-side and are used only for the authorization
  header of the current request.
- The gateway does not log message arrays, provider response bodies, headers,
  credentials, exception strings, or traceback content.
- SMS callers remain responsible for exact tenant/provider/account context and
  output-safety checks.

## Known Issues, Edge Cases & Outstanding Work

- The gateway retains a legacy configuration fallback for callers that do not
  pass a credential. New security-sensitive callers should select and validate
  the exact credential before invocation.
- A fixed 30-second timeout exists, but provider retry and circuit-breaker
  policy are not implemented here.
- The placeholder cost accounting is not production billing evidence.
- No live provider availability or performance guarantee is established by the
  synthetic tests.

## Verification & Testing Commands

```powershell
python -m pytest -q -p no:cacheprovider tests/test_gateway_responses_privacy.py
python -m py_compile app/services/gateway/responses_client.py
python -m ruff check app/services/gateway/responses_client.py tests/test_gateway_responses_privacy.py
```

Tests must use mocked transports and synthetic markers. They must never call a
live model provider or place real prompts, credentials, or customer data in
logs.
