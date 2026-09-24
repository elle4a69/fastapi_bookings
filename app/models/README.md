# Application Models

## 1. Purpose & Scope

`app/models` defines the SQLAlchemy persistence boundary for FastAPI Bookings.
The SMS credential models in this package own encrypted-at-rest account and
Chatwoot binding secrets. Models do not perform external provider calls and do
not expose decrypted values through response schemas.

## 2. Architecture & Key Files

- `sms_account.py` defines `SmsAccount`, encrypted transport/AI credentials,
  line controls, and the fixed `SmsCredentialError` failure contract.
- `sms_chatwoot.py` defines `SmsChatwootBinding`, encrypted API/webhook
  secrets, tenant/provider/inbox ownership, and
  `SmsChatwootCredentialError`.
- Other model files define the booking, tenant, provider, message, outbox and
  audit relationships used by the application services.

## 3. Setup, Configuration & Dependencies

Credential ciphers derive their Fernet key from configured server-side
application security settings. Secrets are supplied to model setters by
authenticated server routes; raw values must never be assigned to the mapped
storage attributes. The `cryptography` and SQLAlchemy packages are required.

## 4. Core Workflows & Contracts

1. A credential setter serializes/encrypts into a local value.
2. Only successful encryption replaces the mapped ciphertext; failure raises a
   fixed typed exception and leaves an existing ciphertext unchanged.
3. A getter decrypts a recognized ciphertext envelope. Non-empty plaintext,
   malformed ciphertext, invalid JSON and wrong decrypted types raise a fixed
   typed exception instead of masquerading as an empty credential.
4. Service and API callers translate typed failures into generic fail-closed
   outcomes.

## 5. Data Safety & Isolation

Credential failures never log values or raw exception text. Model
representations omit credentials. Tenant/provider isolation is enforced by the
service queries that load these records; a decrypted secret must never be
cached or returned to the frontend.

## 6. Known Issues, Edge Cases & Outstanding Work

- Historical rows may contain plaintext because older setters used plaintext
  as an encryption-error fallback. Do not inspect or print those rows. A
  separately approved, offline runbook must identify affected row IDs using
  envelope shape only, rotate every affected provider credential, replace it
  through the normal encrypted setter, verify provider access, and revoke the
  old secret. This task includes no data migration.
- Application security-key rotation needs an explicit decrypt/re-encrypt
  procedure before changing the configured key.

## 7. Verification & Testing Commands

```powershell
$env:OTEL_SDK_DISABLED='true'
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m pytest tests/test_sms_credential_privacy.py -q
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m pytest tests/test_sms_foundation.py::test_sms_credentials_encryption -q
```
