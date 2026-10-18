#!/usr/bin/env python3
"""Unconditional Automated Audit Gate (Antigravity Stop Hook).
Enforces AGENTS.md Rule 3: Absolute Prohibition of Mock Implementations.

This hook runs on 'Stop' events before Antigravity finishes a turn or conversation.
If any modified or created code file contains forbidden mock patterns:
  - Outputs decision: "continue" with a detailed rejection reason.
  - Exits with 0 to force the agent back into the execution loop.
If clean:
  - Outputs {} and exits with 0 to allow completion.
"""

import json
import os
import sys

# Ensure scripts/hooks can import sibling modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from anti_mock_scanner import find_repo_root, read_stdin_payload, scan_repository_for_mocks


def main():
    payload = read_stdin_payload()

    workspace_paths = payload.get("workspacePaths", [])
    repo_root = find_repo_root(start_dir=current_dir, workspace_paths=workspace_paths)

    violations = scan_repository_for_mocks(repo_root=repo_root, workspace_paths=workspace_paths)

    if violations:
        violation_summaries = [v.to_summary() for v in violations]
        summary_str = "; ".join(violation_summaries)
        output = {
            "decision": "continue",
            "reason": (
                f"MANDATORY AUDIT GATE BLOCKED TERMINATION: Forbidden mock patterns detected under AGENTS.md Rule 3: "
                f"[{summary_str}]. You cannot finish or mark complete until all mocks are removed and real endpoints are wired."
            ),
        }
    else:
        output = {}

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
