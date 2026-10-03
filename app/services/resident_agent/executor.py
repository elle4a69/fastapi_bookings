"""Unavailable remediation-execution boundary for the Resident Agent.

The Resident Agent can audit and propose remediation, but it is not a coding
worker.  This boundary must fail closed until a separately approved, isolated
worker can apply real changes and return independently verifiable evidence.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from .event_broker import event_broker

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class FixExecutionError(Exception):
    """Raised when fix execution or verification fails."""

    status_code = 400


class FixExecutionUnavailableError(FixExecutionError):
    """Raised when code execution is requested without a real worker path."""

    status_code = 503


class SafeFixExecutor:
    """Fail-closed boundary; it never applies or verifies code changes."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or PROJECT_ROOT

    async def execute_plan(
        self,
        plan: Dict[str, Any],
        approved: bool = False,
        simulate_only: bool = False,
    ) -> Dict[str, Any]:
        """Reject execution honestly because no real worker is connected.

        ``simulate_only`` is retained only for request compatibility. It does
        not enable a simulation or any other execution path.
        """
        plan_id = plan.get("plan_id", "unknown_plan")
        issue_id = plan.get("issue_id", "unknown_issue")

        if not approved:
            err_msg = f"Execution rejected for plan '{plan_id}': Explicit approval ('approved: true') is required."
            await event_broker.publish(
                "fix_status",
                {"plan_id": plan_id, "error": err_msg, "status": "REJECTED_UNAPPROVED"},
                title=f"Plan {plan_id} Rejected",
                severity="WARNING",
            )
            raise FixExecutionError(err_msg)

        unavailable_message = (
            "Remediation execution is unavailable: the Resident Agent is not an "
            "isolated coding worker and cannot apply or verify code changes."
        )
        await event_broker.publish(
            "fix_status",
            {
                "success": False,
                "plan_id": plan_id,
                "issue_id": issue_id,
                "status": "UNAVAILABLE",
                "verified": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": unavailable_message,
            },
            title=f"Fix {plan_id} Unavailable",
            severity="WARNING",
        )
        raise FixExecutionUnavailableError(unavailable_message)


# Global executor singleton
safe_fix_executor = SafeFixExecutor()
