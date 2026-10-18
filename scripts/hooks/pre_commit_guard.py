#!/usr/bin/env python3
"""Pre-Commit and Pre-Push Guard (Antigravity PreToolUse Hook).
Enforces AGENTS.md Rule 3: Absolute Prohibition of Mock Implementations.

This hook intercepts 'run_command' tool calls.
If the command attempts 'git commit' or 'git push':
  - Runs the independent Anti-Mock Scanner on all modified and created code files.
  - If mock violations are detected:
      Outputs decision: "deny" with rejection reason.
  - If clean:
      Outputs decision: "allow".
If the command is not a git commit or git push:
  - Outputs decision: "allow".
"""

import json
import os
import re
import sys

# Ensure scripts/hooks can import sibling modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from anti_mock_scanner import find_repo_root, read_stdin_payload, scan_repository_for_mocks

RE_GIT_COMMIT_OR_PUSH = re.compile(r"\bgit\s+(?:commit|push)\b", re.IGNORECASE)


def main():
    payload = read_stdin_payload()

    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    cmd = (
        args.get("CommandLine")
        or args.get("command")
        or args.get("cmd")
        or ""
    )

    # Check if the command is a git commit or push
    is_commit_or_push = bool(RE_GIT_COMMIT_OR_PUSH.search(cmd))

    if not is_commit_or_push:
        print(json.dumps({"decision": "allow"}))
        sys.exit(0)

    # If it is git commit or push, run the mock audit
    workspace_paths = payload.get("workspacePaths", [])
    repo_root = find_repo_root(start_dir=current_dir, workspace_paths=workspace_paths)
    violations = scan_repository_for_mocks(repo_root=repo_root, workspace_paths=workspace_paths)

    if violations:
        violation_summaries = [v.to_summary() for v in violations]
        summary_str = "; ".join(violation_summaries)
        output = {
            "decision": "deny",
            "reason": (
                f"BLOCKED: git commit is strictly forbidden until the independent audit gate passes with zero mocks. "
                f"Detected violations under AGENTS.md Rule 3: [{summary_str}]."
            ),
        }
    else:
        output = {"decision": "allow"}

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
