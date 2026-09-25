import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, AliasChoices, model_validator

from backend.services.event_service import EventEnvelope


class JsonRpcErrorObj(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class JsonRpcError(Exception):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        err: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            err["data"] = self.data
        return err


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Union[Dict[str, Any], List[Any], BaseModel]] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int, None]
    result: Optional[Any] = None
    error: Optional[Union[JsonRpcErrorObj, Dict[str, Any]]] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class JsonRpcNotification(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# --- Codex App-Server Request Parameter Schemas ---

class InitializeParams(BaseModel):
    client_info: Optional[Dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("clientInfo", "client_info"),
        serialization_alias="clientInfo"
    )
    capabilities: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ThreadCreateParams(BaseModel):
    workspace_root: str = Field(
        validation_alias=AliasChoices("workspaceRoot", "workspace_root"),
        serialization_alias="workspaceRoot"
    )

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ThreadResumeParams(BaseModel):
    thread_id: str = Field(
        validation_alias=AliasChoices("threadId", "thread_id"),
        serialization_alias="threadId"
    )

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ThreadStartParams(BaseModel):
    cwd: Optional[str] = None
    model: Optional[str] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class TurnStartParams(BaseModel):
    thread_id: str = Field(
        validation_alias=AliasChoices("threadId", "thread_id"),
        serialization_alias="threadId"
    )
    prompt: Optional[str] = None
    input: Optional[List[Dict[str, Any]]] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("reasoningEffort", "reasoning_effort", "effort"),
        serialization_alias="reasoningEffort"
    )
    effort: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("effort", "reasoningEffort", "reasoning_effort"),
        serialization_alias="effort"
    )
    workspace_root: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("workspaceRoot", "workspace_root"),
        serialization_alias="workspaceRoot"
    )
    cwd: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("cwd", "workspaceRoot"),
        serialization_alias="cwd"
    )

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _ensure_input_and_prompt(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            p = data.get("prompt")
            inp = data.get("input")
            if p and not inp:
                data["input"] = [{"type": "text", "text": p}]
            elif inp and not p:
                if isinstance(inp, list) and len(inp) > 0 and isinstance(inp[0], dict):
                    data["prompt"] = inp[0].get("text", "")
            eff = data.get("effort") or data.get("reasoningEffort") or data.get("reasoning_effort")
            if eff:
                data["effort"] = eff
                data["reasoning_effort"] = eff
                data["reasoningEffort"] = eff
        return data


class TurnSteerParams(BaseModel):
    thread_id: str = Field(
        validation_alias=AliasChoices("threadId", "thread_id"),
        serialization_alias="threadId"
    )
    expected_turn_id: str = Field(
        validation_alias=AliasChoices("expectedTurnId", "expected_turn_id"),
        serialization_alias="expectedTurnId"
    )
    turn_id: Optional[Union[int, str]] = Field(
        default=None,
        validation_alias=AliasChoices("turnId", "turn_id"),
        serialization_alias="turnId"
    )
    instruction: Optional[str] = None
    input: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            tid = data.get("turnId") if "turnId" in data else data.get("turn_id")
            etid = data.get("expectedTurnId") if "expectedTurnId" in data else data.get("expected_turn_id")
            if etid is None and tid is not None:
                data["expected_turn_id"] = str(tid)
            elif etid is not None and tid is None:
                data["turn_id"] = etid
            inst = data.get("instruction")
            inp = data.get("input")
            if inst and not inp:
                data["input"] = [{"type": "text", "text": inst}]
            elif inp and not inst:
                if isinstance(inp, list) and len(inp) > 0 and isinstance(inp[0], dict):
                    data["instruction"] = inp[0].get("text", "")
        return data


class TurnInterruptParams(BaseModel):
    thread_id: str = Field(
        validation_alias=AliasChoices("threadId", "thread_id"),
        serialization_alias="threadId"
    )
    turn_id: str = Field(
        validation_alias=AliasChoices("turnId", "turn_id"),
        serialization_alias="turnId"
    )

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            tid = data.get("turnId") if "turnId" in data else data.get("turn_id")
            if tid is not None:
                data["turn_id"] = str(tid)
        return data


class ApprovalRespondParams(BaseModel):
    tool_call_id: str = Field(
        validation_alias=AliasChoices("toolCallId", "tool_call_id"),
        serialization_alias="toolCallId"
    )
    approved: bool
    feedback: Optional[str] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)



METHOD_PARAMS_SCHEMAS: Dict[str, type[BaseModel]] = {
    "initialize": InitializeParams,
    "thread/start": ThreadStartParams,
    "thread/create": ThreadCreateParams,
    "thread/resume": ThreadResumeParams,
    "turn/start": TurnStartParams,
    "turn/steer": TurnSteerParams,
    "turn/interrupt": TurnInterruptParams,
    "approval/respond": ApprovalRespondParams,
}


def _serialize_params(params: Optional[Union[Dict[str, Any], BaseModel]]) -> Optional[Dict[str, Any]]:
    if params is None:
        return None
    if isinstance(params, BaseModel):
        return params.model_dump(by_alias=True, exclude_none=True)
    return params


class Protocol:
    @staticmethod
    def build_request(
        method: str,
        params: Optional[Union[Dict[str, Any], BaseModel]] = None,
        msg_id: Optional[Union[str, int]] = None
    ) -> str:
        serialized_params = _serialize_params(params)
        msg: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": msg_id if msg_id is not None else str(uuid4())
        }
        if serialized_params is not None:
            msg["params"] = serialized_params
        return json.dumps(msg)

    @staticmethod
    def build_notification(
        method: str,
        params: Optional[Union[Dict[str, Any], BaseModel]] = None
    ) -> str:
        serialized_params = _serialize_params(params)
        msg: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method
        }
        if serialized_params is not None:
            msg["params"] = serialized_params
        return json.dumps(msg)

    @staticmethod
    def build_response(msg_id: Union[str, int, None], result: Any) -> str:
        msg = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result
        }
        return json.dumps(msg)

    @staticmethod
    def build_error(
        msg_id: Union[str, int, None],
        code: int,
        message: str,
        data: Optional[Any] = None
    ) -> str:
        error_obj: Dict[str, Any] = {
            "code": code,
            "message": message
        }
        if data is not None:
            error_obj["data"] = data

        msg = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": error_obj
        }
        return json.dumps(msg)

    @staticmethod
    def parse_message(raw_msg: str) -> Dict[str, Any]:
        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            raise JsonRpcError(JsonRpcError.PARSE_ERROR, "Parse error")

        if not isinstance(msg, dict):
            raise JsonRpcError(JsonRpcError.INVALID_REQUEST, "Invalid Request")

        if msg.get("jsonrpc") != "2.0":
            raise JsonRpcError(
                JsonRpcError.INVALID_REQUEST,
                "Invalid Request",
                data={"reason": "Missing or invalid jsonrpc version"}
            )

        if "id" in msg and msg["id"] is not None and not isinstance(msg["id"], (str, int)):
            raise JsonRpcError(
                JsonRpcError.INVALID_REQUEST,
                "Invalid Request",
                data={"reason": "id must be a string, integer, or null"}
            )

        if "error" in msg:
            err = msg["error"]
            if not isinstance(err, dict) or "code" not in err or "message" not in err:
                raise JsonRpcError(
                    JsonRpcError.INVALID_REQUEST,
                    "Invalid Request",
                    data={"reason": "Error object must contain code and message"}
                )

        return msg

    @staticmethod
    def validate_request_params(method: str, params: Any) -> BaseModel:
        schema = METHOD_PARAMS_SCHEMAS.get(method)
        if not schema:
            raise JsonRpcError(JsonRpcError.METHOD_NOT_FOUND, f"Method not found: {method}")
        try:
            if isinstance(params, dict):
                return schema(**params)
            elif isinstance(params, schema):
                return params
            else:
                raise ValueError("Params must be a dictionary or schema instance")
        except Exception as e:
            raise JsonRpcError(JsonRpcError.INVALID_PARAMS, f"Invalid params for {method}: {e}")

    # Typed request builders for Codex App-Server
    @staticmethod
    def build_initialize_request(
        client_info: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        msg_id: Optional[Union[str, int]] = None
    ) -> str:
        params = InitializeParams(client_info=client_info, capabilities=capabilities)
        return Protocol.build_request("initialize", params, msg_id=msg_id)

    @staticmethod
    def build_thread_start_request(
        cwd: Optional[str] = None,
        model: Optional[str] = None,
        msg_id: Optional[Union[str, int]] = None,
        **extra: Any
    ) -> str:
        params = ThreadStartParams(cwd=cwd, model=model, **extra)
        return Protocol.build_request("thread/start", params, msg_id=msg_id)

    @staticmethod
    def build_thread_create_request(
        workspace_root: str,
        msg_id: Optional[Union[str, int]] = None,
        **extra: Any
    ) -> str:
        params_dict: Dict[str, Any] = {"workspace_root": workspace_root, **extra}
        params = ThreadCreateParams(**params_dict)
        return Protocol.build_request("thread/create", params, msg_id=msg_id)

    @staticmethod
    def build_thread_resume_request(
        thread_id: str,
        msg_id: Optional[Union[str, int]] = None
    ) -> str:
        params = ThreadResumeParams(thread_id=thread_id)
        return Protocol.build_request("thread/resume", params, msg_id=msg_id)

    @staticmethod
    def build_turn_start_request(
        thread_id: str,
        prompt: str,
        model: str = "gpt-4o",
        reasoning_effort: Optional[str] = None,
        workspace_root: Optional[str] = None,
        cwd: Optional[str] = None,
        msg_id: Optional[Union[str, int]] = None,
        input: Optional[List[Dict[str, Any]]] = None,
        effort: Optional[str] = None,
        **extra: Any
    ) -> str:
        eff_ws = workspace_root or cwd
        eff_input = input or [{"type": "text", "text": prompt}]
        eff_effort = effort or reasoning_effort
        params = TurnStartParams(
            thread_id=thread_id,
            prompt=prompt,
            input=eff_input,
            model=model,
            reasoning_effort=eff_effort,
            effort=eff_effort,
            workspace_root=eff_ws,
            cwd=cwd or eff_ws,
            **extra
        )
        return Protocol.build_request("turn/start", params, msg_id=msg_id)

    @staticmethod
    def build_turn_steer_request(
        thread_id: str,
        turn_id: Union[int, str],
        instruction: str,
        input: Optional[List[Dict[str, Any]]] = None,
        expected_turn_id: Optional[str] = None,
        msg_id: Optional[Union[str, int]] = None,
        **extra: Any
    ) -> str:
        eff_input = input or [{"type": "text", "text": instruction}]
        eff_expected_turn_id = expected_turn_id or str(turn_id)
        params = TurnSteerParams(
            thread_id=thread_id,
            turn_id=turn_id,
            expected_turn_id=eff_expected_turn_id,
            instruction=instruction,
            input=eff_input,
            **extra
        )
        return Protocol.build_request("turn/steer", params, msg_id=msg_id)

    @staticmethod
    def build_turn_interrupt_request(
        thread_id: str,
        turn_id: Union[int, str],
        msg_id: Optional[Union[str, int]] = None
    ) -> str:
        params = TurnInterruptParams(
            thread_id=thread_id,
            turn_id=str(turn_id)
        )
        return Protocol.build_request("turn/interrupt", params, msg_id=msg_id)

    @staticmethod
    def build_approval_respond_request(
        tool_call_id: str,
        approved: bool,
        feedback: Optional[str] = None,
        msg_id: Optional[Union[str, int]] = None
    ) -> str:
        params = ApprovalRespondParams(
            tool_call_id=tool_call_id,
            approved=approved,
            feedback=feedback
        )
        return Protocol.build_request("approval/respond", params, msg_id=msg_id)

    @staticmethod
    def normalize_notification(
        method: str,
        params: dict,
        project_id: str = "default",
        thread_id: str = "",
        turn_id: Optional[int] = None
    ) -> Optional[EventEnvelope]:
        return normalize_codex_notification(method, params, project_id, thread_id, turn_id)


def normalize_codex_notification(
    method: str,
    params: dict,
    project_id: str = "default",
    thread_id: str = "",
    turn_id: Optional[int] = None
) -> Optional[EventEnvelope]:
    """
    Translates Codex App-Server JSON-RPC notifications into normalized EventEnvelopes.
    Supported mappings:
      - turn/reasoningDelta -> 'reasoning'
      - item/agentMessage/delta or turn/messageDelta -> 'agent_message' (streaming)
      - item/started (agentMessage) -> 'agent_message' (streaming started)
      - item/completed (agentMessage) -> 'agent_message' (completed)
      - item/completed (commandExecution) or turn/commandExecution -> 'command'
      - turn/fileModified -> 'file_change'
      - turn/toolApprovalRequested or tool_approval_requested -> 'approval_requested'
      - turn/started -> 'turn_started'
      - turn/completed -> 'turn_completed'
    """
    turn_obj = params.get("turn") if isinstance(params.get("turn"), dict) else {}
    item_obj = params.get("item") if isinstance(params.get("item"), dict) else {}

    eff_thread_id = (
        thread_id
        or params.get("threadId")
        or params.get("thread_id")
        or turn_obj.get("threadId")
        or turn_obj.get("thread_id")
        or ""
    )
    eff_project_id = project_id or params.get("projectId") or params.get("project_id") or "default"
    eff_turn_id = (
        turn_id
        if turn_id is not None
        else (
            turn_obj.get("id")
            or params.get("turnId")
            or params.get("turn_id")
        )
    )

    # 1. Reasoning Delta
    if method in ("turn/reasoningDelta", "item/reasoningDelta"):
        chunk = (
            params.get("chunk")
            or params.get("delta")
            or params.get("text")
            or params.get("reasoning")
            or params.get("content")
            or ""
        )
        sequence = params.get("sequence") or params.get("seq") or params.get("index") or 0
        payload = {
            "chunk": chunk,
            "reasoning": chunk,
            "sequence": sequence,
            "summary": params.get("summary") or chunk,
        }
        if eff_turn_id is not None:
            payload["turn_id"] = eff_turn_id
            payload["turnId"] = eff_turn_id
        return EventEnvelope(
            project_id=eff_project_id,
            thread_id=eff_thread_id,
            type="reasoning",
            payload=payload
        )

    # 2. Message Delta (v2 item/agentMessage/delta or v1 turn/messageDelta)
    elif method in ("item/agentMessage/delta", "turn/messageDelta"):
        text = (
            params.get("delta")
            or params.get("text")
            or params.get("chunk")
            or params.get("content")
            or ""
        )
        item_id = (
            params.get("itemId")
            or params.get("id")
            or params.get("item_id")
            or item_obj.get("id")
        )
        payload = {
            "text": text,
            "chunk": text,
            "content": text,
            "is_streaming": True,
        }
        if item_id:
            payload["item_id"] = item_id
            payload["itemId"] = item_id
        turn_id_val = params.get("turnId") or params.get("turn_id") or eff_turn_id
        if turn_id_val is not None:
            payload["turn_id"] = turn_id_val
            payload["turnId"] = turn_id_val
        return EventEnvelope(
            project_id=eff_project_id,
            thread_id=eff_thread_id,
            type="agent_message",
            payload=payload
        )

    # 3. Item Started (v2 item/started)
    elif method == "item/started":
        item_type = item_obj.get("type")
        item_id = item_obj.get("id") or params.get("itemId") or params.get("id") or params.get("item_id")
        turn_id_val = params.get("turnId") or params.get("turn_id") or eff_turn_id

        if item_type == "agentMessage":
            payload = {
                "text": "",
                "chunk": "",
                "content": "",
                "is_streaming": True,
            }
            if item_id:
                payload["item_id"] = item_id
                payload["itemId"] = item_id
            if turn_id_val is not None:
                payload["turn_id"] = turn_id_val
                payload["turnId"] = turn_id_val
            return EventEnvelope(
                project_id=eff_project_id,
                thread_id=eff_thread_id,
                type="agent_message",
                payload=payload
            )

    # 4. Item Completed (v2 item/completed)
    elif method == "item/completed":
        item_type = item_obj.get("type")
        item_id = item_obj.get("id") or params.get("itemId") or params.get("id") or params.get("item_id")
        turn_id_val = params.get("turnId") or params.get("turn_id") or eff_turn_id

        if item_type == "agentMessage":
            text = item_obj.get("text") or item_obj.get("content") or ""
            payload = {
                "text": text,
                "content": text,
                "chunk": text,
                "item_id": item_id,
                "itemId": item_id,
                "is_streaming": False,
            }
            if turn_id_val is not None:
                payload["turn_id"] = turn_id_val
                payload["turnId"] = turn_id_val
            return EventEnvelope(
                project_id=eff_project_id,
                thread_id=eff_thread_id,
                type="agent_message",
                payload=payload
            )

        elif item_type in ("commandExecution", "command"):
            command = item_obj.get("command") or params.get("command") or ""
            exit_code = (
                item_obj.get("exit_code") if "exit_code" in item_obj
                else item_obj.get("exitCode", params.get("exit_code", params.get("exitCode", 0)))
            )
            stdout = item_obj.get("stdout") or item_obj.get("stdout_chunk") or params.get("stdout") or params.get("stdout_chunk") or ""
            stderr = item_obj.get("stderr") or item_obj.get("stderr_chunk") or params.get("stderr") or params.get("stderr_chunk") or ""
            chunk = item_obj.get("chunk") or params.get("chunk") or stdout or stderr or ""
            status = item_obj.get("status") or params.get("status") or ("completed" if exit_code == 0 else "failed")
            payload = {
                "command": command,
                "exit_code": exit_code,
                "exitCode": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "chunk": chunk,
                "status": status,
            }
            if item_id:
                payload["item_id"] = item_id
                payload["itemId"] = item_id
            if turn_id_val is not None:
                payload["turn_id"] = turn_id_val
                payload["turnId"] = turn_id_val
            if "working_directory" in item_obj or "workingDirectory" in item_obj or "working_directory" in params or "workingDirectory" in params:
                payload["working_directory"] = item_obj.get("working_directory") or item_obj.get("workingDirectory") or params.get("working_directory") or params.get("workingDirectory")
            if "duration_ms" in item_obj or "durationMs" in item_obj or "duration_ms" in params or "durationMs" in params:
                payload["duration_ms"] = item_obj.get("duration_ms") or item_obj.get("durationMs") or params.get("duration_ms") or params.get("durationMs")
            return EventEnvelope(
                project_id=eff_project_id,
                thread_id=eff_thread_id,
                type="command",
                payload=payload
            )

        elif item_type in ("fileChange", "fileModified"):
            path = item_obj.get("path") or item_obj.get("file_path") or item_obj.get("filePath") or params.get("path") or ""
            additions = item_obj.get("additions") if "additions" in item_obj else item_obj.get("total_additions", params.get("additions", 0))
            deletions = item_obj.get("deletions") if "deletions" in item_obj else item_obj.get("total_deletions", params.get("deletions", 0))
            diff = item_obj.get("diff") or item_obj.get("diff_text") or item_obj.get("diffText") or params.get("diff") or ""
            payload = {
                "path": path,
                "additions": additions,
                "deletions": deletions,
                "diff": diff,
                "diff_text": diff,
                "total_additions": additions,
                "total_deletions": deletions,
                "files": [
                    {
                        "path": path,
                        "additions": additions,
                        "deletions": deletions,
                        "diff": diff
                    }
                ] if path else item_obj.get("files", params.get("files", [])),
                "summary": item_obj.get("summary") or params.get("summary") or (f"Modified {path}" if path else "Applied file modifications")
            }
            if item_id:
                payload["item_id"] = item_id
                payload["itemId"] = item_id
            if turn_id_val is not None:
                payload["turn_id"] = turn_id_val
                payload["turnId"] = turn_id_val
            return EventEnvelope(
                project_id=eff_project_id,
                thread_id=eff_thread_id,
                type="file_change",
                payload=payload
            )

    # 5. Command Execution (v1 turn/commandExecution)
    elif method in ("turn/commandExecution", "commandExecution", "turn/command_execution"):
        command = params.get("command") or ""
        exit_code = params.get("exit_code") if "exit_code" in params else params.get("exitCode", 0)
        stdout = params.get("stdout") or params.get("stdout_chunk") or ""
        stderr = params.get("stderr") or params.get("stderr_chunk") or ""
        chunk = params.get("chunk") or stdout or stderr or ""
        payload = {
            "command": command,
            "exit_code": exit_code,
            "exitCode": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "chunk": chunk,
            "status": params.get("status") or ("completed" if exit_code == 0 else "failed")
        }
        item_id = params.get("item_id") or params.get("itemId") or params.get("id")
        if item_id:
            payload["item_id"] = item_id
            payload["itemId"] = item_id
        if eff_turn_id is not None:
            payload["turn_id"] = eff_turn_id
            payload["turnId"] = eff_turn_id
        if "working_directory" in params or "workingDirectory" in params:
            payload["working_directory"] = params.get("working_directory") or params.get("workingDirectory")
        if "duration_ms" in params or "durationMs" in params:
            payload["duration_ms"] = params.get("duration_ms") or params.get("durationMs")
        return EventEnvelope(
            project_id=eff_project_id,
            thread_id=eff_thread_id,
            type="command",
            payload=payload
        )

    # 6. File Modified (v1 turn/fileModified)
    elif method in ("turn/fileModified", "fileModified", "turn/file_modified"):
        path = params.get("path") or params.get("file_path") or params.get("filePath") or ""
        additions = params.get("additions") if "additions" in params else params.get("total_additions", 0)
        deletions = params.get("deletions") if "deletions" in params else params.get("total_deletions", 0)
        diff = params.get("diff") or params.get("diff_text") or params.get("diffText") or ""
        payload = {
            "path": path,
            "additions": additions,
            "deletions": deletions,
            "diff": diff,
            "diff_text": diff,
            "total_additions": additions,
            "total_deletions": deletions,
            "files": [
                {
                    "path": path,
                    "additions": additions,
                    "deletions": deletions,
                    "diff": diff
                }
            ] if path else params.get("files", []),
            "summary": params.get("summary") or (f"Modified {path}" if path else "Applied file modifications")
        }
        item_id = params.get("item_id") or params.get("itemId") or params.get("id")
        if item_id:
            payload["item_id"] = item_id
            payload["itemId"] = item_id
        if eff_turn_id is not None:
            payload["turn_id"] = eff_turn_id
            payload["turnId"] = eff_turn_id
        return EventEnvelope(
            project_id=eff_project_id,
            thread_id=eff_thread_id,
            type="file_change",
            payload=payload
        )

    # 7. Tool Approval Requested
    elif method in (
        "turn/toolApprovalRequested",
        "tool_approval_requested",
        "turn/tool_approval_requested",
        "toolApprovalRequested",
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
    ):
        tool_call_id = (
            params.get("toolCallId")
            or params.get("tool_call_id")
            or params.get("approval_id")
            or params.get("id")
            or ""
        )
        command = params.get("command") or ""
        risk_level = (
            params.get("riskLevel")
            or params.get("risk_level")
            or params.get("risk")
            or "medium"
        )
        consequence = params.get("consequence") or "Requires operator authorization"
        payload = {
            "toolCallId": tool_call_id,
            "tool_call_id": tool_call_id,
            "approval_id": tool_call_id,
            "approvalId": tool_call_id,
            "command": command,
            "riskLevel": risk_level,
            "risk_level": risk_level,
            "risk": risk_level,
            "consequence": consequence,
            "category": params.get("category", "command"),
            "title": params.get("title") or command or "Approval Request",
            "reason": params.get("reason") or "Safety policy check"
        }
        if eff_turn_id is not None:
            payload["turn_id"] = eff_turn_id
            payload["turnId"] = eff_turn_id
        return EventEnvelope(
            project_id=eff_project_id,
            thread_id=eff_thread_id,
            type="approval_requested",
            payload=payload
        )

    # 8. Turn Started (v2 turn/started)
    elif method in ("turn/started", "turnStarted"):
        tid = turn_obj.get("id") or params.get("turnId") or params.get("turn_id") or eff_turn_id
        payload = {
            "status": "active",
        }
        if tid is not None:
            payload["turn_id"] = tid
            payload["turnId"] = tid
        return EventEnvelope(
            project_id=eff_project_id,
            thread_id=eff_thread_id,
            type="turn_started",
            payload=payload
        )

    # 9. Turn Completed
    elif method in ("turn/completed", "turn/complete", "turnCompleted"):
        tid = turn_obj.get("id") or params.get("turnId") or params.get("turn_id") or eff_turn_id
        status = params.get("status") or turn_obj.get("status") or "completed"
        completed_at = (
            params.get("completed_at")
            or params.get("completedAt")
            or turn_obj.get("completed_at")
            or turn_obj.get("completedAt")
            or datetime.now(timezone.utc).isoformat()
        )
        payload = {
            "status": status,
            "completed_at": completed_at,
            "completedAt": completed_at
        }
        if tid is not None:
            payload["turn_id"] = tid
            payload["turnId"] = tid
        if "summary" in params or "summary" in turn_obj:
            payload["summary"] = params.get("summary") or turn_obj.get("summary")
        return EventEnvelope(
            project_id=eff_project_id,
            thread_id=eff_thread_id,
            type="turn_completed",
            payload=payload
        )

    return None

