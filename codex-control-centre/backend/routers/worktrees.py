from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.worktree_service import create_worktree, list_worktrees, remove_worktree

router = APIRouter(prefix="/codex/worktrees", tags=["worktrees"])

class CreateWorktreeRequest(BaseModel):
    repo_path: str
    branch: str
    worktree_name: str

@router.post("/create")
def create_worktree_endpoint(req: CreateWorktreeRequest):
    try:
        result = create_worktree(req.repo_path, req.branch, req.worktree_name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
def list_worktrees_endpoint(repo_path: str):
    try:
        result = list_worktrees(repo_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{worktree_name}")
def remove_worktree_endpoint(worktree_name: str, repo_path: str, force: bool = False):
    try:
        result = remove_worktree(repo_path, worktree_name, force)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
