import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from backend.models.codex import ToolApproval, SubAgent, Thread
from backend.services.event_service import broker, EventEnvelope

# Risk Level Constants
RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"

# Governance Profiles
PROFILE_MANAGED = "managed"
PROFILE_STRICT = "strict"
PROFILE_PERMISSIVE = "permissive"

# Concurrency limits
MAX_ACTIVE_SUBAGENTS = 6

ACTIVE_STATUSES = {"active", "running", "pending", "busy", "in_progress"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "stopped", "terminated"}


def evaluate_tool_risk(
    command: str,
    tool_name: Optional[str] = None,
    profile: str = PROFILE_MANAGED
) -> Tuple[str, bool, str]:
    """
    Evaluates risk tier and approval requirement for a tool call or shell command.
    
    Risk Tiers:
    - LOW: read-only file inspection, git status, search -> auto-approved in managed profile.
    - MEDIUM: file modification, git add/commit, workspace file creation -> requires approval in strict profile.
    - HIGH: shell execution, external npm/pip installs, destructive commands, rm/del -> strictly requires human approval.
    - CRITICAL: git push, branch deletion, credential access, external network writes -> strictly requires human approval.

    Returns:
        Tuple[risk_level (str), requires_approval (bool), consequence (str)]
    """
    cmd_clean = (command or "").strip()
    tool = (tool_name or "").lower().strip()

    # 1. CRITICAL Risk Checks
    # -------------------------------------------------------------
    # Git push or branch deletion
    if re.search(r'\bgit\s+(push|branch\s+(-[dD]|--delete))\b', cmd_clean, re.IGNORECASE):
        risk = RISK_CRITICAL
        consequence = "Modifies remote repository history or permanently deletes git branches."
        requires_approval = True
        return risk, requires_approval, consequence

    # Credential / secret access
    secret_patterns = r'(\.env(\.[a-zA-Z0-9_-]+)?|id_rsa|id_ed25519|\.pem|\.key|credentials\.json|vault|shadow|aws/credentials|\btoken_secret\b|\bsecret_key\b|\bpasswords?\b)'
    if re.search(secret_patterns, cmd_clean, re.IGNORECASE):
        risk = RISK_CRITICAL
        consequence = "Accesses or exposes sensitive credentials, secrets, or private keys."
        requires_approval = True
        return risk, requires_approval, consequence

    # External network writes / mutations / raw outbound connections
    if re.search(r'\bcurl\b.*(-X\s*(POST|PUT|DELETE|PATCH)|-d\b|--data\b|--data-raw\b|-F\b)', cmd_clean, re.IGNORECASE):
        risk = RISK_CRITICAL
        consequence = "Performs outbound HTTP write/mutation request to external network."
        requires_approval = True
        return risk, requires_approval, consequence

    if re.search(r'\bwget\b.*--post-(data|file)\b', cmd_clean, re.IGNORECASE):
        risk = RISK_CRITICAL
        consequence = "Posts data to external network via wget."
        requires_approval = True
        return risk, requires_approval, consequence

    if re.search(r'\b(ssh|scp|rsync|nc|ncat|telnet)\b', cmd_clean, re.IGNORECASE):
        risk = RISK_CRITICAL
        consequence = "Establishes raw outbound network/tunnel connection."
        requires_approval = True
        return risk, requires_approval, consequence

    # 2. HIGH Risk Checks
    # -------------------------------------------------------------
    # Destructive file / process commands
    if re.search(r'\b(rm\s|rmdir\s|del\s|erase\s|git\s+reset\s+--hard|git\s+clean\s+-[a-zA-Z]*f|kill\s|pkill\s|taskkill\s|drop\s+table|truncate\s+table)', cmd_clean, re.IGNORECASE):
        risk = RISK_HIGH
        consequence = "Destructive command that permanently removes files, resets workspace, or kills processes."
        requires_approval = True
        return risk, requires_approval, consequence

    # External package installations
    if re.search(r'\b(npm\s+(install|i|add|uninstall|update)|pip\s+(install|uninstall)|yarn\s+(add|remove)|pnpm\s+(add|install|remove)|cargo\s+(install|add)|brew\s+install|apt-get\s+install|gem\s+install|pipx)\b', cmd_clean, re.IGNORECASE):
        risk = RISK_HIGH
        consequence = "Installs or removes external packages/dependencies from external repositories."
        requires_approval = True
        return risk, requires_approval, consequence

    # Direct shell invocation / code execution
    if tool in {"run_command", "shell_exec", "terminal"} or re.search(r'^(powershell|pwsh|cmd(\.exe)?|bash|sh|zsh)\b', cmd_clean, re.IGNORECASE) or re.search(r'\b(python\s+-c|node\s+-e)\b', cmd_clean, re.IGNORECASE):
        risk = RISK_HIGH
        consequence = "Executes arbitrary system shell command or subprocess."
        requires_approval = True
        return risk, requires_approval, consequence

    # 3. MEDIUM Risk Checks
    # -------------------------------------------------------------
    # File modification / workspace creation / git staging
    if tool in {"write_to_file", "replace_file_content", "edit_file", "create_file"}:
        risk = RISK_MEDIUM
        consequence = "Modifies or creates files in the workspace."
        requires_approval = (profile == PROFILE_STRICT)
        return risk, requires_approval, consequence

    if re.search(r'\bgit\s+(add|commit|stash|checkout\s+-b|switch\s+-c|merge)\b', cmd_clean, re.IGNORECASE):
        risk = RISK_MEDIUM
        consequence = "Modifies git staging, commits, or branch workspace state."
        requires_approval = (profile == PROFILE_STRICT)
        return risk, requires_approval, consequence

    if re.search(r'\b(touch|mkdir|cp\s|copy\s|mv\s|move\s)\b', cmd_clean, re.IGNORECASE) or re.search(r'(>|>>)\s*[^\s]+', cmd_clean):
        risk = RISK_MEDIUM
        consequence = "Modifies workspace filesystem structure or creates files."
        requires_approval = (profile == PROFILE_STRICT)
        return risk, requires_approval, consequence

    # 4. LOW Risk Checks
    # -------------------------------------------------------------
    # Read-only inspection / search / git status
    if tool in {"view_file", "list_dir", "grep_search", "find_by_name", "read_url_content"}:
        risk = RISK_LOW
        consequence = "Read-only inspection of repository or workspace."
        requires_approval = False
        return risk, requires_approval, consequence

    if re.search(r'^\s*git\s+(status|diff|log|show|branch(\s+--list)?|check-ignore)\b', cmd_clean, re.IGNORECASE):
        risk = RISK_LOW
        consequence = "Read-only git status or history inspection."
        requires_approval = False
        return risk, requires_approval, consequence

    if re.search(r'^\s*(grep|rg|ripgrep|find|fd|locate|cat|head|tail|type|less|more|ls|dir|tree|pwd|stat|which|where)\b', cmd_clean, re.IGNORECASE):
        risk = RISK_LOW
        consequence = "Read-only workspace file or directory inspection."
        requires_approval = False
        return risk, requires_approval, consequence

    # Fallback: Default to HIGH for unrecognized custom shell commands for security
    risk = RISK_HIGH
    consequence = f"Unclassified command execution: '{cmd_clean}'."
    requires_approval = True
    return risk, requires_approval, consequence


# Pending approval RPC trackers: maps tool_call_id and approval_id -> RPC dict
_pending_rpc_registry: Dict[str, Dict[str, Any]] = {}


def register_pending_rpc(
    tool_call_id: str,
    resp_id: Any,
    worker: Any,
    approval_id: Optional[str] = None
):
    """
    Registers a pending tool approval RPC mapping so resolution can dispatch
    the JSON-RPC response back to the Codex App-Server worker process.
    """
    entry = {
        "tool_call_id": tool_call_id,
        "resp_id": resp_id,
        "worker": worker,
        "approval_id": approval_id
    }
    if tool_call_id:
        _pending_rpc_registry[tool_call_id] = entry
    if approval_id:
        _pending_rpc_registry[approval_id] = entry


def get_pending_rpc(identifier: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves pending RPC tracking data by approval_id or tool_call_id.
    """
    return _pending_rpc_registry.get(identifier)


def pop_pending_rpc(identifier: str) -> Optional[Dict[str, Any]]:
    """
    Pops and unregisters pending RPC tracking data by approval_id or tool_call_id.
    """
    entry = _pending_rpc_registry.pop(identifier, None)
    if entry:
        for key in (entry.get("tool_call_id"), entry.get("approval_id")):
            if key and key in _pending_rpc_registry:
                _pending_rpc_registry.pop(key, None)
    return entry


def dispatch_approval_rpc(
    resp_id: Any,
    worker: Any,
    approved: bool,
    feedback: Optional[str] = None
):
    """
    Dispatches the JSON-RPC response packet back to the Codex App-Server worker:
    {"jsonrpc": "2.0", "id": "<resp_id>", "result": {"approved": true/false}}
    """
    if not worker or resp_id is None:
        return

    response_payload = {
        "jsonrpc": "2.0",
        "id": resp_id,
        "result": {"approved": approved}
    }
    if feedback:
        response_payload["result"]["feedback"] = feedback

    msg_str = json.dumps(response_payload)
    if hasattr(worker, "send_raw"):
        try:
            loop = asyncio.get_running_loop()
            res = worker.send_raw(msg_str)
            if asyncio.iscoroutine(res):
                loop.create_task(res)
        except RuntimeError:
            try:
                res = worker.send_raw(msg_str)
                if asyncio.iscoroutine(res):
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(res)
                    loop.close()
            except Exception:
                pass
    elif getattr(worker, "process", None) and worker.process.stdin and not worker.process.stdin.is_closing():
        worker.process.stdin.write((msg_str + "\n").encode("utf-8"))


def create_approval_request(
    thread_id: str,
    tool_call_id: str,
    command: str,
    risk_level: str,
    consequence: str,
    db: Session
) -> ToolApproval:
    """
    Creates and records a pending tool approval request in the database and broadcasts an event.
    """
    approval = ToolApproval(
        id=f"appr_{uuid.uuid4().hex[:12]}",
        thread_id=thread_id,
        tool_call_id=tool_call_id,
        command=command,
        risk_level=risk_level,
        consequence=consequence,
        status="pending",
        created_at=datetime.now(timezone.utc),
        resolved_at=None
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    # Publish event
    project_id = "default"
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread and thread.project_id:
        project_id = thread.project_id

    event_payload = {
        "approval_id": approval.id,
        "approvalId": approval.id,
        "tool_call_id": approval.tool_call_id,
        "toolCallId": approval.tool_call_id,
        "command": approval.command,
        "risk_level": approval.risk_level,
        "riskLevel": approval.risk_level,
        "consequence": approval.consequence,
        "status": approval.status,
        "created_at": approval.created_at.isoformat() if approval.created_at else None
    }

    # Broadcast both approval_requested (CAS-03 spec) and approval.requested (legacy compatibility)
    broker.publish_event(EventEnvelope(
        project_id=project_id,
        thread_id=thread_id,
        type="approval_requested",
        payload=event_payload
    ))
    broker.publish_event(EventEnvelope(
        project_id=project_id,
        thread_id=thread_id,
        type="approval.requested",
        payload=event_payload
    ))

    return approval


def resolve_approval(
    approval_id: str,
    approved: bool,
    db: Session,
    feedback: Optional[str] = None
) -> ToolApproval:
    """
    Resolves an approval request, updates status and timestamp, broadcasts resolution events,
    and dispatches JSON-RPC response back to the Codex App-Server if a pending worker request exists.
    """
    approval = db.query(ToolApproval).filter(ToolApproval.id == approval_id).first()
    if not approval:
        raise ValueError(f"Approval request '{approval_id}' not found")

    approval.status = "approved" if approved else "declined"
    approval.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(approval)

    project_id = "default"
    if approval.thread and approval.thread.project_id:
        project_id = approval.thread.project_id

    event_payload = {
        "approval_id": approval.id,
        "approvalId": approval.id,
        "tool_call_id": approval.tool_call_id,
        "toolCallId": approval.tool_call_id,
        "approved": approved,
        "status": approval.status,
        "feedback": feedback,
        "resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None
    }

    # Broadcast both approval_resolved and approval.resolved
    broker.publish_event(EventEnvelope(
        project_id=project_id,
        thread_id=approval.thread_id,
        type="approval_resolved",
        payload=event_payload
    ))
    broker.publish_event(EventEnvelope(
        project_id=project_id,
        thread_id=approval.thread_id,
        type="approval.resolved",
        payload=event_payload
    ))

    # Dispatch JSON-RPC response packet back to Codex App-Server if pending RPC is tracked
    rpc_entry = pop_pending_rpc(approval.id) or pop_pending_rpc(approval.tool_call_id)
    if rpc_entry and rpc_entry.get("resp_id") is not None:
        dispatch_approval_rpc(
            resp_id=rpc_entry["resp_id"],
            worker=rpc_entry.get("worker"),
            approved=approved,
            feedback=feedback
        )

    return approval


def list_pending_approvals(db: Session, thread_id: Optional[str] = None) -> List[ToolApproval]:
    """
    Lists all pending tool approval requests, optionally filtered by thread_id.
    """
    query = db.query(ToolApproval).filter(ToolApproval.status == "pending")
    if thread_id:
        query = query.filter(ToolApproval.thread_id == thread_id)
    return query.order_by(ToolApproval.created_at.desc()).all()


def register_subagent(
    thread_id: str,
    parent_thread_id: Optional[str],
    name: str,
    role: str,
    db: Session,
    max_concurrency: int = MAX_ACTIVE_SUBAGENTS
) -> SubAgent:
    """
    Registers a new subagent for a thread, enforcing the active subagent concurrency limit (default: 6).
    """
    active_count = db.query(SubAgent).filter(
        SubAgent.thread_id == thread_id,
        SubAgent.status.in_(ACTIVE_STATUSES)
    ).count()

    if active_count >= max_concurrency:
        raise ValueError(f"Maximum active subagent concurrency reached ({max_concurrency})")

    subagent = SubAgent(
        id=f"sub_{uuid.uuid4().hex[:12]}",
        thread_id=thread_id,
        parent_thread_id=parent_thread_id,
        name=name,
        role=role,
        status="active",
        progress=0,
        current_action=None,
        created_at=datetime.now(timezone.utc)
    )
    db.add(subagent)
    db.commit()
    db.refresh(subagent)

    project_id = "default"
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread and thread.project_id:
        project_id = thread.project_id

    broker.publish_event(EventEnvelope(
        project_id=project_id,
        thread_id=thread_id,
        type="subagent.registered",
        payload={
            "subagent_id": subagent.id,
            "thread_id": subagent.thread_id,
            "parent_thread_id": subagent.parent_thread_id,
            "name": subagent.name,
            "role": subagent.role,
            "status": subagent.status,
            "progress": subagent.progress,
            "created_at": subagent.created_at.isoformat() if subagent.created_at else None
        }
    ))

    return subagent


def update_subagent_progress(
    subagent_id: str,
    progress: int,
    current_action: Optional[str],
    status: str,
    db: Session
) -> SubAgent:
    """
    Updates the progress, current action, and status of a subagent.
    """
    subagent = db.query(SubAgent).filter(SubAgent.id == subagent_id).first()
    if not subagent:
        raise ValueError(f"Subagent '{subagent_id}' not found")

    subagent.progress = max(0, min(100, progress))
    subagent.status = status
    if current_action is not None:
        subagent.current_action = current_action

    db.commit()
    db.refresh(subagent)

    project_id = "default"
    if subagent.thread and subagent.thread.project_id:
        project_id = subagent.thread.project_id

    broker.publish_event(EventEnvelope(
        project_id=project_id,
        thread_id=subagent.thread_id,
        type="subagent.progress",
        payload={
            "subagent_id": subagent.id,
            "thread_id": subagent.thread_id,
            "progress": subagent.progress,
            "status": subagent.status,
            "current_action": subagent.current_action
        }
    ))

    return subagent


def cancel_pending_approvals_for_thread(
    thread_id: str,
    db: Session,
    reason: str = "Thread or turn interrupted"
) -> List[ToolApproval]:
    """
    Cascades cancellation to all pending tool approvals when a thread or turn is stopped/interrupted.
    Marks approvals as cancelled, records resolved_at, dispatches abort RPC to worker, and broadcasts events.
    """
    pending_approvals = db.query(ToolApproval).filter(
        ToolApproval.thread_id == thread_id,
        ToolApproval.status == "pending"
    ).all()

    cancelled = []
    now = datetime.now(timezone.utc)
    project_id = "default"
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread and thread.project_id:
        project_id = thread.project_id

    for appr in pending_approvals:
        appr.status = "cancelled"
        appr.resolved_at = now
        cancelled.append(appr)

        # Dispatch negative RPC response to worker if pending
        rpc_entry = pop_pending_rpc(appr.id) or pop_pending_rpc(appr.tool_call_id)
        if rpc_entry and rpc_entry.get("resp_id") is not None:
            dispatch_approval_rpc(
                resp_id=rpc_entry["resp_id"],
                worker=rpc_entry.get("worker"),
                approved=False,
                feedback=reason
            )

        payload = {
            "approval_id": appr.id,
            "approvalId": appr.id,
            "tool_call_id": appr.tool_call_id,
            "toolCallId": appr.tool_call_id,
            "status": "cancelled",
            "reason": reason,
            "resolved_at": now.isoformat()
        }
        broker.publish_event(EventEnvelope(
            project_id=project_id,
            thread_id=thread_id,
            type="approval_cancelled",
            payload=payload
        ))
        broker.publish_event(EventEnvelope(
            project_id=project_id,
            thread_id=thread_id,
            type="approval.cancelled",
            payload=payload
        ))

    db.commit()
    for appr in cancelled:
        db.refresh(appr)

    return cancelled


def terminate_subagents_for_thread(thread_id: str, db: Session) -> List[SubAgent]:
    """
    Cascades cancellation to all active child subagents and pending tool approvals when a thread is cancelled, stopped, or archived.
    """
    # Cascade cancel any lingering pending tool approvals for this thread
    cancel_pending_approvals_for_thread(thread_id=thread_id, db=db, reason=f"Parent thread '{thread_id}' cascade cancellation")

    # Fetch all active subagents for this thread or child threads
    active_subagents = db.query(SubAgent).filter(
        (SubAgent.thread_id == thread_id) | (SubAgent.parent_thread_id == thread_id),
        SubAgent.status.in_(ACTIVE_STATUSES)
    ).all()

    project_id = "default"
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread and thread.project_id:
        project_id = thread.project_id

    terminated = []
    for sub in active_subagents:
        sub.status = "cancelled"
        terminated.append(sub)

        broker.publish_event(EventEnvelope(
            project_id=project_id,
            thread_id=sub.thread_id,
            type="subagent.terminated",
            payload={
                "subagent_id": sub.id,
                "thread_id": sub.thread_id,
                "status": sub.status,
                "reason": f"Parent thread '{thread_id}' cascade cancellation"
            }
        ))

    db.commit()
    for sub in terminated:
        db.refresh(sub)

    return terminated


def stop_subagent(subagent_id: str, db: Session) -> SubAgent:
    """
    Terminates a specific subagent.
    """
    subagent = db.query(SubAgent).filter(SubAgent.id == subagent_id).first()
    if not subagent:
        raise ValueError(f"Subagent '{subagent_id}' not found")

    subagent.status = "stopped"
    db.commit()
    db.refresh(subagent)

    project_id = "default"
    if subagent.thread and subagent.thread.project_id:
        project_id = subagent.thread.project_id

    broker.publish_event(EventEnvelope(
        project_id=project_id,
        thread_id=subagent.thread_id,
        type="subagent.stopped",
        payload={
            "subagent_id": subagent.id,
            "thread_id": subagent.thread_id,
            "status": subagent.status
        }
    ))

    return subagent


def steer_subagent(subagent_id: str, instruction: str, db: Session) -> Dict[str, Any]:
    """
    Sends steering instructions to an active subagent.
    """
    subagent = db.query(SubAgent).filter(SubAgent.id == subagent_id).first()
    if not subagent:
        raise ValueError(f"Subagent '{subagent_id}' not found")

    project_id = "default"
    if subagent.thread and subagent.thread.project_id:
        project_id = subagent.thread.project_id

    broker.publish_event(EventEnvelope(
        project_id=project_id,
        thread_id=subagent.thread_id,
        type="subagent.steered",
        payload={
            "subagent_id": subagent.id,
            "thread_id": subagent.thread_id,
            "instruction": instruction
        }
    ))

    return {
        "status": "steered",
        "subagent_id": subagent_id,
        "instruction": instruction
    }


def list_subagents_for_thread(thread_id: str, db: Session) -> List[SubAgent]:
    """
    Lists all subagents associated with a thread.
    """
    return db.query(SubAgent).filter(
        (SubAgent.thread_id == thread_id) | (SubAgent.parent_thread_id == thread_id)
    ).all()
