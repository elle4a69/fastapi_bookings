"""Standalone safety checks; mounted end-to-end checks live in root tests."""

from pathlib import Path
import sys

import pytest

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

from backend.middleware.v2_errors import SupervisorHTTPError
from backend.services.supervisor_repository import _safe_text


def test_planning_has_no_execution_surface():
    source = (Path(__file__).resolve().parents[1] / "backend" / "routers" / "v2_supervisor.py").read_text(encoding="utf-8")
    assert '"/runs' not in source
    assert '"/dispatch' not in source
    assert '"/worktrees' not in source


@pytest.mark.parametrize("unsafe", [
    "print(1)", "C:\\workspace\\secret", "/srv/application", "ls -la",
    "You are an agent", "operator@example.test", "0400 123 456",
    "credential rotation", "raw prompt material", "log output", "audit evidence",
    "finding summary", "verdict accepted", "result report", "outcome achieved",
])
def test_planning_text_rejects_operational_and_private_material(unsafe):
    with pytest.raises(SupervisorHTTPError) as exc:
        _safe_text(unsafe, 4000, "content")
    assert exc.value.code == "validation_failed"


@pytest.mark.parametrize("safe", [
    "Define tenant scoped planning records", "No production actions", "Acceptance criteria are deterministic",
])
def test_planning_text_accepts_bounded_structural_statements(safe):
    assert _safe_text(safe, 4000, "content") == safe
