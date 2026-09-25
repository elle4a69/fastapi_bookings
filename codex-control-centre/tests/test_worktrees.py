import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.worktree_service import create_worktree, list_worktrees, remove_worktree
from backend.config import settings

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {settings.token_secret}"}

@pytest.fixture
def repo_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True)
    
    # Create initial commit
    (repo / "initial.txt").write_text("Hello")
    subprocess.run(["git", "add", "initial.txt"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo), check=True)
    return str(repo)

def test_path_traversal_rejected(repo_path):
    with pytest.raises(ValueError, match="Invalid worktree name: traversal characters are not allowed"):
        create_worktree(repo_path, "main", "../evil_worktree")
        
    with pytest.raises(ValueError, match="Invalid worktree name: traversal characters are not allowed"):
        create_worktree(repo_path, "main", "foo/bar")

def test_successful_worktree_creation_and_list(repo_path):
    res = create_worktree(repo_path, "feature-branch", "feature-wt")
    assert res["name"] == "feature-wt"
    assert res["branch"] == "feature-branch"
    
    wts = list_worktrees(repo_path)
    # the main worktree + the newly created one
    assert len(wts) == 2
    assert any("feature-wt" in wt.get("path", "") for wt in wts)

def test_remove_dirty_worktree_fails_without_force(repo_path):
    create_worktree(repo_path, "dirty-branch", "dirty-wt")
    wt_dir = Path(repo_path) / "worktrees" / "dirty-wt"
    (wt_dir / "new_file.txt").write_text("dirty")
    
    with pytest.raises(ValueError, match="Cannot remove worktree with uncommitted changes without force=True"):
        remove_worktree(repo_path, "dirty-wt")

def test_remove_dirty_worktree_succeeds_with_force(repo_path):
    create_worktree(repo_path, "dirty-branch2", "dirty-wt2")
    wt_dir = Path(repo_path) / "worktrees" / "dirty-wt2"
    (wt_dir / "new_file.txt").write_text("dirty")
    
    res = remove_worktree(repo_path, "dirty-wt2", force=True)
    assert res["status"] == "success"
    assert not wt_dir.exists()

def test_delete_main_repository_root_rejected(repo_path):
    with pytest.raises(ValueError, match="Cannot delete the primary repository root"):
        remove_worktree(repo_path, ".")
        
    with pytest.raises(ValueError, match="Cannot delete the primary repository root"):
        remove_worktree(repo_path, "..")
        
    with pytest.raises(ValueError, match="Cannot delete the primary repository root"):
        remove_worktree(repo_path, Path(repo_path).name)

def test_api_endpoints(repo_path):
    # Create
    resp = client.post("/codex/worktrees/create", json={
        "repo_path": repo_path,
        "branch": "api-branch",
        "worktree_name": "api-wt"
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "api-wt"
    
    # List
    resp = client.get(f"/codex/worktrees?repo_path={repo_path}", headers=auth_headers)
    assert resp.status_code == 200
    wts = resp.json()
    assert len(wts) == 2
    
    # Delete
    resp = client.delete(f"/codex/worktrees/api-wt?repo_path={repo_path}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
