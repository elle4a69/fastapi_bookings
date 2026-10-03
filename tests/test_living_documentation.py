"""
Unit and Integration Tests for Living Documentation Indexer & Agent Knowledge Manifest (Rule 10)
Repository: FastAPI Bookings (f:/Projects/fastapi_bookings)
Standard: AGENTS.md Rule 10 (Living Module Documentation and README Maintenance)
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.index_living_docs import (
    MANDATORY_SECTION_SPECS,
    ModuleDoc,
    check_stub,
    clean_heading_text,
    extract_known_issues,
    extract_primary_files,
    extract_title,
    extract_verification_command,
    find_readme_files,
    generate_markdown_index,
    generate_module_id,
    index_database,
    infer_domain,
    parse_readme,
    split_markdown_headings,
    write_manifest,
)
from scripts.query_docs import (
    ensure_index_exists,
    query_known_issues,
    query_module,
    query_search,
    query_test_command,
    sanitize_fts_query,
)
from scripts.verify_living_docs import print_report, run_verification, verify_readme_file

REPO_ROOT = Path(__file__).resolve().parent.parent


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

VALID_README_CONTENT = """# Mock Booking Service (`app/services/mock_booking`)

This package manages mock booking appointments.

---

## 1. Purpose & Scope

The Mock Booking Service owns synthetic calendar scheduling and slot allocation rules.
It deliberately avoids external carrier network dispatches and direct database access.

---

## 2. Architecture & Key Files

```text
app/services/mock_booking/
├── scheduler.py       # Core scheduling logic
├── validator.py       # Input validation
└── README.md          # Documentation
```

Key files:
- [scheduler.py](file:///f:/Projects/fastapi_bookings/app/services/mock_booking/scheduler.py)
- [validator.py](file:///f:/Projects/fastapi_bookings/app/services/mock_booking/validator.py)

---

## 3. Setup, Configuration & Dependencies

Requires settings in `app/core/config.py`:
- `MOCK_SCHEDULER_TIMEOUT=30`
- `DATABASE_URL` for state storage.

---

## 4. Core Workflows & Contracts

### 4.1 Inbound Slot Booking
Clients submit an appointment slot. The scheduler verifies availability:
- `POST /api/mock/book`

---

## 5. Data Safety & Isolation

- Enforces strict tenant isolation on every database lookup.
- PII scrubbing on all customer names and addresses before storage.

---

## 6. Known Issues, Edge Cases & Outstanding Work

1. Concurrency locks under SQLite in multi-worker environments.
2. Outbox retry backoff interval is fixed rather than exponential.

---

## 7. Verification & Testing Commands

```powershell
# Run unit and integration tests
python -m pytest tests/test_mock_booking.py -v
```
"""

MALFORMED_README_CONTENT = """# Incomplete Module

## Purpose & Scope
TODO: Write purpose here

## Architecture & Key Files
Architecture under construction.

## Setup, Configuration & Dependencies
TBD

## Core Workflows & Contracts
None yet.

## Data Safety & Isolation
Placeholder.

## Known Issues, Edge Cases & Outstanding Work
N/A

## Verification & Testing Commands
"""


@pytest.fixture
def temp_repo(tmp_path: Path):
    """Creates a temporary workspace with compliant and malformed READMEs."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Module 1: Compliant
    mod1_dir = repo / "app" / "services" / "mock_booking"
    mod1_dir.mkdir(parents=True)
    (mod1_dir / "scheduler.py").write_text("# scheduler", encoding="utf-8")
    (mod1_dir / "validator.py").write_text("# validator", encoding="utf-8")
    (mod1_dir / "README.md").write_text(VALID_README_CONTENT, encoding="utf-8")

    # Module 2: Malformed
    mod2_dir = repo / "app" / "services" / "incomplete_mod"
    mod2_dir.mkdir(parents=True)
    (mod2_dir / "README.md").write_text(MALFORMED_README_CONTENT, encoding="utf-8")

    return repo


# -----------------------------------------------------------------------------
# Parser Tests
# -----------------------------------------------------------------------------

def test_split_markdown_headings_with_code_blocks():
    """Ensures comments inside code fences are not mistaken for headings."""
    sample = """# Main Title
Text before code block.

```python
# This is a python comment, not a heading
def foo():
    pass
```

## Section 1
Content of section 1.
"""
    sections = split_markdown_headings(sample)
    # Headings should only be # Main Title and ## Section 1
    titles = [s[1] for s in sections]
    assert "Main Title" in titles
    assert "Section 1" in titles
    assert not any("This is a python comment" in t for t in titles)


def test_clean_heading_text():
    assert clean_heading_text("## 1. Purpose & Scope") == "Purpose & Scope"
    assert clean_heading_text("### 4.2 Core Workflows") == "Core Workflows"
    assert clean_heading_text("Phase 5: Governance") == "Governance"
    assert clean_heading_text("`README.md` Overview") == "README.md Overview"


def test_check_stub_detection():
    assert check_stub("")[0] is True
    assert check_stub("   \n\t  ")[0] is True
    assert check_stub("<!-- TODO: write this -->")[0] is True
    assert check_stub("TODO")[0] is True
    assert check_stub("TBD")[0] is True
    assert check_stub("WIP")[0] is True
    assert check_stub("Placeholder")[0] is True
    assert check_stub("N/A")[0] is True
    assert check_stub("Coming soon")[0] is True

    # Real documentation must pass
    is_stub, _ = check_stub("This module manages tenant bookings and payment settlement.")
    assert is_stub is False


def test_extract_verification_command():
    sample = """## Verification & Testing Commands
```powershell
# Run the test suite
python -m pytest tests/test_sms.py -v
```
"""
    cmd = extract_verification_command(sample)
    assert cmd == "python -m pytest tests/test_sms.py -v"


def test_extract_known_issues():
    sample = """## Known Issues
1. Concurrency locks under high load.
2. Missing foreign key index on customer_id.
"""
    issues = extract_known_issues(sample)
    assert len(issues) == 2
    assert "Concurrency locks under high load." in issues[0]
    assert "Missing foreign key index" in issues[1]


def test_parse_compliant_readme(temp_repo: Path):
    readme_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    doc = parse_readme(readme_path, temp_repo)

    assert doc.id == "app_services_mock_booking"
    assert doc.title == "Mock Booking Service"
    assert "Scheduling" in doc.domain or "Booking" in doc.domain
    assert doc.is_compliant is True
    assert len(doc.missing_sections) == 0
    assert len(doc.stub_sections) == 0
    assert "scheduler.py" in doc.primary_files
    assert doc.verification_command == "python -m pytest tests/test_mock_booking.py -v"
    assert len(doc.known_issues) == 2


def test_parse_malformed_readme(temp_repo: Path):
    readme_path = temp_repo / "app" / "services" / "incomplete_mod" / "README.md"
    doc = parse_readme(readme_path, temp_repo)

    assert doc.is_compliant is False
    # Verification section was completely empty
    assert any("Verification & Testing Commands" in s for s in doc.missing_sections)
    # Stubs detected
    assert len(doc.stub_sections) > 0


# -----------------------------------------------------------------------------
# Manifest & Database Indexing Tests
# -----------------------------------------------------------------------------

def test_manifest_generation(temp_repo: Path, tmp_path: Path):
    readme_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    doc = parse_readme(readme_path, temp_repo)

    manifest_file = tmp_path / "manifest.json"
    write_manifest([doc], manifest_file)

    assert manifest_file.exists()
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert data["total_modules"] == 1
    assert data["compliant_modules"] == 1
    assert data["modules"][0]["id"] == "app_services_mock_booking"
    assert data["modules"][0]["title"] == "Mock Booking Service"
    assert "purpose_and_scope" in data["modules"][0]["sections"]


def test_sqlite_fts5_indexing_and_search(temp_repo: Path, tmp_path: Path):
    readme_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    doc = parse_readme(readme_path, temp_repo)

    db_file = tmp_path / "module_docs.db"
    index_database([doc], db_file)

    assert db_file.exists()
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    # Verify tables
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    assert "modules" in tables
    assert "module_sections" in tables
    assert "module_fts" in tables
    conn.close()

    # Search with query_search
    results = query_search(db_file, "scheduling")
    assert len(results) > 0
    assert results[0]["module_id"] == "app_services_mock_booking"
    assert "scheduling" in results[0]["snippet"].lower()

    # Search with special characters sanitized
    results_sanitized = query_search(db_file, "app/services/mock_booking")
    assert len(results_sanitized) > 0


def test_sanitize_fts_query():
    assert sanitize_fts_query("arrival") == '"arrival"'
    assert sanitize_fts_query("app/services/sms") == '"app" "services" "sms"'
    assert sanitize_fts_query("") == '""'
    assert sanitize_fts_query("test-case_123") == '"test-case_123"'


def test_markdown_index_generation(temp_repo: Path, tmp_path: Path):
    readme_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    doc = parse_readme(readme_path, temp_repo)

    index_md = tmp_path / "MODULE_INDEX.md"
    generate_markdown_index([doc], index_md, temp_repo)

    assert index_md.exists()
    content = index_md.read_text(encoding="utf-8")
    assert "# FastAPI Bookings — Application Module Index" in content
    assert "Mock Booking Service" in content
    assert "python -m pytest tests/test_mock_booking.py -v" in content


# -----------------------------------------------------------------------------
# Query Docs CLI Tool Tests
# -----------------------------------------------------------------------------

def test_query_test_command(temp_repo: Path, tmp_path: Path):
    readme_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    doc = parse_readme(readme_path, temp_repo)

    db_file = tmp_path / "module_docs.db"
    index_database([doc], db_file)

    cmd = query_test_command(db_file, "mock_booking")
    assert cmd == "python -m pytest tests/test_mock_booking.py -v"

    # Non-existent
    assert query_test_command(db_file, "non_existent") is None


def test_query_module_and_known_issues(temp_repo: Path, tmp_path: Path):
    readme_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    doc = parse_readme(readme_path, temp_repo)

    db_file = tmp_path / "module_docs.db"
    manifest_file = tmp_path / "manifest.json"
    index_database([doc], db_file)
    write_manifest([doc], manifest_file)

    mod_data = query_module(db_file, manifest_file, "mock_booking")
    assert mod_data is not None
    assert mod_data["title"] == "Mock Booking Service"
    assert "scheduler.py" in mod_data["primary_files"]

    issues = query_known_issues(manifest_file, db_file)
    assert len(issues) == 1
    assert len(issues[0]["known_issues"]) == 2


def test_query_docs_cli_execution(temp_repo: Path, tmp_path: Path):
    readme_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    doc = parse_readme(readme_path, temp_repo)

    db_file = tmp_path / "module_docs.db"
    manifest_file = tmp_path / "manifest.json"
    index_database([doc], db_file)
    write_manifest([doc], manifest_file)

    script = REPO_ROOT / "scripts" / "query_docs.py"

    # 1. Test test-command flag
    res1 = subprocess.run(
        [sys.executable, str(script), "--test-command", "mock_booking", "--db", str(db_file), "--manifest", str(manifest_file)],
        capture_output=True,
        text=True,
        cwd=str(temp_repo),
    )
    assert res1.returncode == 0
    assert "python -m pytest tests/test_mock_booking.py -v" in res1.stdout

    # 2. Test search flag with JSON output
    res2 = subprocess.run(
        [sys.executable, str(script), "--search", "synthetic", "--json", "--db", str(db_file), "--manifest", str(manifest_file)],
        capture_output=True,
        text=True,
        cwd=str(temp_repo),
    )
    assert res2.returncode == 0
    search_json = json.loads(res2.stdout)
    assert search_json["count"] > 0
    assert search_json["results"][0]["module_id"] == "app_services_mock_booking"

    # 3. Test known-issues flag
    res3 = subprocess.run(
        [sys.executable, str(script), "--known-issues", "--json", "--db", str(db_file), "--manifest", str(manifest_file)],
        capture_output=True,
        text=True,
        cwd=str(temp_repo),
    )
    assert res3.returncode == 0
    issues_json = json.loads(res3.stdout)
    assert issues_json["total_modules_with_issues"] == 1


# -----------------------------------------------------------------------------
# Verifier & Release Gate Linter Tests
# -----------------------------------------------------------------------------

def test_verify_living_docs_linter_compliant_file(temp_repo: Path):
    readme_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    doc = verify_readme_file(readme_path, temp_repo)
    assert doc.is_compliant is True

    # print_report returns 0 on all compliant
    exit_code = print_report([doc], json_output=True)
    assert exit_code == 0


def test_verify_living_docs_linter_failing_file(temp_repo: Path):
    readme_path = temp_repo / "app" / "services" / "incomplete_mod" / "README.md"
    doc = verify_readme_file(readme_path, temp_repo)
    assert doc.is_compliant is False

    # print_report returns 1 on violation
    exit_code = print_report([doc], json_output=True)
    assert exit_code == 1


def test_verify_living_docs_cli_execution(temp_repo: Path):
    script = REPO_ROOT / "scripts" / "verify_living_docs.py"
    compliant_path = temp_repo / "app" / "services" / "mock_booking" / "README.md"
    failing_path = temp_repo / "app" / "services" / "incomplete_mod" / "README.md"

    # Compliant file check -> exit 0
    res_pass = subprocess.run(
        [sys.executable, str(script), "--path", str(compliant_path), "--root", str(temp_repo)],
        capture_output=True,
        text=True,
    )
    assert res_pass.returncode == 0
    assert "[PASS]" in res_pass.stdout

    # Failing file check -> exit 1
    res_fail = subprocess.run(
        [sys.executable, str(script), "--path", str(failing_path), "--root", str(temp_repo)],
        capture_output=True,
        text=True,
    )
    assert res_fail.returncode == 1
    assert "[FAIL]" in res_fail.stdout


# -----------------------------------------------------------------------------
# Real Repository Artifacts Verification
# -----------------------------------------------------------------------------

def test_real_repo_indexer_artifacts():
    """Validates that real generated artifacts exist, are non-empty, and valid."""
    manifest_path = REPO_ROOT / "docs" / "module_manifest.json"
    db_path = REPO_ROOT / "docs" / "module_docs.db"
    index_md = REPO_ROOT / "docs" / "MODULE_INDEX.md"

    assert manifest_path.exists(), "docs/module_manifest.json must exist"
    assert db_path.exists(), "docs/module_docs.db must exist"
    assert index_md.exists(), "docs/MODULE_INDEX.md must exist"

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["total_modules"] >= 20
    assert "modules" in manifest_data

    # SQLite check
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM modules;")
    mod_count = cur.fetchone()[0]
    assert mod_count >= 20

    cur.execute("SELECT COUNT(*) FROM module_sections;")
    sec_count = cur.fetchone()[0]
    assert sec_count >= 100
    conn.close()

    # Index.md check
    md_text = index_md.read_text(encoding="utf-8")
    assert "# FastAPI Bookings — Application Module Index" in md_text
    assert "Master Module Inventory Table" in md_text

    # Boot snapshot check
    snapshot_path = REPO_ROOT / "docs" / "AGENT_BOOT_SNAPSHOT.md"
    assert snapshot_path.exists(), "docs/AGENT_BOOT_SNAPSHOT.md must exist"
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    assert "FastAPI Bookings — Agent Boot Snapshot" in snapshot_text
    assert "fastapi_bookings/" in snapshot_text


def test_generate_module_id_removesuffix():
    """Validates that removesuffix prevents stripping trailing matching letters from directory names."""
    assert generate_module_id("app/core/README.md") == "app_core"
    assert generate_module_id("frontend/README.md") == "frontend"
    assert generate_module_id("app/services/sms/README.md") == "app_services_sms"
    assert generate_module_id("docs/README.md") == "docs"


def test_extract_verification_command_prefixes():
    """Validates PowerShell call operator (&) stripping and py -3.11 prefix support."""
    sample_ps = """```powershell
& .\\.venv\\Scripts\\python.exe -m pytest tests/test_routing.py -v
```"""
    assert extract_verification_command(sample_ps) == ".\\.venv\\Scripts\\python.exe -m pytest tests/test_routing.py -v"

    sample_py = """```powershell
py -3.11 -m pytest tests/test_booking.py -v
```"""
    assert extract_verification_command(sample_py) == "py -3.11 -m pytest tests/test_booking.py -v"


def test_query_docs_boot_snapshot_cli():
    """Validates query_docs.py --boot-snapshot and JSON format."""
    script = REPO_ROOT / "scripts" / "query_docs.py"
    res = subprocess.run(
        [sys.executable, str(script), "--boot-snapshot", "--root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0
    assert "Agent Boot Snapshot" in res.stdout
    assert "fastapi_bookings/" in res.stdout

    res_json = subprocess.run(
        [sys.executable, str(script), "--boot-snapshot", "--json", "--root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert "boot_snapshot" in data
    assert "Agent Boot Snapshot" in data["boot_snapshot"]


