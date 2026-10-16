from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
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


class PromoteWorktreeRequest(BaseModel):
    repo_path: str | None = None
    target_branch: str | None = None


@router.post("/{worktree_id}/promote")
@router.post("/worktrees/{worktree_id}/promote")
def promote_worktree_endpoint(
    worktree_id: str,
    req: PromoteWorktreeRequest | None = None,
    repo_path: str | None = None,
    db: Session = Depends(get_db),
):
    from backend.services.worktree_service import promote_worktree
    from backend.config import settings
    effective_repo = None
    target_branch = None
    if req is not None:
        effective_repo = req.repo_path
        target_branch = req.target_branch
    if not effective_repo and repo_path:
        effective_repo = repo_path
    if not effective_repo:
        effective_repo = str(settings.repo_root)

    try:
        result = promote_worktree(
            repo_path=effective_repo,
            worktree_id=worktree_id,
            target_branch=target_branch,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

