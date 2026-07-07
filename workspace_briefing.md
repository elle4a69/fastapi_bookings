### SYSTEM PRE-FLIGHT DIRECTIVES & WORKSPACE RULES

You are entering the active implementation phase for a production-ready, highly reliable FastAPI booking API. All agents in this workspace must strictly adhere to these operational and architectural rules. Any file edits or code outputs violating these conditions will be automatically rejected.

### 1\. CRITICAL CONSTRAINTS: ZERO-PLACEHOLDER POLICY

*   NO MOCK IMPLEMENTATIONS: Every function, API route, database query, and external integration must be fully functional. Do not simulate network or data responses.
*   NO CODE STUBS: Every code path must be fully written out. Do not use temporary return values or shortcuts (e.g., `return True # placeholder`).
*   NO "TODO" OR "FIXME" COMMENTS: Do not leave any comments indicating future work. If a feature or edge case is part of the current task, it must be completely delivered.
*   EXPLICIT ERROR HANDLING: Implement robust try/catch blocks and semantic logging for all failure paths instead of leaving a comment placeholder.

### 2\. FASTAPI & SQLALCHEMY COMPLIANCE

*   INJECTED SESSIONS: Never instantiate a database session directly inside business logic or routes. You MUST use FastAPI’s `Depends()` utility to inject the session yield, ensuring proper cleanup and preventing connection leaks.
*   NO AUTO-CREATE SCHEMA: Do not use `Base.metadata.create_all(bind=engine)` anywhere in the application runtime or startup events. The system must rely entirely on Alembic migrations to manage tables.
*   STRICT TIMEZONE DISCIPLINE: All system datetimes must use explicit timezone-aware UTC (`datetime.now(timezone.utc)`). Reject any raw, naive `datetime.utcnow()`. Database columns must enforce `DateTime(timezone=True)`.
*   TRANSPORT SEPARATION: Keep the persistence layer (SQLAlchemy models) completely isolated from the transport layer (Pydantic schemas). Never leak raw database entities directly to the client; always serialize through explicit response validation schemas.

### 3\. CODE ECONOMY & CONTEXT PRESERVATION

*   NO DUPLICATION: Before writing a helper, utility, or database operation, scan the existing workspace files to reuse existing code.
*   FILE SIZE BOUNDARIES: Keep files single-purpose. If a code file exceeds 250 lines, it must be refactored and broken down into smaller, highly cohesive modules.
*   NO LAZY TRUNCATION: When modifying a file, you must output the ENTIRE file with changes integrated. Do NOT use placeholders like `# ... rest of the code stays the same ...`.
*   BACKUP SECURITY: If executing a destructive rewrite or major architectural refactor, automatically archive a copy of the previous state in `.antigravity/backups/`.

### 4\. MULTI-AGENT STATE ALIGNMENT

*   STATE SYNCHRONISATION: Before handing a task over to another agent, append a concise, bulleted markdown summary to the workspace log detailing what was accomplished, what changed in the file structure, and the immediate next step.
*   DOCUMENT AS YOU GO: Update any changes to environment variables, database schemas, or API contracts in the local `README.md` or centralized workspace log file immediately before marking a task complete.