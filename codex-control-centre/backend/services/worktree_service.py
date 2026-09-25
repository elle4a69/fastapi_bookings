import subprocess
import shutil
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("codex.worktree_service")

def validate_worktree_name(name: str):
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError("Invalid worktree name: traversal characters are not allowed")

def get_worktree_path(repo_path: str, worktree_name: str) -> Path:
    repo_root = Path(repo_path).resolve()
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
    # 1. Try requested branch
    try:
        subprocess.run(["git", "rev-parse", "--verify", requested_branch], cwd=repo_path, check=True, capture_output=True)
        return requested_branch
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    # 2. Try current branch via symbolic-ref HEAD
    try:
        res = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo_path, check=True, capture_output=True, text=True)
        curr = res.stdout.strip()
        if curr:
            return curr
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    # 3. Try alternate branch (master if main was requested, main if master was requested)
    alt = "master" if requested_branch == "main" else "main"
    try:
        subprocess.run(["git", "rev-parse", "--verify", alt], cwd=repo_path, check=True, capture_output=True)
        return alt
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    # 4. Fallback to HEAD
    try:
        subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=repo_path, check=True, capture_output=True)
        return "HEAD"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    return None

def create_worktree(repo_path: str, branch: str, worktree_name: str, base_branch: Optional[str] = None) -> dict:
    target_path = get_worktree_path(repo_path, worktree_name)
    
    # Ensure worktrees dir exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # git worktree add <target_path> -b <branch> (or without -b if branch exists)
    # Check if branch exists
    try:
        subprocess.run(["git", "rev-parse", "--verify", branch], cwd=repo_path, check=True, capture_output=True)
        # Branch exists
        cmd = ["git", "worktree", "add", str(target_path), branch]
    except subprocess.CalledProcessError:
        # Branch does not exist
        base_ref = resolve_base_branch(repo_path, base_branch or "main")
        if base_ref:
            cmd = ["git", "worktree", "add", "-b", branch, str(target_path), base_ref]
        else:
            cmd = ["git", "worktree", "add", "-b", branch, str(target_path)]
        
    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create worktree: {result.stderr}")
        
    return {
        "name": worktree_name,
        "path": str(target_path),
        "branch": branch
    }

def list_worktrees(repo_path: str) -> list[dict]:
    # git worktree list --porcelain
    result = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo_path, capture_output=True, text=True)
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
    if not worktree_name or worktree_name in [".", "..", Path(repo_path).name]:
        raise ValueError("Cannot delete the primary repository root")
        
    target_path = get_worktree_path(repo_path, worktree_name)
    repo_root = Path(repo_path).resolve()
    
    if target_path == repo_root or target_path in repo_root.parents:
        raise ValueError("Cannot delete the primary repository root")
        
    if not target_path.exists():
        raise ValueError(f"Worktree {worktree_name} does not exist at {target_path}")
        
    # Dirty check: git status --porcelain in the worktree
    status_result = subprocess.run(["git", "status", "--porcelain"], cwd=str(target_path), capture_output=True, text=True)
    if status_result.returncode != 0:
        raise RuntimeError(f"Failed to check worktree status: {status_result.stderr}")
        
    if status_result.stdout.strip() and not force:
        raise ValueError("Cannot remove worktree with uncommitted changes without force=True")
        
    # Remove worktree
    cmd = ["git", "worktree", "remove", str(target_path)]
    if force:
        cmd.append("--force")
        
    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to remove worktree: {result.stderr}")
        
    # Cleanup empty dir
    if target_path.exists() and not any(target_path.iterdir()):
        target_path.rmdir()
        
    # Prune
    subprocess.run(["git", "worktree", "prune"], cwd=repo_path, check=True, capture_output=True)
    
    return {"status": "success", "worktree": worktree_name}


def ensure_thread_worktree(repo_path: str, thread_id: str, default_branch: str = "main") -> Path:
    """
    Guarantees an isolated Git worktree exists for the given thread under <repo_path>/worktrees/wt-<threadId>.
    Validates worktree path safety to prevent directory traversal outside of the worktree sandbox.
    If the worktree directory already exists, returns it immediately.
    If not, attempts Git worktree creation or creates the isolated directory structure.
    If git worktree add fails, fallback to creating the isolated directory or copying/symlinking safely if needed,
    but ensure fallback doesn't leave an empty directory if the repo itself can be safely referenced.
    """
    clean_thread_id = str(thread_id).strip()
    worktree_name = f"wt-{clean_thread_id}"
    validate_worktree_name(worktree_name)
    target_path = get_worktree_path(repo_path, worktree_name)

    if target_path.exists() and target_path.is_dir():
        return target_path

    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        create_worktree(
            repo_path=repo_path,
            branch=worktree_name,
            worktree_name=worktree_name,
            base_branch=default_branch,
        )
    except Exception as e:
        logger.warning(f"git worktree add failed for {worktree_name} on {repo_path}: {e}")
        # Fallback for mock/test repositories or non-git environments:
        # Create the isolated directory structure and copy source files if available
        target_path.mkdir(parents=True, exist_ok=True)
        repo_dir = Path(repo_path).resolve()
        if repo_dir.exists() and repo_dir.is_dir():
            try:
                for item in repo_dir.iterdir():
                    if item.name in [
                        ".git",
                        "worktrees",
                        "node_modules",
                        ".venv",
                        "venv",
                        "__pycache__",
                        ".pytest_cache",
                        ".ruff_cache",
                        ".mypy_cache",
                    ]:
                        continue
                    dest = target_path / item.name
                    if not dest.exists():
                        if item.is_dir():
                            shutil.copytree(
                                item,
                                dest,
                                ignore=shutil.ignore_patterns(
                                    ".git", "worktrees", "node_modules", "__pycache__", ".pytest_cache"
                                ),
                            )
                        else:
                            shutil.copy2(item, dest)
            except Exception as copy_err:
                logger.warning(f"Could not copy files to isolated fallback worktree {target_path}: {copy_err}")

    return target_path
