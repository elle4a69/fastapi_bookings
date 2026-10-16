from pathlib import Path


def test_planning_action_codes_are_auditable_ledger_values():
    source = (
        Path(__file__).resolve().parents[1] / "backend" / "models" / "codex.py"
    ).read_text(encoding="utf-8")
    for action in ("create_mission", "create_work_package", "create_brief", "approve_brief", "record_context_checkpoint", "define_audit_scope"):
        assert action in source
