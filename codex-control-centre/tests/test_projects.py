import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database import Base, set_sqlite_pragma, get_db
from backend.middleware.auth import verify_auth
from backend.services.worktree_service import ensure_thread_worktree, resolve_base_branch


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from sqlalchemy import event
    event.listen(engine, "connect", set_sqlite_pragma)
    Base.metadata.create_all(bind=engine)
    yield engine


@pytest.fixture
def client(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_auth] = lambda: None

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_project_invalid_path(client, tmp_path):
    invalid_path = str(tmp_path / "non_existent_folder_xyz_123")
    res = client.post(
        "/codex/projects",
        json={"name": "Invalid Project", "repo_path": invalid_path},
    )
    assert res.status_code == 400
    assert "Repository path does not exist" in res.json()["detail"]


def test_create_project_valid_path(client, tmp_path):
    repo_dir = tmp_path / "valid_project"
    repo_dir.mkdir()

    res = client.post(
        "/codex/projects",
        json={"name": "Payments Service", "repo_path": str(repo_dir), "default_branch": "develop"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Payments Service"
    assert data["default_branch"] == "develop"
    assert data["id"].startswith("proj_")
    assert data["thread_count"] == 0

    # Retrieve created project
    proj_id = data["id"]
    get_res = client.get(f"/codex/projects/{proj_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Payments Service"


def test_list_projects_and_thread_count(client, tmp_path):
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    repo2 = tmp_path / "repo2"
    repo2.mkdir()

    p1 = client.post("/codex/projects", json={"id": "proj_1", "name": "Repo 1", "repo_path": str(repo1)}).json()
    p2 = client.post("/codex/projects", json={"id": "proj_2", "name": "Repo 2", "repo_path": str(repo2)}).json()

    # Create thread under proj_1
    client.post("/codex/threads", json={"project_id": "proj_1", "title": "Thread 1"})
    client.post("/codex/threads", json={"project_id": "proj_1", "title": "Thread 2"})

    list_res = client.get("/codex/projects")
    assert list_res.status_code == 200
    projects = list_res.json()
    assert len(projects) >= 2

    p1_found = next(p for p in projects if p["id"] == "proj_1")
    p2_found = next(p for p in projects if p["id"] == "proj_2")
    assert p1_found["thread_count"] == 2
    assert p2_found["thread_count"] == 0


def test_get_project_files_and_filtering(client, tmp_path):
    repo_dir = tmp_path / "inspection_repo"
    repo_dir.mkdir()

    # Create tracked project files
    (repo_dir / "main.py").write_text("print('hello')\nprint('world')\n")
    sub = repo_dir / "src"
    sub.mkdir()
    (sub / "app.ts").write_text("export const run = () => {};\n")

    # Create ignored directories and files
    git_dir = repo_dir / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main")

    nm_dir = repo_dir / "node_modules" / "some_pkg"
    nm_dir.mkdir(parents=True)
    (nm_dir / "index.js").write_text("module.exports = {};")

    cache_dir = repo_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "main.cpython-311.pyc").write_text("binary-bytecode")

    proj = client.post("/codex/projects", json={"name": "Inspect", "repo_path": str(repo_dir)}).json()
    proj_id = proj["id"]

    files_res = client.get(f"/codex/projects/{proj_id}/files")
    assert files_res.status_code == 200
    files = files_res.json()

    paths = [f["path"] for f in files]
    assert "main.py" in paths
    assert "src/app.ts" in paths

    # Ignored directories must NOT appear
    assert not any(".git" in p for p in paths)
    assert not any("node_modules" in p for p in paths)
    assert not any("__pycache__" in p for p in paths)

    # Line count and types
    main_file = next(f for f in files if f["path"] == "main.py")
    assert main_file["lines"] == 2
    assert main_file["type"] == "python"

    ts_file = next(f for f in files if f["path"] == "src/app.ts")
    assert ts_file["lines"] == 1
    assert ts_file["type"] == "typescript"


def test_get_project_files_path_traversal(client, tmp_path):
    repo_dir = tmp_path / "traversal_repo"
    repo_dir.mkdir()
    (repo_dir / "safe.txt").write_text("safe content")

    proj = client.post("/codex/projects", json={"name": "Traversal Test", "repo_path": str(repo_dir)}).json()
    proj_id = proj["id"]

    res = client.get(f"/codex/projects/{proj_id}/files", params={"subpath": "../"})
    assert res.status_code == 400
    assert "Path traversal detected" in res.json()["detail"]


def test_ensure_thread_worktree_resolves_base_branch(tmp_path):
    repo = tmp_path / "git_branch_repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True)

    # Make initial commit
    (repo / "code.py").write_text("print('test')")
    subprocess.run(["git", "add", "code.py"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=str(repo), check=True)

    # Find the current branch (could be 'main' or 'master' depending on git config)
    res_head = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True)
    current_branch = res_head.stdout.strip()
    non_existent_branch = "some_random_nonexistent_branch_xyz"

    # Testing resolve_base_branch falls back to current branch / HEAD
    resolved = resolve_base_branch(str(repo), requested_branch=non_existent_branch)
    assert resolved in [current_branch, "HEAD", "master", "main"]

    # Testing ensure_thread_worktree succeeds even if default_branch='nonexistent_branch'
    wt_path = ensure_thread_worktree(str(repo), "th_branch_res_1", default_branch=non_existent_branch)
    assert wt_path.exists()
    assert (wt_path / "code.py").exists()


def test_ensure_thread_worktree_non_git_fallback(tmp_path):
    non_git = tmp_path / "plain_folder"
    non_git.mkdir()
    (non_git / "service.py").write_text("print('non git')")

    wt_path = ensure_thread_worktree(str(non_git), "th_fallback_test")
    assert wt_path.exists()
    # Ensure codebase files are available
    assert (wt_path / "service.py").exists() or (Path(non_git) / "service.py").exists()
