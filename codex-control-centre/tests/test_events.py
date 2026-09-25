import asyncio
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from backend.routers.events import router
from backend.services.event_service import broker, EventEnvelope
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_broker():
    broker.subscribers.clear()
    broker.history.clear()
    broker.sequences.clear()

def test_event_envelope_structure():
    event = EventEnvelope(
        project_id="proj_1",
        thread_id="thread_1",
        type="test_event",
        payload={"msg": "hello"}
    )
    broker.publish_event(event)
    
    assert event.id.startswith("evt_")
    assert event.schema_version == "1.0"
    assert event.project_id == "proj_1"
    assert event.thread_id == "thread_1"
    assert event.sequence == 1
    assert event.type == "test_event"
    assert event.payload == {"msg": "hello"}
    
    dt = datetime.fromisoformat(event.occurred_at)
    assert dt.tzname() == "UTC"

@pytest.mark.asyncio
async def test_scoped_subscription_isolation():
    queue1 = broker.subscribe("thread_1")
    queue2 = broker.subscribe("thread_2")

    broker.publish_event(EventEnvelope(project_id="p", thread_id="thread_1", type="t1", payload={}))
    broker.publish_event(EventEnvelope(project_id="p", thread_id="thread_2", type="t2", payload={}))

    recv1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
    assert recv1.thread_id == "thread_1"
    assert queue1.empty()

    recv2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
    assert recv2.thread_id == "thread_2"
    assert queue2.empty()

def test_reconnection_backlog_replay():
    events = []
    for i in range(3):
        e = EventEnvelope(project_id="p", thread_id="t", type=f"type_{i}", payload={})
        events.append(broker.publish_event(e))

    history = broker.get_history("t", last_event_id=events[0].id)
    assert len(history) == 2
    assert history[0].id == events[1].id
    assert history[0].sequence == 2
    assert history[1].id == events[2].id
    assert history[1].sequence == 3

def test_bounded_history_buffer():
    for i in range(150):
        broker.publish_event(EventEnvelope(project_id="p", thread_id="t_bound", type="m", payload={}))
    
    history = broker.get_history("t_bound", last_event_id="dummy")
    assert len(history) == 100
    assert history[-1].sequence == 150
    assert history[0].sequence == 51

def test_bounded_subscriber_queue_slow_consumer():
    queue = broker.subscribe("t_slow")
    
    # maxsize is 100
    for i in range(150):
        broker.publish_event(EventEnvelope(project_id="p", thread_id="t_slow", type="m", payload={"i": i}))
    
    # Should not crash and should have kept the queue alive
    assert queue.qsize() > 0

def test_publish_event_endpoint():
    response = client.post("/codex/events/publish", json={
        "project_id": "proj_api",
        "thread_id": "thread_api",
        "type": "api_msg",
        "payload": {"data": 123}
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == "proj_api"
    assert data["thread_id"] == "thread_api"
    assert data["type"] == "api_msg"
    assert data["payload"] == {"data": 123}
    assert data["sequence"] == 1
