"""Read-only fixed cutover posture for WP-UI-01A."""

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from backend import database
from backend.middleware.v2_errors import SupervisorHTTPError
from backend.models.codex import ControlPlaneCutoverState
from backend.schemas.v2_supervisor import fixed_cutover


def read_cutover(db_engine: Engine | None = None) -> dict[str, object]:
    selected_engine = db_engine or database.engine
    try:
        with selected_engine.connect() as connection:
            row = connection.execute(
                select(ControlPlaneCutoverState.__table__).where(
                    ControlPlaneCutoverState.__table__.c.singleton_id == 1
                )
            ).first()
        if row is None or row.mode != "v1_only" or row.version != 1:
            raise SupervisorHTTPError(503, "database_migration_required")
        return fixed_cutover()
    except SupervisorHTTPError:
        raise
    except SQLAlchemyError as exc:
        raise SupervisorHTTPError(503, "dependency_unavailable") from exc
