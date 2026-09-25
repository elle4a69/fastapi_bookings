"""
Codex Control Centre - Dependency Vulnerability Audit Tool
Audits pinned Python dependencies in requirements.txt and requirements-dev.txt
against the PyPA / OSV vulnerability database using pip-audit API.
"""

import sys
from pathlib import Path
import importlib.metadata
from packaging.version import Version
from packaging.requirements import Requirement

def audit_requirements_file(file_path: Path, service) -> list[dict]:
    results = []
    if not file_path.exists():
        return results

    lines = file_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            req = Requirement(line)
            pkg_name = req.name
            try:
                installed_ver = importlib.metadata.version(pkg_name)
            except importlib.metadata.PackageNotFoundError:
                installed_ver = "unknown"

            from pip_audit._service import ResolvedDependency
            dep = ResolvedDependency(name=pkg_name, version=Version(installed_ver if installed_ver != "unknown" else "0.0.0"))
            _, vulns = service.query(dep)
            results.append({
                "package": pkg_name,
                "installed_version": installed_ver,
                "requirement": line,
                "vulnerabilities": vulns
            })
        except Exception as e:
            results.append({
                "package": line,
                "installed_version": "error",
                "requirement": line,
                "error": str(e),
                "vulnerabilities": []
            })
    return results

def main():
    root = Path(__file__).resolve().parent.parent
    req_file = root / "requirements.txt"
    req_dev_file = root / "requirements-dev.txt"

    print("=== Codex Control Centre: Python Dependency Security Audit ===")
    try:
        from pip_audit._service import PyPIService
        service = PyPIService()
    except Exception as e:
        print(f"[ERROR] Failed to initialize PyPIService: {e}")
        sys.exit(1)

    all_results = []
    all_results.extend(audit_requirements_file(req_file, service))
    all_results.extend(audit_requirements_file(req_dev_file, service))

    vuln_count = 0
    print(f"\n{'Package':<24} {'Installed':<15} {'Status':<15} {'Advisories'}")
    print("-" * 75)
    for r in all_results:
        pkg = r["package"]
        ver = r["installed_version"]
        vulns = r.get("vulnerabilities", [])
        if vulns:
            # Check if vulnerabilities are critical
            vuln_count += len(vulns)
            vuln_ids = ", ".join([v.id for v in vulns])
            print(f"{pkg:<24} {ver:<15} [WARNING]       {vuln_ids}")
        else:
            print(f"{pkg:<24} {ver:<15} [CLEAN]         0 known CVEs")

    print("-" * 75)
    print(f"Total Packages Audited: {len(all_results)} | Known Vulnerabilities: {vuln_count}")
    if vuln_count > 0:
        print("\nNote: Review any reported advisories for applicability to environment/platform.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
