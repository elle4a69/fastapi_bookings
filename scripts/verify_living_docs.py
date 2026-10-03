#!/usr/bin/env python3
"""
Living Documentation Compliance Verifier & Release Gate (Rule 10)
Repository: FastAPI Bookings (f:/Projects/fastapi_bookings)
Standard: AGENTS.md Rule 10 (Living Module Documentation and README Maintenance)

Linter and CI release gate script that validates discovered module README.md files
against the 7 mandatory sections without empty placeholder stubs:
  1. Purpose & Scope
  2. Architecture & Key Files
  3. Setup, Configuration & Dependencies
  4. Core Workflows & Contracts
  5. Data Safety & Isolation
  6. Known Issues, Edge Cases & Outstanding Work
  7. Verification & Testing Commands

Returns exit code 0 on full compliance, exit code 1 on violations with detailed diagnostics.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.index_living_docs import (
    DEFAULT_TARGET_DIRS,
    find_readme_files,
    parse_readme,
    ModuleDoc,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def verify_readme_file(file_path: Path, repo_root: Path) -> ModuleDoc:
    """Verifies a single README file against Rule 10 standards."""
    return parse_readme(file_path, repo_root)


def run_verification(
    repo_root: Path,
    target_path: Optional[Path] = None,
    target_dir: Optional[Path] = None,
    target_dirs: Optional[List[str]] = None,
) -> List[ModuleDoc]:
    """Discovers and validates target README files."""
    if target_path:
        resolved = (repo_root / target_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Target README not found: {resolved}")
        return [verify_readme_file(resolved, repo_root)]

    if target_dir:
        resolved_dir = (repo_root / target_dir).resolve()
        if not resolved_dir.exists():
            raise FileNotFoundError(f"Target directory not found: {resolved_dir}")
        found = find_readme_files(resolved_dir.parent, [resolved_dir.name])
        return [verify_readme_file(f, repo_root) for f in found]

    # Default: scan target repository directories
    found_files = find_readme_files(repo_root, target_dirs or DEFAULT_TARGET_DIRS)
    return [verify_readme_file(f, repo_root) for f in found_files]


def print_report(modules: List[ModuleDoc], json_output: bool = False, quiet: bool = False) -> int:
    """Prints diagnostic report and returns appropriate process exit code."""
    total = len(modules)
    passed = sum(1 for m in modules if m.is_compliant)
    failed = total - passed

    report_data = {
        "total_checked": total,
        "compliant_count": passed,
        "violation_count": failed,
        "all_compliant": (failed == 0),
        "results": [],
    }

    for m in modules:
        entry = {
            "path": m.path,
            "title": m.title,
            "is_compliant": m.is_compliant,
            "missing_sections": m.missing_sections,
            "stub_sections": m.stub_sections,
        }
        report_data["results"].append(entry)

    if json_output:
        print(json.dumps(report_data, indent=2))
        return 0 if failed == 0 else 1

    print("=" * 80)
    print("  FASTAPI BOOKINGS — LIVING DOCUMENTATION COMPLIANCE LINTER (RULE 10)")
    print("=" * 80)

    for m in modules:
        if m.is_compliant:
            if not quiet:
                print(f"[PASS] {m.path}")
                print(f"       Title: {m.title}")
                print(f"       All 7 mandatory sections present with complete documentation.\n")
        else:
            print(f"[FAIL] {m.path}")
            print(f"       Title: {m.title}")
            if m.missing_sections:
                print(f"       Missing Mandatory Sections ({len(m.missing_sections)}):")
                for s in m.missing_sections:
                    print(f"         - {s}")
            if m.stub_sections:
                print(f"       Empty or Placeholder Stubs ({len(m.stub_sections)}):")
                for s in m.stub_sections:
                    print(f"         - {s}")
            print()

    print("-" * 80)
    print(f"Summary: {total} files inspected | {passed} compliant | {failed} non-compliant")
    if failed == 0:
        print("[OK] All verified documentation files strictly comply with AGENTS.md Rule 10.")
        return 0
    else:
        print(f"[ERROR] {failed} documentation file(s) violate Rule 10 standards.")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule 10 Living Documentation Verifier")
    parser.add_argument("--path", type=str, help="Verify a single README.md file")
    parser.add_argument("--dir", type=str, help="Verify all README.md files under a directory")
    parser.add_argument("--dirs", nargs="*", default=None, help="Directories to scan")
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON diagnostic report")
    parser.add_argument("--quiet", action="store_true", help="Suppress output for passing files")

    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    target_path = Path(args.path) if args.path else None
    target_dir = Path(args.dir) if args.dir else None

    try:
        modules = run_verification(repo_root, target_path, target_dir, args.dirs)
    except FileNotFoundError as e:
        print(f"[!] Error: {e}", file=sys.stderr)
        return 1

    return print_report(modules, json_output=args.json, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
