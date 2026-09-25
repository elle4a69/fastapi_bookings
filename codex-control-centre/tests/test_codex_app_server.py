import asyncio
import json
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database import Base, set_sqlite_pragma, get_db
from backend.models.codex import Project, Thread, Turn, Item
from backend.services import governance_service
from backend.services.event_service import broker
from backend.services.worker import WorkerProcess, resolve_codex_binary
from backend.services.worker_manager import worker_manager
from backend.services.protocol import Protocol
from backend.routers.events import stream_events
from backend.middleware.auth import verify_auth


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", set_sqlite_pragma)
    Base.metadata.create_all(bind=engine)
    yield engine


@pytest.fixture
def db_session(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        proj = Project(
            id="proj_cas04",
            name="CAS-04 Integration Project",
            repo_path="/tmp/repo",
            default_branch="main",
        )
        thread = Thread(
            id="thread_cas04_e2e",
            project_id="proj_cas04",
            title="E2E Integration Thread",
        )
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


@pytest.fixture(autouse=True)
def reset_event_broker():
    broker.subscribers.clear()
    broker.history.clear()
    broker.sequences.clear()
    yield
    broker.subscribers.clear()
    broker.history.clear()
    broker.sequences.clear()


# =============================================================================
# Test 1: Handshake and Discovery
# =============================================================================

@pytest.mark.asyncio
async def test_handshake_and_discovery_simulated():
    """
    Test 1a: Verifies initialize request parameters and initialized notification
    conforming to JSON-RPC 2.0 Codex App-Server protocol with a simulated server.
    """
    mock_server_script = (
        "import sys, json\n"
        "records = []\n"
        "while True:\n"
        "    line = sys.stdin.readline()\n"
        "    if not line: break\n"
        "    msg = json.loads(line)\n"
        "    records.append(msg)\n"
        "    if msg.get('method') == 'initialize':\n"
        "        sys.stdout.write(json.dumps({\n"
        "            'jsonrpc': '2.0',\n"
        "            'id': msg['id'],\n"
        "            'result': {\n"
        "                'userAgent': 'codex-app-server/0.144.4',\n"
        "                'capabilities': {'streaming': True, 'approvals': True},\n"
        "                'protocolVersion': '2024-11-05'\n"
        "            }\n"
        "        }) + '\\n')\n"
        "        sys.stdout.flush()\n"
        "    elif msg.get('method') == 'get_records':\n"
        "        sys.stdout.write(json.dumps({\n"
        "            'jsonrpc': '2.0',\n"
        "            'id': msg['id'],\n"
        "            'result': records\n"
        "        }) + '\\n')\n"
        "        sys.stdout.flush()\n"
    )

    cmd = [sys.executable, "-u", "-c", mock_server_script]
    worker = WorkerProcess(command=cmd, perform_handshake=True)
    await worker.start()

    try:
        assert worker.running
        assert worker.init_result is not None
        assert worker.init_result["userAgent"] == "codex-app-server/0.144.4"
        assert worker.init_result["capabilities"]["streaming"] is True
        assert worker.init_result["capabilities"]["approvals"] is True

        records = await worker.send_request("get_records")
        assert len(records) >= 2

        # 1. Inspect initialize request frame
        init_req = records[0]
        assert init_req["jsonrpc"] == "2.0"
        assert init_req["method"] == "initialize"
        assert init_req["id"] == 1
        assert init_req["params"]["clientInfo"]["name"] == "CodexControlCentre"
        assert init_req["params"]["capabilities"]["streaming"] is True
        assert init_req["params"]["capabilities"]["approvals"] is True

        # 2. Inspect initialized notification frame
        init_notif = records[1]
        assert init_notif["jsonrpc"] == "2.0"
        assert init_notif["method"] == "initialized"
        assert "id" not in init_notif
    finally:
        await worker.stop()
        assert not worker.running


@pytest.mark.asyncio
async def test_handshake_and_discovery_real_app_server():
    """
    Test 1b: Live handshake and capability discovery with real Codex App-Server binary.
    """
    resolved_bin = resolve_codex_binary()
    if not resolved_bin or not Path(resolved_bin).is_file():
        pytest.skip("Real Codex binary not found on this system")

    worker = WorkerProcess(command=[resolved_bin, "app-server"], perform_handshake=True)
    try:
        await worker.start()
        assert worker.running
        assert worker.init_result is not None
        # Verify server returned capabilities or userAgent metadata
        assert (
            "capabilities" in worker.init_result
            or "userAgent" in worker.init_result
            or "protocolVersion" in worker.init_result
        )
    finally:
        await worker.stop()
        assert not worker.running


# =============================================================================
# Test 2: Full Turn Lifecycle with Worktree Sandboxing
# =============================================================================

def test_full_turn_lifecycle_worktree_sandboxing(client, db_session):
    """
    Test 2: Full turn lifecycle verifying that starting a turn ensures an isolated git
    worktree under 'worktrees/wt-<threadId>' and strictly binds workspaceRoot and cwd to it.
    """
    thread_id = "thread_cas04_e2e"

    with patch(
        "backend.services.worker_manager.worker_manager.get_worker_for_thread"
    ) as mock_get_worker_for_thread:
        mock_worker = AsyncMock()
        mock_worker.running = True
        mock_worker.send_request = AsyncMock()
        mock_get_worker_for_thread.return_value = mock_worker

        # 1. Dispatch turn start via REST API
        prompt_text = "Implement end-to-end quality gate validation"
        response = client.post(
            "/codex/turns/start",
            json={
                "thread_id": thread_id,
                "prompt": prompt_text,
                "model": "gpt-4o",
                "reasoning_effort": "high",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert "turn_id" in data
        assert "workspace_root" in data
        expected_wt_segment = f"wt-{thread_id}"
        assert expected_wt_segment in data["workspace_root"]

        # 2. Verify database records
        turn = db_session.query(Turn).filter(Turn.id == data["turn_id"]).first()
        assert turn is not None
        assert turn.thread_id == thread_id
        assert turn.turn_number == 1
        assert turn.status == "active"
        assert turn.prompt == prompt_text

        # 3. Verify get_worker_for_thread was called with thread_id
        mock_get_worker_for_thread.assert_called_once()
        call_args, _ = mock_get_worker_for_thread.call_args
        assert call_args[0] == thread_id

        # 4. Verify turn/start RPC was sent to worker with sandboxed workspaceRoot and cwd
        mock_worker.send_request.assert_called_once()
        rpc_method, rpc_params = mock_worker.send_request.call_args[0]
        assert rpc_method == "turn/start"
        assert rpc_params["threadId"] == thread_id
        assert rpc_params["prompt"] == prompt_text
        assert rpc_params["input"] == [{"type": "text", "text": prompt_text}]
        assert rpc_params["model"] == "gpt-4o"
        assert rpc_params["reasoningEffort"] == "high"
        assert expected_wt_segment in rpc_params["workspaceRoot"]
        assert expected_wt_segment in rpc_params["cwd"]
        assert rpc_params["workspaceRoot"] == rpc_params["cwd"]


# =============================================================================
# Test 3: Real-Time SSE Event Streaming
# =============================================================================

@pytest.mark.asyncio
async def test_realtime_sse_event_streaming():
    """
    Test 3: Simulates and verifies that 'turn/reasoningDelta', 'turn/messageDelta',
    'turn/commandExecution', and 'turn/fileModified' notifications stream into
    the EventBroker and are correctly retrieved via the SSE endpoint.
    """
    project_id = "proj_cas04"
    thread_id = "thread_cas04_e2e"

    # 1. Publish 4 distinct Codex App-Server notifications
    notifs = [
        (
            "turn/reasoningDelta",
            {
                "threadId": thread_id,
                "turnId": 1,
                "chunk": "Analyzing directory structure for sandboxed worktrees...",
                "sequence": 1,
            },
            "reasoning",
        ),
        (
            "turn/messageDelta",
            {
                "threadId": thread_id,
                "turnId": 1,
                "text": "Starting validation of Work Package CAS-04.",
                "is_streaming": True,
            },
            "agent_message",
        ),
        (
            "turn/commandExecution",
            {
                "threadId": thread_id,
                "turnId": 1,
                "command": "pytest tests/ -v",
                "exit_code": 0,
                "stdout": "100 passed in 12s",
                "status": "completed",
            },
            "command",
        ),
        (
            "turn/fileModified",
            {
                "threadId": thread_id,
                "turnId": 1,
                "path": "tests/test_codex_app_server.py",
                "additions": 150,
                "deletions": 0,
                "diff": "+# CAS-04 End-to-End Suite",
            },
            "file_change",
        ),
    ]

    for method, params, expected_type in notifs:
        env = Protocol.normalize_notification(
            method=method,
            params=params,
            project_id=project_id,
            thread_id=thread_id,
            turn_id=1,
        )
        assert env is not None
        assert env.type == expected_type
        broker.publish_event(env)

    # 2. Connect to SSE streaming endpoint and verify replayed backlog events
    req = MagicMock()
    response = await stream_events(project_id, thread_id, req)
    assert response.status_code == 200
    assert "text/event-stream" in response.media_type

    received_events = []
    async for chunk in response.body_iterator:
        chunk_str = chunk if isinstance(chunk, str) else chunk.decode("utf-8")
        for block in chunk_str.strip().split("\n\n"):
            if not block.strip():
                continue
            event_obj = {}
            for line in block.strip().split("\n"):
                if line.startswith("id: "):
                    event_obj["id"] = line[4:].strip()
                elif line.startswith("event: "):
                    event_obj["event"] = line[7:].strip()
                elif line.startswith("data: "):
                    event_obj["data"] = json.loads(line[6:].strip())
            if event_obj and "event" in event_obj and event_obj["event"] != "ping":
                received_events.append(event_obj)
        if len(received_events) >= 4:
            break

    # 3. Assert all 4 typed events were received in order
    assert len(received_events) >= 4
    types = [e["event"] for e in received_events[:4]]
    assert types == ["reasoning", "agent_message", "command", "file_change"]

    # Verify payloads
    assert "Analyzing directory structure" in received_events[0]["data"]["chunk"]
    assert "Starting validation" in received_events[1]["data"]["text"]
    assert received_events[2]["data"]["command"] == "pytest tests/ -v"
    assert received_events[2]["data"]["exit_code"] == 0
    assert received_events[3]["data"]["path"] == "tests/test_codex_app_server.py"
    assert received_events[3]["data"]["additions"] == 150

    # 4. Also verify live dynamic SSE stream reception
    queue = broker.subscribe(thread_id)
    try:
        live_env = Protocol.normalize_notification(
            method="turn/reasoningDelta",
            params={"threadId": thread_id, "chunk": "Live reasoning dynamic stream"},
            project_id=project_id,
            thread_id=thread_id,
            turn_id=1,
        )
        assert live_env is not None
        broker.publish_event(live_env)
        rec = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert rec.type == "reasoning"
        assert rec.payload["chunk"] == "Live reasoning dynamic stream"
    finally:
        broker.unsubscribe(thread_id, queue)


# =============================================================================
# Test 4: Approval Gate Round-Trip
# =============================================================================

@pytest.mark.asyncio
async def test_approval_gate_roundtrip(client, db_session):
    """
    Test 4: Simulates a high-risk tool call ('turn/toolApprovalRequested'), verifies it pauses
    worker execution, creates a pending ToolApproval, and checks that POST /codex/approvals/respond
    resolves the approval and returns {"approved": True} to unblock the worker.
    """
    thread_id = "thread_cas04_e2e"
    tool_call_id = "tc_high_risk_drop_db"
    rpc_req_id = "rpc_req_9988"

    # Setup worker process mock
    worker = WorkerProcess(command=["mock"], perform_handshake=False)
    worker.thread_id = thread_id
    worker.send_raw = AsyncMock()

    # 1. Simulate incoming HIGH risk tool approval request from Codex App-Server
    high_risk_msg = {
        "jsonrpc": "2.0",
        "id": rpc_req_id,
        "method": "turn/toolApprovalRequested",
        "params": {
            "threadId": thread_id,
            "toolCallId": tool_call_id,
            "command": "git reset --hard HEAD~1",
            "parameters": {"command": "git reset --hard HEAD~1"},
        },
    }

    with patch("backend.services.worker.SessionLocal", return_value=db_session):
        await worker._handle_tool_approval(high_risk_msg)

    # Worker was NOT auto-approved
    worker.send_raw.assert_not_called()

    # Pending ToolApproval record exists in DB
    pending_approvals = governance_service.list_pending_approvals(db_session, thread_id)
    assert len(pending_approvals) == 1
    approval = pending_approvals[0]
    assert approval.tool_call_id == tool_call_id
    assert approval.status == "pending"
    assert approval.risk_level in ("HIGH", "CRITICAL")

    # Verify approval is listed by the governance pending endpoint
    list_res = client.get(f"/codex/governance/approvals/pending?thread_id={thread_id}")
    assert list_res.status_code == 200
    assert any(a["tool_call_id"] == tool_call_id for a in list_res.json())

    # 2. Operator responds to approval gate via POST /codex/approvals/respond
    with patch("backend.services.worker_manager.worker_manager.get_worker", return_value=worker):
        res = client.post(
            "/codex/approvals/respond",
            json={
                "thread_id": thread_id,
                "tool_call_id": tool_call_id,
                "approved": True,
                "feedback": "Authorization granted by operator",
            },
        )

    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "approved"
    assert res_data["tool_call_id"] == tool_call_id

    # 3. Verify DB record is updated to 'approved'
    db_session.refresh(approval)
    assert approval.status == "approved"
    assert approval.resolved_at is not None

    # 4. Verify worker received unblocking JSON-RPC response with approved: True
    worker.send_raw.assert_called_once()
    raw_packet = worker.send_raw.call_args[0][0]
    packet = json.loads(raw_packet)
    assert packet["jsonrpc"] == "2.0"
    assert packet["id"] == rpc_req_id
    assert packet["result"]["approved"] is True
    assert packet["result"]["feedback"] == "Authorization granted by operator"


# =============================================================================
# Test 5: Turn Interruption & Cascade Cleanup
# =============================================================================

def test_turn_interruption_and_cascade_cleanup(client, db_session):
    """
    Test 5: Verifies that POST /codex/turns/interrupt sends turn/interrupt to the worker,
    cancels the active turn, and cascades cancellation to all pending tool approvals.
    """
    thread_id = "thread_cas04_e2e"

    # 1. Create active Turn and multiple pending ToolApprovals in DB
    turn = Turn(id=301, thread_id=thread_id, turn_number=1, status="active")
    db_session.add(turn)

    appr1 = governance_service.create_approval_request(
        thread_id=thread_id,
        tool_call_id="tc_cascade_1",
        command="npm install -g corepack",
        risk_level="HIGH",
        consequence="Global package installation",
        db=db_session,
    )
    appr2 = governance_service.create_approval_request(
        thread_id=thread_id,
        tool_call_id="tc_cascade_2",
        command="git push --force origin main",
        risk_level="CRITICAL",
        consequence="Destructive remote history overwrite",
        db=db_session,
    )
    assert len(governance_service.list_pending_approvals(db_session, thread_id)) == 2

    # 2. Dispatch turn interruption via POST /codex/turns/interrupt
    with patch("backend.services.worker_manager.worker_manager.get_worker") as mock_get_worker:
        mock_worker = AsyncMock()
        mock_worker.running = True
        mock_worker.send_request = AsyncMock()
        mock_get_worker.return_value = mock_worker

        response = client.post(
            "/codex/turns/interrupt",
            json={
                "thread_id": thread_id,
                "turn_id": 301,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "interrupted"

        # Verify worker received turn/interrupt request
        mock_worker.send_request.assert_called_once()
        rpc_method, rpc_params = mock_worker.send_request.call_args[0]
        assert rpc_method == "turn/interrupt"
        assert rpc_params["threadId"] == thread_id
        assert rpc_params["turnId"] == "301"

    # 3. Verify all pending approvals for the thread were cascade-cancelled
    db_session.refresh(appr1)
    db_session.refresh(appr2)
    assert appr1.status == "cancelled"
    assert appr1.resolved_at is not None
    assert appr2.status == "cancelled"
    assert appr2.resolved_at is not None

    pending_remaining = governance_service.list_pending_approvals(db_session, thread_id)
    assert len(pending_remaining) == 0

    # 4. Verify cascade cancellation events were published to broker
    events = broker.get_history(thread_id)
    cancelled_event_types = [e.type for e in events if e.type in ("approval_cancelled", "approval.cancelled")]
    assert len(cancelled_event_types) >= 2


# =============================================================================
# Test 6: Turn Steer Schema & expectedTurnId Validation
# =============================================================================

def test_turn_steer_schema_and_expected_turn_id(client, db_session):
    """
    Test 6: Verifies that POST /codex/turns/steer formats expectedTurnId as a string,
    includes input payload as a list of typed user inputs, and passes turnId as a string.
    """
    thread_id = "thread_cas04_e2e"
    turn = Turn(id=401, thread_id=thread_id, turn_number=1, status="active")
    db_session.add(turn)
    db_session.commit()

    with patch("backend.services.worker_manager.worker_manager.get_worker") as mock_get_worker:
        mock_worker = AsyncMock()
        mock_worker.running = True
        mock_worker.send_request = AsyncMock()
        mock_get_worker.return_value = mock_worker

        instruction_text = "Refactor turn handler to use safe async dispatch runner"
        response = client.post(
            "/codex/turns/steer",
            json={
                "thread_id": thread_id,
                "turn_id": 401,
                "instruction": instruction_text,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "steered"

        mock_worker.send_request.assert_called_once()
        rpc_method, rpc_params = mock_worker.send_request.call_args[0]
        assert rpc_method == "turn/steer"
        assert rpc_params["threadId"] == thread_id
        assert rpc_params["expectedTurnId"] == "401"
        assert rpc_params["turnId"] == "401"
        assert rpc_params["instruction"] == instruction_text
        assert rpc_params["input"] == [{"type": "text", "text": instruction_text}]


# =============================================================================
# Test 7: Thread Initialization & Persistent Mapping Flow
# =============================================================================

@pytest.mark.asyncio
async def test_turn_start_thread_initialization_and_mapping(client, db_session):
    """
    Test 7: Verifies that when a thread requires initialization on the worker,
    thread/start is called with cwd, the returned codex thread ID is mapped and saved,
    and turn/start uses that codex thread ID. Subsequent turns reuse the cached ID.
    """
    thread_id = "thread_cas04_e2e"
    codex_assigned_uuid = "01a074d1-ad33-7dd3-9718-f1a24f3a9fe7"

    # Reset any previous mappings for clean test state
    worker_manager.thread_map.pop(thread_id, None)
    worker_manager.reverse_thread_map.pop(codex_assigned_uuid, None)

    mock_worker = AsyncMock()
    mock_worker.running = True
    mock_worker.requires_thread_init = True
    mock_worker.thread_map = {}
    mock_worker.reverse_thread_map = {}

    async def fake_send_request(method, params, timeout=None, req_id=None):
        if method == "thread/start":
            return {"thread": {"id": codex_assigned_uuid}}
        elif method == "turn/start":
            return {"turn": {"id": "turn_001", "status": "inProgress"}}
        return {}

    mock_worker.send_request = AsyncMock(side_effect=fake_send_request)

    with patch(
        "backend.services.worker_manager.worker_manager.get_worker_for_thread",
        return_value=mock_worker,
    ):
        # 1. First turn dispatch: triggers thread/start and then turn/start
        res1 = client.post(
            "/codex/turns/start",
            json={
                "thread_id": thread_id,
                "prompt": "First prompt on uninitialized thread",
            },
        )
        assert res1.status_code == 200
        await asyncio.sleep(0.05)

        # Verify thread mapping was registered
        assert worker_manager.thread_map.get(thread_id) == codex_assigned_uuid
        assert worker_manager.reverse_thread_map.get(codex_assigned_uuid) == thread_id

        # Verify calls on mock_worker
        assert mock_worker.send_request.call_count == 2
        calls = mock_worker.send_request.call_args_list
        assert calls[0][0][0] == "thread/start"
        assert "cwd" in calls[0][0][1]

        assert calls[1][0][0] == "turn/start"
        assert calls[1][0][1]["threadId"] == codex_assigned_uuid
        assert calls[1][0][1]["prompt"] == "First prompt on uninitialized thread"
        assert calls[1][0][1]["input"] == [{"type": "text", "text": "First prompt on uninitialized thread"}]

        # 2. Second turn dispatch: should reuse cached mapping without extra thread/start
        res2 = client.post(
            "/codex/turns/start",
            json={
                "thread_id": thread_id,
                "prompt": "Second prompt on initialized thread",
            },
        )
        assert res2.status_code == 200
        await asyncio.sleep(0.05)

        # Call count increments by 1 (only turn/start was sent, not thread/start)
        assert mock_worker.send_request.call_count == 3
        third_call = mock_worker.send_request.call_args_list[2]
        assert third_call[0][0] == "turn/start"
        assert third_call[0][1]["threadId"] == codex_assigned_uuid


# =============================================================================
# Test 8: Error Resilience & UI Visibility on Worker Exception
# =============================================================================

@pytest.mark.asyncio
async def test_turn_start_error_resilience_and_broker_event(client, db_session):
    """
    Test 8: Verifies that when worker.send_request fails with an exception, the background
    task catches it safely, updates the Turn record to status='failed', persists an error Item,
    and publishes typed error and turn_completed events to the EventBroker for immediate UI display.
    """
    thread_id = "thread_cas04_e2e"
    error_message = "Invalid request: missing field `input`"

    mock_worker = AsyncMock()
    mock_worker.running = True
    mock_worker.send_request = AsyncMock(side_effect=Exception(error_message))

    with patch(
        "backend.services.worker_manager.worker_manager.get_worker_for_thread",
        return_value=mock_worker,
    ):
        response = client.post(
            "/codex/turns/start",
            json={
                "thread_id": thread_id,
                "prompt": "Simulated failing turn dispatch",
            },
        )
        assert response.status_code == 200
        turn_id = response.json()["turn_id"]

        # Allow background safe dispatch task to run
        await asyncio.sleep(0.05)
        db_session.expire_all()

        # 1. Verify Turn DB record was updated to 'failed'
        turn_in_db = db_session.query(Turn).filter(Turn.id == turn_id).first()
        assert turn_in_db is not None
        assert turn_in_db.status == "failed"
        assert turn_in_db.completed_at is not None

        # 2. Verify error Item record was persisted in DB
        err_item = (
            db_session.query(Item)
            .filter(Item.turn_id == turn_id, Item.item_type == "error")
            .first()
        )
        assert err_item is not None
        assert error_message in str(err_item.content)

        # 3. Verify error and turn_completed events were published to EventBroker
        events = broker.get_history(thread_id)
        error_events = [e for e in events if e.type == "error"]
        completed_events = [e for e in events if e.type == "turn_completed"]

        assert len(error_events) >= 1
        assert error_events[-1].payload["status"] == "failed"
        assert error_message in error_events[-1].payload["message"]

        assert len(completed_events) >= 1
        assert completed_events[-1].payload["status"] == "failed"
