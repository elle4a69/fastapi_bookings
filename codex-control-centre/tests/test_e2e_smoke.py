import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database import Base, set_sqlite_pragma, get_db
from backend.config import settings
from backend.models.codex import Project, Thread, Turn, ToolApproval, SubAgent
from backend.services.event_service import broker


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_engine():
    """
    Creates an isolated in-memory SQLite database using StaticPool
    with SQLite foreign keys pragma explicitly enabled.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    event.listen(engine, "connect", set_sqlite_pragma)
    Base.metadata.create_all(bind=engine)
    yield engine


@pytest.fixture
def db_session(db_engine):
    """
    Provides a transactional database session for assertions and queries.
    """
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine):
    """
    Provides a FastAPI TestClient bound to the in-memory SQLite database.
    """
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_event_broker():
    """
    Resets the event broker state between test runs.
    """
    broker.subscribers.clear()
    broker.history.clear()
    broker.sequences.clear()
    yield
    broker.subscribers.clear()
    broker.history.clear()
    broker.sequences.clear()


@pytest.fixture
def repo_path(tmp_path):
    """
    Initializes a valid temporary git repository for safe worktree testing.
    """
    repo = tmp_path / "e2e_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Smoke Test Specialist"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "smoke@example.com"], cwd=str(repo), check=True, capture_output=True)

    # Initial commit on default branch
    (repo / "README.md").write_text("# E2E Test Repository\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo), check=True, capture_output=True)
    return str(repo)


@pytest.fixture
def mock_worker(monkeypatch):
    """
    Mocks the worker manager for turn dispatch without spawning external subprocesses.
    """
    class MockWorkerProcess:
        async def send_request(self, method, params, timeout=30.0):
            return {"status": "ok", "method": method, "params": params}

    class MockWorkerManager:
        async def get_worker(self):
            return MockWorkerProcess()

    from backend.routers import turns
    mock_mgr = MockWorkerManager()
    monkeypatch.setattr(turns, "worker_manager", mock_mgr)
    return mock_mgr


# Auth helper
AUTH_HEADERS = {"Authorization": f"Bearer {settings.token_secret}"}


# ============================================================================
# Comprehensive End-to-End Master Lifecycle Smoke Test
# ============================================================================

def test_e2e_complete_system_lifecycle(client, db_session, repo_path, mock_worker):
    """
    Comprehensive End-to-End Smoke Test validating the full Codex Control Centre lifecycle:
    - Step 1: Health & Diagnostics verification (/health public 200, /codex/diagnostics/deep authenticated)
    - Step 2: Project & Thread lifecycle (create project, create thread, list threads, update thread metadata)
    - Step 3: Turn & Event streaming flow (start turn, verify DB persistence in turns, publish event to EventBroker, verify SSE event backlog replay with Last-Event-ID)
    - Step 4: Approval gate lifecycle (create HIGH risk tool call approval request, verify pending status in DB, resolve approval with approved=True, verify resolved_at and event emission)
    - Step 5: Sub-agent governance lifecycle (register subagent, update progress to 50%, steer subagent, and test cascade cancellation on thread termination)
    - Step 6: Safe Worktree lifecycle (create worktree, verify git branch isolation, verify traversal rejection, verify dirty worktree deletion prevention, and perform forced deletion)
    """

    # ------------------------------------------------------------------------
    # STEP 1: Health & Diagnostics Verification
    # ------------------------------------------------------------------------
    # 1.1 Public /health liveness probe (Unauthenticated -> 200 OK)
    health_res = client.get("/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["status"] == "healthy"
    assert "timestamp" in health_data

    # 1.2 Deep diagnostics unauthenticated rejected (401 Unauthorized)
    unauth_diag = client.get("/codex/diagnostics/deep")
    assert unauth_diag.status_code == 401

    # 1.3 Deep diagnostics authenticated (Bearer token -> 200 OK)
    deep_res = client.get("/codex/diagnostics/deep", headers=AUTH_HEADERS)
    assert deep_res.status_code == 200
    deep_data = deep_res.json()
    assert deep_data["status"] == "healthy"
    assert "subsystems" in deep_data
    subsystems = deep_data["subsystems"]
    assert subsystems["database"]["status"] == "healthy"
    assert subsystems["database"]["connected"] is True
    assert subsystems["event_broker"]["status"] == "healthy"
    assert subsystems["worktree_storage"]["status"] == "healthy"
    assert subsystems["worktree_storage"]["writable"] is True
    assert "worker" in subsystems
    assert "telemetry" in subsystems

    # ------------------------------------------------------------------------
    # STEP 2: Project & Thread Lifecycle
    # ------------------------------------------------------------------------
    # 2.1 Seed Project in database
    project_id = "proj_e2e_smoke"
    project = Project(
        id=project_id,
        name="E2E Smoke Test Project",
        repo_path=repo_path,
        default_branch="main"
    )
    db_session.add(project)
    db_session.commit()

    # 2.2 Create Thread via API
    create_thread_res = client.post(
        "/codex/threads",
        json={"project_id": project_id, "title": "E2E Master Verification Thread"},
        headers=AUTH_HEADERS
    )
    assert create_thread_res.status_code == 200
    thread_data = create_thread_res.json()
    thread_id = thread_data["id"]
    assert thread_data["project_id"] == project_id
    assert thread_data["title"] == "E2E Master Verification Thread"
    assert thread_data["status"] == "active"

    # 2.3 List Threads
    list_threads_res = client.get("/codex/threads", headers=AUTH_HEADERS)
    assert list_threads_res.status_code == 200
    threads_list = list_threads_res.json()
    assert any(t["id"] == thread_id for t in threads_list)

    # 2.4 Get Thread by ID
    get_thread_res = client.get(f"/codex/threads/{thread_id}", headers=AUTH_HEADERS)
    assert get_thread_res.status_code == 200
    assert get_thread_res.json()["title"] == "E2E Master Verification Thread"

    # 2.5 Update Thread Metadata (Pin and rename)
    update_thread_res = client.patch(
        f"/codex/threads/{thread_id}",
        json={"title": "E2E Thread — Verified Active", "is_pinned": True},
        headers=AUTH_HEADERS
    )
    assert update_thread_res.status_code == 200
    assert update_thread_res.json()["title"] == "E2E Thread — Verified Active"
    assert update_thread_res.json()["is_pinned"] is True

    # Verify DB persistence of Thread update
    db_thread = db_session.query(Thread).filter(Thread.id == thread_id).first()
    assert db_thread is not None
    assert db_thread.title == "E2E Thread — Verified Active"
    assert db_thread.is_pinned is True

    # ------------------------------------------------------------------------
    # STEP 3: Turn & Event Streaming Flow
    # ------------------------------------------------------------------------
    # 3.1 Start Turn via API
    turn_start_res = client.post(
        "/codex/turns/start",
        json={"thread_id": thread_id, "prompt": "Execute end-to-end audit verification"},
        headers=AUTH_HEADERS
    )
    assert turn_start_res.status_code == 200
    turn_id = turn_start_res.json()["turn_id"]
    assert turn_start_res.json()["status"] == "active"

    # 3.2 Verify DB Persistence in `turns` table
    db_turn = db_session.query(Turn).filter(Turn.id == turn_id, Turn.thread_id == thread_id).first()
    assert db_turn is not None
    assert db_turn.turn_number == 1
    assert db_turn.status == "active"
    assert db_turn.prompt == "Execute end-to-end audit verification"

    # 3.3 Publish sequential events to EventBroker via API
    pub1_res = client.post(
        "/codex/events/publish",
        json={
            "project_id": project_id,
            "thread_id": thread_id,
            "type": "turn.plan",
            "payload": {"step": 1, "description": "Planning test execution"}
        },
        headers=AUTH_HEADERS
    )
    assert pub1_res.status_code == 200
    event_1 = pub1_res.json()
    event_1_id = event_1["id"]
    assert event_1["sequence"] == 1
    assert event_1["type"] == "turn.plan"

    pub2_res = client.post(
        "/codex/events/publish",
        json={
            "project_id": project_id,
            "thread_id": thread_id,
            "type": "turn.progress",
            "payload": {"step": 2, "description": "Running smoke suite"}
        },
        headers=AUTH_HEADERS
    )
    assert pub2_res.status_code == 200
    event_2 = pub2_res.json()
    event_2_id = event_2["id"]
    assert event_2["sequence"] == 2
    assert event_2["type"] == "turn.progress"

    # 3.4 Verify SSE Backlog Replay via broker.get_history with Last-Event-ID
    replayed_history = broker.get_history(thread_id=thread_id, last_event_id=event_1_id)
    assert len(replayed_history) == 1
    assert replayed_history[0].id == event_2_id
    assert replayed_history[0].type == "turn.progress"
    assert replayed_history[0].sequence == 2

    # ------------------------------------------------------------------------
    # STEP 4: Approval Gate Lifecycle
    # ------------------------------------------------------------------------
    # 4.1 Evaluate risk tier for HIGH-risk command
    eval_res = client.post(
        "/codex/governance/evaluate",
        json={"command": "npm install lodash", "profile": "managed"},
        headers=AUTH_HEADERS
    )
    assert eval_res.status_code == 200
    assert eval_res.json()["risk_level"] == "HIGH"
    assert eval_res.json()["requires_approval"] is True

    # 4.2 Create HIGH risk tool call approval request
    create_appr_res = client.post(
        "/codex/governance/approvals",
        json={
            "thread_id": thread_id,
            "tool_call_id": "tc_e2e_npm_01",
            "command": "npm install lodash",
            "risk_level": "HIGH",
            "consequence": "Installs external package dependencies."
        },
        headers=AUTH_HEADERS
    )
    assert create_appr_res.status_code == 200
    appr_data = create_appr_res.json()
    approval_id = appr_data["id"]
    assert appr_data["status"] == "pending"
    assert appr_data["risk_level"] == "HIGH"
    assert appr_data["resolved_at"] is None

    # 4.3 Verify `pending` status in DB
    db_approval = db_session.query(ToolApproval).filter(ToolApproval.id == approval_id).first()
    assert db_approval is not None
    assert db_approval.status == "pending"
    assert db_approval.resolved_at is None

    # Verify listing pending approvals
    pending_list_res = client.get(f"/codex/governance/approvals/pending?thread_id={thread_id}", headers=AUTH_HEADERS)
    assert pending_list_res.status_code == 200
    assert any(a["id"] == approval_id for a in pending_list_res.json())

    # 4.4 Resolve approval with approved=True
    resolve_res = client.post(
        f"/codex/governance/approvals/{approval_id}/resolve",
        json={"approved": True, "feedback": "Authorized by Release Engineer"},
        headers=AUTH_HEADERS
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "approved"
    assert resolve_res.json()["resolved_at"] is not None

    # 4.5 Verify `resolved_at` in DB and event emission in EventBroker
    db_session.refresh(db_approval)
    assert db_approval.status == "approved"
    assert db_approval.resolved_at is not None

    # Check broker history contains approval.resolved event
    thread_events = broker.get_history(thread_id=thread_id)
    assert any(e.type == "approval.resolved" and e.payload.get("approval_id") == approval_id for e in thread_events)

    # ------------------------------------------------------------------------
    # STEP 5: Sub-Agent Governance Lifecycle
    # ------------------------------------------------------------------------
    # 5.1 Register primary subagent
    reg_sub_res = client.post(
        "/codex/governance/subagents/register",
        json={"thread_id": thread_id, "name": "Verification-Worker", "role": "QA Specialist"},
        headers=AUTH_HEADERS
    )
    assert reg_sub_res.status_code == 200
    subagent_id = reg_sub_res.json()["id"]
    assert reg_sub_res.json()["name"] == "Verification-Worker"
    assert reg_sub_res.json()["status"] == "active"
    assert reg_sub_res.json()["progress"] == 0

    # Register child subagent attached to thread
    child_sub_res = client.post(
        "/codex/governance/subagents/register",
        json={"thread_id": thread_id, "parent_thread_id": thread_id, "name": "Telemetry-Worker", "role": "Observability"},
        headers=AUTH_HEADERS
    )
    assert child_sub_res.status_code == 200
    child_sub_id = child_sub_res.json()["id"]

    # 5.2 Update subagent progress to 50%
    prog_res = client.post(
        f"/codex/governance/subagents/{subagent_id}/progress",
        json={"progress": 50, "current_action": "Executing integration smoke verification", "status": "active"},
        headers=AUTH_HEADERS
    )
    assert prog_res.status_code == 200
    assert prog_res.json()["progress"] == 50
    assert prog_res.json()["current_action"] == "Executing integration smoke verification"

    # Verify DB persistence
    db_subagent = db_session.query(SubAgent).filter(SubAgent.id == subagent_id).first()
    assert db_subagent is not None
    assert db_subagent.progress == 50

    # 5.3 Steer subagent
    steer_res = client.post(
        f"/codex/governance/subagents/{subagent_id}/steer",
        json={"instruction": "Ensure 100% test pass rate across all modules"},
        headers=AUTH_HEADERS
    )
    assert steer_res.status_code == 200
    assert steer_res.json()["status"] == "steered"

    # Verify steer event in broker
    thread_events = broker.get_history(thread_id=thread_id)
    assert any(e.type == "subagent.steered" and e.payload.get("subagent_id") == subagent_id for e in thread_events)

    # 5.4 Test cascade cancellation on thread termination
    term_res = client.post(f"/codex/governance/threads/{thread_id}/terminate-subagents", headers=AUTH_HEADERS)
    assert term_res.status_code == 200
    term_data = term_res.json()
    assert term_data["status"] == "terminated"
    assert subagent_id in term_data["terminated_ids"]
    assert child_sub_id in term_data["terminated_ids"]

    # Verify both subagents are marked 'cancelled' in DB
    db_session.refresh(db_subagent)
    db_child = db_session.query(SubAgent).filter(SubAgent.id == child_sub_id).first()
    assert db_subagent.status == "cancelled"
    assert db_child.status == "cancelled"

    # ------------------------------------------------------------------------
    # STEP 6: Safe Worktree Lifecycle
    # ------------------------------------------------------------------------
    # 6.1 Create Worktree via API
    wt_name = "wt-e2e-feature"
    wt_branch = "feature/e2e-smoke"
    create_wt_res = client.post(
        "/codex/worktrees/create",
        json={"repo_path": repo_path, "branch": wt_branch, "worktree_name": wt_name},
        headers=AUTH_HEADERS
    )
    assert create_wt_res.status_code == 200
    wt_data = create_wt_res.json()
    assert wt_data["name"] == wt_name
    assert wt_data["branch"] == wt_branch
    wt_path = Path(wt_data["path"])
    assert wt_path.exists()

    # 6.2 Verify Git Branch Isolation
    list_wt_res = client.get(f"/codex/worktrees?repo_path={repo_path}", headers=AUTH_HEADERS)
    assert list_wt_res.status_code == 200
    worktrees_list = list_wt_res.json()
    assert len(worktrees_list) >= 2
    assert any(wt["branch"] == wt_branch for wt in worktrees_list)

    # 6.3 Verify Path Traversal Rejection
    traversal_res = client.post(
        "/codex/worktrees/create",
        json={"repo_path": repo_path, "branch": "evil-branch", "worktree_name": "../escape_dir"},
        headers=AUTH_HEADERS
    )
    assert traversal_res.status_code == 400
    assert "traversal" in traversal_res.json()["detail"].lower()

    # 6.4 Verify Dirty Worktree Deletion Prevention
    dirty_file = wt_path / "uncommitted_work.txt"
    dirty_file.write_text("Uncommitted changes", encoding="utf-8")

    delete_dirty_res = client.delete(
        f"/codex/worktrees/{wt_name}?repo_path={repo_path}&force=false",
        headers=AUTH_HEADERS
    )
    assert delete_dirty_res.status_code == 400
    assert "uncommitted changes" in delete_dirty_res.json()["detail"].lower()
    assert wt_path.exists()

    # 6.5 Perform Forced Deletion
    force_delete_res = client.delete(
        f"/codex/worktrees/{wt_name}?repo_path={repo_path}&force=true",
        headers=AUTH_HEADERS
    )
    assert force_delete_res.status_code == 200
    assert force_delete_res.json()["status"] == "success"
    assert not wt_path.exists()

    # Verify worktree list no longer contains the deleted worktree
    final_wt_res = client.get(f"/codex/worktrees?repo_path={repo_path}", headers=AUTH_HEADERS)
    assert final_wt_res.status_code == 200
    assert not any(wt_name in wt.get("path", "") for wt in final_wt_res.json())


# ============================================================================
# Granular Step-Specific Tests for Modular Validation
# ============================================================================

def test_e2e_step1_health_and_diagnostics(client):
    """Step 1 Modular: Public liveness and authenticated deep diagnostics."""
    res_pub = client.get("/health")
    assert res_pub.status_code == 200
    assert res_pub.json()["status"] == "healthy"

    res_unauth = client.get("/codex/diagnostics/deep")
    assert res_unauth.status_code == 401

    res_auth = client.get("/codex/diagnostics/deep", headers=AUTH_HEADERS)
    assert res_auth.status_code == 200
    assert res_auth.json()["subsystems"]["database"]["status"] == "healthy"


def test_e2e_step2_project_thread_lifecycle(client, db_session, repo_path):
    """Step 2 Modular: Project registration, Thread CRUD, and metadata persistence."""
    proj = Project(id="proj_s2", name="Step2 Project", repo_path=repo_path, default_branch="main")
    db_session.add(proj)
    db_session.commit()

    res = client.post("/codex/threads", json={"project_id": "proj_s2", "title": "Step2 Thread"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    th_id = res.json()["id"]

    res_get = client.get(f"/codex/threads/{th_id}", headers=AUTH_HEADERS)
    assert res_get.status_code == 200
    assert res_get.json()["title"] == "Step2 Thread"

    res_patch = client.patch(f"/codex/threads/{th_id}", json={"is_pinned": True}, headers=AUTH_HEADERS)
    assert res_patch.status_code == 200
    assert res_patch.json()["is_pinned"] is True


def test_e2e_step3_turn_event_streaming(client, db_session, mock_worker):
    """Step 3 Modular: Turn start, DB persistence, EventBroker publishing, and replay."""
    proj = Project(id="proj_s3", name="Step3 Project", repo_path="/tmp", default_branch="main")
    thread = Thread(id="th_s3", project_id="proj_s3", title="Step3 Thread")
    db_session.add_all([proj, thread])
    db_session.commit()

    res = client.post("/codex/turns/start", json={"thread_id": "th_s3", "prompt": "Step3 Prompt"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    turn_id = res.json()["turn_id"]

    turn = db_session.query(Turn).filter(Turn.id == turn_id).first()
    assert turn is not None
    assert turn.turn_number == 1

    e1 = client.post("/codex/events/publish", json={"project_id": "proj_s3", "thread_id": "th_s3", "type": "e1", "payload": {}}, headers=AUTH_HEADERS).json()
    e2 = client.post("/codex/events/publish", json={"project_id": "proj_s3", "thread_id": "th_s3", "type": "e2", "payload": {}}, headers=AUTH_HEADERS).json()

    history = broker.get_history("th_s3", last_event_id=e1["id"])
    assert len(history) == 1
    assert history[0].id == e2["id"]


def test_e2e_step4_approval_gate_lifecycle(client, db_session):
    """Step 4 Modular: HIGH risk approval creation, pending check, resolution, and event broadcast."""
    proj = Project(id="proj_s4", name="Step4 Project", repo_path="/tmp", default_branch="main")
    thread = Thread(id="th_s4", project_id="proj_s4", title="Step4 Thread")
    db_session.add_all([proj, thread])
    db_session.commit()

    res_appr = client.post(
        "/codex/governance/approvals",
        json={"thread_id": "th_s4", "tool_call_id": "tc_s4", "command": "rm -rf /tmp/test", "risk_level": "HIGH", "consequence": "Deletes data"},
        headers=AUTH_HEADERS
    )
    assert res_appr.status_code == 200
    appr_id = res_appr.json()["id"]

    res_resolve = client.post(f"/codex/governance/approvals/{appr_id}/resolve", json={"approved": True}, headers=AUTH_HEADERS)
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "approved"
    assert res_resolve.json()["resolved_at"] is not None


def test_e2e_step5_subagent_governance_lifecycle(client, db_session):
    """Step 5 Modular: Subagent registration, progress tracking, steering, and cascade cancellation."""
    proj = Project(id="proj_s5", name="Step5 Project", repo_path="/tmp", default_branch="main")
    thread = Thread(id="th_s5", project_id="proj_s5", title="Step5 Thread")
    db_session.add_all([proj, thread])
    db_session.commit()

    res_sub = client.post("/codex/governance/subagents/register", json={"thread_id": "th_s5", "name": "Worker-S5", "role": "Tester"}, headers=AUTH_HEADERS)
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    res_prog = client.post(f"/codex/governance/subagents/{sub_id}/progress", json={"progress": 50, "current_action": "Testing"}, headers=AUTH_HEADERS)
    assert res_prog.status_code == 200
    assert res_prog.json()["progress"] == 50

    res_steer = client.post(f"/codex/governance/subagents/{sub_id}/steer", json={"instruction": "Continue tests"}, headers=AUTH_HEADERS)
    assert res_steer.status_code == 200

    res_term = client.post("/codex/governance/threads/th_s5/terminate-subagents", headers=AUTH_HEADERS)
    assert res_term.status_code == 200
    assert sub_id in res_term.json()["terminated_ids"]


def test_e2e_step6_safe_worktree_lifecycle(client, repo_path):
    """Step 6 Modular: Worktree creation, branch isolation, traversal check, dirty protection, and force removal."""
    # Create
    res_create = client.post("/codex/worktrees/create", json={"repo_path": repo_path, "branch": "wt-step6-branch", "worktree_name": "wt-step6"}, headers=AUTH_HEADERS)
    assert res_create.status_code == 200
    wt_dir = Path(res_create.json()["path"])
    assert wt_dir.exists()

    # Traversal rejection
    res_trav = client.post("/codex/worktrees/create", json={"repo_path": repo_path, "branch": "b", "worktree_name": "../escape"}, headers=AUTH_HEADERS)
    assert res_trav.status_code == 400

    # Dirty worktree deletion protection
    (wt_dir / "dirty.txt").write_text("changes", encoding="utf-8")
    res_del_dirty = client.delete(f"/codex/worktrees/wt-step6?repo_path={repo_path}&force=false", headers=AUTH_HEADERS)
    assert res_del_dirty.status_code == 400
    assert wt_dir.exists()

    # Force delete
    res_force = client.delete(f"/codex/worktrees/wt-step6?repo_path={repo_path}&force=true", headers=AUTH_HEADERS)
    assert res_force.status_code == 200
    assert not wt_dir.exists()
