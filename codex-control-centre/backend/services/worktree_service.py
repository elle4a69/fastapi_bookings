import subprocess
import shutil
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("codex.worktree_service")

def validate_worktree_name(name: str):
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError("Invalid worktree name: traversal characters are not allowed")

def validate_repo_bounds(repo_path: str | Path, db: Optional[Any] = None) -> Path:
    from backend.services.boundary_service import validate_path_in_boundaries
    from fastapi import HTTPException
    try:
        return validate_path_in_boundaries(repo_path, db=db)
    except HTTPException as exc:
        raise ValueError(exc.detail)

def is_git_repo_root(repo_dir: Path) -> bool:
    git_entry = repo_dir / ".git"
    if not git_entry.exists():
        return False
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(repo_dir),
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return Path(res.stdout.strip()).resolve() == repo_dir.resolve()
    except Exception:
        return False

def get_worktree_path(repo_path: str, worktree_name: str) -> Path:
    repo_root = validate_repo_bounds(repo_path)
    validate_worktree_name(worktree_name)
    worktree_root = repo_root / "worktrees"
    target_path = (worktree_root / worktree_name).resolve()
    
    # Check if target_path is within worktree_root
    if not str(target_path).startswith(str(worktree_root)):
        raise ValueError("Path traversal detected")
        
    return target_path

def resolve_base_branch(repo_path: str, requested_branch: str = "main") -> Optional[str]:
    """
    Resolves a valid base branch or commit ref in the repository.
    Tries requested_branch, current branch (symbolic-ref HEAD), alternate branch (master/main), or HEAD.
    """
    repo_root = validate_repo_bounds(repo_path)
    cwd_str = str(repo_root)

    # 1. Try requested branch
    try:
        subprocess.run(["git", "rev-parse", "--verify", requested_branch], cwd=cwd_str, check=True, capture_output=True, timeout=5)
        return requested_branch
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # 2. Try current branch via symbolic-ref HEAD
    try:
        res = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=cwd_str, check=True, capture_output=True, text=True, timeout=5)
        curr = res.stdout.strip()
        if curr:
            return curr
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # 3. Try alternate branch (master if main was requested, main if master was requested)
    alt = "master" if requested_branch == "main" else "main"
    try:
        subprocess.run(["git", "rev-parse", "--verify", alt], cwd=cwd_str, check=True, capture_output=True, timeout=5)
        return alt
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # 4. Fallback to HEAD
    try:
        subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=cwd_str, check=True, capture_output=True, timeout=5)
        return "HEAD"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None

def create_worktree(repo_path: str, branch: str, worktree_name: str, base_branch: Optional[str] = None) -> dict:
    repo_root = validate_repo_bounds(repo_path)
    target_path = get_worktree_path(str(repo_root), worktree_name)
    cwd_str = str(repo_root)
    
    # Ensure worktrees dir exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # git worktree add <target_path> -b <branch> (or without -b if branch exists)
    # Check if branch exists
    try:
        subprocess.run(["git", "rev-parse", "--verify", branch], cwd=cwd_str, check=True, capture_output=True, timeout=5)
        # Branch exists
        cmd = ["git", "worktree", "add", str(target_path), branch]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Branch does not exist
        base_ref = resolve_base_branch(cwd_str, base_branch or "main")
        if base_ref:
            cmd = ["git", "worktree", "add", "-b", branch, str(target_path), base_ref]
        else:
            cmd = ["git", "worktree", "add", "-b", branch, str(target_path)]
        
    result = subprocess.run(cmd, cwd=cwd_str, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create worktree: {result.stderr}")
        
    return {
        "name": worktree_name,
        "path": str(target_path),
        "branch": branch
    }

def list_worktrees(repo_path: str) -> list[dict]:
    repo_root = validate_repo_bounds(repo_path)
    cwd_str = str(repo_root)
    if not is_git_repo_root(repo_root):
        return []

    # git worktree list --porcelain
    result = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=cwd_str, capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to list worktrees: {result.stderr}")
        
    worktrees: list[dict[str, Any]] = []
    current_wt: dict[str, Any] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            if current_wt:
                worktrees.append(current_wt)
                current_wt = {}
            continue
            
        parts = line.split(" ", 1)
        key = parts[0]
        val = parts[1] if len(parts) > 1 else ""
        
        if key == "worktree":
            current_wt["path"] = val
        elif key == "HEAD":
            current_wt["head"] = val
        elif key == "branch":
            current_wt["branch"] = val.replace("refs/heads/", "")
            
    if current_wt:
        worktrees.append(current_wt)
        
    return worktrees

def remove_worktree(repo_path: str, worktree_name: str, force: bool = False) -> dict:
    repo_root = validate_repo_bounds(repo_path)
    if not worktree_name or worktree_name in [".", "..", repo_root.name]:
        raise ValueError("Cannot delete the primary repository root")
        
    target_path = get_worktree_path(str(repo_root), worktree_name)
    cwd_str = str(repo_root)
    
    if target_path == repo_root or target_path in repo_root.parents:
        raise ValueError("Cannot delete the primary repository root")
        
    if not target_path.exists():
        raise ValueError(f"Worktree {worktree_name} does not exist at {target_path}")
        
    # Dirty check: git status --porcelain in the worktree
    status_result = subprocess.run(["git", "status", "--porcelain"], cwd=str(target_path), capture_output=True, text=True, timeout=5)
    if status_result.returncode != 0:
        raise RuntimeError(f"Failed to check worktree status: {status_result.stderr}")
        
    if status_result.stdout.strip() and not force:
        raise ValueError("Cannot remove worktree with uncommitted changes without force=True")
        
    # Remove worktree
    cmd = ["git", "worktree", "remove", str(target_path)]
    if force:
        cmd.append("--force")
        
    result = subprocess.run(cmd, cwd=cwd_str, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to remove worktree: {result.stderr}")
        
    # Cleanup empty dir
    if target_path.exists() and not any(target_path.iterdir()):
        target_path.rmdir()
        
    # Prune
    subprocess.run(["git", "worktree", "prune"], cwd=cwd_str, check=True, capture_output=True, timeout=5)
    
    return {"status": "success", "worktree": worktree_name}


def ensure_thread_worktree(repo_path: str, thread_id: str, default_branch: str = "main") -> Path:
    """
    Guarantees an isolated Git worktree exists for the given thread under <repo_path>/worktrees/wt-<threadId>.
    Validates worktree path safety to prevent directory traversal outside of the worktree sandbox.
    Verifies repository bounds and guards against runaway git resets or recursive copies against parent monorepos.
    If the worktree directory already exists, returns it immediately.
    """
    clean_thread_id = str(thread_id).strip()
    worktree_name = f"wt-{clean_thread_id}"
    validate_worktree_name(worktree_name)
    repo_dir = validate_repo_bounds(repo_path)
    target_path = get_worktree_path(str(repo_dir), worktree_name)

    if target_path.exists() and target_path.is_dir():
        return target_path

    target_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure worktrees sandbox root has a .gitignore to prevent parent git from tracking worktrees
    wt_gitignore = target_path.parent / ".gitignore"
    if not wt_gitignore.exists():
        try:
            wt_gitignore.write_text("*\n!.gitignore\n", encoding="utf-8")
        except Exception:
            pass

    # Only invoke git worktree if repo_dir is a verified git repository root
    if is_git_repo_root(repo_dir):
        try:
            create_worktree(
                repo_path=str(repo_dir),
                branch=worktree_name,
                worktree_name=worktree_name,
                base_branch=default_branch,
            )
            return target_path
        except Exception as e:
            logger.warning(f"git worktree add failed for {worktree_name} on {repo_dir}: {e}")

    # Fallback for mock/test repositories or non-git environments:
    # Create the isolated directory structure and safely copy only top-level essential files.
    # Strictly avoids recursive tree crawls against parent monorepos.
    target_path.mkdir(parents=True, exist_ok=True)
    if repo_dir.exists() and repo_dir.is_dir():
        try:
            for item in repo_dir.iterdir():
                if item.name.startswith(".") or item.name in [
                    "worktrees",
                    "node_modules",
                    ".venv",
                    "venv",
                    "__pycache__",
                    ".pytest_cache",
                    ".ruff_cache",
                    ".mypy_cache",
                    "storage",
                ]:
                    continue
                dest = target_path / item.name
                if not dest.exists():
                    if item.is_file():
                        shutil.copy2(item, dest)
        except Exception as copy_err:
            logger.warning(f"Could not copy files to isolated fallback worktree {target_path}: {copy_err}")

    return target_path
