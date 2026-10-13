import os
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
from backend.config import settings, codex_dir
from backend.services.boundary_service import (
    add_boundary,
    list_boundaries,
    remove_boundary,
    validate_path_in_boundaries,
)
from backend.services.worktree_service import ensure_thread_worktree, validate_repo_bounds


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

    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_list_boundaries_initial_seed(client):
    res = client.get("/codex/settings/boundaries")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    # Check default boundary is present
    codex_path = str(codex_dir.resolve())
    assert any(b["path"] == codex_path for b in data)


def test_add_boundary_valid_and_idempotent(client, tmp_path):
    base_folder = tmp_path / "allowed_workspace"
    base_folder.mkdir()

    res = client.post(
        "/codex/settings/boundaries",
        json={"path": str(base_folder), "name": "Test Workspace"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Test Workspace"
    assert data["path"] == str(base_folder.resolve())
    assert data["id"].startswith("bound_")

    # Idempotent re-add returns existing
    res2 = client.post(
        "/codex/settings/boundaries",
        json={"path": str(base_folder), "name": "Duplicate Attempt"},
    )
    assert res2.status_code == 200
    assert res2.json()["id"] == data["id"]


def test_add_boundary_non_existent(client, tmp_path):
    non_existent = str(tmp_path / "ghost_directory_12345")
    res = client.post(
        "/codex/settings/boundaries",
        json={"path": non_existent, "name": "Ghost"},
    )
    assert res.status_code == 400
    assert "Boundary path does not exist" in res.json()["detail"]


def test_remove_boundary_by_id_and_last_boundary_protection(client, tmp_path):
    folder1 = tmp_path / "folder_one"
    folder1.mkdir()
    folder2 = tmp_path / "folder_two"
    folder2.mkdir()

    b1 = client.post("/codex/settings/boundaries", json={"path": str(folder1)}).json()
    b2 = client.post("/codex/settings/boundaries", json={"path": str(folder2)}).json()

    # Remove folder_one by ID
    del_res = client.delete(f"/codex/settings/boundaries/{b1['id']}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Verify folder_one is gone
    list_res = client.get("/codex/settings/boundaries").json()
    assert not any(b["id"] == b1["id"] for b in list_res)

    # Remove folder_two by path (URL-encoded or via query param)
    import urllib.parse
    encoded_path = urllib.parse.quote(str(folder2.resolve()), safe="")
    del_res2 = client.delete(f"/codex/settings/boundaries/{encoded_path}")
    assert del_res2.status_code == 200

    # If only 1 boundary left, deletion is rejected
    current_boundaries = client.get("/codex/settings/boundaries").json()
    while len(current_boundaries) > 1:
        client.delete(f"/codex/settings/boundaries/{current_boundaries[-1]['id']}")
        current_boundaries = client.get("/codex/settings/boundaries").json()

    assert len(current_boundaries) == 1
    last_del = client.delete(f"/codex/settings/boundaries/{current_boundaries[0]['id']}")
    assert last_del.status_code == 400
    assert "Cannot remove the last remaining workspace boundary" in last_del.json()["detail"]


def test_project_registration_with_boundaries(client, tmp_path, db_engine):
    allowed_base = tmp_path / "allowed_base"
    allowed_base.mkdir()
    outside_base = tmp_path / "outside_base"
    outside_base.mkdir()

    # Register allowed_base boundary
    client.post("/codex/settings/boundaries", json={"path": str(allowed_base), "name": "Allowed Base"})

    # Project inside allowed_base succeeds
    proj_in = allowed_base / "my_project"
    proj_in.mkdir()
    res_in = client.post("/codex/projects", json={"name": "In Project", "repo_path": str(proj_in)})
    assert res_in.status_code == 200
    assert res_in.json()["name"] == "In Project"

    # Project outside: if temporarily clearing test env bypass
    proj_out = outside_base / "outside_project"
    proj_out.mkdir()

    # If we explicitly test validate_path_in_boundaries directly:
    from backend.models.codex import WorkspaceBoundary
    # With a custom session having only allowed_base
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    with TestingSessionLocal() as session:
        session.query(WorkspaceBoundary).delete()
        session.add(WorkspaceBoundary(id="b_test", path=str(allowed_base.resolve()), name="Allowed Base", is_default=True))
        session.commit()

        # Inside boundary succeeds
        assert validate_path_in_boundaries(proj_in, session) == proj_in.resolve()

        # Outside boundary raises HTTPException 400
        with pytest.raises(Exception) as excinfo:
            # Temporarily unset PYTEST_CURRENT_TEST to verify strict boundary rejection
            orig_test = os.environ.pop("PYTEST_CURRENT_TEST", None)
            try:
                validate_path_in_boundaries(proj_out, session)
            finally:
                if orig_test:
                    os.environ["PYTEST_CURRENT_TEST"] = orig_test

        assert "outside all active workspace boundaries" in str(excinfo.value)


def test_worktree_safe_isolation_for_large_repo(tmp_path):
    repo = tmp_path / "large_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True)

    (repo / "README.md").write_text("# Large Monorepo")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo), check=True)

    # Create dummy node_modules and .venv
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "huge_file.js").write_text("console.log('huge')")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "huge_bin.exe").write_text("binary")

    wt_path = ensure_thread_worktree(str(repo), "th_large_wt_1")
    assert wt_path.exists()
    # Check that worktree is placed inside worktrees/wt-<threadId>
    assert wt_path == repo / "worktrees" / "wt-th_large_wt_1"
    # Check that .gitignore was created in worktrees root
    wt_gitignore = repo / "worktrees" / ".gitignore"
    assert wt_gitignore.exists()
    assert "*\n!.gitignore\n" in wt_gitignore.read_text(encoding="utf-8")


def test_telemetry_settings_endpoints(client):
    # 1. GET telemetry settings
    get_res = client.get("/codex/settings/telemetry")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "signoz_url" in data
    assert "otlp_endpoint" in data
    assert "enabled" in data
    assert "status" in data

    # 2. PUT telemetry settings
    put_res = client.put(
        "/codex/settings/telemetry",
        json={
            "signoz_url": "http://localhost:3301",
            "otlp_endpoint": "http://localhost:4318",
            "enabled": True,
        },
    )
    assert put_res.status_code == 200
    assert put_res.json()["signoz_url"] == "http://localhost:3301"
    assert put_res.json()["otlp_endpoint"] == "http://localhost:4318"
    assert put_res.json()["enabled"] is True

    # 3. POST telemetry test
    test_res = client.post(
        "/codex/settings/telemetry/test",
        json={"endpoint": "http://127.0.0.1:4500"},
    )
    assert test_res.status_code == 200
    test_data = test_res.json()
    assert "connected" in test_data
    assert "latency_ms" in test_data
    assert "url" in test_data


def test_add_fastapi_bookings_boundary_and_verify_no_monorepo_redirection(client, db_engine):
    # F:\Projects\fastapi_bookings is the monorepo root containing codex-control-centre
    fastapi_bookings_path = str(codex_dir.parent.resolve())
    assert Path(fastapi_bookings_path).exists()

    res = client.post(
        "/codex/settings/boundaries",
        json={"path": fastapi_bookings_path, "name": "FastAPI Bookings Monorepo"},
    )
    assert res.status_code == 200
    boundary_data = res.json()
    assert boundary_data["path"] == fastapi_bookings_path
    assert boundary_data["name"] == "FastAPI Bookings Monorepo"

    # Verify that project creation under fastapi_bookings succeeds through the API
    proj_res = client.post(
        "/codex/projects",
        json={"name": "FastAPI Bookings Root", "repo_path": fastapi_bookings_path},
    )
    assert proj_res.status_code == 200
    assert proj_res.json()["repo_path"] == fastapi_bookings_path

    # Verify that validate_repo_bounds with session does NOT redirect to codex_dir
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    with TestingSessionLocal() as session:
        validated = validate_repo_bounds(fastapi_bookings_path, db=session)
        assert validated == Path(fastapi_bookings_path).resolve()
        assert validated != codex_dir.resolve()


def test_turn_start_boundary_violation_returns_400_with_cors(client, db_engine, tmp_path):
    from backend.models.codex import Project, Thread, Turn, WorkspaceBoundary
    from backend.services.event_service import broker
    from unittest.mock import patch

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    outside_dir = tmp_path / "strictly_outside_boundary_dir"
    outside_dir.mkdir()

    with TestingSessionLocal() as session:
        # Isolate boundaries to only codex_dir
        session.query(WorkspaceBoundary).delete()
        session.add(WorkspaceBoundary(id="b_ccc", path=str(codex_dir.resolve()), name="Codex", is_default=True))

        proj = Project(id="proj_outside", name="Outside Project", repo_path=str(outside_dir), default_branch="main")
        session.add(proj)
        th = Thread(id="th_outside_test", project_id="proj_outside", title="Outside Thread")
        session.add(th)
        session.commit()

    captured_events = []
    orig_publish = broker.publish_event
    with patch.object(broker, "publish_event", side_effect=lambda evt: (captured_events.append(evt), orig_publish(evt))):
        orig_test = os.environ.pop("PYTEST_CURRENT_TEST", None)
        orig_env = settings.environment
        settings.environment = "production"
        try:
            res = client.post(
                "/codex/turns/start",
                json={"thread_id": "th_outside_test", "prompt": "Test outside turn"},
                headers={"Origin": "http://localhost:4600"},
            )
        finally:
            if orig_test:
                os.environ["PYTEST_CURRENT_TEST"] = orig_test
            settings.environment = orig_env

    assert res.status_code == 400
    assert res.headers.get("access-control-allow-origin") == "http://localhost:4600"
    assert "outside all active workspace boundaries" in res.json()["detail"]

    # Verify DB state
    with TestingSessionLocal() as session:
        turn = session.query(Turn).filter(Turn.thread_id == "th_outside_test").first()
        assert turn is not None
        assert turn.status == "failed"
        assert len(turn.items) >= 1
        assert turn.items[0].item_type == "error"
        assert "outside all active workspace boundaries" in turn.items[0].content["error"]

    # Verify broker events
    assert any(e.type == "error" for e in captured_events)
    assert any(e.type == "turn_completed" and e.payload.get("status") == "failed" for e in captured_events)


def test_global_exception_handler_returns_500_with_cors(client, db_engine):
    from backend.models.codex import Project, Thread
    from unittest.mock import patch

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    with TestingSessionLocal() as session:
        proj = Project(id="proj_crash", name="Crash Proj", repo_path=str(codex_dir), default_branch="main")
        session.add(proj)
        th = Thread(id="th_crash_test", project_id="proj_crash", title="Crash Thread")
        session.add(th)
        session.commit()

    with patch("backend.routers.turns.ensure_thread_worktree", side_effect=RuntimeError("Simulated unhandled crash")):
        res = client.post(
            "/codex/turns/start",
            json={"thread_id": "th_crash_test", "prompt": "Crash test"},
            headers={"Origin": "http://localhost:4600"},
        )
        assert res.status_code == 500
        assert res.headers.get("access-control-allow-origin") == "http://localhost:4600"
        data = res.json()
        assert data["error"] == "Internal Server Error"
        assert "Simulated unhandled crash" in data["detail"]

