from pathlib import Path
import sys

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

from backend.services.idempotency_service import reserve
import inspect


def test_reserve_accepts_planning_action_code():
    assert "action_code" in inspect.signature(reserve).parameters
