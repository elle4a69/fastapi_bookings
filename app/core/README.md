# Core Application Services

## Purpose & Scope

The core package owns process-wide configuration, authentication primitives,
pagination, state-machine helpers, and privacy-bounded telemetry setup. It does
not own tenant business data, provider credentials persisted on SMS accounts,
booking behavior, message delivery, or external-provider lifecycle decisions.

## Architecture & Key Files

- `config.py` defines the typed `Settings` contract and the process-wide
  `settings` instance.
- `security.py` provides password and access-token primitives.
- `pagination.py` provides shared pagination contracts.
- `state_machine.py` provides shared transition helpers.
- `telemetry.py` owns low-cardinality, privacy-filtered observability setup.

## Setup, Configuration & Dependencies

Settings are loaded by `pydantic-settings` from server environment variables
and the server-local `.env` file. Secrets must never be sent to the frontend or
included in application diagnostics.

`OPENAI_API_KEY` is a typed `SecretStr`. It is excluded from settings dumps and
JSON serialization, omitted from the settings representation, and masked by
Pydantic when its field is represented directly. Server code must call
`get_secret_value()` only at the narrow provider-call boundary. An
account-scoped AI credential, when valid, remains the SMS responder's more
specific override. Encryption-at-rest for that account field is supplied by
the separate operations-v5 stack and is not present on this branch alone.

## Core Workflows & Contracts

Configuration is parsed once into the global `settings` instance. The SMS AI
responder selects an exact account override or the typed global OpenAI key
before its model await, snapshots the selected value for confidential-output
detection, and passes it directly to the gateway. The gateway uses the same
typed global setting only for legacy callers that do not pass an explicit key.

## Data Safety & Isolation

- Configuration secrets remain server-only and are excluded from normal
  settings serialization.
- Code must not log, return, trace, or persist a revealed secret value.
- Tenant/provider/account ownership is enforced in the owning business service,
  not inferred by this process-wide package.
- Production validation continues to reject known unsafe application security
  defaults and SQLite production databases.

## Known Issues, Edge Cases & Outstanding Work

- The process-wide OpenAI credential is shared server configuration. Per-line
  isolation requires a valid account-scoped credential, the SMS account
  binding checks, and operations-v5 when encrypted storage is required.
- Secret rotation changes future calls; an in-flight call deliberately retains
  its exact pre-await key snapshot so a response cannot evade leak detection by
  rotating configuration during the await.
- This branch does not add a secret manager, automatic rotation, or a frontend
  configuration surface.
- Concurrent validation/operations branches also modify core documentation and
  require manual README reconciliation when stacked.

## Verification & Testing Commands

```powershell
$env:OTEL_SDK_DISABLED='true'
$env:OPENAI_API_KEY=''
python -m pytest -p no:cacheprovider tests/test_gateway_responses_privacy.py tests/test_sms_ai_safety.py -q
python -m py_compile app/core/config.py app/services/gateway/responses_client.py app/services/sms/ai_orchestrator.py
python -m ruff check app/core/config.py app/services/gateway/responses_client.py app/services/sms/ai_orchestrator.py tests/test_gateway_responses_privacy.py tests/test_sms_ai_safety.py
```

All provider calls in tests must use synthetic labelled values and mocked
clients. Tests must override secret settings, must not inspect or print `.env`,
and must not contact a live model provider.
