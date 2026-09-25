import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.services.worker_manager import (
    WorkerProcess,
    WorkerManager,
    resolve_codex_binary,
    resolve_codex_command,
)
from backend.config import settings
from backend.database import Base, set_sqlite_pragma
from backend.models.codex import Project, Thread, Turn, Item

MOCK_WORKER_SCRIPT = (
    "import sys, json\n"
    "while True:\n"
    "    line = sys.stdin.readline()\n"
    "    if not line: break\n"
    "    data = json.loads(line)\n"
    "    req_id = data.get('id')\n"
    "    if req_id is not None:\n"
    "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req_id, 'result': 'ok'}) + '\\n')\n"
    "        sys.stdout.flush()\n"
)

MOCK_TIMEOUT_SCRIPT = (
    "import sys, json, time\n"
    "while True:\n"
    "    line = sys.stdin.readline()\n"
    "    if not line: break\n"
    "    data = json.loads(line)\n"
    "    req_id = data.get('id')\n"
    "    if data.get('method') == 'ping':\n"
    "        time.sleep(2)\n"
    "    if req_id is not None:\n"
    "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req_id, 'result': 'ok'}) + '\\n')\n"
    "        sys.stdout.flush()\n"
)


@pytest.mark.asyncio
async def test_worker_process():
    cmd = [sys.executable, "-u", "-c", MOCK_WORKER_SCRIPT]
    worker = WorkerProcess(cmd)
    await worker.start()

    assert worker.running
    assert worker.process is not None
    assert worker.init_result == "ok"

    res = await worker.send_request("test_method", {"param": 1})
    assert res == "ok"

    await worker.stop()
    assert not worker.running


@pytest.mark.asyncio
async def test_worker_manager():
    cmd = [sys.executable, "-u", "-c", MOCK_WORKER_SCRIPT]
    manager = WorkerManager(cmd)

    worker = await manager.get_worker()
    assert worker.running

    res = await worker.send_request("ping")
    assert res == "ok"

    await manager.stop()
    assert not worker.running


@pytest.mark.asyncio
async def test_worker_timeout():
    cmd = [sys.executable, "-u", "-c", MOCK_TIMEOUT_SCRIPT]
    manager = WorkerManager(cmd)
    worker = await manager.get_worker()

    with pytest.raises(asyncio.TimeoutError):
        await worker.send_request("ping", timeout=0.5)

    # Ensure timed-out request is cleaned up from pending_requests
    assert len(worker.pending_requests) == 0

    await manager.stop()
    assert not worker.running


@pytest.mark.asyncio
async def test_worker_initialize_handshake():
    # Worker script that records initialize parameters and initialized notification
    handshake_recorder = (
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
        "            'result': {'capabilities': {'streaming': True}, 'status': 'initialized'}\n"
        "        }) + '\\n')\n"
        "        sys.stdout.flush()\n"
        "    elif msg.get('method') == 'dump':\n"
        "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': records}) + '\\n')\n"
        "        sys.stdout.flush()\n"
    )
    cmd = [sys.executable, "-u", "-c", handshake_recorder]
    worker = WorkerProcess(cmd, perform_handshake=True)
    await worker.start()

    assert worker.running
    assert worker.init_result == {"capabilities": {"streaming": True}, "status": "initialized"}

    # Request the recorded messages
    records = await worker.send_request("dump")
    await worker.stop()

    assert len(records) >= 2
    # Verify initialize request
    init_msg = records[0]
    assert init_msg["jsonrpc"] == "2.0"
    assert init_msg["id"] == 1
    assert init_msg["method"] == "initialize"
    assert init_msg["params"]["clientInfo"]["name"] == "CodexControlCentre"
    assert init_msg["params"]["capabilities"]["streaming"] is True
    assert init_msg["params"]["capabilities"]["approvals"] is True

    # Verify initialized notification
    notif_msg = records[1]
    assert notif_msg["jsonrpc"] == "2.0"
    assert "id" not in notif_msg
    assert notif_msg["method"] == "initialized"


def test_binary_resolution():
    # 1. Test standard binary resolution using default settings
    resolved = resolve_codex_binary()
    assert isinstance(resolved, str)
    assert len(resolved) > 0

    # 2. Test resolution with explicit existing executable (e.g. sys.executable)
    py_resolved = resolve_codex_binary(sys.executable)
    assert py_resolved == sys.executable

    # 3. Test resolution with nonexistent executable
    fake_resolved = resolve_codex_binary("nonexistent_codex_executable_xyz")
    assert fake_resolved == "nonexistent_codex_executable_xyz"

    # 4. Test resolve_codex_command
    cmd = resolve_codex_command()
    assert isinstance(cmd, list)
    assert len(cmd) >= 1
    assert cmd[0] == resolved
    assert cmd[1:] == settings.codex_app_server_args


@pytest.mark.asyncio
async def test_concurrent_line_reading_no_deadlock():
    # Worker that floods stderr while responding to stdout
    flood_script = (
        "import sys, json\n"
        "while True:\n"
        "    line = sys.stdin.readline()\n"
        "    if not line: break\n"
        "    msg = json.loads(line)\n"
        "    if 'id' in msg:\n"
        "        # Write 200 lines to stderr to test concurrent drain\n"
        "        for i in range(200):\n"
        "            sys.stderr.write(f'stderr log line {i}\\n')\n"
        "        sys.stderr.flush()\n"
        "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': 'drain_ok'}) + '\\n')\n"
        "        sys.stdout.flush()\n"
    )
    cmd = [sys.executable, "-u", "-c", flood_script]
    worker = WorkerProcess(cmd, perform_handshake=True)
    await worker.start()

    res = await worker.send_request("test_flood")
    assert res == "drain_ok"
    assert len(worker.stderr_lines) > 0

    await worker.stop()
    assert not worker.running


@pytest.mark.asyncio
async def test_clean_shutdown_and_idempotence():
    cmd = [sys.executable, "-u", "-c", MOCK_WORKER_SCRIPT]
    worker = WorkerProcess(cmd)
    await worker.start()
    assert worker.running

    # First stop
    await worker.stop()
    assert not worker.running

    # Idempotent second stop
    await worker.stop()
    assert not worker.running


@pytest.mark.asyncio
async def test_real_codex_app_server_if_available():
    resolved = resolve_codex_binary()
    if not resolved or not Path(resolved).is_file():
        pytest.skip("Real codex binary not available on this system")

    worker = WorkerProcess(command=[resolved, "app-server"], perform_handshake=True)
    try:
        await worker.start()
        assert worker.running
        assert worker.init_result is not None
        # On real codex app-server, result contains userAgent or capabilities
        assert "userAgent" in worker.init_result or "capabilities" in worker.init_result
    finally:
        await worker.stop()
        assert not worker.running


@pytest.mark.asyncio
async def test_worker_handle_notification_sqlite_persistence():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", set_sqlite_pragma)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        proj = Project(id="p1", name="Proj", repo_path="/tmp", default_branch="main")
        th = Thread(id="th_worker_persist", project_id="p1", title="Worker Test")
        turn = Turn(id=1, thread_id="th_worker_persist", turn_number=1, status="active")
        session.add(proj)
        session.add(th)
        session.add(turn)
        session.commit()

    worker = WorkerProcess(command=["mock"], perform_handshake=False)
    worker.thread_id = "th_worker_persist"

    with patch("backend.services.worker.SessionLocal", TestingSession):
        # 1. Non-streaming agent message completion
        agent_msg = {
            "jsonrpc": "2.0",
            "method": "item/completed",
            "params": {
                "threadId": "th_worker_persist",
                "turnId": 1,
                "item": {
                    "id": "item_msg_99",
                    "type": "agentMessage",
                    "text": "Completed response from worker"
                }
            }
        }
        await worker._handle_notification(agent_msg)

        with TestingSession() as session:
            persisted_msg = session.query(Item).filter(Item.id == "item_msg_99").first()
            assert persisted_msg is not None
            assert persisted_msg.turn_id == 1
            assert persisted_msg.item_type == "text"
            assert persisted_msg.content["text"] == "Completed response from worker"

        # 2. Command execution item completion
        cmd_msg = {
            "jsonrpc": "2.0",
            "method": "item/completed",
            "params": {
                "threadId": "th_worker_persist",
                "turnId": 1,
                "item": {
                    "id": "item_cmd_99",
                    "type": "commandExecution",
                    "command": "echo test",
                    "exitCode": 0,
                    "stdout": "test output",
                    "stderr": ""
                }
            }
        }
        await worker._handle_notification(cmd_msg)

        with TestingSession() as session:
            persisted_cmd = session.query(Item).filter(Item.id == "item_cmd_99").first()
            assert persisted_cmd is not None
            assert persisted_cmd.turn_id == 1
            assert persisted_cmd.item_type == "command"
            assert persisted_cmd.content["command"] == "echo test"

        # 3. Turn completed notification
        turn_comp_msg = {
            "jsonrpc": "2.0",
            "method": "turn/completed",
            "params": {
                "threadId": "th_worker_persist",
                "turn": {
                    "id": 1,
                    "status": "completed"
                }
            }
        }
        await worker._handle_notification(turn_comp_msg)

        with TestingSession() as session:
            t = session.query(Turn).filter(Turn.id == 1).first()
            assert t.status == "completed"
            assert t.completed_at is not None
