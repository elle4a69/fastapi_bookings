import pytest

from app.core.config import settings
from app.main import create_app


@pytest.mark.parametrize(
    "enable_docs_url, enable_redoc_url, expect_docs, expect_redoc",
    [
        (True, True, True, True),
        (True, False, True, False),
        (False, True, False, True),
        (False, False, False, False),
    ],
)
def test_docs_and_redoc_routes_can_be_toggled(
    monkeypatch,
    enable_docs_url: bool,
    enable_redoc_url: bool,
    expect_docs: bool,
    expect_redoc: bool,
):
    monkeypatch.setattr(settings, "enable_docs_url", enable_docs_url)
    monkeypatch.setattr(settings, "enable_redoc_url", enable_redoc_url)

    app = create_app()
    route_paths = {route.path for route in app.routes}

    assert ("/docs" in route_paths) is expect_docs
    assert ("/redoc" in route_paths) is expect_redoc
