import pytest
import json
from backend.services.protocol import (
    Protocol,
    JsonRpcError,
    InitializeParams,
    ThreadCreateParams,
    ThreadResumeParams,
    TurnStartParams,
    TurnSteerParams,
    TurnInterruptParams,
    ApprovalRespondParams,
    normalize_codex_notification,
)
from backend.services.event_service import EventBroker

def test_build_request():
    req = json.loads(Protocol.build_request("thread/start", {"thread_id": "123"}, msg_id="1"))
    assert req["jsonrpc"] == "2.0"
    assert req["method"] == "thread/start"
    assert req["params"] == {"thread_id": "123"}
    assert req["id"] == "1"

def test_build_notification():
    req = json.loads(Protocol.build_notification("notification/event", {"type": "text"}))
    assert req["jsonrpc"] == "2.0"
    assert req["method"] == "notification/event"
    assert req["params"] == {"type": "text"}
    assert "id" not in req

def test_build_response():
    resp = json.loads(Protocol.build_response("1", {"status": "ok"}))
    assert resp["jsonrpc"] == "2.0"
    assert resp["result"] == {"status": "ok"}
    assert resp["id"] == "1"
    assert "error" not in resp

def test_build_error():
    err = json.loads(Protocol.build_error("1", -32600, "Invalid request"))
    assert err["jsonrpc"] == "2.0"
    assert err["error"]["code"] == -32600
    assert err["error"]["message"] == "Invalid request"
    assert err["id"] == "1"

def test_parse_valid_message():
    raw = '{"jsonrpc": "2.0", "id": "1", "result": "ok"}'
    parsed = Protocol.parse_message(raw)
    assert parsed["id"] == "1"
    assert parsed["result"] == "ok"

def test_parse_invalid_json():
    with pytest.raises(JsonRpcError) as exc:
        Protocol.parse_message("not json")
    assert exc.value.code == -32700

def test_parse_invalid_version():
    with pytest.raises(JsonRpcError) as exc:
        Protocol.parse_message('{"jsonrpc": "1.0", "id": "1"}')
    assert exc.value.code == -32600

def test_parse_invalid_id_type():
    with pytest.raises(JsonRpcError) as exc:
        Protocol.parse_message('{"jsonrpc": "2.0", "id": {"invalid": "object"}}')
    assert exc.value.code == -32600

def test_parse_invalid_error_structure():
    with pytest.raises(JsonRpcError) as exc:
        Protocol.parse_message('{"jsonrpc": "2.0", "id": "1", "error": "not_an_object"}')
    assert exc.value.code == -32600


# --- Codex App-Server Request Schema & Builder Tests ---

def test_initialize_request():
    req_json = Protocol.build_initialize_request(
        client_info={"name": "CodexControlCentre", "version": "1.0"},
        capabilities={"streaming": True},
        msg_id="init_1"
    )
    req = Protocol.parse_message(req_json)
    assert req["jsonrpc"] == "2.0"
    assert req["method"] == "initialize"
    assert req["id"] == "init_1"
    assert req["params"]["clientInfo"]["name"] == "CodexControlCentre"

    params = Protocol.validate_request_params("initialize", req["params"])
    assert isinstance(params, InitializeParams)
    assert params.client_info["name"] == "CodexControlCentre"

def test_thread_create_serialization_and_deserialization():
    req_json = Protocol.build_thread_create_request(
        workspace_root="/home/user/repo",
        msg_id="th_create_1",
        title="New Thread"
    )
    req = Protocol.parse_message(req_json)
    assert req["jsonrpc"] == "2.0"
    assert req["method"] == "thread/create"
    assert req["id"] == "th_create_1"
    assert req["params"]["workspaceRoot"] == "/home/user/repo"
    assert req["params"]["title"] == "New Thread"

    # Deserialization & validation
    params = Protocol.validate_request_params("thread/create", req["params"])
    assert isinstance(params, ThreadCreateParams)
    assert params.workspace_root == "/home/user/repo"

    # Invalid params (missing workspaceRoot)
    with pytest.raises(JsonRpcError) as exc:
        Protocol.validate_request_params("thread/create", {})
    assert exc.value.code == -32602

def test_thread_resume_serialization_and_deserialization():
    req_json = Protocol.build_thread_resume_request("thread_abc", msg_id="th_resume_1")
    req = Protocol.parse_message(req_json)
    assert req["method"] == "thread/resume"
    assert req["params"]["threadId"] == "thread_abc"

    params = Protocol.validate_request_params("thread/resume", req["params"])
    assert isinstance(params, ThreadResumeParams)
    assert params.thread_id == "thread_abc"

def test_thread_start_serialization_and_deserialization():
    req_json = Protocol.build_thread_start_request(cwd="/path/to/repo", msg_id="th_start_1")
    req = Protocol.parse_message(req_json)
    assert req["method"] == "thread/start"
    assert req["id"] == "th_start_1"
    assert req["params"]["cwd"] == "/path/to/repo"

    params = Protocol.validate_request_params("thread/start", req["params"])
    assert params.cwd == "/path/to/repo"

def test_turn_start_serialization_and_deserialization():
    req_json = Protocol.build_turn_start_request(
        thread_id="th_99",
        prompt="Explain the architecture",
        model="gpt-4o",
        reasoning_effort="high",
        msg_id="turn_start_1"
    )
    req = Protocol.parse_message(req_json)
    assert req["method"] == "turn/start"
    assert req["id"] == "turn_start_1"
    assert req["params"]["threadId"] == "th_99"
    assert req["params"]["prompt"] == "Explain the architecture"
    assert req["params"]["input"] == [{"type": "text", "text": "Explain the architecture"}]
    assert req["params"]["model"] == "gpt-4o"
    assert req["params"]["reasoningEffort"] == "high"

    # Deserialization & validation
    params = Protocol.validate_request_params("turn/start", req["params"])
    assert isinstance(params, TurnStartParams)
    assert params.thread_id == "th_99"
    assert params.prompt == "Explain the architecture"
    assert params.input == [{"type": "text", "text": "Explain the architecture"}]
    assert params.model == "gpt-4o"
    assert params.reasoning_effort == "high"

def test_turn_steer_serialization_and_deserialization():
    req_json = Protocol.build_turn_steer_request(
        thread_id="th_99",
        turn_id=3,
        instruction="Focus on performance",
        msg_id="turn_steer_1"
    )
    req = Protocol.parse_message(req_json)
    assert req["method"] == "turn/steer"
    assert req["params"]["threadId"] == "th_99"
    assert req["params"]["turnId"] == 3
    assert req["params"]["expectedTurnId"] == "3"
    assert req["params"]["instruction"] == "Focus on performance"
    assert req["params"]["input"] == [{"type": "text", "text": "Focus on performance"}]

    params = Protocol.validate_request_params("turn/steer", req["params"])
    assert isinstance(params, TurnSteerParams)
    assert params.thread_id == "th_99"
    assert str(params.turn_id) == "3"
    assert params.expected_turn_id == "3"
    assert params.instruction == "Focus on performance"
    assert params.input == [{"type": "text", "text": "Focus on performance"}]

def test_turn_interrupt_serialization_and_deserialization():
    req_json = Protocol.build_turn_interrupt_request("th_99", 3, msg_id="turn_int_1")
    req = Protocol.parse_message(req_json)
    assert req["method"] == "turn/interrupt"
    assert req["params"]["threadId"] == "th_99"
    assert req["params"]["turnId"] == "3"

    params = Protocol.validate_request_params("turn/interrupt", req["params"])
    assert isinstance(params, TurnInterruptParams)
    assert params.thread_id == "th_99"
    assert params.turn_id == "3"

def test_approval_respond_serialization_and_deserialization():
    req_json = Protocol.build_approval_respond_request(
        tool_call_id="call_xyz",
        approved=True,
        feedback="Proceed with cautious execution",
        msg_id="appr_1"
    )
    req = Protocol.parse_message(req_json)
    assert req["method"] == "approval/respond"
    assert req["params"]["toolCallId"] == "call_xyz"
    assert req["params"]["approved"] is True
    assert req["params"]["feedback"] == "Proceed with cautious execution"

    params = Protocol.validate_request_params("approval/respond", req["params"])
    assert isinstance(params, ApprovalRespondParams)
    assert params.tool_call_id == "call_xyz"
    assert params.approved is True
    assert params.feedback == "Proceed with cautious execution"

def test_validate_unknown_method():
    with pytest.raises(JsonRpcError) as exc:
        Protocol.validate_request_params("unknown/method", {})
    assert exc.value.code == -32601


# --- Event Normalization Adapter Tests ---

def test_normalize_reasoning_delta():
    params = {
        "chunk": "Considering caching layer...",
        "sequence": 5
    }
    env = normalize_codex_notification(
        method="turn/reasoningDelta",
        params=params,
        project_id="proj_codex",
        thread_id="th_100",
        turn_id=2
    )
    assert env is not None
    assert env.type == "reasoning"
    assert env.project_id == "proj_codex"
    assert env.thread_id == "th_100"
    assert env.payload["chunk"] == "Considering caching layer..."
    assert env.payload["sequence"] == 5
    assert env.payload["turn_id"] == 2

def test_normalize_message_delta():
    params = {
        "text": "The test run completed successfully.",
        "item_id": "msg_42"
    }
    env = normalize_codex_notification(
        method="turn/messageDelta",
        params=params,
        project_id="proj_codex",
        thread_id="th_100",
        turn_id=2
    )
    assert env is not None
    assert env.type == "agent_message"
    assert env.payload["text"] == "The test run completed successfully."
    assert env.payload["content"] == "The test run completed successfully."
    assert env.payload["item_id"] == "msg_42"
    assert env.payload["is_streaming"] is True

def test_normalize_command_execution():
    params = {
        "command": "pytest tests/test_protocol.py",
        "exit_code": 0,
        "stdout": "7 passed in 0.5s",
        "stderr": ""
    }
    env = normalize_codex_notification(
        method="turn/commandExecution",
        params=params,
        project_id="proj_codex",
        thread_id="th_100",
        turn_id=2
    )
    assert env is not None
    assert env.type == "command"
    assert env.payload["command"] == "pytest tests/test_protocol.py"
    assert env.payload["exit_code"] == 0
    assert env.payload["stdout"] == "7 passed in 0.5s"
    assert env.payload["status"] == "completed"

def test_normalize_file_modified():
    params = {
        "path": "backend/services/protocol.py",
        "additions": 45,
        "deletions": 5,
        "diff": "@@ -1,5 +1,10 @@"
    }
    env = normalize_codex_notification(
        method="turn/fileModified",
        params=params,
        project_id="proj_codex",
        thread_id="th_100",
        turn_id=2
    )
    assert env is not None
    assert env.type == "file_change"
    assert env.payload["path"] == "backend/services/protocol.py"
    assert env.payload["additions"] == 45
    assert env.payload["deletions"] == 5
    assert env.payload["diff"] == "@@ -1,5 +1,10 @@"
    assert len(env.payload["files"]) == 1
    assert env.payload["files"][0]["path"] == "backend/services/protocol.py"

def test_normalize_tool_approval_requested():
    for method in ["turn/toolApprovalRequested", "tool_approval_requested"]:
        params = {
            "toolCallId": "call_danger_1",
            "command": "rm -rf /build/cache",
            "riskLevel": "high",
            "consequence": "Destructive cache purging"
        }
        env = normalize_codex_notification(
            method=method,
            params=params,
            project_id="proj_codex",
            thread_id="th_100",
            turn_id=2
        )
        assert env is not None
        assert env.type == "approval_requested"
        assert env.payload["toolCallId"] == "call_danger_1"
        assert env.payload["command"] == "rm -rf /build/cache"
        assert env.payload["riskLevel"] == "high"
        assert env.payload["consequence"] == "Destructive cache purging"

def test_normalize_turn_completed():
    params = {
        "status": "completed",
        "completed_at": "2026-09-04T12:00:00Z"
    }
    env = normalize_codex_notification(
        method="turn/completed",
        params=params,
        project_id="proj_codex",
        thread_id="th_100",
        turn_id=2
    )
    assert env is not None
    assert env.type == "turn_completed"
    assert env.payload["status"] == "completed"
    assert env.payload["completed_at"] == "2026-09-04T12:00:00Z"

def test_normalize_unhandled_notification():
    env = normalize_codex_notification(
        method="unhandled/customNotification",
        params={"foo": "bar"},
        project_id="proj_codex",
        thread_id="th_100"
    )
    assert env is None

def test_event_broker_publish_normalized_event():
    broker = EventBroker()
    queue = broker.subscribe("th_live")

    params = {
        "command": "git status",
        "exit_code": 0,
        "stdout": "nothing to commit, working tree clean"
    }
    env = broker.publish_codex_notification(
        method="turn/commandExecution",
        params=params,
        project_id="proj_live",
        thread_id="th_live",
        turn_id=1
    )
    assert env is not None
    assert env.type == "command"
    assert env.sequence == 1

    # Verify event reached the subscriber queue
    received = queue.get_nowait()
    assert received.id == env.id
    assert received.type == "command"
    assert received.payload["command"] == "git status"


def test_normalize_item_agent_message_delta_v2():
    params = {
        "threadId": "th_v2",
        "turnId": 10,
        "itemId": "item_msg_1",
        "delta": "Hello from Codex app-server v2!"
    }
    env = normalize_codex_notification(
        method="item/agentMessage/delta",
        params=params,
        project_id="proj_codex"
    )
    assert env is not None
    assert env.type == "agent_message"
    assert env.payload["text"] == "Hello from Codex app-server v2!"
    assert env.payload["chunk"] == "Hello from Codex app-server v2!"
    assert env.payload["item_id"] == "item_msg_1"
    assert env.payload["turn_id"] == 10
    assert env.payload["is_streaming"] is True


def test_normalize_item_started_v2():
    params = {
        "threadId": "th_v2",
        "turnId": 10,
        "item": {
            "id": "item_msg_2",
            "type": "agentMessage"
        }
    }
    env = normalize_codex_notification(
        method="item/started",
        params=params,
        project_id="proj_codex"
    )
    assert env is not None
    assert env.type == "agent_message"
    assert env.payload["text"] == ""
    assert env.payload["chunk"] == ""
    assert env.payload["item_id"] == "item_msg_2"
    assert env.payload["turn_id"] == 10
    assert env.payload["is_streaming"] is True


def test_normalize_item_completed_agent_message_v2():
    params = {
        "threadId": "th_v2",
        "turnId": 10,
        "item": {
            "id": "item_msg_3",
            "type": "agentMessage",
            "text": "Full completed assistant response."
        }
    }
    env = normalize_codex_notification(
        method="item/completed",
        params=params,
        project_id="proj_codex"
    )
    assert env is not None
    assert env.type == "agent_message"
    assert env.payload["text"] == "Full completed assistant response."
    assert env.payload["content"] == "Full completed assistant response."
    assert env.payload["item_id"] == "item_msg_3"
    assert env.payload["turn_id"] == 10
    assert env.payload["is_streaming"] is False


def test_normalize_item_completed_command_execution_v2():
    params = {
        "threadId": "th_v2",
        "turnId": 10,
        "item": {
            "id": "item_cmd_1",
            "type": "commandExecution",
            "command": "python -m pytest",
            "exitCode": 0,
            "stdout": "All tests passed",
            "stderr": ""
        }
    }
    env = normalize_codex_notification(
        method="item/completed",
        params=params,
        project_id="proj_codex"
    )
    assert env is not None
    assert env.type == "command"
    assert env.payload["command"] == "python -m pytest"
    assert env.payload["exit_code"] == 0
    assert env.payload["stdout"] == "All tests passed"
    assert env.payload["item_id"] == "item_cmd_1"
    assert env.payload["turn_id"] == 10
    assert env.payload["status"] == "completed"


def test_normalize_turn_started_v2():
    params = {
        "threadId": "th_v2",
        "turn": {
            "id": 10,
            "status": "inProgress"
        }
    }
    env = normalize_codex_notification(
        method="turn/started",
        params=params,
        project_id="proj_codex"
    )
    assert env is not None
    assert env.type == "turn_started"
    assert env.payload["turn_id"] == 10
    assert env.payload["status"] == "active"


def test_normalize_turn_completed_v2():
    params = {
        "threadId": "th_v2",
        "turn": {
            "id": 10,
            "status": "completed",
            "completedAt": "2026-09-06T04:00:00Z"
        }
    }
    env = normalize_codex_notification(
        method="turn/completed",
        params=params,
        project_id="proj_codex"
    )
    assert env is not None
    assert env.type == "turn_completed"
    assert env.payload["turn_id"] == 10
    assert env.payload["status"] == "completed"
    assert env.payload["completed_at"] == "2026-09-06T04:00:00Z"

