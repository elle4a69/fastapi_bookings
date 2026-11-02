from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_backend_runtime_and_clients_use_port_7060() -> None:
    expected_fragments = {
        "start.bat": ("--port 7060", "http://localhost:7060/docs"),
        "Dockerfile": ("EXPOSE 7060", "${PORT:-7060}"),
        "docker-compose.yml": ('"7060:7060"', "PORT=7060"),
        "docker-compose.prod.yml": (
            '"--port", "7060"',
            '"127.0.0.1:7060:7060"',
            "http://127.0.0.1:7060/api/v1/diagnostics/readiness",
        ),
        "frontend/vite.config.ts": ("http://127.0.0.1:7060",),
        "mapbox/vite.config.ts": ("http://127.0.0.1:7060",),
        "dev-dashboard/project-modules.json": (
            '"port": 7060',
            "http://127.0.0.1:7060/health",
        ),
        "tools/postman-sweep/prepare_authenticated_sweep.py": (
            "http://127.0.0.1:7060",
        ),
    }

    for relative_path, fragments in expected_fragments.items():
        content = _text(relative_path)
        for fragment in fragments:
            assert fragment in content, f"{relative_path} is missing {fragment!r}"


def test_active_backend_port_configuration_has_no_legacy_8000_default() -> None:
    active_configuration = (
        "start.bat",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.prod.yml",
        "frontend/vite.config.ts",
        "frontend/src/lib/api.ts",
        "app/core/config.py",
        "app/services/sms/chatwoot_service.py",
        "app/services/sms/chatwoot_provisioning_service.py",
        "app/services/stripe_service.py",
        "dev-dashboard/project-modules.json",
        "mapbox/vite.config.ts",
        "tests/smoke.http",
        "tools/postman-sweep/run-sweep-delayed.ps1",
        "tools/postman-sweep/run-authenticated-sweep-delayed.ps1",
        "tools/postman-sweep/launch-and-save-authenticated-sweep.ps1",
        "tools/postman-sweep/prepare_authenticated_sweep.py",
        "tools/postman-sweep/SimplyDemo-Local.postman_environment.json",
    )

    for relative_path in active_configuration:
        assert "8000" not in _text(relative_path), relative_path
