#!/usr/bin/env python3
"""
Living Documentation Indexer & Agent Knowledge Manifest (LDI-AKM)
Repository: FastAPI Bookings (f:/Projects/fastapi_bookings)
Standard: AGENTS.md Rule 10 (Living Module Documentation and README Maintenance)

Traverses repository module READMEs, validates the 7 mandatory sections,
extracts domain metadata, verification commands, primary files, and known issues,
builds docs/module_manifest.json, generates docs/MODULE_INDEX.md, and creates
docs/module_docs.db with full-text SQLite FTS5 search.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# -----------------------------------------------------------------------------
# Constants & Configuration
# -----------------------------------------------------------------------------

DEFAULT_TARGET_DIRS = ["app", "frontend", "docs", "alembic", "scripts", "tests", "mapbox"]

EXCLUDED_DIR_NAMES = {
    ".venv",
    "node_modules",
    ".git",
    ".pytest_cache",
    "__pycache__",
    "signoz",
    "scratch",
    "pours",
    "backups",
    "worktrees",
    "codex-control-centre",
    "dev-dashboard",
    "htmlcov",
    ".coverage",
}

# The 7 mandatory sections specified in Rule 10
MANDATORY_SECTION_SPECS = [
    {
        "key": "purpose_and_scope",
        "title": "Purpose & Scope",
        "patterns": [
            re.compile(r"purpose\s*(?:&|and)?\s*scope", re.IGNORECASE),
            re.compile(r"purpose\s*(?:&|and)?\s*architectural\s*mandate", re.IGNORECASE),
            re.compile(r"^purpose\b", re.IGNORECASE),
            re.compile(r"^scope\b", re.IGNORECASE),
        ],
    },
    {
        "key": "architecture_and_key_files",
        "title": "Architecture & Key Files",
        "patterns": [
            re.compile(r"architecture\s*(?:&|and)?\s*key\s*files", re.IGNORECASE),
            re.compile(r"architecture\s*(?:&|and)?\s*(?:directory|structure|layout|subsystems)", re.IGNORECASE),
            re.compile(r"^architecture\b", re.IGNORECASE),
            re.compile(r"key\s*files", re.IGNORECASE),
        ],
    },
    {
        "key": "setup_configuration_and_dependencies",
        "title": "Setup, Configuration & Dependencies",
        "patterns": [
            re.compile(r"setup[,\s]+configuration\s*(?:&|and)?\s*dependencies", re.IGNORECASE),
            re.compile(r"setup\s*(?:&|and)?\s*configuration", re.IGNORECASE),
            re.compile(r"configuration\s*(?:&|and)?\s*dependencies", re.IGNORECASE),
            re.compile(r"setup\s*(?:&|and)?\s*dependencies", re.IGNORECASE),
            re.compile(r"^setup\b", re.IGNORECASE),
            re.compile(r"^configuration\b", re.IGNORECASE),
            re.compile(r"dependencies", re.IGNORECASE),
            re.compile(r"environment\s*variables", re.IGNORECASE),
        ],
    },
    {
        "key": "core_workflows_and_contracts",
        "title": "Core Workflows & Contracts",
        "patterns": [
            re.compile(r"(?:core\s+)?workflows\s*(?:&|and)?\s*contracts", re.IGNORECASE),
            re.compile(r"core\s+workflows", re.IGNORECASE),
            re.compile(r"workflows", re.IGNORECASE),
            re.compile(r"api\s*contracts?", re.IGNORECASE),
            re.compile(r"contracts?", re.IGNORECASE),
            re.compile(r"endpoints?", re.IGNORECASE),
            re.compile(r"lifecycle", re.IGNORECASE),
            re.compile(r"presets", re.IGNORECASE),
        ],
    },
    {
        "key": "data_safety_and_isolation",
        "title": "Data Safety & Isolation",
        "patterns": [
            re.compile(r"data\s*safety\s*(?:&|and)?\s*isolation", re.IGNORECASE),
            re.compile(r"data\s*safety\s*(?:&|and)?\s*privacy", re.IGNORECASE),
            re.compile(r"data\s*safety", re.IGNORECASE),
            re.compile(r"security\s*(?:&|and)?\s*isolation", re.IGNORECASE),
            re.compile(r"multi-tenant\s*isolation", re.IGNORECASE),
            re.compile(r"tenant\s*isolation", re.IGNORECASE),
        ],
    },
    {
        "key": "known_issues_and_limitations",
        "title": "Known Issues, Edge Cases & Outstanding Work",
        "patterns": [
            re.compile(r"known\s*issues[,\s]+edge\s*cases\s*(?:&|and)?\s*outstanding\s*work", re.IGNORECASE),
            re.compile(r"known\s*issues\s*(?:&|and)?\s*(?:limitations|outstanding\s*work|technical\s*debt|edge\s*cases)", re.IGNORECASE),
            re.compile(r"known\s*issues", re.IGNORECASE),
            re.compile(r"outstanding\s*work", re.IGNORECASE),
            re.compile(r"technical\s*debt", re.IGNORECASE),
            re.compile(r"limitations", re.IGNORECASE),
            re.compile(r"current\s*limitations", re.IGNORECASE),
            re.compile(r"edge\s*cases", re.IGNORECASE),
        ],
    },
    {
        "key": "verification_and_testing",
        "title": "Verification & Testing Commands",
        "patterns": [
            re.compile(r"verification\s*(?:&|and)?\s*testing\s*commands", re.IGNORECASE),
            re.compile(r"verification\s*(?:&|and)?\s*testing", re.IGNORECASE),
            re.compile(r"testing\s*commands", re.IGNORECASE),
            re.compile(r"verification\s*commands", re.IGNORECASE),
            re.compile(r"^verification\b", re.IGNORECASE),
            re.compile(r"^testing\b", re.IGNORECASE),
        ],
    },
]

STUB_REGEXES = [
    re.compile(r"^\s*(?:todo|tbd|wip|placeholder|empty|coming\s+soon|none\s+yet|n/a|fill\s+in)\s*$", re.IGNORECASE),
    re.compile(r"<!--\s*(?:todo|tbd|placeholder)\s*-->", re.IGNORECASE),
    re.compile(r"^\[(?:insert|placeholder|todo|tbd)[^\]]*\]$", re.IGNORECASE),
]


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------

@dataclass
class SectionRecord:
    key: str
    title: str
    content: str
    is_mandatory: bool
    is_stub: bool
    stub_reason: str = ""


@dataclass
class ModuleDoc:
    id: str
    path: str
    dir_path: str
    title: str
    domain: str
    primary_files: List[str]
    verification_command: str
    known_issues: List[str]
    sections: Dict[str, str]
    all_sections: List[Dict[str, Any]]
    is_compliant: bool
    missing_sections: List[str]
    stub_sections: List[str]
    updated_at: str


# -----------------------------------------------------------------------------
# Domain & Metadata Resolution
# -----------------------------------------------------------------------------

def infer_domain(rel_path: str) -> str:
    """Infers high-level system domain based on module path."""
    p = rel_path.replace("\\", "/").lower()
    if "app/api/routers" in p:
        return "HTTP REST API Endpoints"
    if "app/api" in p:
        return "API Dependency & Security Boundaries"
    if "app/core" in p:
        return "Core Configuration & Telemetry"
    if "app/db" in p:
        return "Database Engine & Sessions"
    if "app/models" in p:
        return "SQLAlchemy ORM Data Models"
    if "app/schemas" in p:
        return "Pydantic Schema Contracts"
    if "app/services/sms" in p:
        return "Autonomous SMS Dialogue Engine"
    if "app/services/business_assistant" in p:
        return "Business Assistant Foundation"
    if "app/services/scheduling" in p:
        return "Scheduling & Slot Allocation"
    if "app/services/resident_agent" in p:
        return "Autonomous Resident Sentinel"
    if "app/services/curation" in p:
        return "Semantic Memory Curation"
    if "app/services/knowledge" in p:
        return "Knowledge Subsystems & Graphiti"
    if "app/services/routing" in p:
        return "Routing & Geospatial Engine"
    if "app/services/messaging" in p:
        return "Chatwoot & Omnichannel Messaging"
    if "app/services/localization" in p:
        return "Dynamic Localization & Terminology"
    if "app/services/booking" in p or "booking" in p:
        return "Core Booking Engine"
    if "app/services/assistant" in p:
        return "Assistant Runtime Services"
    if "app/services/channel" in p:
        return "Communication Channel Transports"
    if "app/services" in p:
        return "Application Business Services"
    if "frontend/src/pages/admin/sms" in p:
        return "Frontend Admin SMS Workspace"
    if "frontend/src/pages/admin/business-assistant" in p:
        return "Frontend Admin Business Assistant"
    if "frontend/src/pages/admin/finance" in p:
        return "Frontend Admin Finance & Billing"
    if "frontend/src/pages/admin/catalog" in p:
        return "Frontend Admin Catalog & Services"
    if "frontend/src/pages/admin/schedule" in p:
        return "Frontend Admin Schedule Calendar"
    if "frontend/src/pages/admin/assistant-studio" in p:
        return "Frontend Admin Assistant Studio"
    if "frontend/src/pages/admin" in p:
        return "Frontend Administration Views"
    if "frontend/src/pages/portal" in p:
        return "Frontend Client Portal"
    if "frontend/src/pages/public" in p:
        return "Frontend Public Booking Widget"
    if "frontend" in p:
        return "React Frontend SPA"
    if "alembic" in p:
        return "Database Schema Migrations"
    if "docs" in p:
        return "Documentation & Architecture Catalog"
    if "mapbox" in p:
        return "Mapbox GL Geospatial Discovery Prototype"
    if "scripts" in p:
        return "Operational Automation & Release Gates"
    if "tests" in p:
        return "Automated Test Suites"
    return "Application Module"


def generate_module_id(rel_path: str) -> str:
    """Creates a clean deterministic module identifier from its relative path."""
    clean = rel_path.replace("\\", "/")
    for suffix in ("/README.md", "/readme.md", "/README.MD", "/Readme.md"):
        clean = clean.removesuffix(suffix)
    if clean.endswith("/"):
        clean = clean[:-1]
    ident = re.sub(r"[^a-zA-Z0-9]+", "_", clean).strip("_")
    return ident if ident else "root"


# -----------------------------------------------------------------------------
# Markdown Heading & Content Parsing
# -----------------------------------------------------------------------------

def check_stub(content: str) -> Tuple[bool, str]:
    """
    Checks if a section content block constitutes an empty placeholder stub.
    Returns (is_stub, reason).
    """
    stripped = content.strip()
    if not stripped:
        return True, "Section is empty"
    
    # Strip HTML comments and markdown markers
    clean = re.sub(r"<!--.*?-->", "", stripped, flags=re.DOTALL).strip()
    clean = re.sub(r"^[#>*\-\s]+", "", clean).strip()
    if not clean:
        return True, "Section contains only empty markdown or HTML comments"

    for pat in STUB_REGEXES:
        if pat.search(clean):
            return True, f"Matched stub pattern: '{clean[:40]}'"
    
    # Text shorter than 15 chars without code block or lists
    if len(clean) < 15 and not any(tag in stripped for tag in ("`", "-", "*", "1.")):
        if any(w in clean.lower() for w in ("todo", "tbd", "wip", "none", "n/a", "coming")):
            return True, f"Stub phrase under 15 characters: '{clean}'"

    return False, ""


def split_markdown_headings(content: str) -> List[Tuple[int, str, str]]:
    """
    Splits markdown content into a list of tuples:
    (heading_level, heading_title, section_body).
    Correctly ignores '#' comments inside fenced code blocks.
    """
    lines = content.splitlines()
    sections: List[Tuple[int, str, str]] = []
    current_level = 0
    current_title = ""
    current_body: List[str] = []
    in_code_block = False

    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            current_body.append(line)
            continue

        if not in_code_block:
            match = heading_pattern.match(line)
            if match:
                if current_title or current_body:
                    sections.append((current_level, current_title, "\n".join(current_body).strip()))
                    current_body = []
                current_level = len(match.group(1))
                current_title = match.group(2).strip()
                continue

        current_body.append(line)

    if current_title or current_body:
        sections.append((current_level, current_title, "\n".join(current_body).strip()))

    return sections


def clean_heading_text(heading: str) -> str:
    """Removes leading hashes, numbers (e.g. '1.', '## 2.3', 'Phase 5:') and backticks."""
    text = re.sub(r"^#+\s*", "", heading)
    text = re.sub(r"^[0-9]+(?:\.[0-9]+)*[\.\:\-\)\s]+", "", text)
    text = re.sub(r"^(?:Phase|Step|Gate)\s+[0-9]+[\.\:\-\)\s]+", "", text, flags=re.IGNORECASE)
    text = text.replace("`", "").strip()
    return text


def extract_title(content: str, fallback_path: str) -> str:
    """Extracts module title from the first H1 heading, or falls back to path name."""
    for line in content.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            raw = line[2:].strip()
            # Remove trailing parens with path like (`app/services/sms`)
            cleaned = re.sub(r"\s*\(.*?\)$", "", raw).strip()
            cleaned = cleaned.replace("`", "")
            if cleaned:
                return cleaned
    # Fallback to directory name
    p = Path(fallback_path)
    parent = p.parent.name
    return parent.replace("_", " ").title() if parent else "FastAPI Bookings Module"


def extract_primary_files(arch_text: str, full_content: str, base_dir: Path) -> List[str]:
    """Extracts key files mentioned in the architecture section or document."""
    candidates: List[str] = []
    text_to_search = arch_text if len(arch_text) > 40 else full_content

    # 1. Markdown link targets or titles: [file.py](...)
    link_files = re.findall(r"\[([a-zA-Z0-9_\-\.\/]+\.(?:py|tsx?|jsx?|json|sql|md|ya?ml))\]", text_to_search)
    candidates.extend(link_files)

    # 2. Backticked filenames: `inbound_service.py`
    backtick_files = re.findall(r"`([a-zA-Z0-9_\-\.\/]+\.(?:py|tsx?|jsx?|json|sql|md|ya?ml))`", text_to_search)
    candidates.extend(backtick_files)

    # 3. File tree lines: ├── inbound_service.py or - inbound_service.py
    tree_files = re.findall(r"[├└│\-\*\s]+([a-zA-Z0-9_\-\/]+\.(?:py|tsx?|jsx?|json|sql|ya?ml))", text_to_search)
    candidates.extend(tree_files)

    seen = set()
    cleaned_files: List[str] = []
    for f in candidates:
        basename = os.path.basename(f)
        if basename in seen or not basename:
            continue
        # Exclude typical false positives
        if basename.lower() in ("readme.md", "package.json", "tsconfig.json", "docker-compose.yml"):
            continue
        seen.add(basename)
        cleaned_files.append(basename)

    # If we found files located right in base_dir, ensure they're prioritized
    if base_dir.exists():
        for p in base_dir.glob("*.py"):
            if p.name not in seen and not p.name.startswith("__"):
                cleaned_files.append(p.name)
                seen.add(p.name)

    return cleaned_files[:12]


def extract_verification_command(verif_text: str) -> str:
    """Extracts the primary executable test command from verification text."""
    if not verif_text:
        return ""

    # Check for code blocks
    blocks = re.findall(r"```(?:powershell|bash|sh|shell|cmd)?\s*\n(.*?)\n```", verif_text, re.DOTALL)
    for block in blocks:
        for line in block.strip().splitlines():
            clean = line.strip()
            # Remove leading prompt symbols including PowerShell call operator (&)
            clean = re.sub(r"^[\$\#\>\&]\s*", "", clean)
            if clean.startswith(("python", "pytest", "py ", "py -", ".venv", ".\\.venv", "npm", "pnpm", "npx")):
                return clean

    # Look for inline command mentions
    inline = re.findall(r"`((?:pytest|python\s+-[m]|py\s+-[m0-9]|npm\s+test)[^`]*)`", verif_text)
    if inline:
        return inline[0].strip()

    # Plain text search
    for line in verif_text.splitlines():
        clean = line.strip()
        clean = re.sub(r"^[\$\#\>\&]\s*", "", clean)
        if clean.startswith(("pytest ", "python -m pytest ", "py ", "py -")):
            return clean

    return ""


def extract_known_issues(issues_text: str) -> List[str]:
    """Extracts known issues as a clean list of bullet points or numbered items."""
    if not issues_text:
        return []

    items: List[str] = []
    lines = issues_text.splitlines()
    current_item: List[str] = []

    for line in lines:
        stripped = line.strip()
        # Detect new item: 1. ... or - ... or * ...
        if re.match(r"^(?:[0-9]+[\.\)]|[\-\*])\s+", stripped):
            if current_item:
                items.append(" ".join(current_item).strip())
                current_item = []
            clean = re.sub(r"^(?:[0-9]+[\.\)]|[\-\*])\s+", "", stripped)
            current_item.append(clean)
        elif stripped and current_item:
            current_item.append(stripped)

    if current_item:
        items.append(" ".join(current_item).strip())

    if not items:
        # Fallback to non-empty paragraphs
        paragraphs = [p.strip() for p in issues_text.split("\n\n") if p.strip()]
        for p in paragraphs:
            if not p.startswith("#"):
                items.append(p)

    return items[:10]


# -----------------------------------------------------------------------------
# Module README Parser
# -----------------------------------------------------------------------------

def parse_readme(file_path: Path, repo_root: Path) -> ModuleDoc:
    """
    Parses a single README.md file, maps the 7 mandatory sections,
    extracts metadata, checks compliance, and returns a structured ModuleDoc.
    """
    rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")
    dir_path = str(file_path.parent.relative_to(repo_root)).replace("\\", "/")

    content = file_path.read_text(encoding="utf-8", errors="replace")
    title = extract_title(content, rel_path)
    domain = infer_domain(rel_path)

    raw_sections = split_markdown_headings(content)

    canonical_sections: Dict[str, str] = {spec["key"]: "" for spec in MANDATORY_SECTION_SPECS}
    all_sections_record: List[Dict[str, Any]] = []

    current_canonical_key: Optional[str] = None
    current_canonical_level: int = 2

    for lvl, raw_title, body in raw_sections:
        clean_title = clean_heading_text(raw_title)
        matched_key: Optional[str] = None

        # Check against mandatory specs
        for spec in MANDATORY_SECTION_SPECS:
            for pattern in spec["patterns"]:
                if pattern.search(clean_title) or pattern.search(raw_title):
                    matched_key = spec["key"]
                    break
            if matched_key:
                break

        if matched_key:
            current_canonical_key = matched_key
            current_canonical_level = lvl
            if canonical_sections[matched_key]:
                canonical_sections[matched_key] += f"\n\n### {clean_title}\n\n{body}"
            else:
                canonical_sections[matched_key] = body
            mapped_for_record = matched_key
        elif current_canonical_key and lvl > current_canonical_level:
            # Hierarchical child subsection belonging to the current canonical section
            canonical_sections[current_canonical_key] += f"\n\n### {clean_title}\n\n{body}"
            mapped_for_record = current_canonical_key
        else:
            # A new heading that does not match and is not a child of previous canonical section
            current_canonical_key = None
            mapped_for_record = None

        all_sections_record.append({
            "level": lvl,
            "title": raw_title,
            "clean_title": clean_title,
            "mapped_canonical": mapped_for_record,
            "content": body,
        })

    # Verify compliance and stubs
    missing_sections: List[str] = []
    stub_sections: List[str] = []

    for spec in MANDATORY_SECTION_SPECS:
        key = spec["key"]
        sec_title = spec["title"]
        sec_content = canonical_sections.get(key, "").strip()

        if not sec_content:
            missing_sections.append(sec_title)
        else:
            is_stub, reason = check_stub(sec_content)
            if is_stub:
                stub_sections.append(f"{sec_title} ({reason})")

    is_compliant = (len(missing_sections) == 0 and len(stub_sections) == 0)

    arch_text = canonical_sections.get("architecture_and_key_files", "")
    primary_files = extract_primary_files(arch_text, content, file_path.parent)

    verif_text = canonical_sections.get("verification_and_testing", "")
    verif_cmd = extract_verification_command(verif_text)
    if not verif_cmd:
        verif_cmd = extract_verification_command(content)

    known_text = canonical_sections.get("known_issues_and_limitations", "")
    known_issues = extract_known_issues(known_text)

    # File updated timestamp
    try:
        mtime = file_path.stat().st_mtime
        updated_at = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).isoformat()
    except Exception:
        updated_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    return ModuleDoc(
        id=generate_module_id(rel_path),
        path=rel_path,
        dir_path=dir_path,
        title=title,
        domain=domain,
        primary_files=primary_files,
        verification_command=verif_cmd,
        known_issues=known_issues,
        sections=canonical_sections,
        all_sections=all_sections_record,
        is_compliant=is_compliant,
        missing_sections=missing_sections,
        stub_sections=stub_sections,
        updated_at=updated_at,
    )


def find_readme_files(repo_root: Path, target_dirs: Optional[List[str]] = None) -> List[Path]:
    """Finds all module README.md files across target directories."""
    dirs_to_scan = target_dirs or DEFAULT_TARGET_DIRS
    found: List[Path] = []

    for target in dirs_to_scan:
        target_path = repo_root / target
        if not target_path.exists():
            continue
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")]
            for f in files:
                if f.lower() == "readme.md":
                    full_p = Path(root) / f
                    found.append(full_p)

    return sorted(found)


# -----------------------------------------------------------------------------
# Database Indexing (SQLite with FTS5)
# -----------------------------------------------------------------------------

def index_database(modules: List[ModuleDoc], db_path: Path) -> None:
    """Populates SQLite database with modules, sections, and FTS5 search index."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    with conn:
        conn.execute("""
            CREATE TABLE modules (
                id TEXT PRIMARY KEY,
                path TEXT UNIQUE,
                dir_path TEXT,
                title TEXT,
                domain TEXT,
                verification_command TEXT,
                is_compliant INTEGER,
                updated_at TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE module_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id TEXT,
                section_index INTEGER,
                section_key TEXT,
                section_title TEXT,
                content TEXT,
                FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
            );
        """)

        conn.execute("""
            CREATE VIRTUAL TABLE module_fts USING fts5(
                module_id UNINDEXED,
                title,
                path,
                section_title,
                content,
                tokenize = 'porter unicode61'
            );
        """)

        for mod in modules:
            conn.execute(
                """
                INSERT INTO modules (id, path, dir_path, title, domain, verification_command, is_compliant, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mod.id,
                    mod.path,
                    mod.dir_path,
                    mod.title,
                    mod.domain,
                    mod.verification_command,
                    1 if mod.is_compliant else 0,
                    mod.updated_at,
                ),
            )

            # Insert canonical sections
            idx = 0
            for spec in MANDATORY_SECTION_SPECS:
                key = spec["key"]
                title = spec["title"]
                cnt = mod.sections.get(key, "")
                if cnt:
                    conn.execute(
                        """
                        INSERT INTO module_sections (module_id, section_index, section_key, section_title, content)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (mod.id, idx, key, title, cnt),
                    )
                    conn.execute(
                        """
                        INSERT INTO module_fts (module_id, title, path, section_title, content)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (mod.id, mod.title, mod.path, title, cnt),
                    )
                    idx += 1

            # Insert any extra sections not mapped to the 7
            for sec in mod.all_sections:
                if not sec.get("mapped_canonical") and sec.get("content"):
                    sec_title = sec.get("clean_title") or sec.get("title") or "Additional Section"
                    cnt = sec.get("content", "")
                    conn.execute(
                        """
                        INSERT INTO module_sections (module_id, section_index, section_key, section_title, content)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (mod.id, idx, "extra", sec_title, cnt),
                    )
                    conn.execute(
                        """
                        INSERT INTO module_fts (module_id, title, path, section_title, content)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (mod.id, mod.title, mod.path, sec_title, cnt),
                    )
                    idx += 1

    conn.close()


# -----------------------------------------------------------------------------
# Manifest Generation
# -----------------------------------------------------------------------------

def write_manifest(modules: List[ModuleDoc], manifest_path: Path) -> None:
    """Writes docs/module_manifest.json with structured module catalog."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    compliant_count = sum(1 for m in modules if m.is_compliant)

    data = {
        "version": "1.0.0",
        "generated_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        "total_modules": len(modules),
        "compliant_modules": compliant_count,
        "compliance_rate_percent": round((compliant_count / len(modules) * 100) if modules else 0.0, 1),
        "modules": [
            {
                "id": m.id,
                "path": m.path,
                "dir_path": m.dir_path,
                "title": m.title,
                "domain": m.domain,
                "primary_files": m.primary_files,
                "verification_command": m.verification_command,
                "known_issues": m.known_issues,
                "compliance": {
                    "is_compliant": m.is_compliant,
                    "missing_sections": m.missing_sections,
                    "stub_sections": m.stub_sections,
                },
                "sections": m.sections,
                "updated_at": m.updated_at,
            }
            for m in modules
        ],
    }

    manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# -----------------------------------------------------------------------------
# Markdown Index Generation (docs/MODULE_INDEX.md)
# -----------------------------------------------------------------------------

def generate_markdown_index(modules: List[ModuleDoc], index_path: Path, repo_root: Path) -> None:
    """Generates an up-to-date docs/MODULE_INDEX.md master catalog."""
    index_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = [
        "# FastAPI Bookings — Application Module Index",
        "",
        "This document provides a master catalog of all modules, directories, domain boundaries, and their active operational status across the **FastAPI Bookings** codebase.",
        "",
        "---",
        "",
        "## 1. Purpose & Scope",
        "",
        "The Module Index acts as an authoritative directory for engineers and autonomous agents to locate functional subsystems, identify file ownership, trace integration points, and inspect technical debt or operational readiness without searching ad-hoc transcripts.",
        "",
        "---",
        "",
        "## 2. Master Module Inventory Table",
        "",
        "| Path | Domain / Responsibility | Primary Files / Entrypoint | Verification Command | Status | Link |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for m in modules:
        primary_str = ", ".join(f"`{f}`" for f in m.primary_files[:3]) if m.primary_files else "*(directory)*"
        verif_str = f"`{m.verification_command[:45]}...`" if len(m.verification_command) > 45 else (f"`{m.verification_command}`" if m.verification_command else "*None recorded*")
        status_str = "**Compliant (Rule 10)**" if m.is_compliant else "*In Review*"
        link_str = f"[{Path(m.path).name}]({m.path})"
        lines.append(f"| `{m.dir_path}/` | {m.domain} | {primary_str} | {verif_str} | {status_str} | {link_str} |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Subsystem Domain Breakdowns",
        "",
    ])

    # Group by domain
    domain_groups: Dict[str, List[ModuleDoc]] = {}
    for m in modules:
        domain_groups.setdefault(m.domain, []).append(m)

    section_num = 1
    for domain, group_modules in sorted(domain_groups.items()):
        lines.append(f"### 3.{section_num} {domain}")
        lines.append("")
        for mod in group_modules:
            lines.append(f"#### [{mod.title}]({mod.path}) (`{mod.dir_path}`)")
            purpose = mod.sections.get("purpose_and_scope", "").strip()
            if purpose:
                first_para = purpose.split("\n\n")[0].replace("\n", " ")
                lines.append(f"{first_para[:250]}...")
            if mod.primary_files:
                lines.append(f"- **Key Files**: {', '.join(f'`{f}`' for f in mod.primary_files)}")
            if mod.verification_command:
                lines.append(f"- **Verification**: `{mod.verification_command}`")
            if mod.known_issues:
                lines.append(f"- **Known Debt/Issues**: {len(mod.known_issues)} item(s) logged")
            lines.append("")
        section_num += 1

    lines.extend([
        "---",
        "",
        "## 4. Documentation Maintenance Protocol (Rule 10)",
        "",
        "Whenever code is modified, agents and developers MUST update the corresponding module `README.md` to keep this index fresh.",
        "",
        "- **Re-index entire repository**:",
        "  ```powershell",
        "  python scripts/index_living_docs.py",
        "  ```",
        "- **Query module details or verification commands**:",
        "  ```powershell",
        '  python scripts/query_docs.py --search "arrival"',
        '  python scripts/query_docs.py --test-command "sms"',
        '  python scripts/query_docs.py --known-issues',
        "  ```",
        "- **Verify compliance (Release Gate)**:",
        "  ```powershell",
        "  python scripts/verify_living_docs.py",
        "  ```",
        "",
        f"*Catalog generated automatically on {datetime.datetime.now(tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} by `scripts/index_living_docs.py`.*",
    ])

    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_agent_boot_snapshot(modules: List[ModuleDoc], snapshot_path: Path) -> None:
    """
    Generates docs/AGENT_BOOT_SNAPSHOT.md: a dense, ~400-token ASCII directory tree
    annotated with module titles, primary files, and test commands for fast agent orientation.
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    mod_map = {m.dir_path: m for m in modules}

    def _cmd(dir_key: str, fallback: str = "pytest") -> str:
        m = mod_map.get(dir_key)
        if m and m.verification_command:
            c = m.verification_command.strip()
            # Compact display
            return c if len(c) <= 50 else c[:47] + "..."
        return fallback

    lines = [
        "# FastAPI Bookings — Agent Boot Snapshot",
        "",
        "> Authoritative: Tenants, Providers, Calendars, Holds, Bookings, SMS Dialogue, Knowledge.",
        "> Operating Rules: AGENTS.md (No mocks, strict scope discipline, Rule 10 living documentation).",
        "",
        "```text",
        "fastapi_bookings/",
        "├── app/",
        f"│   ├── api/routers/           # HTTP REST API [{_cmd('app/api/routers', 'pytest')}]",
        f"│   ├── core/                  # Config & Telemetry [{_cmd('app/core', 'pytest')}]",
        "│   ├── db/                    # Database Engine & Sessions (PostgreSQL / SQLite)",
        "│   ├── models/                # SQLAlchemy ORM Models (Multi-Tenant)",
        "│   └── services/",
        f"│       ├── assistant/         # Assistant Runtime & Tools [{_cmd('app/services/assistant', 'pytest')}]",
        f"│       ├── booking/           # Core Booking Engine [{_cmd('app/services/booking', 'pytest')}]",
        f"│       ├── business_assistant/# Business Assistant [{_cmd('app/services/business_assistant', 'pytest')}]",
        f"│       ├── curation/          # Memory Curator & PII Scrubber [{_cmd('app/services/curation', 'pytest')}]",
        f"│       ├── knowledge/         # Knowledge & Graphiti Client [{_cmd('app/services/knowledge', 'pytest')}]",
        f"│       ├── messaging/         # Chatwoot & Omnichannel [{_cmd('app/services/messaging', 'pytest')}]",
        f"│       ├── resident_agent/    # Autonomous Resident Sentinel [{_cmd('app/services/resident_agent', 'pytest')}]",
        f"│       ├── routing/           # Routing & Geospatial [{_cmd('app/services/routing', 'pytest')}]",
        f"│       ├── scheduling/        # Scheduling & Slot Allocation [{_cmd('app/services/scheduling', 'pytest')}]",
        f"│       └── sms/               # SMS Autonomous Engine [{_cmd('app/services/sms', 'pytest')}]",
        f"├── frontend/                  # React/Vite SPA [{_cmd('frontend', 'npm run build')}]",
        "│   └── src/pages/admin/       # Admin Management Pages",
        f"│       ├── finance/           # Finance & Invoicing [{_cmd('frontend/src/pages/admin/finance', 'npm run build')}]",
        f"│       └── sms/               # SMS Workspace & Console [{_cmd('frontend/src/pages/admin/sms', 'npm run build')}]",
        f"├── alembic/                   # Database Migrations [{_cmd('alembic', 'alembic heads')}]",
        f"├── scripts/                   # Release Gates & Tooling [{_cmd('scripts', 'python verify_all_release_gates.py')}]",
        f"└── tests/                     # Pytest Suites [{_cmd('tests', 'pytest tests/ -v')}]",
        "```",
        "",
        "### High-Speed Agent Retrieval Commands",
        "- **FTS5 Search**: `python scripts/query_docs.py --search \"<term>\"`",
        "- **Test Command**: `python scripts/query_docs.py --test-command \"<module>\"`",
        "- **Known Debt/Issues**: `python scripts/query_docs.py --known-issues`",
        "- **Rule 10 Gate**: `python scripts/verify_living_docs.py`",
        "",
        f"*Generated automatically on {datetime.datetime.now(tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} by scripts/index_living_docs.py*",
    ]

    snapshot_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# -----------------------------------------------------------------------------
# Main CLI Entrypoint
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="FastAPI Bookings Living Documentation Indexer")
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--db", type=str, default="docs/module_docs.db", help="Target SQLite database path")
    parser.add_argument("--manifest", type=str, default="docs/module_manifest.json", help="Target JSON manifest path")
    parser.add_argument("--index-md", type=str, default="docs/MODULE_INDEX.md", help="Target markdown catalog path")
    parser.add_argument("--snapshot", type=str, default="docs/AGENT_BOOT_SNAPSHOT.md", help="Target agent boot snapshot path")
    parser.add_argument("--dirs", nargs="*", default=DEFAULT_TARGET_DIRS, help="Directories to scan for module READMEs")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose stdout output")

    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    db_path = repo_root / args.db
    manifest_path = repo_root / args.manifest
    index_path = repo_root / args.index_md
    snapshot_path = repo_root / args.snapshot

    if not args.quiet:
        print(f"[*] Living Documentation Indexer (AGENTS.md Rule 10)")
        print(f"[*] Scanning repository: {repo_root}")
        print(f"[*] Target directories: {', '.join(args.dirs)}")

    readme_files = find_readme_files(repo_root, args.dirs)
    if not args.quiet:
        print(f"[*] Found {len(readme_files)} module README.md files")

    modules: List[ModuleDoc] = []
    for f in readme_files:
        try:
            doc = parse_readme(f, repo_root)
            modules.append(doc)
        except Exception as e:
            print(f"[!] Error parsing {f}: {e}", file=sys.stderr)

    if not args.quiet:
        print(f"[*] Writing manifest: {manifest_path}")
    write_manifest(modules, manifest_path)

    if not args.quiet:
        print(f"[*] Populating SQLite FTS5 database: {db_path}")
    index_database(modules, db_path)

    if not args.quiet:
        print(f"[*] Generating master markdown index: {index_path}")
    generate_markdown_index(modules, index_path, repo_root)

    if not args.quiet:
        print(f"[*] Generating agent boot snapshot: {snapshot_path}")
    generate_agent_boot_snapshot(modules, snapshot_path)

    compliant = sum(1 for m in modules if m.is_compliant)
    if not args.quiet:
        print(f"[OK] Indexed {len(modules)} modules ({compliant} compliant with Rule 10)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
