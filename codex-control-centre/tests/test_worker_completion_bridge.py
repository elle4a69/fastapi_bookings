"""Tests for Safe Worker Completion Bridge, Evidence Collector, and Guarded Worktree Promotion."""

import os
import sys
import uuid
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

import backend.database
from backend.main import app
from backend.config import settings
from backend.models.codex import (
    Project, SupervisorRun, SupervisorRunBaseline,
    SupervisorAcceptanceContract, SupervisorAuditRequest,
    SupervisorAuditCriterionResult,
)
from backend.services.actor_scope import ActorScope
from backend.services.idempotency_service import canonical_fingerprint, reserve, utc_now
from backend.services.legacy_adoption_service import root_identity_for_path
from backend.services.supervisor_repository import (
    claim_reserved_project,
    planning_create_in_transaction,
    planning_approve_in_transaction,
)
from backend.services.evidence_audit_service import (
    create_acceptance_contract,
    collect_post_turn_evidence,
    CRITERION_CODES,
)
from backend.services.supervisor_run_service import (
    issue_start_authorization,
    create_intent,
    record_launch_outcome,
    record_run_completion,
    notify_supervisor_lifecycle_signal,
)
from backend.services.event_service import broker
from backend.services.worktree_service import create_worktree, promote_worktree
from test_supervisor_bootstrap_claim import configured_project, migrated_engine


@pytest.fixture(autouse=True)
def reset_event_broker():
    broker.subscribers.clear()
    broker.history.clear()
    broker.sequences.clear()


def _setup_claimed_project_and_work_package(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    backend.database.engine = engine
    backend.database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=10, user_id=20)
    key = str(uuid.uuid4())
    reservation = reserve(
        actor=actor,
        idempotency_key=key,
        fingerprint=canonical_fingerprint(
            actor=actor,
            project_id=configured.public_id,
            expected_version=0,
            confirmation=True,
        ),
        db_engine=engine,
    )
    claim_reserved_project(
        actor=actor,
        configured=configured,
        reservation=reservation,
        idempotency_key=key,
        expected_version=0,
        db_engine=engine,
    )

    repo_dir = Path(configured.canonical_root)
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=str(repo_dir), check=True, capture_output=True)
    (repo_dir / "README.md").write_text("# Project Root\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial baseline"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", configured.default_branch], cwd=str(repo_dir), check=True, capture_output=True)

    with engine.begin() as conn:
        mission, _, _ = planning_create_in_transaction(
            conn, "mission", configured.public_id,
            {"title": "Initial Mission", "summary": "Mission summary"},
            actor=actor,
        )
        wpk, _, _ = planning_create_in_transaction(
            conn, "work_package", mission["id"],
            {"title": "WP Title", "scope": "WP Scope"},
            actor=actor,
        )
        brief, _, _ = planning_create_in_transaction(
            conn, "brief", wpk["id"],
            {"content": "Brief content for test"},
            actor=actor,
        )
        planning_approve_in_transaction(conn, brief["id"], actor=actor)
        audit, _, _ = planning_create_in_transaction(
            conn, "audit_scope", wpk["id"],
            {"criteria": "All unit tests pass", "exclusions": "none"},
            actor=actor,
        )
        contract = create_acceptance_contract(conn, work_package_id=wpk["id"], actor=actor)

    return engine, configured, actor, wpk, contract


def test_supervisor_run_lifecycle_transitions(tmp_path: Path):
    """Test transitions from dispatch_acknowledged to completed/failed and event emission safety."""
    engine, configured, actor, wpk, _ = _setup_claimed_project_and_work_package(tmp_path)

    try:
        # Create Run 1
        with engine.begin() as conn:
            grant, token = issue_start_authorization(conn, work_package_id=wpk["id"], actor=actor, waiver_requested=False)
            intent = create_intent(
                conn,
                work_package_id=wpk["id"],
                actor=actor,
                request_id="req_" + uuid.uuid4().hex,
                grant_token=token,
            )
            run_id = str(intent["run_id"])
            record_launch_outcome(conn, run_id=run_id, actor=actor, outcome="dispatch_acknowledged")

        # Verify initial state
        with engine.connect() as conn:
            row = conn.execute(select(SupervisorRun.__table__).where(SupervisorRun.__table__.c.id == run_id)).mappings().first()
            assert row["status"] == "dispatch_acknowledged"

        broker.history.clear()

        # Transition to completed
        with engine.begin() as conn:
            res = record_run_completion(conn, run_id=run_id, status="completed", actor=actor)
            assert res["status"] == "completed"

        # Verify completed status persisted
        with engine.connect() as conn:
            row = conn.execute(select(SupervisorRun.__table__).where(SupervisorRun.__table__.c.id == run_id)).mappings().first()
            assert row["status"] == "completed"

        # Check emitted event
        completed_events = [e for dq in broker.history.values() for e in dq if e.type == "supervisor_run_completed"]
        assert len(completed_events) == 1
        evt = completed_events[0]
        assert evt.thread_id == run_id
        assert evt.payload["run_id"] == run_id
        assert evt.payload["status"] == "completed"
        # Verify NO raw prompt or source leakage
        payload_str = json.dumps(evt.payload)
        assert "Brief content" not in payload_str
        assert "password" not in payload_str
        assert "secret" not in payload_str

        # Verify terminal state invariant: cannot transition from completed back to dispatching or failed
        with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.execute(
                    update(SupervisorRun.__table__)
                    .where(SupervisorRun.__table__.c.id == run_id)
                    .values(status="dispatching")
                )

        # Create Run 2 to test failed transition
        # Need a second work package & grant
        with engine.begin() as conn:
            wpk2, _, _ = planning_create_in_transaction(
                conn, "work_package", wpk["mission_id"],
                {"title": "WP 2", "scope": "WP 2 Scope"},
                actor=actor,
            )
            brief2, _, _ = planning_create_in_transaction(
                conn, "brief", wpk2["id"],
                {"content": "Brief 2 content"},
                actor=actor,
            )
            planning_approve_in_transaction(conn, brief2["id"], actor=actor)
            planning_create_in_transaction(
                conn, "audit_scope", wpk2["id"],
                {"criteria": "Tests pass", "exclusions": "none"},
                actor=actor,
            )
            create_acceptance_contract(conn, work_package_id=wpk2["id"], actor=actor)
            grant2, token2 = issue_start_authorization(conn, work_package_id=wpk2["id"], actor=actor, waiver_requested=False)
            intent2 = create_intent(
                conn,
                work_package_id=wpk2["id"],
                actor=actor,
                request_id="req_" + uuid.uuid4().hex,
                grant_token=token2,
            )
            run_id_2 = str(intent2["run_id"])
            record_launch_outcome(conn, run_id=run_id_2, actor=actor, outcome="dispatch_acknowledged")

        # Test notify_supervisor_lifecycle_signal bridging 'interrupted' signal to 'failed'
        notify_supervisor_lifecycle_signal(run_id_2, "interrupted")

        with engine.connect() as conn:
            row2 = conn.execute(select(SupervisorRun.__table__).where(SupervisorRun.__table__.c.id == run_id_2)).mappings().first()
            assert row2["status"] == "failed"

        failed_events = [e for dq in broker.history.values() for e in dq if e.type == "supervisor_run_failed"]
        assert len(failed_events) >= 1
        assert failed_events[-1].payload["status"] == "failed"
    finally:
        engine.dispose()


def test_post_turn_evidence_collection(tmp_path: Path):
    """Test capturing diff, git IDs, running test command, and persisting criteria results."""
    engine, configured, actor, wpk, _ = _setup_claimed_project_and_work_package(tmp_path)
    repo_dir = Path(configured.canonical_root)

    try:
        with engine.begin() as conn:
            grant, token = issue_start_authorization(conn, work_package_id=wpk["id"], actor=actor, waiver_requested=False)
            intent = create_intent(
                conn,
                work_package_id=wpk["id"],
                actor=actor,
                request_id="req_" + uuid.uuid4().hex,
                grant_token=token,
            )
            run_id = str(intent["run_id"])
            record_launch_outcome(conn, run_id=run_id, actor=actor, outcome="dispatch_acknowledged")

        # Create worktree for the run
        wt_result = create_worktree(str(repo_dir), f"branch-{run_id}", f"wt-{run_id}")
        wt_path = Path(wt_result["path"])

        # Make modifications and commit in the worktree
        feature_file = wt_path / "solution.py"
        feature_file.write_text("def solve():\n    return 42\n")
        subprocess.run(["git", "add", "solution.py"], cwd=str(wt_path), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Implement solution"], cwd=str(wt_path), check=True, capture_output=True)

        # Collect post-turn evidence with a passing test command
        with engine.begin() as conn:
            evidence = collect_post_turn_evidence(
                conn,
                run_id=run_id,
                actor=actor,
                test_command=[sys.executable, "-c", "import sys; sys.exit(0)"],
            )

        assert evidence["run_id"] == run_id
        assert evidence["tests_passed"] is True
        assert evidence["files_changed"] >= 1
        assert evidence["insertions"] >= 1
        assert len(str(evidence["commit_id"])) == 40
        assert len(str(evidence["tree_id"])) == 40
        assert len(evidence["criterion_results"]) == 3

        # Verify database persisted rows in supervisor_audit_requests and supervisor_audit_criterion_results
        with engine.connect() as conn:
            req = conn.execute(
                select(SupervisorAuditRequest.__table__).where(SupervisorAuditRequest.__table__.c.run_id == run_id)
            ).mappings().first()
            assert req is not None
            assert req["state"] == "submitted"

            criterion_rows = conn.execute(
                select(SupervisorAuditCriterionResult.__table__).where(
                    SupervisorAuditCriterionResult.__table__.c.audit_request_id == req["id"]
                )
            ).mappings().all()
            assert len(criterion_rows) == 3

            by_code = {r["criterion_code"]: r for r in criterion_rows}
            for code in CRITERION_CODES:
                assert code in by_code
                assert by_code[code]["outcome"] == "passed"
                assert len(by_code[code]["evidence_digest"]) == 64
    finally:
        engine.dispose()


def test_worktree_promotion_negative_and_positive_gates(tmp_path: Path):
    """Test worktree promotion endpoint rejecting unverified worktrees and cleanly merging verified ones."""
    engine, configured, actor, wpk, _ = _setup_claimed_project_and_work_package(tmp_path)
    repo_dir = Path(configured.canonical_root)

    # Setup FastAPI client
    client = TestClient(app)
    auth_headers = {"Authorization": f"Bearer {settings.token_secret}"}

    def override_get_db():
        session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[backend.database.get_db] = override_get_db

    try:
        with engine.begin() as conn:
            grant, token = issue_start_authorization(conn, work_package_id=wpk["id"], actor=actor, waiver_requested=False)
            intent = create_intent(
                conn,
                work_package_id=wpk["id"],
                actor=actor,
                request_id="req_" + uuid.uuid4().hex,
                grant_token=token,
            )
            run_id = str(intent["run_id"])
            record_launch_outcome(conn, run_id=run_id, actor=actor, outcome="dispatch_acknowledged")

        # Create worktree
        wt_name = f"wt-{run_id}"
        wt_result = create_worktree(str(repo_dir), f"branch-{run_id}", wt_name)
        wt_path = Path(wt_result["path"])
        (wt_path / "feature.txt").write_text("Promoted feature content\n")
        subprocess.run(["git", "add", "feature.txt"], cwd=str(wt_path), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Commit in worktree"], cwd=str(wt_path), check=True, capture_output=True)

        # 1. Negative Gate: Promotion fails with 409 because no evidence has been collected
        resp = client.post(
            f"/api/admin/codex/worktrees/{wt_name}/promote",
            json={"repo_path": str(repo_dir), "target_branch": configured.default_branch},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert "No audit request or evidence found" in resp.json()["detail"]
        assert wt_path.exists()

        # 2. Collect passing evidence
        with engine.begin() as conn:
            collect_post_turn_evidence(
                conn,
                run_id=run_id,
                actor=actor,
                test_command=[sys.executable, "-c", "import sys; sys.exit(0)"],
            )

        # 3. Positive Gate: Promotion succeeds with 200
        resp = client.post(
            f"/api/admin/codex/worktrees/{wt_name}/promote",
            json={"repo_path": str(repo_dir), "target_branch": configured.default_branch},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["target_branch"] == configured.default_branch
        assert len(data["verified_criteria"]) == 3

        # Worktree directory must be cleanly removed
        assert not wt_path.exists()

        # Target branch must contain the promoted file
        main_feature = repo_dir / "feature.txt"
        assert main_feature.exists()
        assert main_feature.read_text() == "Promoted feature content\n"

    finally:
        app.dependency_overrides.clear()
        engine.dispose()
