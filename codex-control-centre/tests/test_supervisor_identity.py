"""Authority projection and five-operation OpenAPI contract."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from backend.routers import v2_supervisor
from backend.routers import projects as v1_projects
from backend.models.codex import Project, Thread
from backend.services.actor_scope import ActorScope, get_actor_scope
from backend.services.legacy_adoption_service import root_identity_for_path


V2_PREFIX = "/api/admin/codex/v2"
BASE_RESPONSE_HEADERS = {"Cache-Control", "X-Request-ID"}
EXPECTED_RESPONSE_CONTRACTS = {
    ("get", f"{V2_PREFIX}/bootstrap"): {
        "200": ("BootstrapEnvelope", BASE_RESPONSE_HEADERS | {"ETag"}),
        "401": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "403": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "422": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "500": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "503": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
    },
    ("get", f"{V2_PREFIX}/operations/readiness"): {
        "200": ("ReadinessEnvelope", BASE_RESPONSE_HEADERS),
        "401": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "403": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "422": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "500": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "503": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
    },
    ("get", f"{V2_PREFIX}/operations/cutover-mode"): {
        "200": ("CutoverEnvelope", BASE_RESPONSE_HEADERS | {"ETag"}),
        "401": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "403": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "422": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "500": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "503": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
    },
    ("get", f"{V2_PREFIX}/projects"): {
        "200": ("ProjectsEnvelope", BASE_RESPONSE_HEADERS | {"ETag"}),
        "401": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "403": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "409": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "422": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "500": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "503": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
    },
    ("post", f"{V2_PREFIX}/projects/{{project_id}}/claim"): {
        "200": (
            "ClaimEnvelope",
            BASE_RESPONSE_HEADERS | {"ETag", "Idempotency-Replayed"},
        ),
        "202": ("InProgressEnvelope", BASE_RESPONSE_HEADERS | {"Retry-After"}),
        "400": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "401": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "403": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "404": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "409": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "412": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "415": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "422": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "428": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "500": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
        "503": ("ErrorEnvelope", BASE_RESPONSE_HEADERS),
    },
}
ACTION_EXTENSIONS = {
    "x-operator-action",
    "x-action-code",
    "x-action-registry-version",
    "x-backend-permission",
}


class _ProjectQuery:
    def __init__(self, database, model):
        self.database = database
        self.model = model

    def filter(self, *_args):
        return self

    def first(self):
        return self.database.project if self.model is Project else None

    def count(self):
        return 0


class _ProjectSession:
    def __init__(self):
        self.project = None

    def query(self, model):
        return _ProjectQuery(self, model)

    def add(self, project):
        self.project = project

    def commit(self):
        return None

    def refresh(self, _project):
        return None


@pytest.fixture(scope="module")
def supervisor_openapi():
    application = FastAPI()
    application.include_router(v2_supervisor.router, prefix=V2_PREFIX)
    schema = application.openapi()
    operations = {
        (method.lower(), path): operation
        for path, path_item in schema["paths"].items()
        if path.startswith(V2_PREFIX)
        for method, operation in path_item.items()
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    }
    return schema, operations


def test_actor_scope_contains_only_server_derived_positive_scalar_authority():
    actor = asyncio.run(
        get_actor_scope(
            SimpleNamespace(tenant_id=12, id=34, is_platform_owner=True, is_active=True)
        )
    )
    assert actor == ActorScope(tenant_id=12, user_id=34)
    assert actor.is_platform_owner is True
    with pytest.raises(ValueError, match="invalid_actor_scope"):
        ActorScope(tenant_id=0, user_id=34)


def test_v1_project_create_and_update_maintain_root_identity_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    monkeypatch.setattr(
        "backend.services.boundary_service.validate_path_in_boundaries",
        lambda *_args, **_kwargs: None,
    )
    session = _ProjectSession()

    v1_projects.create_project(
        v1_projects.ProjectCreate(
            id="v1-project", name="First", repo_path=str(first_root)
        ),
        db=session,
    )
    first_identity = root_identity_for_path(first_root)
    assert first_identity is not None
    assert session.project.root_identity_digest == first_identity[1]

    v1_projects.create_project(
        v1_projects.ProjectCreate(
            id="v1-project", name="Second", repo_path=str(second_root)
        ),
        db=session,
    )
    second_identity = root_identity_for_path(second_root)
    assert second_identity is not None
    assert session.project.root_identity_digest == second_identity[1]
    assert session.project.root_identity_digest != first_identity[1]


def test_v1_project_create_fails_closed_when_root_identity_is_inconclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    monkeypatch.setattr(
        "backend.services.boundary_service.validate_path_in_boundaries",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(v1_projects, "root_identity_for_path", lambda _path: None)

    with pytest.raises(HTTPException) as exc_info:
        v1_projects.create_project(
            v1_projects.ProjectCreate(name="Rejected", repo_path=str(repository_root)),
            db=_ProjectSession(),
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Repository root identity could not be proven."


def test_orm_project_insert_derives_identity_and_rejects_unprovable_root(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Project.__table__.create(engine)
    valid_root = tmp_path / "valid-root"
    valid_root.mkdir()
    expected_identity = root_identity_for_path(valid_root)
    assert expected_identity is not None
    try:
        with Session(engine) as session:
            project = Project(
                id="orm-valid",
                name="Valid",
                repo_path=str(valid_root),
                default_branch="main",
            )
            session.add(project)
            session.commit()
            assert project.root_identity_digest == expected_identity[1]

        with Session(engine) as session:
            session.add(
                Project(
                    id="orm-invalid",
                    name="Invalid",
                    repo_path=str(tmp_path / "missing-root"),
                    default_branch="main",
                )
            )
            with pytest.raises(StatementError, match="project_root_identity_unavailable"):
                session.flush()
            session.rollback()
    finally:
        engine.dispose()


def test_authority_dependency_completes_before_claim_body_or_ccc_access(monkeypatch):
    application = FastAPI()
    application.include_router(v2_supervisor.router, prefix="/api/admin/codex/v2")
    inspected = False

    def forbidden():
        raise HTTPException(status_code=403, detail="forbidden")

    def should_not_inspect():
        nonlocal inspected
        inspected = True
        raise AssertionError("CCC inspection ran before authority")

    application.dependency_overrides[get_actor_scope] = forbidden
    monkeypatch.setattr(v2_supervisor, "inspect_infrastructure", should_not_inspect)
    with TestClient(application) as client:
        response = client.post(
            "/api/admin/codex/v2/projects/guessed/claim",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 403
    assert inspected is False


def test_openapi_has_exact_five_operation_surface(supervisor_openapi):
    _, operations = supervisor_openapi
    assert set(operations) == set(EXPECTED_RESPONSE_CONTRACTS)


@pytest.mark.parametrize("operation_key", EXPECTED_RESPONSE_CONTRACTS)
def test_openapi_response_status_schema_and_header_matrix(
    supervisor_openapi, operation_key
):
    _, operations = supervisor_openapi
    operation = operations[operation_key]
    expected_responses = EXPECTED_RESPONSE_CONTRACTS[operation_key]

    assert set(operation["responses"]) == set(expected_responses)
    for status_code, (schema_name, expected_headers) in expected_responses.items():
        response = operation["responses"][status_code]
        assert set(response["content"]) == {"application/json"}
        assert response["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{schema_name}"
        }
        assert set(response.get("headers", {})) == expected_headers


def test_openapi_response_header_schemas_are_exact(supervisor_openapi):
    _, operations = supervisor_openapi
    declared_headers = {
        header_name: header
        for operation in operations.values()
        for response in operation["responses"].values()
        for header_name, header in response.get("headers", {}).items()
    }

    assert declared_headers["Cache-Control"]["schema"] == {
        "type": "string",
        "const": "no-store",
    }
    assert declared_headers["X-Request-ID"]["schema"] == {
        "type": "string",
        "pattern": "^req_[0-9a-f]{32}$",
    }
    assert declared_headers["Retry-After"]["schema"] == {
        "type": "string",
        "const": "1",
    }
    assert declared_headers["Idempotency-Replayed"]["schema"] == {
        "type": "string",
        "const": "true",
    }
    assert declared_headers["ETag"]["schema"] == {"type": "string"}


def test_openapi_represents_native_auth_without_browser_authority_inputs(
    supervisor_openapi,
):
    _, operations = supervisor_openapi
    forbidden_authority_names = {
        "tenant_id",
        "user_id",
        "owner_user_id",
        "is_platform_owner",
        "role",
        "repo_path",
        "configured_fingerprint",
        "control_plane",
    }

    for (method, _), operation in operations.items():
        parameters = operation.get("parameters", [])
        token_parameters = [
            parameter
            for parameter in parameters
            if parameter["in"] == "header" and parameter["name"] == "X-Token"
        ]
        assert len(token_parameters) == 1
        assert token_parameters[0]["required"] is False
        assert not {
            parameter["name"].lower()
            for parameter in parameters
            if parameter["in"] in {"query", "header", "path"}
        } & forbidden_authority_names

        if method == "get":
            assert parameters == token_parameters
            assert "requestBody" not in operation

    claim = operations[("post", f"{V2_PREFIX}/projects/{{project_id}}/claim")]
    assert {
        (parameter["in"], parameter["name"], parameter["required"])
        for parameter in claim["parameters"]
    } == {
        ("path", "project_id", True),
        ("header", "X-Token", False),
    }
    claim_schema = claim["requestBody"]["content"]["application/json"]["schema"]
    assert claim["requestBody"]["required"] is True
    assert claim_schema["additionalProperties"] is False
    assert set(claim_schema["properties"]) == {
        "action",
        "registry_version",
        "expected_version",
        "confirmation",
    }
    assert set(claim_schema["required"]) == set(claim_schema["properties"])


def test_openapi_has_exact_v01_action_bijection(supervisor_openapi):
    _, operations = supervisor_openapi
    claim_key = ("post", f"{V2_PREFIX}/projects/{{project_id}}/claim")

    for operation_key, operation in operations.items():
        present_action_extensions = ACTION_EXTENSIONS & set(operation)
        if operation_key == claim_key:
            assert {key: operation[key] for key in ACTION_EXTENSIONS} == {
                "x-operator-action": True,
                "x-action-code": "claim_project",
                "x-action-registry-version": "0.1",
                "x-backend-permission": "project.claim",
            }
        else:
            assert present_action_extensions == {"x-operator-action"}
            assert operation["x-operator-action"] is False
