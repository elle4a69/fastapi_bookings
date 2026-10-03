#!/usr/bin/env python3
"""
Living Documentation Query Tool (LDI-AKM)
Repository: FastAPI Bookings (f:/Projects/fastapi_bookings)
Standard: AGENTS.md Rule 10 (Living Module Documentation and README Maintenance)

High-speed CLI utility and subagent retrieval engine for searching module docs,
retrieving verification test commands, inspecting module architecture,
and auditing codebase-wide known technical debt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_DB_REL_PATH = "docs/module_docs.db"
DEFAULT_MANIFEST_REL_PATH = "docs/module_manifest.json"


def ensure_index_exists(repo_root: Path, db_path: Path, manifest_path: Path) -> None:
    """Verifies that the SQLite database exists and is populated; if not, triggers indexer."""
    needs_rebuild = False

    if not db_path.exists() or db_path.stat().st_size == 0:
        needs_rebuild = True
    else:
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM modules;")
            count = cur.fetchone()[0]
            conn.close()
            if count == 0:
                needs_rebuild = True
        except Exception:
            needs_rebuild = True

    if needs_rebuild:
        indexer_script = repo_root / "scripts" / "index_living_docs.py"
        if not indexer_script.exists():
            print(f"[!] Cannot auto-index: {indexer_script} not found.", file=sys.stderr)
            return
        
        # Invoke indexer
        cmd = [sys.executable, str(indexer_script), "--root", str(repo_root), "--quiet"]
        try:
            subprocess.run(cmd, check=True, cwd=str(repo_root))
        except subprocess.CalledProcessError as e:
            print(f"[!] Auto-indexing failed with exit code {e.returncode}", file=sys.stderr)


def sanitize_fts_query(query: str) -> str:
    """
    Sanitizes arbitrary user or agent search queries into valid SQLite FTS5 syntax,
    preventing syntax errors from slashes, colons, or punctuation.
    """
    query = query.strip()
    if not query:
        return '""'

    # Extract all alphanumeric words, underscores, hyphens
    tokens = re.findall(r"[a-zA-Z0-9_\-]+", query)
    if not tokens:
        return '""'

    # Quote each token and combine with NEAR or AND
    quoted_tokens = [f'"{tok}"' for tok in tokens]
    return " ".join(quoted_tokens)


def query_search(db_path: Path, search_query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Executes FTS5 search across title, path, section_title, and content."""
    sanitized = sanitize_fts_query(search_query)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql = """
        SELECT 
            m.id AS module_id,
            m.path,
            m.title,
            m.domain,
            m.verification_command,
            f.section_title,
            snippet(module_fts, 4, '[[', ']]', '...', 18) AS snippet,
            bm25(module_fts) AS rank
        FROM module_fts f
        JOIN modules m ON m.id = f.module_id
        WHERE module_fts MATCH ?
        ORDER BY rank ASC
        LIMIT ?;
    """

    results: List[Dict[str, Any]] = []
    try:
        for row in cursor.execute(sql, (sanitized, limit)):
            results.append({
                "module_id": row["module_id"],
                "path": row["path"],
                "title": row["title"],
                "domain": row["domain"],
                "section_title": row["section_title"],
                "snippet": row["snippet"],
                "verification_command": row["verification_command"] or "",
                "rank": round(float(row["rank"]), 4),
            })
    except sqlite3.OperationalError as e:
        # Fallback to direct LIKE if query still trips syntax
        fallback_sql = """
            SELECT 
                m.id AS module_id,
                m.path,
                m.title,
                m.domain,
                m.verification_command,
                s.section_title,
                SUBSTR(s.content, 1, 140) AS snippet,
                1.0 AS rank
            FROM module_sections s
            JOIN modules m ON m.id = s.module_id
            WHERE s.content LIKE ? OR s.section_title LIKE ? OR m.title LIKE ?
            LIMIT ?;
        """
        pattern = f"%{search_query.strip()}%"
        for row in cursor.execute(fallback_sql, (pattern, pattern, pattern, limit)):
            results.append({
                "module_id": row["module_id"],
                "path": row["path"],
                "title": row["title"],
                "domain": row["domain"],
                "section_title": row["section_title"],
                "snippet": row["snippet"] + "...",
                "verification_command": row["verification_command"] or "",
                "rank": 1.0,
            })
    finally:
        conn.close()

    return results


def query_module(db_path: Path, manifest_path: Path, identifier: str) -> Optional[Dict[str, Any]]:
    """Retrieves comprehensive details for a specific module by path, id, or keyword."""
    # First attempt to read from manifest for complete structured dictionary
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            modules = data.get("modules", [])
            norm_id = identifier.strip().lower().replace("\\", "/")
            for suffix in ("/readme.md", "/readme.MD"):
                norm_id = norm_id.removesuffix(suffix)
            # 1. Exact path or ID match
            for m in modules:
                m_path = m["path"].lower()
                for suffix in ("/readme.md", "/readme.MD"):
                    m_path = m_path.removesuffix(suffix)
                if m["id"].lower() == norm_id or m_path == norm_id or m["dir_path"].lower() == norm_id:
                    return m
            # 2. Substring match
            for m in modules:
                if norm_id in m["path"].lower() or norm_id in m["id"].lower() or norm_id in m["title"].lower():
                    return m
        except Exception:
            pass

    # Fallback to DB
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    pattern = f"%{identifier.strip().lower()}%"
    row = cursor.execute("""
        SELECT * FROM modules 
        WHERE LOWER(path) LIKE ? OR LOWER(id) LIKE ? OR LOWER(title) LIKE ?
        LIMIT 1;
    """, (pattern, pattern, pattern)).fetchone()

    if not row:
        conn.close()
        return None

    mod_dict = dict(row)
    sections = {}
    for s_row in cursor.execute("""
        SELECT section_key, section_title, content 
        FROM module_sections 
        WHERE module_id = ? 
        ORDER BY section_index ASC;
    """, (row["id"],)):
        sections[s_row["section_key"]] = s_row["content"]

    mod_dict["sections"] = sections
    conn.close()
    return mod_dict


def query_test_command(db_path: Path, identifier: str) -> Optional[str]:
    """Retrieves only the verification test command for a module."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    pattern = f"%{identifier.strip().lower()}%"
    row = cursor.execute("""
        SELECT path, verification_command FROM modules 
        WHERE LOWER(path) LIKE ? OR LOWER(id) LIKE ? OR LOWER(title) LIKE ?
        LIMIT 1;
    """, (pattern, pattern, pattern)).fetchone()
    conn.close()

    if row and row["verification_command"]:
        return row["verification_command"]
    return None


def query_known_issues(manifest_path: Path, db_path: Path) -> List[Dict[str, Any]]:
    """Aggregates all known issues, limitations, and edge cases across the codebase."""
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            modules = data.get("modules", [])
            output = []
            for m in modules:
                issues = m.get("known_issues", [])
                if issues:
                    output.append({
                        "path": m["path"],
                        "dir_path": m.get("dir_path", ""),
                        "title": m["title"],
                        "domain": m["domain"],
                        "known_issues": issues,
                    })
            return output
        except Exception:
            pass

    # Fallback to DB
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    output = []
    for row in cursor.execute("""
        SELECT m.path, m.dir_path, m.title, m.domain, s.content
        FROM modules m
        JOIN module_sections s ON s.module_id = m.id
        WHERE s.section_key = 'known_issues_and_limitations' AND LENGTH(TRIM(s.content)) > 0;
    """):
        text = row["content"].strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        output.append({
            "path": row["path"],
            "dir_path": row["dir_path"],
            "title": row["title"],
            "domain": row["domain"],
            "known_issues": lines[:10],
        })

    conn.close()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Living Documentation & Agent Knowledge Manifest")
    parser.add_argument("--search", type=str, help="Full-text FTS5 search query")
    parser.add_argument("--module", type=str, help="View detailed documentation for a specific module")
    parser.add_argument("--test-command", type=str, help="Get verification test command for a module")
    parser.add_argument("--known-issues", action="store_true", help="Summarize all known technical debt across codebase")
    parser.add_argument("--boot-snapshot", action="store_true", help="Print concise agent boot snapshot directory briefing")
    parser.add_argument("--json", action="store_true", help="Output raw structured JSON")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_REL_PATH, help="Path to module_docs.db")
    parser.add_argument("--manifest", type=str, default=DEFAULT_MANIFEST_REL_PATH, help="Path to module_manifest.json")
    parser.add_argument("--root", type=str, default=".", help="Repository root path")

    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    db_path = repo_root / args.db
    manifest_path = repo_root / args.manifest

    # Ensure database is present and initialized
    ensure_index_exists(repo_root, db_path, manifest_path)

    # 0. Agent Boot Snapshot Mode
    if args.boot_snapshot:
        snapshot_file = repo_root / "docs" / "AGENT_BOOT_SNAPSHOT.md"
        if not snapshot_file.exists():
            ensure_index_exists(repo_root, db_path, manifest_path)
        if snapshot_file.exists():
            content = snapshot_file.read_text(encoding="utf-8")
            if args.json:
                print(json.dumps({"boot_snapshot": content}, indent=2))
            else:
                print(content)
            return 0
        else:
            print("[!] Agent boot snapshot not found.", file=sys.stderr)
            return 1

    # 1. Verification Test Command Mode
    if args.test_command:
        cmd = query_test_command(db_path, args.test_command)
        if args.json:
            print(json.dumps({"module": args.test_command, "verification_command": cmd or ""}, indent=2))
        else:
            if cmd:
                print(cmd)
            else:
                print(f"[!] No verification command found for module matching '{args.test_command}'", file=sys.stderr)
        return 0 if cmd else 1

    # 2. Known Issues Audit Mode
    if args.known_issues:
        issues = query_known_issues(manifest_path, db_path)
        if args.json:
            print(json.dumps({"total_modules_with_issues": len(issues), "modules": issues}, indent=2))
        else:
            print(f"=== Known Issues & Technical Debt Summary ({len(issues)} modules) ===\n")
            for item in issues:
                print(f"[*] {item['title']} ({item['path']}):")
                for issue in item["known_issues"]:
                    print(f"    - {issue}")
                print()
        return 0

    # 3. Specific Module Inspection Mode
    if args.module:
        mod = query_module(db_path, manifest_path, args.module)
        if not mod:
            if args.json:
                print(json.dumps({"error": f"Module not found matching '{args.module}'"}, indent=2))
            else:
                print(f"[!] Module not found matching '{args.module}'", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(mod, indent=2))
        else:
            print(f"=== Module: {mod.get('title')} ===")
            print(f"Path: {mod.get('path')}")
            print(f"Domain: {mod.get('domain')}")
            if mod.get("verification_command"):
                print(f"Verification Command: {mod.get('verification_command')}")
            if mod.get("primary_files"):
                print(f"Primary Files: {', '.join(mod.get('primary_files'))}")
            print("\n--- Sections ---")
            sections = mod.get("sections", {})
            for sec_key, sec_val in sections.items():
                if sec_val:
                    readable_key = sec_key.replace("_", " ").title()
                    print(f"\n[## {readable_key}]")
                    # Print first 500 characters of section
                    snippet = sec_val.strip()
                    if len(snippet) > 600:
                        snippet = snippet[:600] + "\n...(truncated)..."
                    print(snippet)
        return 0

    # 4. Search Query Mode
    if args.search:
        results = query_search(db_path, args.search)
        if args.json:
            print(json.dumps({"query": args.search, "count": len(results), "results": results}, indent=2))
        else:
            print(f"=== Search Results for '{args.search}' ({len(results)} matches) ===\n")
            if not results:
                print("No matches found.")
            for r in results:
                print(f"[*] {r['title']} [{r['path']}]")
                print(f"    Section: {r['section_title']}")
                print(f"    Snippet: {r['snippet']}")
                if r.get("verification_command"):
                    print(f"    Test: {r['verification_command']}")
                print()
        return 0

    # No arguments provided
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
