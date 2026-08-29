import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator, Dict, Any

router = APIRouter(prefix="/codex", tags=["codex"])

class CodexEvent(BaseModel):
    event_type: str
    data: Dict[str, Any]

event_queues = []

@router.post("/events/publish")
async def publish_event(event: CodexEvent):
    for queue in event_queues:
        await queue.put(event)
    return {"status": "ok"}

async def event_generator(request: Request) -> AsyncGenerator[str, None]:
    queue = asyncio.Queue()
    event_queues.append(queue)
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"event: {event.event_type}\ndata: {json.dumps(event.data)}\n\n"
            except asyncio.TimeoutError:
                yield f"event: ping\ndata: {{}}\n\n"
    finally:
        event_queues.remove(queue)

@router.get("/events")
async def codex_events_stream(request: Request):
    return StreamingResponse(event_generator(request), media_type="text/event-stream")
