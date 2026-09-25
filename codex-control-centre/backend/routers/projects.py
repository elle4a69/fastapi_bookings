from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.codex import Project, Thread

logger = logging.getLogger("codex.projects")

router = APIRouter(prefix="/codex/projects", tags=["projects"])

IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "worktrees",
    ".idea",
    ".vscode",
}

TYPE_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".txt": "text",
    ".rs": "rust",
    ".go": "go",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
}


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def count_lines(filepath: Path) -> int:
    try:
        if filepath.stat().st_size > 5 * 1024 * 1024:
            return 0
        with open(filepath, "rb") as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                return 0
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


class ProjectCreate(BaseModel):
    name: str
    repo_path: str
    id: Optional[str] = None
    default_branch: Optional[str] = "main"


class ProjectResponse(BaseModel):
    id: str
    name: str
    repo_path: str
    default_branch: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    thread_count: Optional[int] = 0

    model_config = {"from_attributes": True}


class ProjectFileEntry(BaseModel):
    path: str
    size: str
    lines: int
    type: str


@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    path_obj = Path(payload.repo_path).expanduser().resolve()
    if not path_obj.exists() or not path_obj.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Repository path does not exist or is not a directory: {payload.repo_path}",
        )

    resolved_repo_path = str(path_obj)
    project_id = payload.id.strip() if payload.id and payload.id.strip() else f"proj_{uuid.uuid4().hex[:8]}"
    default_branch = payload.default_branch.strip() if payload.default_branch and payload.default_branch.strip() else "main"

    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        project.name = payload.name.strip()
        project.repo_path = resolved_repo_path
        project.default_branch = default_branch
        project.updated_at = datetime.now(timezone.utc)
    else:
        project = Project(
            id=project_id,
            name=payload.name.strip(),
            repo_path=resolved_repo_path,
            default_branch=default_branch,
        )
        db.add(project)

    db.commit()
    db.refresh(project)

    thread_count = db.query(Thread).filter(Thread.project_id == project.id).count()
    return ProjectResponse(
        id=project.id,
        name=project.name,
        repo_path=project.repo_path,
        default_branch=project.default_branch,
        created_at=project.created_at,
        updated_at=project.updated_at,
        thread_count=thread_count,
    )


@router.get("", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    result: List[ProjectResponse] = []
    for p in projects:
        thread_count = db.query(Thread).filter(Thread.project_id == p.id).count()
        result.append(
            ProjectResponse(
                id=p.id,
                name=p.name,
                repo_path=p.repo_path,
                default_branch=p.default_branch,
                created_at=p.created_at,
                updated_at=p.updated_at,
                thread_count=thread_count,
            )
        )
    return result


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    thread_count = db.query(Thread).filter(Thread.project_id == project.id).count()
    return ProjectResponse(
        id=project.id,
        name=project.name,
        repo_path=project.repo_path,
        default_branch=project.default_branch,
        created_at=project.created_at,
        updated_at=project.updated_at,
        thread_count=thread_count,
    )


@router.get("/{project_id}/files", response_model=List[ProjectFileEntry])
def get_project_files(project_id: str, subpath: Optional[str] = None, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    repo_root = Path(project.repo_path).resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Repository path '{project.repo_path}' is not accessible on disk",
        )

    scan_root = repo_root
    if subpath:
        requested = (repo_root / subpath).resolve()
        if not requested.is_relative_to(repo_root):
            raise HTTPException(status_code=400, detail="Path traversal detected")
        if not requested.exists():
            raise HTTPException(status_code=404, detail="Subpath not found")
        scan_root = requested

    files_list: List[ProjectFileEntry] = []

    def scan_dir(curr_dir: Path, depth: int):
        if depth > 4:
            return
        try:
            entries = sorted(curr_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except (PermissionError, OSError):
            return

        for entry in entries:
            name = entry.name
            if name.startswith(".") and name not in [".env", ".gitignore"]:
                continue
            if name in IGNORED_DIRS:
                continue

            try:
                resolved = entry.resolve()
                if not resolved.is_relative_to(repo_root):
                    continue
            except (OSError, ValueError):
                continue

            if entry.is_dir():
                scan_dir(entry, depth + 1)
            elif entry.is_file():
                rel = entry.relative_to(repo_root).as_posix()
                try:
                    st = entry.stat()
                    size_str = format_size(st.st_size)
                except OSError:
                    size_str = "0 B"
                lines = count_lines(entry)
                ext = entry.suffix.lower()
                ftype = TYPE_MAP.get(ext, ext.lstrip(".") if ext else "text")

                files_list.append(
                    ProjectFileEntry(
                        path=rel,
                        size=size_str,
                        lines=lines,
                        type=ftype,
                    )
                )

    scan_dir(scan_root, 1)
    return files_list
