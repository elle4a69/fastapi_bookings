import pytest
import os
import shutil
from pathlib import Path
from app.services.codex.workspace_manager import WorkspaceManager

@pytest.mark.asyncio
async def test_workspace_manager_worktree(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    
    import subprocess
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True)
    
    (repo_path / "test.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)
    
    manager = WorkspaceManager(str(repo_path))
    
    branch_name = "test-agent-branch"
    worktree_path = await manager.create_worktree(branch_name)
    
    assert worktree_path.exists()
    assert (worktree_path / "test.txt").exists()
    
    proc = subprocess.run(["git", "branch"], cwd=repo_path, capture_output=True, text=True)
    assert branch_name in proc.stdout
    
    await manager.cleanup_worktree(worktree_path, branch_name)
    
    assert not worktree_path.exists()
    proc = subprocess.run(["git", "branch"], cwd=repo_path, capture_output=True, text=True)
    assert branch_name not in proc.stdout
