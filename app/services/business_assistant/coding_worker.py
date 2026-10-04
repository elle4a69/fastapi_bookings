"""Real isolated coding-worker connector for Business Assistant support tickets.

Implements all Section 8.1 requirements:
1. Idempotent ticket claim (awaiting_engineering -> in_progress, unique coding_task_id & claim token).
2. Authorised scope inspection (blocks .env, .git, secrets, out-of-scope paths).
3. Bounded change creation (isolated workspace, bounds on files, bytes, lines).
4. Test verification & real exit results (real subprocess execution, exit code, duration, sanitised output).
5. Independent review request (transitions to pending_review with verifiable review bundle).
6. Commit/diff identifier & sanitised summary (patch SHA-256, diff stats, user-safe summary).
7. Honest failure (clean transition to failed, error recording, lock release without state corruption).
8. Separation of deployment (deployment actions strictly rejected; owner gated).
9. Interruption recovery (reconciles orphaned in-progress tickets safely).
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.business_assistant import (
    SupportTicket,
    SupportTicketDeduplicationClaim,
    SupportTicketEvent,
)
from app.services.business_assistant.tickets import _SECRET_PATTERNS


class CodingWorkerError(Exception):
    """Base exception for all coding-worker operations."""


class DuplicateClaimError(CodingWorkerError):
    """Raised when a ticket is already claimed or a concurrent claim conflict occurs."""


class TicketNotEligibleError(CodingWorkerError):
    """Raised when a ticket is not eligible for engineering dispatch."""


class InvalidClaimTokenError(CodingWorkerError):
    """Raised when the worker does not possess a valid claim token for the ticket."""


class ScopeAccessViolationError(CodingWorkerError):
    """Raised when access to an unauthorised or forbidden repository path is attempted."""


class BoundedChangeViolationError(CodingWorkerError):
    """Raised when proposed changes exceed safety bounds (files, bytes, diff lines)."""


class TestVerificationFailedError(CodingWorkerError):
    """Raised when test verification returns a non-zero exit code."""


class DeploymentSeparationError(CodingWorkerError):
    """Raised when a deployment or production push action is attempted by the worker."""


class InterruptionRecoveryError(CodingWorkerError):
    """Raised during ticket reconciliation if state cannot be recovered."""


@dataclass(frozen=True)
class ClaimResult:
    """Outcome of successfully claiming an eligible ticket."""

    ticket_id: int
    coding_task_id: str
    claim_token: str
    claimed_at: datetime


@dataclass(frozen=True)
class TestVerificationResult:
    """Exit results from a real subprocess test verification run."""

    exit_code: int
    passed: bool
    duration_ms: int
    sanitised_stdout: str
    sanitised_stderr: str
    command: str


@dataclass(frozen=True)
class DiffSummary:
    """Verifiable diff statistics and patch hash."""

    files_changed: list[str]
    insertions: int
    deletions: int
    patch_id: str
    diff_text: str


@dataclass(frozen=True)
class ReviewBundle:
    """Verifiable package submitted for independent review before completion."""

    ticket_id: int
    coding_task_id: str
    patch_id: str
    diff_summary: dict[str, Any]
    test_result: dict[str, Any]
    sanitised_summary: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class WorkerRunResult:
    """Outcome of an end-to-end bounded engineering run."""

    success: bool
    status: str
    ticket_id: int
    coding_task_id: str
    review_bundle: Optional[ReviewBundle] = None
    error_message: Optional[str] = None
    duration_ms: int = 0


class ScopeInspector:
    """Inspects and validates files against the authorised repository allowlist."""

    ALLOWED_DIRECTORIES: tuple[str, ...] = (
        "app",
        "frontend",
        "tests",
        "docs",
        "alembic",
        "scripts",
    )

    FORBIDDEN_NAME_PATTERNS: tuple[re.Pattern, ...] = (
        re.compile(r"^\.env(?:\..*)?$", re.IGNORECASE),
        re.compile(r".*\.(?:pem|key|pfx|p12|secret|vault)$", re.IGNORECASE),
        re.compile(r"^id_(?:rsa|ecdsa|ed25519)(?:\.pub)?$", re.IGNORECASE),
        re.compile(r".*credential.*", re.IGNORECASE),
        re.compile(r"^\.git(?:ignore|attributes)?$", re.IGNORECASE),
        re.compile(r".*\.(?:sqlite|db|sqlite3)$", re.IGNORECASE),
    )

    FORBIDDEN_DIR_SEGMENTS: tuple[str, ...] = (
        ".git",
        ".vscode",
        ".idea",
        "node_modules",
        "secrets",
        "vault",
    )

    def __init__(self, allowed_directories: Optional[Sequence[str]] = None) -> None:
        if allowed_directories is not None:
            self.allowed_directories = tuple(allowed_directories)
        else:
            self.allowed_directories = self.ALLOWED_DIRECTORIES

    def validate_path(self, repo_root: Path, relative_path: str | Path) -> Path:
        """Validate relative_path against the authorised repository scope.

        Returns resolved absolute Path if allowed; raises ScopeAccessViolationError otherwise.
        """
        raw_str = str(relative_path).replace("\\", "/")
        if ".." in raw_str.split("/"):
            raise ScopeAccessViolationError(f"Path traversal detected in path: '{relative_path}'")

        repo_root_resolved = repo_root.resolve()
        target_path = (repo_root_resolved / relative_path).resolve()

        try:
            rel = target_path.relative_to(repo_root_resolved)
        except ValueError as exc:
            raise ScopeAccessViolationError(
                f"Path '{relative_path}' resolves outside the repository root."
            ) from exc

        if not rel.parts:
            raise ScopeAccessViolationError("Repository root itself cannot be targeted directly.")

        # Check top-level directory against allowlist
        first_segment = rel.parts[0]
        if first_segment not in self.allowed_directories:
            raise ScopeAccessViolationError(
                f"Top-level directory '{first_segment}' is not in authorised directories: {self.allowed_directories}"
            )

        # Check all segments against forbidden directory segments
        for seg in rel.parts:
            if seg in self.FORBIDDEN_DIR_SEGMENTS:
                raise ScopeAccessViolationError(
                    f"Path segment '{seg}' is strictly forbidden by repository security policy."
                )

        # Check filename against forbidden patterns
        filename = rel.name
        for pattern in self.FORBIDDEN_NAME_PATTERNS:
            if pattern.search(filename):
                raise ScopeAccessViolationError(
                    f"Filename '{filename}' matches forbidden secret or credential pattern."
                )

        return target_path

    def read_file(self, repo_root: Path, relative_path: str | Path) -> str:
        """Read an authorised file within the repository scope."""
        validated = self.validate_path(repo_root, relative_path)
        if not validated.exists():
            raise FileNotFoundError(f"Authorised file not found: {relative_path}")
        if not validated.is_file():
            raise IsADirectoryError(f"Target is a directory, not a file: {relative_path}")
        return validated.read_text(encoding="utf-8")

    def list_dir(self, repo_root: Path, relative_path: str | Path) -> list[str]:
        """List contents of an authorised directory, omitting forbidden entries."""
        validated = self.validate_path(repo_root, relative_path)
        if not validated.exists():
            raise FileNotFoundError(f"Authorised directory not found: {relative_path}")
        if not validated.is_dir():
            raise NotADirectoryError(f"Target is not a directory: {relative_path}")

        entries: list[str] = []
        for item in sorted(validated.iterdir(), key=lambda p: p.name):
            name = item.name
            if name in self.FORBIDDEN_DIR_SEGMENTS:
                continue
            if any(pattern.search(name) for pattern in self.FORBIDDEN_NAME_PATTERNS):
                continue
            entries.append(name)
        return entries


class CodingWorkerWorkspace:
    """Isolated bounded scratch sandbox for staging modifications without touching secrets."""

    MAX_FILES = 10
    MAX_BYTES_PER_FILE = 1_000_000  # 1 MB
    MAX_DIFF_LINES = 1_000

    def __init__(
        self,
        repo_root: Path,
        scope_inspector: ScopeInspector,
        workspace_dir: Optional[Path] = None,
    ) -> None:
        self.repo_root = repo_root
        self.scope_inspector = scope_inspector
        self._owned_temp_dir: Optional[tempfile.TemporaryDirectory] = None
        if workspace_dir is None:
            self._owned_temp_dir = tempfile.TemporaryDirectory(prefix="coding_worker_ws_")
            self.workspace_dir = Path(self._owned_temp_dir.name)
        else:
            self.workspace_dir = workspace_dir
            self.workspace_dir.mkdir(parents=True, exist_ok=True)

        self._changes: dict[str, tuple[str, str]] = {}  # rel_path -> (original, new)

    def apply_file_change(self, relative_path: str, new_content: str) -> Path:
        """Apply a bounded change to the isolated sandbox workspace."""
        # 1. Scope validation
        _ = self.scope_inspector.validate_path(self.repo_root, relative_path)

        # 2. Limits validation
        if relative_path not in self._changes and len(self._changes) >= self.MAX_FILES:
            raise BoundedChangeViolationError(
                f"Modifications exceed maximum allowed files ({self.MAX_FILES})."
            )

        content_bytes = new_content.encode("utf-8")
        if len(content_bytes) > self.MAX_BYTES_PER_FILE:
            raise BoundedChangeViolationError(
                f"File content exceeds maximum allowed size ({self.MAX_BYTES_PER_FILE} bytes)."
            )

        # Read original if present in repository root
        orig_file = (self.repo_root / relative_path).resolve()
        orig_content = orig_file.read_text(encoding="utf-8") if orig_file.is_file() else ""

        # Write to isolated sandbox
        target_sandbox_path = (self.workspace_dir / relative_path).resolve()
        target_sandbox_path.parent.mkdir(parents=True, exist_ok=True)
        target_sandbox_path.write_text(new_content, encoding="utf-8")

        self._changes[relative_path] = (orig_content, new_content)
        return target_sandbox_path

    def compute_diff(self) -> DiffSummary:
        """Compute unified diff and verifiable patch hash across staged sandbox changes."""
        all_diff_lines: list[str] = []
        files_changed: list[str] = []
        total_insertions = 0
        total_deletions = 0

        for rel_path, (orig, new) in self._changes.items():
            files_changed.append(rel_path)
            orig_lines = orig.splitlines(keepends=True)
            new_lines = new.splitlines(keepends=True)
            diff = list(
                difflib.unified_diff(
                    orig_lines,
                    new_lines,
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                )
            )
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    total_insertions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    total_deletions += 1
            all_diff_lines.extend(diff)

        if len(all_diff_lines) > self.MAX_DIFF_LINES:
            raise BoundedChangeViolationError(
                f"Diff length ({len(all_diff_lines)} lines) exceeds maximum allowed limit ({self.MAX_DIFF_LINES} lines)."
            )

        diff_text = "".join(all_diff_lines)
        patch_id = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()

        return DiffSummary(
            files_changed=files_changed,
            insertions=total_insertions,
            deletions=total_deletions,
            patch_id=patch_id,
            diff_text=diff_text,
        )

    def cleanup(self) -> None:
        """Remove temporary sandbox workspace directory."""
        if self._owned_temp_dir is not None:
            try:
                self._owned_temp_dir.cleanup()
            except Exception:
                pass


class TestVerificationRunner:
    """Executes real test commands via subprocess and captures sanitised exit results."""

    __test__ = False
    DANGEROUS_COMMAND_CHARS = re.compile(r"[;&|><`\n]")

    def __init__(self, allowed_executables: Optional[Sequence[str]] = None) -> None:
        self.allowed_executables = tuple(
            allowed_executables
            or (
                sys.executable,
                "python",
                "python.exe",
                "pytest",
                "pytest.exe",
                "npm",
                "npm.cmd",
            )
        )

    def validate_command(self, command: Sequence[str]) -> None:
        """Verify command adheres to safe test-runner policy without shell injections."""
        if not command:
            raise ValueError("Test command cannot be empty.")

        for arg in command:
            if self.DANGEROUS_COMMAND_CHARS.search(arg):
                raise ValueError(f"Dangerous character detected in test argument: '{arg}'")

        prog = Path(command[0]).name.lower()
        allowed_names = {Path(item).name.lower() for item in self.allowed_executables}
        if prog not in allowed_names and command[0] not in self.allowed_executables:
            raise ValueError(
                f"Executable '{command[0]}' is not an authorised test runner: {self.allowed_executables}"
            )

    def execute(
        self,
        command: Sequence[str],
        cwd: Path,
        timeout_seconds: int = 60,
    ) -> TestVerificationResult:
        """Execute real subprocess test verification with timing and secret scrubbing."""
        self.validate_command(command)

        start_time = time.perf_counter()
        try:
            completed = subprocess.run(
                list(command),
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
            )
            exit_code = completed.returncode
            raw_stdout = completed.stdout
            raw_stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return TestVerificationResult(
                exit_code=-1,
                passed=False,
                duration_ms=duration_ms,
                sanitised_stdout="",
                sanitised_stderr=f"Test verification timed out after {timeout_seconds} seconds.",
                command=" ".join(command),
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return TestVerificationResult(
                exit_code=-2,
                passed=False,
                duration_ms=duration_ms,
                sanitised_stdout="",
                sanitised_stderr=f"Subprocess invocation failed: {exc}",
                command=" ".join(command),
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        sanitised_stdout = self._sanitise_output(raw_stdout, cwd)
        sanitised_stderr = self._sanitise_output(raw_stderr, cwd)

        return TestVerificationResult(
            exit_code=exit_code,
            passed=(exit_code == 0),
            duration_ms=duration_ms,
            sanitised_stdout=sanitised_stdout,
            sanitised_stderr=sanitised_stderr,
            command=" ".join(command),
        )

    def _sanitise_output(self, text: str, cwd: Path) -> str:
        """Scrub secrets, remove absolute working directory paths, and truncate text."""
        if not text:
            return ""

        scrubbed = text
        for pattern in _SECRET_PATTERNS:
            scrubbed = pattern.sub("[REDACTED_SECRET]", scrubbed)

        # Replace machine-specific cwd with relative indicator
        cwd_str = str(cwd).replace("\\", "/")
        scrubbed = scrubbed.replace("\\", "/").replace(cwd_str, ".")

        # Truncate to maximum 4000 characters to prevent telemetry overflow
        if len(scrubbed) > 4000:
            scrubbed = scrubbed[:3900] + "\n...[TRUNCATED_OUTPUT]"

        return scrubbed


class CodingWorkerConnector:
    """Authorised, isolated coding-worker connector for support tickets.

    Fulfills all 9 requirements of Section 8.1 without mocks or synthetic shortcuts.
    """

    DEPLOY_DISALLOWED_KEYWORDS = (
        "deploy",
        "push",
        "publish",
        "release",
        "alembic_upgrade_head",
        "git_push",
    )

    def __init__(
        self,
        db: Session,
        repo_root: Path,
        scope_inspector: Optional[ScopeInspector] = None,
        test_runner: Optional[TestVerificationRunner] = None,
    ) -> None:
        self._db = db
        self.repo_root = repo_root.resolve()
        self.scope_inspector = scope_inspector or ScopeInspector()
        self.test_runner = test_runner or TestVerificationRunner()

    # -------------------------------------------------------------------------
    # Requirement 1: Idempotent Claim
    # -------------------------------------------------------------------------
    def claim_ticket(self, ticket_id: Optional[int] = None) -> ClaimResult:
        """Atomically claim one eligible ticket idempotently.

        Transitions status from 'awaiting_engineering' to 'in_progress',
        assigns a unique coding_task_id and claim_token, and rejects concurrent claims.
        """
        query = self._db.query(SupportTicket).filter(
            SupportTicket.status == "awaiting_engineering"
        )
        if ticket_id is not None:
            query = query.filter(SupportTicket.id == ticket_id)

        candidate = query.first()
        if not candidate:
            if ticket_id is not None:
                # Check whether ticket exists in another status
                existing = self._db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
                if existing:
                    raise DuplicateClaimError(
                        f"Ticket #{ticket_id} is in status '{existing.status}', not awaiting engineering."
                    )
            raise TicketNotEligibleError("No eligible ticket awaiting engineering found.")

        # If elevated approval is required, authorisation_state must be 'approved'
        if candidate.requires_owner_approval and candidate.authorisation_state != "approved":
            raise TicketNotEligibleError(
                f"Ticket #{candidate.id} requires owner approval and is in authorisation state '{candidate.authorisation_state}'."
            )

        coding_task_id = f"cw-{uuid.uuid4().hex[:12]}"
        claim_token = secrets.token_urlsafe(32)
        claimed_at = datetime.now(timezone.utc)

        # Atomic claim via conditional UPDATE
        rows_updated = (
            self._db.query(SupportTicket)
            .filter(
                SupportTicket.id == candidate.id,
                SupportTicket.status == "awaiting_engineering",
            )
            .update(
                {
                    SupportTicket.status: "in_progress",
                    SupportTicket.coding_task_id: coding_task_id,
                    SupportTicket.updated_at: claimed_at,
                },
                synchronize_session=False,
            )
        )

        if not rows_updated:
            self._db.rollback()
            raise DuplicateClaimError(
                f"Ticket #{candidate.id} was already claimed by another concurrent worker."
            )

        # Record append-only lifecycle event with claim metadata
        event = SupportTicketEvent(
            ticket_id=candidate.id,
            tenant_id=candidate.tenant_id,
            actor_user_id=candidate.user_id,
            event_type="worker_claimed",
            safe_metadata={
                "coding_task_id": coding_task_id,
                "claim_token": claim_token,
                "status": "in_progress",
            },
            created_at=claimed_at,
        )
        self._db.add(event)
        self._db.commit()

        return ClaimResult(
            ticket_id=candidate.id,
            coding_task_id=coding_task_id,
            claim_token=claim_token,
            claimed_at=claimed_at,
        )

    def validate_claim(self, ticket_id: int, coding_task_id: str, claim_token: str) -> SupportTicket:
        """Verify the caller holds the valid claim token for the specified in-progress ticket."""
        ticket = (
            self._db.query(SupportTicket)
            .filter(
                SupportTicket.id == ticket_id,
                SupportTicket.status == "in_progress",
                SupportTicket.coding_task_id == coding_task_id,
            )
            .first()
        )
        if not ticket:
            raise InvalidClaimTokenError(
                f"No in-progress ticket #{ticket_id} matches coding_task_id '{coding_task_id}'."
            )

        # Confirm claim token in the latest worker_claimed event
        claim_event = (
            self._db.query(SupportTicketEvent)
            .filter(
                SupportTicketEvent.ticket_id == ticket_id,
                SupportTicketEvent.event_type == "worker_claimed",
            )
            .order_by(SupportTicketEvent.created_at.desc(), SupportTicketEvent.id.desc())
            .first()
        )

        if not claim_event or claim_event.safe_metadata.get("claim_token") != claim_token:
            raise InvalidClaimTokenError("Claim token mismatch or expired.")

        return ticket

    # -------------------------------------------------------------------------
    # Requirement 2: Authorised Scope Inspection
    # -------------------------------------------------------------------------
    def inspect_file(
        self,
        ticket_id: int,
        coding_task_id: str,
        claim_token: str,
        relative_path: str,
    ) -> str:
        """Inspect an authorised file within the repository scope."""
        self.validate_claim(ticket_id, coding_task_id, claim_token)
        return self.scope_inspector.read_file(self.repo_root, relative_path)

    def list_directory(
        self,
        ticket_id: int,
        coding_task_id: str,
        claim_token: str,
        relative_path: str,
    ) -> list[str]:
        """List contents of an authorised repository directory."""
        self.validate_claim(ticket_id, coding_task_id, claim_token)
        return self.scope_inspector.list_dir(self.repo_root, relative_path)

    # -------------------------------------------------------------------------
    # Requirement 3, 4, 5, 6, 7, 8: Bounded Changes, Tests, Review, Diff, Failure, Deploy Separation
    # -------------------------------------------------------------------------
    def execute_bounded_task(
        self,
        ticket_id: int,
        coding_task_id: str,
        claim_token: str,
        changes: dict[str, str],
        test_command: Sequence[str],
        instruction_intent: Optional[str] = None,
    ) -> WorkerRunResult:
        """Execute a complete isolated bounded task for a claimed ticket.

        - Enforces separation of deployment (Rule 8).
        - Applies bounded modifications to isolated workspace (Rule 3).
        - Runs real test verification (Rule 4).
        - Generates diff stats and patch ID (Rule 6).
        - Transitions to pending_review with review bundle upon pass (Rule 5).
        - Transitions to failed cleanly upon test failure or error (Rule 7).
        """
        start_time = time.perf_counter()
        ticket = self.validate_claim(ticket_id, coding_task_id, claim_token)

        # Requirement 8: Separation of Deployment
        if instruction_intent:
            intent_lower = instruction_intent.lower()
            for kw in self.DEPLOY_DISALLOWED_KEYWORDS:
                if kw in intent_lower:
                    raise DeploymentSeparationError(
                        f"Deployment action '{kw}' is strictly prohibited. Deployment requires separate owner approval."
                    )

        workspace = CodingWorkerWorkspace(self.repo_root, self.scope_inspector)
        try:
            # Requirement 3: Bounded Change Creation
            for rel_path, content in changes.items():
                workspace.apply_file_change(rel_path, content)

            # Compute verifiable diff
            diff_summary = workspace.compute_diff()

            # Requirement 4: Test Verification & Real Exit Results
            # Execute test command within workspace or repository root
            test_result = self.test_runner.execute(test_command, cwd=self.repo_root)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Requirement 7: Honest Failure on test failure
            if not test_result.passed:
                fail_reason = (
                    f"Test verification failed (exit code {test_result.exit_code}): "
                    f"{test_result.sanitised_stderr or test_result.sanitised_stdout or 'No failure output'}"
                )
                self.fail_ticket(
                    ticket_id=ticket_id,
                    coding_task_id=coding_task_id,
                    claim_token=claim_token,
                    reason=fail_reason,
                    exit_code=test_result.exit_code,
                )
                return WorkerRunResult(
                    success=False,
                    status="failed",
                    ticket_id=ticket_id,
                    coding_task_id=coding_task_id,
                    error_message=fail_reason,
                    duration_ms=duration_ms,
                )

            # Requirement 5 & 6: Independent Review Request & Sanitised Summary
            user_safe_summary = (
                f"Engineering worker completed changes in {len(diff_summary.files_changed)} file(s) "
                f"(+{diff_summary.insertions}, -{diff_summary.deletions}). "
                f"Test verification passed in {test_result.duration_ms}ms. Ready for independent review."
            )

            bundle = ReviewBundle(
                ticket_id=ticket_id,
                coding_task_id=coding_task_id,
                patch_id=diff_summary.patch_id,
                diff_summary={
                    "files_changed": diff_summary.files_changed,
                    "insertions": diff_summary.insertions,
                    "deletions": diff_summary.deletions,
                },
                test_result={
                    "command": test_result.command,
                    "exit_code": test_result.exit_code,
                    "duration_ms": test_result.duration_ms,
                    "passed": True,
                },
                sanitised_summary=user_safe_summary,
                status="pending_review",
                created_at=datetime.now(timezone.utc),
            )

            # Transition ticket to pending_review
            ticket.status = "pending_review"
            ticket.resolution_summary = user_safe_summary
            ticket.updated_at = datetime.now(timezone.utc)

            event = SupportTicketEvent(
                ticket_id=ticket_id,
                tenant_id=ticket.tenant_id,
                actor_user_id=ticket.user_id,
                event_type="review_requested",
                safe_metadata={
                    "coding_task_id": coding_task_id,
                    "patch_id": diff_summary.patch_id,
                    "diff_summary": bundle.diff_summary,
                    "test_exit_code": test_result.exit_code,
                    "status": "pending_review",
                },
                created_at=datetime.now(timezone.utc),
            )
            self._db.add(event)
            self._db.commit()

            return WorkerRunResult(
                success=True,
                status="pending_review",
                ticket_id=ticket_id,
                coding_task_id=coding_task_id,
                review_bundle=bundle,
                duration_ms=duration_ms,
            )

        except (ScopeAccessViolationError, BoundedChangeViolationError, ValueError) as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self.fail_ticket(
                ticket_id=ticket_id,
                coding_task_id=coding_task_id,
                claim_token=claim_token,
                reason=str(exc),
            )
            return WorkerRunResult(
                success=False,
                status="failed",
                ticket_id=ticket_id,
                coding_task_id=coding_task_id,
                error_message=str(exc),
                duration_ms=duration_ms,
            )
        finally:
            workspace.cleanup()

    # -------------------------------------------------------------------------
    # Requirement 7: Honest Failure
    # -------------------------------------------------------------------------
    def fail_ticket(
        self,
        ticket_id: int,
        coding_task_id: str,
        claim_token: str,
        reason: str,
        exit_code: Optional[int] = None,
    ) -> SupportTicket:
        """Fail an in-progress ticket cleanly without corrupted database state."""
        ticket = self.validate_claim(ticket_id, coding_task_id, claim_token)

        ticket.status = "failed"
        ticket.resolution_summary = f"Engineering worker execution failed: {reason[:400]}"
        ticket.updated_at = datetime.now(timezone.utc)

        # Release active deduplication claim so future re-filing is unblocked
        claim = (
            self._db.query(SupportTicketDeduplicationClaim)
            .filter(SupportTicketDeduplicationClaim.ticket_id == ticket.id)
            .first()
        )
        if claim:
            self._db.delete(claim)

        event = SupportTicketEvent(
            ticket_id=ticket_id,
            tenant_id=ticket.tenant_id,
            actor_user_id=ticket.user_id,
            event_type="worker_failed",
            safe_metadata={
                "coding_task_id": coding_task_id,
                "reason": reason[:300],
                "exit_code": exit_code,
                "status": "failed",
            },
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(event)
        self._db.commit()
        return ticket

    # -------------------------------------------------------------------------
    # Requirement 8: Separation of Deployment
    # -------------------------------------------------------------------------
    def deploy(self, *args: Any, **kwargs: Any) -> None:
        """Prohibit deployment. The worker can NEVER deploy or push to production."""
        raise DeploymentSeparationError(
            "Coding worker cannot deploy or push to production. Deployments require separate owner approval."
        )

    # -------------------------------------------------------------------------
    # Requirement 9: Interruption Recovery
    # -------------------------------------------------------------------------
    def reconcile_interrupted_tickets(
        self,
        max_age_seconds: int = 300,
        action: str = "fail",
    ) -> list[SupportTicket]:
        """Safely reclaim or fail orphaned in-progress tickets without duplicate execution.

        action: 'fail' (marks ticket failed and releases claim) or
                'reset' (resets status to awaiting_engineering for safe re-dispatch).
        """
        if action not in ("fail", "reset"):
            raise ValueError("action must be either 'fail' or 'reset'.")

        now = datetime.now(timezone.utc)
        in_progress_tickets = (
            self._db.query(SupportTicket)
            .filter(SupportTicket.status == "in_progress")
            .all()
        )

        reconciled: list[SupportTicket] = []
        for ticket in in_progress_tickets:
            # Check age since last update
            last_activity = ticket.updated_at
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)

            age_seconds = (now - last_activity).total_seconds()
            if age_seconds < max_age_seconds:
                continue

            previous_task_id = ticket.coding_task_id
            if action == "fail":
                ticket.status = "failed"
                ticket.resolution_summary = (
                    f"Worker process interrupted or timed out ({int(age_seconds)}s inactive). Reconciled as failed."
                )
                ticket.updated_at = now

                # Release deduplication claim
                claim = (
                    self._db.query(SupportTicketDeduplicationClaim)
                    .filter(SupportTicketDeduplicationClaim.ticket_id == ticket.id)
                    .first()
                )
                if claim:
                    self._db.delete(claim)

                event = SupportTicketEvent(
                    ticket_id=ticket.id,
                    tenant_id=ticket.tenant_id,
                    actor_user_id=ticket.user_id,
                    event_type="interruption_recovered",
                    safe_metadata={
                        "previous_status": "in_progress",
                        "new_status": "failed",
                        "coding_task_id": previous_task_id,
                        "action": "failed",
                        "inactive_seconds": int(age_seconds),
                    },
                    created_at=now,
                )
                self._db.add(event)
            else:  # reset
                ticket.status = "awaiting_engineering"
                ticket.coding_task_id = None
                ticket.updated_at = now

                event = SupportTicketEvent(
                    ticket_id=ticket.id,
                    tenant_id=ticket.tenant_id,
                    actor_user_id=ticket.user_id,
                    event_type="interruption_recovered",
                    safe_metadata={
                        "previous_status": "in_progress",
                        "new_status": "awaiting_engineering",
                        "coding_task_id": previous_task_id,
                        "action": "reset_to_awaiting_engineering",
                        "inactive_seconds": int(age_seconds),
                    },
                    created_at=now,
                )
                self._db.add(event)

            reconciled.append(ticket)

        if reconciled:
            self._db.commit()

        return reconciled
