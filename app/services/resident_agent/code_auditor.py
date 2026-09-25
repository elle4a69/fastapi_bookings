"""Automated Code Auditor for Resident Autonomous Agent.

Executes automated codebase checks:
- Verifies Git diff and worktree cleanliness
- Scans for accidental credential and secret leaks (AGENTS.md compliance)
- Verifies TypeScript / frontend project configurations
- Executes targeted test checks via pytest
- Calculates a structured code quality score (0-100%)
"""

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Regular expressions for identifying potential credential/secret leaks
SUSPICIOUS_SECRET_PATTERNS = [
    (re.compile(r"""(?:api_key|apikey|secret_key|private_key|token)\s*=\s*['"][a-zA-Z0-9_\-]{20,}['"]""", re.IGNORECASE), "Generic API Key/Token"),
    (re.compile(r"""(?:sk_live_|pk_live_)[0-9a-zA-Z]{24,}"""), "Stripe Live Key"),
    (re.compile(r"""AC[0-9a-fA-F]{32}"""), "Twilio Account SID"),
    (re.compile(r"""-----BEGIN (?:RSA )?PRIVATE KEY-----"""), "Private Key PEM Header"),
    (re.compile(r"""ghp_[0-9a-zA-Z]{36}"""), "GitHub Personal Access Token"),
    (re.compile(r"""AIza[0-9A-Za-z\-_]{35}"""), "Google API Key"),
]

# Paths allowed to contain test fixtures or mocks
ALLOWLIST_SECRET_PATHS = [
    ".git",
    ".venv",
    "node_modules",
    ".pytest_cache",
    "tests",
    ".env.example",
    "alembic",
]


class CodeAuditor:
    """Codebase auditor running automated health and security checks."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or PROJECT_ROOT

    def check_git_status(self) -> Dict[str, Any]:
        """Inspect Git working directory status."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
            lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
            modified = [l for l in lines if l.startswith("M") or l.startswith(" M")]
            untracked = [l for l in lines if l.startswith("??")]

            branch_res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=3,
            )
            branch_name = branch_res.stdout.strip() or "unknown"

            return {
                "clean": len(lines) == 0,
                "branch": branch_name,
                "total_changed_files": len(lines),
                "modified_count": len(modified),
                "untracked_count": len(untracked),
                "preview": lines[:10],
            }
        except Exception as exc:
            logger.warning("Git status check failed: %s", exc)
            return {
                "clean": False,
                "branch": "unknown",
                "total_changed_files": 0,
                "modified_count": 0,
                "untracked_count": 0,
                "error": str(exc),
            }

    def scan_secret_leaks(self) -> Dict[str, Any]:
        """Scan codebase files for unencrypted secrets and API keys."""
        findings: List[Dict[str, Any]] = []
        scanned_files_count = 0

        scan_dirs = ["app", "frontend/src"]
        for scan_rel in scan_dirs:
            scan_path = self.root_dir / scan_rel
            if not scan_path.exists():
                continue

            for root, dirs, files in os.walk(str(scan_path)):
                # Skip blacklisted directories
                dirs[:] = [d for d in dirs if d not in ALLOWLIST_SECRET_PATHS and not d.startswith(".")]

                for fname in files:
                    if fname.endswith((".py", ".ts", ".tsx", ".json", ".js")):
                        scanned_files_count += 1
                        file_abs = Path(root) / fname
                        rel_path = file_abs.relative_to(self.root_dir).as_posix()

                        # Skip test or fixture files
                        if "test" in rel_path.lower():
                            continue

                        try:
                            content = file_abs.read_text(encoding="utf-8", errors="ignore")
                            for pattern, desc in SUSPICIOUS_SECRET_PATTERNS:
                                matches = pattern.findall(content)
                                if matches:
                                    # Never echo the actual secret, redact it per AGENTS.md rule 4
                                    findings.append({
                                        "file": rel_path,
                                        "type": desc,
                                        "status": "Potential secret exposed",
                                    })
                                    break
                        except Exception:
                            continue

        return {
            "scanned_files": scanned_files_count,
            "secret_leaks_found": len(findings),
            "findings": findings,
            "passed": len(findings) == 0,
        }

    def check_frontend_build_state(self) -> Dict[str, Any]:
        """Verify frontend tsconfig and package configuration sanity."""
        frontend_dir = self.root_dir / "frontend"
        pkg_json = frontend_dir / "package.json"
        tsconfig = frontend_dir / "tsconfig.json"
        tsconfig_app = frontend_dir / "tsconfig.app.json"

        issues: List[str] = []
        if not pkg_json.exists():
            issues.append("Missing frontend/package.json")
        else:
            try:
                json.loads(pkg_json.read_text(encoding="utf-8"))
            except Exception as e:
                issues.append(f"Invalid package.json: {e}")

        if not tsconfig.exists() and not tsconfig_app.exists():
            issues.append("Missing tsconfig.json or tsconfig.app.json in frontend")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "status": "ready" if len(issues) == 0 else "needs_attention",
        }

    def run_fast_tests(self, target_module: Optional[str] = None) -> Dict[str, Any]:
        """Execute a fast pytest smoke run on a specified test module."""
        module = target_module or "tests/test_role_hierarchy.py"
        test_path = self.root_dir / module

        if not test_path.exists():
            return {
                "passed": True,
                "skipped": True,
                "message": f"Target test module {module} not present, smoke check skipped.",
            }

        python_bin = sys.executable
        venv_python = self.root_dir / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            python_bin = str(venv_python)

        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.root_dir)
            env["OTEL_SDK_DISABLED"] = "true"

            res = subprocess.run(
                [python_bin, "-m", "pytest", module, "-q"],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                env=env,
                timeout=25,
            )

            passed = res.returncode == 0
            return {
                "passed": passed,
                "exit_code": res.returncode,
                "summary": res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "",
                "details": (res.stdout + "\n" + res.stderr)[:500],
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "error": "Pytest execution timed out after 25s",
            }
        except Exception as exc:
            return {
                "passed": False,
                "error": str(exc),
            }

    def run_audit(self) -> Dict[str, Any]:
        """Run full automated codebase checks and compute quality score."""
        git_res = self.check_git_status()
        secret_res = self.scan_secret_leaks()
        fe_res = self.check_frontend_build_state()

        # Score computation (0-100)
        score = 100
        if not secret_res["passed"]:
            score -= 40
        if not fe_res["passed"]:
            score -= 20
        if git_res.get("modified_count", 0) > 30:
            score -= 10

        return {
            "score": max(0, min(100, score)),
            "passed": secret_res["passed"] and fe_res["passed"],
            "git": git_res,
            "secrets": secret_res,
            "frontend_state": fe_res,
        }


# Global auditor singleton
code_auditor = CodeAuditor()
