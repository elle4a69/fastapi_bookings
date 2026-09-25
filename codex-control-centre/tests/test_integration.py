from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Codex Control Centre API"}

def test_publish_event():
    from backend.config import settings
    response = client.post(
        "/codex/events/publish",
        json={"project_id": "test_p", "thread_id": "test_t", "type": "test_event", "payload": {"key": "value"}},
        headers={"Authorization": f"Bearer {settings.token_secret}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == "test_p"
    assert data["type"] == "test_event"
