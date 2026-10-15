"""Process-isolated storage for standalone Control Centre tests."""

import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest


_TEST_DATABASE_DIR = Path(tempfile.mkdtemp(prefix="codex-control-centre-pytest-"))
_TEST_DATABASE = _TEST_DATABASE_DIR / "codex-control-centre.db"
os.environ["database_url"] = f"sqlite:///{_TEST_DATABASE.as_posix()}"
os.environ["OTEL_SDK_DISABLED"] = "true"

_DEFAULT_DATABASES = tuple(
    Path(__file__).resolve().parents[1] / name
    for name in ("codex.db", "codex.db-wal", "codex.db-shm")
)


def _snapshot(path: Path) -> tuple[bool, int | None, int | None, str | None]:
    if not path.exists():
        return (False, None, None, None)
    stat = path.stat()
    return (True, stat.st_size, stat.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())


_BEFORE = {path: _snapshot(path) for path in _DEFAULT_DATABASES}


def pytest_sessionfinish(session, exitstatus):
    cleanup_failures = []
    database_module = sys.modules.get("backend.database")
    loaded_engine = getattr(database_module, "engine", None)
    if loaded_engine is not None:
        try:
            loaded_engine.dispose()
        except Exception as exc:  # pragma: no cover - exercised only on teardown failure
            cleanup_failures.append(
                f"Control Centre engine disposal failed: {type(exc).__name__}"
            )

    changed = [str(path) for path, before in _BEFORE.items() if _snapshot(path) != before]
    try:
        shutil.rmtree(_TEST_DATABASE_DIR)
    except FileNotFoundError:
        pass
    except Exception as exc:  # pragma: no cover - exercised only on teardown failure
        cleanup_failures.append(
            f"temporary test storage removal failed: {type(exc).__name__}: {_TEST_DATABASE_DIR}"
        )
    if _TEST_DATABASE_DIR.exists():
        cleanup_failures.append(f"temporary test storage remains: {_TEST_DATABASE_DIR}")

    if changed or cleanup_failures:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_sep("=", "test database isolation failure")
            if changed:
                reporter.write_line("Unexpectedly changed runtime database sentinel(s):")
                for path in changed:
                    reporter.write_line(path)
            for failure in cleanup_failures:
                reporter.write_line(failure)
