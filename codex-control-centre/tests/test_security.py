from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings

client = TestClient(app)

def test_public_endpoint():
    response = client.get("/")
    assert response.status_code == 200

def test_protected_endpoint_unauthenticated():
    response = client.post("/codex/events/publish", json={"event_type": "test", "data": {}})
    assert response.status_code == 401

def test_protected_endpoint_invalid_token():
    response = client.post("/codex/events/publish", 
                           json={"event_type": "test", "data": {}},
                           headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401

def test_protected_endpoint_valid_token():
    response = client.post("/codex/events/publish", 
                           json={"event_type": "test", "data": {}},
                           headers={"Authorization": f"Bearer {settings.token_secret}"})
    assert response.status_code == 200

def test_cors_headers_allowed_origin():
    response = client.options("/codex/events/publish", 
                              headers={"Origin": "http://127.0.0.1:5180",
                                       "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5180"

def test_cors_headers_unauthorized_origin():
    response = client.options("/codex/events/publish", 
                              headers={"Origin": "http://evil.com",
                                       "Access-Control-Request-Method": "POST"})
    # It might return 200 but without the allow-origin header, or it might fail
    assert response.headers.get("access-control-allow-origin") is None
