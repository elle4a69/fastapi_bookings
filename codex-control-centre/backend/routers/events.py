import asyncio
import json
from typing import Optional
from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.event_service import broker, EventEnvelope

router = APIRouter(prefix="/codex", tags=["events"])

@router.get("/events/{project_id}/{thread_id}")
async def stream_events(
    project_id: str,
    thread_id: str,
    request: Request,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    query_last_event_id: Optional[str] = Query(None, alias="last_event_id")
):
    actual_last_id = last_event_id or query_last_event_id
    
    async def event_generator():
        queue = broker.subscribe(thread_id)
        try:
            # 1. Replay missed backlog
            missed = broker.get_history(thread_id, actual_last_id)
            for event in missed:
                data = json.dumps(event.payload)
                yield f"id: {event.id}\nevent: {event.type}\ndata: {data}\n\n"
            
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                    if getattr(event, "type", None) == "__close__":
                        break
                    data = json.dumps(event.payload)
                    yield f"id: {event.id}\nevent: {event.type}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
                except (asyncio.CancelledError, GeneratorExit):
                    break
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            broker.unsubscribe(thread_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

class PublishRequest(BaseModel):
    project_id: str = "default"
    thread_id: str = "default"
    type: Optional[str] = None
    event_type: Optional[str] = None
    payload: Optional[dict] = None
    data: Optional[dict] = None

@router.post("/events/publish")
async def publish_event(req: PublishRequest):
    event_type = req.type or req.event_type or "event"
    payload = req.payload if req.payload is not None else (req.data or {})
    event = EventEnvelope(
        project_id=req.project_id,
        thread_id=req.thread_id,
        type=event_type,
        payload=payload
    )
    published = broker.publish_event(event)
    return published
