"""Behavioural checks for the fail-closed structural evidence foundation."""

from pathlib import Path
import sys

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.services.migration_readiness_service import (
    EXPECTED_RUN_SCHEMA_HASHES, _schema_hashes, inspect_infrastructure,
)
from backend.services.evidence_audit_service import CRITERION_CODES
from test_migrations import _run_alembic, _url


def test_revision_006_seals_structural_evidence_schema(tmp_path: Path):
    url = _url(tmp_path / "evidence-foundation.db")
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    try:
        assert set(inspect(engine).get_table_names()) >= {
            "supervisor_acceptance_contracts", "supervisor_run_baselines",
            "supervisor_sandbox_attestations", "supervisor_audit_requests",
            "supervisor_audit_criterion_results",
        }
        assert inspect_infrastructure(engine).state == "ready"
        # The database, rather than a client convention, rejects an arbitrary
        # criterion contract. This is not a raw-text/command registry.
        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(text("""
                    INSERT INTO supervisor_acceptance_contracts
                    (id,project_id,work_package_id,audit_scope_id,tenant_id,owner_user_id,
                     registry_version,criterion_codes,criterion_digest,state,created_at,approved_at)
                    VALUES ('acc_invalid','none','none','none',1,1,'1','[\"arbitrary\"]',
                    '0000000000000000000000000000000000000000000000000000000000000000',
                    'approved',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                """))
    finally:
        engine.dispose()


def test_fixed_criterion_registry_is_closed_and_structural():
    assert CRITERION_CODES == (
        "repository_identity_bound", "baseline_captured", "sandbox_attested",
    )


def test_empty_006_downgrade_restores_sealed_005_action_ledgers(tmp_path: Path):
    url = _url(tmp_path / "evidence-empty-downgrade.db")
    _run_alembic(url, "upgrade", "head")
    _run_alembic(url, "downgrade", "005")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            hashes = _schema_hashes(connection)
        assert all(hashes.get(key) == value for key, value in EXPECTED_RUN_SCHEMA_HASHES.items())
    finally:
        engine.dispose()
