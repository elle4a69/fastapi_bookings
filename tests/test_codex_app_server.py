import pytest
import asyncio
import sys
import json
from httpx import AsyncClient, ASGITransport
from app.services.codex.worker import CodexWorker
from app.services.codex.protocol import JsonRpcNotification
from app.api.routers.codex_events import router, publish_event, CodexEvent
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)

@pytest.mark.asyncio
async def test_codex_worker_rpc():
    script = """
import sys
import json
for line in sys.stdin:
    req = json.loads(line)
    res = {"jsonrpc": "2.0", "id": req["id"], "result": "pong"}
    sys.stdout.write(json.dumps(res) + "\\n")
    sys.stdout.flush()
"""
    worker = CodexWorker([sys.executable, "-c", script])
    await worker.start()
    
    try:
        response = await worker.send_request("ping", {})
        assert response.result == "pong"
    finally:
        await worker.stop()

@pytest.mark.asyncio
async def test_codex_events_stream():
    from app.api.routers.codex_events import event_generator
    from fastapi import Request
    
    class MockRequest:
        def __init__(self):
            self._disconnected = False
        async def is_disconnected(self):
            return self._disconnected
            
    req = MockRequest()
    gen = event_generator(req) # it's an async generator
    
    async def publish_delayed():
        await asyncio.sleep(0.1)
        await publish_event(CodexEvent(event_type="test_event", data={"key": "value"}))
        req._disconnected = True
        
    asyncio.create_task(publish_delayed())
    
    events = []
    async for item in gen:
        events.append(item)
        
    assert len(events) >= 1
    assert any("event: test_event" in e and '{"key": "value"}' in e for e in events)
