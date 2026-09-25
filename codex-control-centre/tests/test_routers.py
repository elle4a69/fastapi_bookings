import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database import Base, set_sqlite_pragma, get_db

@pytest.fixture
def db_engine():
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    from sqlalchemy import event
    event.listen(engine, "connect", set_sqlite_pragma)
    
    Base.metadata.create_all(bind=engine)
    yield engine

@pytest.fixture
def client(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    
    # Disable auth for testing
    from backend.middleware.auth import verify_auth
    app.dependency_overrides[verify_auth] = lambda: None
    
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_thread_crud(client):
    # Create thread
    res = client.post("/codex/threads", json={"project_id": "test_proj", "title": "My Thread"})
    assert res.status_code == 200
    thread_id = res.json()["id"]
    
    # List threads
    res = client.get("/codex/threads")
    assert res.status_code == 200
    assert len(res.json()) == 1
    
    # Get thread
    res = client.get(f"/codex/threads/{thread_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "My Thread"
    
    # Update thread
    res = client.patch(f"/codex/threads/{thread_id}", json={"title": "Updated Thread", "is_pinned": True})
    assert res.status_code == 200
    assert res.json()["title"] == "Updated Thread"
    assert res.json()["is_pinned"] is True
    
    # Delete thread
    res = client.delete(f"/codex/threads/{thread_id}")
    assert res.status_code == 200
    
    res = client.get(f"/codex/threads/{thread_id}")
    assert res.status_code == 404

def test_turn_crud(client, monkeypatch):
    # Mock worker manager to avoid actual process spawning in API test
    class MockWorker:
        async def send_request(self, method, params):
            pass
    
    class MockWorkerManager:
        async def get_worker(self):
            return MockWorker()
            
    from backend.routers import turns
    monkeypatch.setattr(turns, "worker_manager", MockWorkerManager())

    # Create thread first
    res = client.post("/codex/threads", json={"project_id": "test_proj", "title": "My Thread"})
    thread_id = res.json()["id"]
    
    # Start turn
    res = client.post("/codex/turns/start", json={"thread_id": thread_id, "prompt": "Hello"})
    assert res.status_code == 200
    turn_id = res.json()["turn_id"]
    
    # Steer turn
    res = client.post("/codex/turns/steer", json={"thread_id": thread_id, "turn_id": turn_id, "instruction": "Do better"})
    assert res.status_code == 200
    
    # Interrupt turn
    res = client.post("/codex/turns/interrupt", json={"thread_id": thread_id, "turn_id": turn_id})
    assert res.status_code == 200
    
    # Respond approval
    res = client.post("/codex/approvals/respond", json={"thread_id": thread_id, "tool_call_id": "tc_1", "approved": True})
    assert res.status_code == 200
