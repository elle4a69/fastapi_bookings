# FastAPI Bookings — Agent Boot Snapshot

> Authoritative: Tenants, Providers, Calendars, Holds, Bookings, SMS Dialogue, Knowledge.
> Operating Rules: AGENTS.md (No mocks, strict scope discipline, Rule 10 living documentation).

```text
fastapi_bookings/
├── app/
│   ├── api/routers/           # HTTP REST API [pytest tests/test_security_isolation_remediatio...]
│   ├── core/                  # Config & Telemetry [python -m pytest tests/test_telemetry_pipeline....]
│   ├── db/                    # Database Engine & Sessions (PostgreSQL / SQLite)
│   ├── models/                # SQLAlchemy ORM Models (Multi-Tenant)
│   └── services/
│       ├── assistant/         # Assistant Runtime & Tools [.venv\Scripts\python.exe -m pytest tests/test_a...]
│       ├── booking/           # Core Booking Engine [py -3.11 -m pytest tests/test_dynamic_itinerary...]
│       ├── business_assistant/# Business Assistant [.venv\Scripts\python.exe -m pytest tests/test_b...]
│       ├── curation/          # Memory Curator & PII Scrubber [.\.venv\Scripts\python.exe -m py_compile app/mo...]
│       ├── knowledge/         # Knowledge & Graphiti Client [python -m pytest tests/test_knowledge_phase1_ga...]
│       ├── messaging/         # Chatwoot & Omnichannel [python -m pytest tests/test_chatwoot_agentbot.p...]
│       ├── resident_agent/    # Autonomous Resident Sentinel [.venv\Scripts\python.exe -m pytest tests/test_r...]
│       ├── routing/           # Routing & Geospatial [python -m pytest tests/test_distance_calculator...]
│       ├── scheduling/        # Scheduling & Slot Allocation [pytest tests/test_concurrency.py -v]
│       └── sms/               # SMS Autonomous Engine [python -m pytest tests/test_sms_chatwoot.py tes...]
├── frontend/                  # React/Vite SPA [npm test]
│   └── src/pages/admin/       # Admin Management Pages
│       ├── finance/           # Finance & Invoicing [npm run build]
│       └── sms/               # SMS Workspace & Console [npm run build]
├── alembic/                   # Database Migrations [.\.venv\Scripts\alembic.exe heads]
├── scripts/                   # Release Gates & Tooling [python scripts/verify_living_docs.py]
└── tests/                     # Pytest Suites [python -m pytest tests/ --ignore=tests/test_fuz...]
```

### High-Speed Agent Retrieval Commands
- **FTS5 Search**: `python scripts/query_docs.py --search "<term>"`
- **Test Command**: `python scripts/query_docs.py --test-command "<module>"`
- **Known Debt/Issues**: `python scripts/query_docs.py --known-issues`
- **Rule 10 Gate**: `python scripts/verify_living_docs.py`

*Generated automatically on 2026-10-02 17:34:40Z by scripts/index_living_docs.py*
