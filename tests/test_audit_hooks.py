"""Tests for scripts/hooks unconditional automated audit gate and pre-commit guard.
Verifies AGENTS.md Rule 3 Anti-Mock Enforcement and Antigravity hook JSON contracts.
"""

import json
import os
import subprocess
import sys
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.hooks.anti_mock_scanner import (
    MockViolation,
    scan_content_for_mocks,
)

HOOKS_DIR = os.path.abspath(os.path.join(REPO_ROOT, "scripts", "hooks"))
AUDIT_GATE_SCRIPT = os.path.join(HOOKS_DIR, "unconditional_audit_gate.py")
PRE_COMMIT_SCRIPT = os.path.join(HOOKS_DIR, "pre_commit_guard.py")


def test_clean_content_passes():
    """Real implementation code with genuine API callers should produce zero violations."""
    clean_ts = """
    import { apiClient } from "@/lib/api";
    import { useState, useEffect } from "react";

    export function ServiceCatalog({ tenantId }: { tenantId: string }) {
      const [services, setServices] = useState([]);
      const [loading, setLoading] = useState(true);

      useEffect(() => {
        apiClient.get(`/api/v1/tenants/${tenantId}/services`)
          .then(res => setServices(res.data))
          .finally(() => setLoading(false));
      }, [tenantId]);

      return <div>{services.map(s => <div key={s.id}>{s.name}</div>)}</div>;
    }
    """
    violations = scan_content_for_mocks("frontend/src/components/ServiceCatalog.tsx", clean_ts)
    assert len(violations) == 0, f"Expected clean content, got: {violations}"


def test_synthetic_settimeout_detected():
    """Synthetic setTimeout handlers masquerading as backend processing must be caught."""
    # Sub-case 1: Fake promise delay
    code_delay = """
    export async function saveProfile(data) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      return { success: true };
    }
    """
    v1 = scan_content_for_mocks("frontend/src/services/profile.ts", code_delay)
    assert any("Synthetic setTimeout" in v.pattern_type for v in v1), f"Expected synthetic delay violation, got: {v1}"

    # Sub-case 2: setTimeout with state mutation
    code_state = """
    const handleSubmit = () => {
      setTimeout(() => {
        setLoading(false);
        setStatus("saved");
      }, 500);
    };
    """
    v2 = scan_content_for_mocks("frontend/src/components/Form.tsx", code_state)
    assert any("Synthetic setTimeout State Mutation" in v.pattern_type for v in v2), f"Expected mutation violation, got: {v2}"


def test_hardcoded_mock_collections_detected():
    """Hardcoded static mock collections (INITIAL_*, SAMPLE_*, fake_*, mock_*) must be caught."""
    # Sub-case 1: TypeScript INITIAL_* and SAMPLE_*
    code_ts = """
    const INITIAL_SERVICES = [
      { id: "s1", name: "Consultation", price: 100 },
      { id: "s2", name: "Followup", price: 50 },
    ];
    export const SAMPLE_CUSTOMERS = [{ id: 1, name: "Alice" }];
    const fake_token = "abc123xyz";
    const mock_bookings = [{ id: "b1" }];
    """
    v_ts = scan_content_for_mocks("frontend/src/data.ts", code_ts)
    assert len(v_ts) >= 4
    types = [v.pattern_type for v in v_ts]
    assert all("Mock Collection" in t for t in types)

    # Sub-case 2: Python INITIAL_*, SAMPLE_*, fake_*, mock_*
    code_py = """
    INITIAL_ROLES = ["admin", "staff", "customer"]
    SAMPLE_TENANTS = [{"id": 1, "name": "Acme"}]
    fake_users = [{"email": "fake@test.com"}]
    mock_payload = {"status": "ok"}
    """
    v_py = scan_content_for_mocks("app/services/data.py", code_py)
    assert len(v_py) >= 4
    for v in v_py:
        assert v.pattern_type == "Hardcoded Mock Collection"


def test_usestate_mock_reference_detected():
    """Components initializing state with mock collections must be caught."""
    code = """
    import React, { useState } from "react";
    export function BookingList() {
      const [bookings, setBookings] = useState(MOCK_BOOKINGS);
      return <ul>{bookings.map(b => <li>{b.title}</li>)}</ul>;
    }
    """
    violations = scan_content_for_mocks("frontend/src/pages/Bookings.tsx", code)
    assert any(v.pattern_type == "useState Mock Data Source" for v in violations)


def test_dummy_component_without_api_client():
    """Components returning hardcoded dummy states without calling real backend API clients must be caught."""
    code = """
    export function StaffList() {
      const staffMembers = [
        { id: "1", name: "Dr. Smith" },
        { id: "2", name: "Nurse Jones" },
      ];
      return <div>{staffMembers.map(s => <span>{s.name}</span>)}</div>;
    }
    """
    violations = scan_content_for_mocks("frontend/src/components/StaffList.tsx", code)
    assert any(v.pattern_type == "Dummy Component Without Backend API" for v in violations)


def test_python_stub_route_detected():
    """Stub endpoints returning fake/mock dictionaries without db queries must be caught."""
    code = '''
    @router.get("/tenants/{tenant_id}/summary")
    async def get_tenant_summary(tenant_id: str):
        """Returns summary of tenant."""
        return {"status": "ok", "mock_metric": 42}
    '''
    violations = scan_content_for_mocks("app/api/tenants.py", code)
    assert any(v.pattern_type == "Stub Endpoint Returning Fake Data" for v in violations)


def test_audit_gate_cli_clean_execution():
    """unconditional_audit_gate.py runs cleanly and emits valid Antigravity JSON contract."""
    payload = {
        "executionNum": 1,
        "terminationReason": "NO_TOOL_CALL",
        "error": "",
        "fullyIdle": True,
        "workspacePaths": [os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))],
    }
    proc = subprocess.run(
        [sys.executable, AUDIT_GATE_SCRIPT],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert isinstance(data, dict)
    # If clean, data must be empty dict {}
    if data:
        assert data.get("decision") == "continue"
        assert "MANDATORY AUDIT GATE BLOCKED TERMINATION" in data.get("reason", "")


def test_pre_commit_guard_cli_contracts():
    """pre_commit_guard.py responds with allow for non-commit commands and enforces JSON schema."""
    # Test 1: Non-commit command allows unconditionally
    non_commit_payload = {
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "npm test"},
        },
        "stepIdx": 1,
    }
    p1 = subprocess.run(
        [sys.executable, PRE_COMMIT_SCRIPT],
        input=json.dumps(non_commit_payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert p1.returncode == 0
    d1 = json.loads(p1.stdout)
    assert d1 == {"decision": "allow"}

    # Test 2: git commit command
    commit_payload = {
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "git commit -m 'feat: clean commit'"},
        },
        "stepIdx": 2,
    }
    p2 = subprocess.run(
        [sys.executable, PRE_COMMIT_SCRIPT],
        input=json.dumps(commit_payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert p2.returncode == 0
    d2 = json.loads(p2.stdout)
    assert "decision" in d2
    assert d2["decision"] in ["allow", "deny"]
    if d2["decision"] == "deny":
        assert "BLOCKED: git commit is strictly forbidden" in d2["reason"]


def test_audit_gate_blocks_on_mock_violation(monkeypatch=None):
    """When mock violations are present in repository, unconditional_audit_gate emits continue decision."""
    import unittest.mock as mock

    fake_violation = MockViolation(
        file_path="frontend/src/pages/FakePage.tsx",
        line_number=42,
        pattern_type="Synthetic setTimeout / Fake Delay",
        message="Synthetic setTimeout delay detected masquerading as backend processing.",
        snippet="await new Promise(r => setTimeout(r, 1000));",
    )

    with mock.patch("scripts.hooks.unconditional_audit_gate.scan_repository_for_mocks", return_value=[fake_violation]):
        from scripts.hooks.unconditional_audit_gate import main as gate_main
        import io

        fake_out = io.StringIO()
        with mock.patch("sys.stdout", fake_out):
            with pytest.raises(SystemExit) as exc:
                gate_main()
            assert exc.value.code == 0

        res = json.loads(fake_out.getvalue())
        assert res.get("decision") == "continue"
        assert "MANDATORY AUDIT GATE BLOCKED TERMINATION" in res.get("reason", "")
        assert "FakePage.tsx:42" in res.get("reason", "")


def test_pre_commit_guard_denies_on_mock_violation():
    """When mock violations are present in repository, pre_commit_guard blocks git commit/push."""
    import unittest.mock as mock

    fake_violation = MockViolation(
        file_path="app/api/fake_endpoint.py",
        line_number=15,
        pattern_type="Hardcoded Mock Collection",
        message="Hardcoded static mock collection 'fake_users' masquerading as backend data.",
        snippet="fake_users = [{'id': 1}]",
    )

    with mock.patch("scripts.hooks.pre_commit_guard.scan_repository_for_mocks", return_value=[fake_violation]):
        from scripts.hooks.pre_commit_guard import main as guard_main
        import io

        commit_payload = {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "git commit -m 'feat: test commit'"},
            }
        }

        fake_out = io.StringIO()
        with mock.patch("sys.stdout", fake_out):
            with mock.patch("scripts.hooks.pre_commit_guard.read_stdin_payload", return_value=commit_payload):
                with pytest.raises(SystemExit) as exc:
                    guard_main()
                assert exc.value.code == 0

        res = json.loads(fake_out.getvalue())
        assert res.get("decision") == "deny"
        assert "BLOCKED: git commit is strictly forbidden" in res.get("reason", "")
        assert "fake_endpoint.py:15" in res.get("reason", "")


if __name__ == "__main__":
    test_clean_content_passes()
    print("PASS: test_clean_content_passes")
    test_synthetic_settimeout_detected()
    print("PASS: test_synthetic_settimeout_detected")
    test_hardcoded_mock_collections_detected()
    print("PASS: test_hardcoded_mock_collections_detected")
    test_usestate_mock_reference_detected()
    print("PASS: test_usestate_mock_reference_detected")
    test_dummy_component_without_api_client()
    print("PASS: test_dummy_component_without_api_client")
    test_python_stub_route_detected()
    print("PASS: test_python_stub_route_detected")
    test_audit_gate_cli_clean_execution()
    print("PASS: test_audit_gate_cli_clean_execution")
    test_pre_commit_guard_cli_contracts()
    print("PASS: test_pre_commit_guard_cli_contracts")
    test_audit_gate_blocks_on_mock_violation()
    print("PASS: test_audit_gate_blocks_on_mock_violation")
    test_pre_commit_guard_denies_on_mock_violation()
    print("PASS: test_pre_commit_guard_denies_on_mock_violation")
    print("\nALL 10 TESTS PASSED SUCCESSFULLY!")
