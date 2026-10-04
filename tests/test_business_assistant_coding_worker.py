"""Real regression tests for the isolated coding-worker connector.

Covers all 9 requirements of Section 8.1 without mocks:
1. Idempotent Claim
2. Authorised Scope Inspection
3. Bounded Change Creation
4. Test Verification & Real Exit Results
5. Independent Review Request
6. Commit/Diff Identifier & Sanitised Summary
7. Honest Failure
8. Separation of Deployment
9. Interruption Recovery
"""

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models.business_assistant import (
    SupportTicket,
    SupportTicketDeduplicationClaim,
    SupportTicketEvent,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.coding_worker import (
    BoundedChangeViolationError,
    CodingWorkerConnector,
    CodingWorkerWorkspace,
    DeploymentSeparationError,
    DuplicateClaimError,
    InvalidClaimTokenError,
    ScopeAccessViolationError,
    ScopeInspector,
    TestVerificationRunner,
    TicketNotEligibleError,
)


@pytest.fixture
def test_tenant_user(db_session: Session) -> tuple[Tenant, User]:
    tenant = Tenant(name="Worker Test Tenant", subdomain="worker-test")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        login="worker-owner",
        password_hash="pw",
        role="owner",
    )
    db_session.add(user)
    db_session.commit()
    return tenant, user


@pytest.fixture
def sample_ticket(db_session: Session, test_tenant_user: tuple[Tenant, User]) -> SupportTicket:
    tenant, user = test_tenant_user
    ticket = SupportTicket(
        tenant_id=tenant.id,
        user_id=user.id,
        category="bug",
        severity="normal",
        status="awaiting_engineering",
        title="Fix syntax error in booking helper",
        description="A bug ticket awaiting engineering dispatch.",
        deduplication_key="dedup-worker-key-1",
        authorisation_state="not_required",
        requires_owner_approval=False,
    )
    db_session.add(ticket)
    db_session.flush()

    claim = SupportTicketDeduplicationClaim(
        ticket_id=ticket.id,
        tenant_id=tenant.id,
        user_id=user.id,
        deduplication_key=ticket.deduplication_key,
    )
    db_session.add(claim)
    db_session.commit()
    return ticket


@pytest.fixture
def mock_sandbox_repo(tmp_path: Path) -> Path:
    """Real temporary directory structure representing authorised repository directories."""
    repo = tmp_path / "fastapi_bookings"
    repo.mkdir()

    # Create authorised top-level directories
    for d in ("app", "tests", "docs", "scripts", "alembic", "frontend"):
        (repo / d).mkdir()

    # Create valid sample files
    (repo / "app" / "sample.py").write_text("x = 42\n", encoding="utf-8")
    (repo / "tests" / "test_sample.py").write_text("def test_x(): assert True\n", encoding="utf-8")

    # Create secret / forbidden files to test rejection
    (repo / ".env").write_text("SECRET_KEY=production_secret_token\n", encoding="utf-8")
    (repo / ".env.production").write_text("DATABASE_URL=postgres://...\n", encoding="utf-8")
    (repo / "app" / "private.key").write_text("PRIVATE_KEY_DATA\n", encoding="utf-8")

    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\nrepositoryformatversion = 0\n", encoding="utf-8")

    return repo


# =============================================================================
# Requirement 1: Idempotent Claim
# =============================================================================
def test_claim_eligible_ticket_transitions_status_and_assigns_ids(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)

    assert sample_ticket.status == "awaiting_engineering"
    assert sample_ticket.coding_task_id is None

    claim_res = connector.claim_ticket(sample_ticket.id)
    assert claim_res.ticket_id == sample_ticket.id
    assert claim_res.coding_task_id.startswith("cw-")
    assert len(claim_res.claim_token) >= 32

    db_session.refresh(sample_ticket)
    assert sample_ticket.status == "in_progress"
    assert sample_ticket.coding_task_id == claim_res.coding_task_id

    # Verify lifecycle event
    events = (
        db_session.query(SupportTicketEvent)
        .filter(SupportTicketEvent.ticket_id == sample_ticket.id)
        .all()
    )
    claim_events = [e for e in events if e.event_type == "worker_claimed"]
    assert len(claim_events) == 1
    assert claim_events[0].safe_metadata["coding_task_id"] == claim_res.coding_task_id
    assert claim_events[0].safe_metadata["claim_token"] == claim_res.claim_token


def test_concurrent_duplicate_claim_is_rejected(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)

    # First claim succeeds
    connector.claim_ticket(sample_ticket.id)

    # Second claim on the same ticket must be rejected
    with pytest.raises(DuplicateClaimError) as exc_info:
        connector.claim_ticket(sample_ticket.id)
    assert "in status 'in_progress'" in str(exc_info.value) or "already claimed" in str(exc_info.value)


def test_unapproved_elevated_ticket_cannot_be_claimed(
    db_session: Session,
    test_tenant_user: tuple[Tenant, User],
    mock_sandbox_repo: Path,
):
    tenant, user = test_tenant_user
    elevated_ticket = SupportTicket(
        tenant_id=tenant.id,
        user_id=user.id,
        category="security",
        severity="critical",
        status="awaiting_engineering",
        title="Patch vulnerability",
        description="Requires owner approval",
        deduplication_key="dedup-sec-1",
        authorisation_state="pending_approval",
        requires_owner_approval=True,
    )
    db_session.add(elevated_ticket)
    db_session.commit()

    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)
    with pytest.raises(TicketNotEligibleError) as exc_info:
        connector.claim_ticket(elevated_ticket.id)
    assert "requires owner approval" in str(exc_info.value).lower()

    # Now approve it and verify claim succeeds
    elevated_ticket.authorisation_state = "approved"
    db_session.commit()

    claim = connector.claim_ticket(elevated_ticket.id)
    assert claim.ticket_id == elevated_ticket.id


# =============================================================================
# Requirement 2: Authorised Scope Inspection
# =============================================================================
def test_authorised_scope_inspection_allows_valid_files(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)
    claim = connector.claim_ticket(sample_ticket.id)

    # Inspect allowed file
    content = connector.inspect_file(
        ticket_id=sample_ticket.id,
        coding_task_id=claim.coding_task_id,
        claim_token=claim.claim_token,
        relative_path="app/sample.py",
    )
    assert content == "x = 42\n"

    # List allowed directory
    items = connector.list_directory(
        ticket_id=sample_ticket.id,
        coding_task_id=claim.coding_task_id,
        claim_token=claim.claim_token,
        relative_path="app",
    )
    assert "sample.py" in items
    # Ensure forbidden files (.key) are filtered out of listing
    assert "private.key" not in items


def test_authorised_scope_inspection_rejects_forbidden_and_out_of_scope_files(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)
    claim = connector.claim_ticket(sample_ticket.id)

    # Path traversal rejected
    with pytest.raises(ScopeAccessViolationError):
        connector.inspect_file(
            ticket_id=sample_ticket.id,
            coding_task_id=claim.coding_task_id,
            claim_token=claim.claim_token,
            relative_path="../outside.txt",
        )

    # .env access rejected
    with pytest.raises(ScopeAccessViolationError):
        connector.inspect_file(
            ticket_id=sample_ticket.id,
            coding_task_id=claim.coding_task_id,
            claim_token=claim.claim_token,
            relative_path=".env",
        )

    # .git directory access rejected
    with pytest.raises(ScopeAccessViolationError):
        connector.inspect_file(
            ticket_id=sample_ticket.id,
            coding_task_id=claim.coding_task_id,
            claim_token=claim.claim_token,
            relative_path=".git/config",
        )

    # Private key pattern rejected
    with pytest.raises(ScopeAccessViolationError):
        connector.inspect_file(
            ticket_id=sample_ticket.id,
            coding_task_id=claim.coding_task_id,
            claim_token=claim.claim_token,
            relative_path="app/private.key",
        )


# =============================================================================
# Requirement 3: Bounded Change Creation
# =============================================================================
def test_bounded_change_applied_safely_in_workspace(mock_sandbox_repo: Path):
    inspector = ScopeInspector()
    ws = CodingWorkerWorkspace(repo_root=mock_sandbox_repo, scope_inspector=inspector)
    try:
        sandbox_path = ws.apply_file_change("app/sample.py", "x = 100\n")
        assert sandbox_path.is_file()
        assert sandbox_path.read_text(encoding="utf-8") == "x = 100\n"

        # Base repository remains intact until applied/merged
        assert (mock_sandbox_repo / "app" / "sample.py").read_text(encoding="utf-8") == "x = 42\n"

        diff = ws.compute_diff()
        assert "app/sample.py" in diff.files_changed
        assert diff.insertions == 1
        assert diff.deletions == 1
        assert len(diff.patch_id) == 64
    finally:
        ws.cleanup()


def test_bounded_change_exceeding_file_count_rejected(mock_sandbox_repo: Path):
    inspector = ScopeInspector()
    ws = CodingWorkerWorkspace(repo_root=mock_sandbox_repo, scope_inspector=inspector)
    try:
        # Applying up to MAX_FILES (10) succeeds
        for i in range(10):
            ws.apply_file_change(f"app/file_{i}.py", f"val = {i}\n")

        # 11th file exceeds bounds
        with pytest.raises(BoundedChangeViolationError) as exc_info:
            ws.apply_file_change("app/file_11.py", "val = 11\n")
        assert "maximum allowed files" in str(exc_info.value).lower()
    finally:
        ws.cleanup()


def test_bounded_change_touching_unauthorised_paths_rejected(mock_sandbox_repo: Path):
    inspector = ScopeInspector()
    ws = CodingWorkerWorkspace(repo_root=mock_sandbox_repo, scope_inspector=inspector)
    try:
        with pytest.raises(ScopeAccessViolationError):
            ws.apply_file_change(".env", "SECRET=modified\n")
    finally:
        ws.cleanup()


# =============================================================================
# Requirement 4: Test Verification & Real Exit Results
# =============================================================================
def test_real_subprocess_test_verification_success(mock_sandbox_repo: Path):
    runner = TestVerificationRunner()
    target_file = mock_sandbox_repo / "app" / "sample.py"

    # Real py_compile execution
    cmd = [sys.executable, "-m", "py_compile", str(target_file)]
    result = runner.execute(cmd, cwd=mock_sandbox_repo)

    assert result.exit_code == 0
    assert result.passed is True
    assert result.duration_ms >= 0


def test_real_subprocess_test_verification_failure_records_exit_code(mock_sandbox_repo: Path):
    runner = TestVerificationRunner()
    bad_syntax_file = mock_sandbox_repo / "app" / "bad.py"
    bad_syntax_file.write_text("def broken syntax (: \n", encoding="utf-8")

    cmd = [sys.executable, "-m", "py_compile", str(bad_syntax_file)]
    result = runner.execute(cmd, cwd=mock_sandbox_repo)

    assert result.exit_code != 0
    assert result.passed is False
    assert result.duration_ms >= 0
    assert "SyntaxError" in result.sanitised_stderr or "syntax" in result.sanitised_stderr.lower()


def test_test_verification_runner_scrubs_secrets_from_output(mock_sandbox_repo: Path):
    runner = TestVerificationRunner()
    # Script that prints a live API key pattern
    leak_script = mock_sandbox_repo / "scripts" / "leak.py"
    leak_script.write_text("print('Found secret sk_live_1234567890abcdef')\n", encoding="utf-8")

    cmd = [sys.executable, str(leak_script)]
    result = runner.execute(cmd, cwd=mock_sandbox_repo)

    assert result.passed is True
    assert "sk_live_1234567890abcdef" not in result.sanitised_stdout
    assert "[REDACTED_SECRET]" in result.sanitised_stdout


def test_test_verification_rejects_dangerous_shell_commands():
    runner = TestVerificationRunner()
    with pytest.raises(ValueError) as exc:
        runner.validate_command([sys.executable, "-c", "print(1); rm -rf /"])
    assert "dangerous character" in str(exc.value).lower()


# =============================================================================
# Requirement 5 & 6: Independent Review Request, Diff Identifier & Sanitised Summary
# =============================================================================
def test_successful_task_transitions_to_pending_review_with_review_bundle(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)
    claim = connector.claim_ticket(sample_ticket.id)

    target_code = "x = 99\ndef helper():\n    return x\n"
    target_file = mock_sandbox_repo / "app" / "sample.py"
    target_file.write_text(target_code, encoding="utf-8")

    # Run real bounded task with real py_compile test command
    run_result = connector.execute_bounded_task(
        ticket_id=sample_ticket.id,
        coding_task_id=claim.coding_task_id,
        claim_token=claim.claim_token,
        changes={"app/sample.py": target_code},
        test_command=[sys.executable, "-m", "py_compile", str(target_file)],
    )

    assert run_result.success is True
    assert run_result.status == "pending_review"
    assert run_result.review_bundle is not None

    bundle = run_result.review_bundle
    assert bundle.ticket_id == sample_ticket.id
    assert bundle.coding_task_id == claim.coding_task_id
    assert len(bundle.patch_id) == 64
    assert "app/sample.py" in bundle.diff_summary["files_changed"]
    assert bundle.test_result["passed"] is True
    assert "Ready for independent review." in bundle.sanitised_summary
    # Ensure no absolute machine-specific path or tokens leaked
    assert "C:\\" not in bundle.sanitised_summary
    assert "/Users/" not in bundle.sanitised_summary

    # Ticket state updated
    db_session.refresh(sample_ticket)
    assert sample_ticket.status == "pending_review"
    assert "Ready for independent review." in sample_ticket.resolution_summary

    # Event logged
    events = (
        db_session.query(SupportTicketEvent)
        .filter(SupportTicketEvent.ticket_id == sample_ticket.id)
        .all()
    )
    review_events = [e for e in events if e.event_type == "review_requested"]
    assert len(review_events) == 1
    assert review_events[0].safe_metadata["patch_id"] == bundle.patch_id


# =============================================================================
# Requirement 7: Honest Failure
# =============================================================================
def test_honest_failure_on_failing_tests(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)
    claim = connector.claim_ticket(sample_ticket.id)

    # Change creates syntax error
    broken_code = "def syntax error !!!\n"
    target_file = mock_sandbox_repo / "app" / "sample.py"
    target_file.write_text(broken_code, encoding="utf-8")

    run_result = connector.execute_bounded_task(
        ticket_id=sample_ticket.id,
        coding_task_id=claim.coding_task_id,
        claim_token=claim.claim_token,
        changes={"app/sample.py": broken_code},
        test_command=[sys.executable, "-m", "py_compile", str(target_file)],
    )

    assert run_result.success is False
    assert run_result.status == "failed"
    assert run_result.review_bundle is None
    assert "Test verification failed" in run_result.error_message

    db_session.refresh(sample_ticket)
    assert sample_ticket.status == "failed"
    assert "Engineering worker execution failed" in sample_ticket.resolution_summary

    # Deduplication claim was cleanly released
    claim_count = (
        db_session.query(SupportTicketDeduplicationClaim)
        .filter(SupportTicketDeduplicationClaim.ticket_id == sample_ticket.id)
        .count()
    )
    assert claim_count == 0

    # worker_failed event recorded
    events = (
        db_session.query(SupportTicketEvent)
        .filter(SupportTicketEvent.ticket_id == sample_ticket.id)
        .all()
    )
    fail_events = [e for e in events if e.event_type == "worker_failed"]
    assert len(fail_events) == 1
    assert fail_events[0].safe_metadata["status"] == "failed"


# =============================================================================
# Requirement 8: Separation of Deployment
# =============================================================================
def test_worker_cannot_deploy_or_push_to_production(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)

    # Direct deploy method strictly prohibited
    with pytest.raises(DeploymentSeparationError) as exc_info:
        connector.deploy()
    assert "cannot deploy or push to production" in str(exc_info.value).lower()

    # Attempting to run task with deploy intent rejected
    claim = connector.claim_ticket(sample_ticket.id)
    with pytest.raises(DeploymentSeparationError):
        connector.execute_bounded_task(
            ticket_id=sample_ticket.id,
            coding_task_id=claim.coding_task_id,
            claim_token=claim.claim_token,
            changes={"app/sample.py": "x = 1\n"},
            test_command=[sys.executable, "-c", "print(1)"],
            instruction_intent="Deploy this fix to production immediately",
        )


# =============================================================================
# Requirement 9: Interruption Recovery
# =============================================================================
def test_interruption_recovery_reconciles_orphaned_ticket_to_failed(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)
    claim = connector.claim_ticket(sample_ticket.id)

    # Simulate worker crash / disconnection: ticket remains in_progress with old updated_at
    past_time = datetime.now(timezone.utc) - timedelta(seconds=600)
    sample_ticket.updated_at = past_time
    db_session.commit()

    # Run reconciliation with threshold 300 seconds
    reconciled = connector.reconcile_interrupted_tickets(max_age_seconds=300, action="fail")

    assert len(reconciled) == 1
    assert reconciled[0].id == sample_ticket.id
    assert sample_ticket.status == "failed"
    assert "interrupted or timed out" in sample_ticket.resolution_summary

    # Event logged
    events = (
        db_session.query(SupportTicketEvent)
        .filter(SupportTicketEvent.ticket_id == sample_ticket.id)
        .all()
    )
    rec_events = [e for e in events if e.event_type == "interruption_recovered"]
    assert len(rec_events) == 1
    assert rec_events[0].safe_metadata["action"] == "failed"


def test_interruption_recovery_resets_ticket_to_awaiting_engineering(
    db_session: Session,
    sample_ticket: SupportTicket,
    mock_sandbox_repo: Path,
):
    connector = CodingWorkerConnector(db=db_session, repo_root=mock_sandbox_repo)
    connector.claim_ticket(sample_ticket.id)

    # Simulate interruption
    past_time = datetime.now(timezone.utc) - timedelta(seconds=600)
    sample_ticket.updated_at = past_time
    db_session.commit()

    reconciled = connector.reconcile_interrupted_tickets(max_age_seconds=300, action="reset")

    assert len(reconciled) == 1
    assert sample_ticket.status == "awaiting_engineering"
    assert sample_ticket.coding_task_id is None

    # Can now be claimed again cleanly
    new_claim = connector.claim_ticket(sample_ticket.id)
    assert new_claim.ticket_id == sample_ticket.id
    assert sample_ticket.status == "in_progress"
