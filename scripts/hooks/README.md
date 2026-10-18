# Automated Audit Gate and Lifecycle Hooks (`scripts/hooks/`)

## 1. Purpose & Scope

The `scripts/hooks/` package provides automated lifecycle hooks and gatekeeper scripts integrated directly with the Antigravity Agent runtime and Git change-control processes.

Its primary purpose is strict, unconditional enforcement of **AGENTS.md Rule 3: Absolute Prohibition of Mock Implementations**:
- Detects synthetic `setTimeout` delays simulating backend processing.
- Blocks hardcoded static mock collections (`INITIAL_*`, `SAMPLE_*`, `fake_*`, `mock_*`) masquerading as live backend state.
- Prevents components or endpoints from returning dummy states without wiring real API clients and database mutations.
- Intercepts agent turn termination via Antigravity `Stop` hooks to force agents back into the execution loop if mock code remains.
- Intercepts tool execution via Antigravity `PreToolUse` hooks to deny `git commit` and `git push` operations whenever mock violations are present.

**What this module deliberately avoids:**
- It does not modify application code or source files automatically.
- It does not interfere with non-commit commands (e.g., test runners, file inspection, builds).
- It does not flag test suites (`tests/`, labelled synthetic test fixtures compliant with Rule 4) or verification scripts.

---

## 2. Architecture & Key Files

```
scripts/hooks/
├── __init__.py                  # Package initializer
├── anti_mock_scanner.py         # Core detection engine and Git status inspector
├── unconditional_audit_gate.py  # Antigravity Stop hook entry point
├── pre_commit_guard.py          # Antigravity PreToolUse hook entry point
└── README.md                    # Living documentation (Rule 10)
```

### Key Components

- **`anti_mock_scanner.py`**:
  - `find_repo_root(...)`: Determines Git repository root across multi-workspace and child-directory invocations.
  - `get_modified_code_files(...)`: Inspects `git status --porcelain` and `git diff --name-only HEAD` for added, modified, or untracked `.py`, `.ts`, `.tsx`, `.js`, `.jsx` files.
  - `scan_content_for_mocks(...)`: Applies regex and structural heuristics to detect forbidden mock patterns.
  - `scan_repository_for_mocks(...)`: Aggregates all violations across all touched files.
- **`unconditional_audit_gate.py`**:
  - Subscribes to the Antigravity `Stop` event.
  - Reads hook payload from `sys.stdin`.
  - Emits `{"decision": "continue", "reason": "..."}` if violations exist, preventing premature termination.
  - Emits `{}` if repository changes are clean.
- **`pre_commit_guard.py`**:
  - Subscribes to `PreToolUse` for `run_command`.
  - Checks if `CommandLine` contains `git commit` or `git push`.
  - Emits `{"decision": "deny", "reason": "..."}` if mock violations exist.
  - Emits `{"decision": "allow"}` otherwise.

---

## 3. Setup, Configuration & Dependencies

### Configuration in `.agents/hooks.json`

Registered in `.agents/hooks.json` under root and Antigravity execution paths:

```json
{
  "anti-mock-audit-gate": {
    "enabled": true,
    "Stop": [
      {
        "type": "command",
        "command": "python -c \"import os, sys, runpy; p = 'scripts/hooks/unconditional_audit_gate.py' if os.path.exists('scripts/hooks/unconditional_audit_gate.py') else '../scripts/hooks/unconditional_audit_gate.py'; runpy.run_path(p, run_name='__main__')\"",
        "timeout": 30
      }
    ]
  },
  "pre-commit-guard": {
    "enabled": true,
    "PreToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          {
            "type": "command",
            "command": "python -c \"import os, sys, runpy; p = 'scripts/hooks/pre_commit_guard.py' if os.path.exists('scripts/hooks/pre_commit_guard.py') else '../scripts/hooks/pre_commit_guard.py'; runpy.run_path(p, run_name='__main__')\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Dependencies

- Python 3.10+ standard library (`os`, `sys`, `json`, `re`, `subprocess`, `dataclasses`, `typing`).
- No external third-party Python packages required.

---

## 4. Core Workflows & Contracts

### Workflow 1: Agent Turn Termination (`Stop` Hook)

1. Agent execution reaches end-of-turn or completion (`NO_TOOL_CALL`).
2. Antigravity runner feeds session metadata to `unconditional_audit_gate.py` via `sys.stdin`.
3. The hook scans all modified code files in the Git working tree.
4. **Clean path**: Returns `{}` with exit code `0`. Antigravity concludes the turn normally.
5. **Violation path**: Returns `{"decision": "continue", "reason": "MANDATORY AUDIT GATE BLOCKED TERMINATION..."}` with exit code `0`. Antigravity resumes the agent session, injecting the rejection reason into context to mandate mock removal.

### Workflow 2: Command Gating (`PreToolUse` Hook)

1. Agent issues `run_command` tool call.
2. Hook checks if `CommandLine` targets `git commit` or `git push`.
3. If not, immediately emits `{"decision": "allow"}`.
4. If commit/push is detected, runs `scan_repository_for_mocks`.
5. If violations exist, emits `{"decision": "deny", "reason": "BLOCKED: git commit is strictly forbidden..."}`. Antigravity prevents execution of the commit.

---

## 5. Data Safety & Isolation

- **Zero Credential or PII Exposure**: Hook scripts inspect source code structures and file paths only. They never read `.env` secrets, database connection strings, customer records, or credentials.
- **Fail-Safe Exit Codes**: Both scripts always exit with code `0` and return well-formed JSON to stdout, ensuring the Antigravity hook runner never crashes or enters an undefined state.
- **Strict Isolation of Tests and Scripts**: Test fixtures under `tests/` and diagnostic scripts under `scripts/` are excluded to allow legitimate synthetic test harnesses per Rule 4.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Multi-line Regex Windowing**: Extremely large components spanning thousands of lines are scanned via chunked regex. Regex performance has been validated on typical source sizes under 50ms per file.
- **Untracked Directories**: Untracked directories (reported as `?? dir/` by `git status`) are recursively enumerated so newly created mock files cannot evade detection before being staged.

---

## 7. Verification & Testing Commands

To verify the audit gate and pre-commit guard against synthetic and real scenarios:

```powershell
# Run the automated synthetic test suite
python tests/test_audit_hooks.py

# Verify compliance with Rule 10 living documentation standard
python scripts/verify_living_docs.py --path scripts/hooks/README.md

# Manual dry run of the audit gate
python scripts/hooks/unconditional_audit_gate.py

# Manual dry run of the pre-commit guard with synthetic input
echo '{"toolCall": {"name": "run_command", "args": {"CommandLine": "git commit -m \"test\""}}}' | python scripts/hooks/pre_commit_guard.py
```
