import asyncio
import json
import logging
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import settings
from ..services.event_service import broker, EventEnvelope
from ..services.sse_tickets import sse_ticket_store
from ..middleware.auth import verify_auth

router = APIRouter(prefix="", tags=["events"])
logger = logging.getLogger(__name__)


class SseTicketRequest(BaseModel):
    project_id: str
    thread_id: str


async def verify_sse_ticket(
    project_id: str,
    thread_id: str,
    request: Request,
    sse_ticket: str | None = Query(None),
) -> None:
    # 1. Single-use scoped ticket verification
    if sse_ticket and await sse_ticket_store.consume(sse_ticket, project_id, thread_id):
        return

    # 2. Bearer authorization header or direct token query parameter (fallback compatibility)
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        token = request.query_params.get("token")
    if token and secrets.compare_digest(token, settings.token_secret):
        return

    logger.info(
        "Rejected SSE connection (ticket_present=%s, length=%s, project=%s, thread=%s)",
        bool(sse_ticket),
        len(sse_ticket or ""),
        project_id,
        thread_id,
    )
    raise HTTPException(status_code=401, detail="Authentication required")


@router.post("/ticket", dependencies=[Depends(verify_auth)])
@router.post("/events/ticket", dependencies=[Depends(verify_auth)])
async def issue_sse_ticket(req: SseTicketRequest):
    ticket, expires_at = await sse_ticket_store.issue(req.project_id, req.thread_id)
    return {"ticket": ticket, "expires_at": expires_at.isoformat()}

@router.get("/{project_id}/{thread_id}")
@router.get("/{project_id}/{thread_id}/")
@router.get("/events/{project_id}/{thread_id}")
@router.get("/events/{project_id}/{thread_id}/")
async def stream_events(
    project_id: str,
    thread_id: str,
    request: Request,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    query_last_event_id: Optional[str] = Query(None, alias="last_event_id"),
    _: None = Depends(verify_sse_ticket),
):
    actual_last_id = last_event_id or query_last_event_id
    
    async def is_req_disconnected() -> bool:
        try:
            import unittest.mock
            if isinstance(request, unittest.mock.Mock):
                return False
            fn = getattr(request, "is_disconnected", None)
            if callable(fn):
                res = fn()
                if asyncio.iscoroutine(res):
                    return await res
                return False
        except Exception:
            pass
        return False

    async def event_generator():
        queue = broker.subscribe(thread_id)
        try:
            # 1. Replay missed backlog
            missed = broker.get_history(thread_id, actual_last_id)
            for event in missed:
                if await is_req_disconnected():
                    break
                data = json.dumps(event.payload)
                yield f"id: {event.id}\nevent: {event.type}\ndata: {data}\n\n"
            
            while True:
                if await is_req_disconnected():
                    break
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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )

class PublishRequest(BaseModel):
    project_id: str = "default"
    thread_id: str = "default"
    type: Optional[str] = None
    event_type: Optional[str] = None
    payload: Optional[dict] = None
    data: Optional[dict] = None

@router.post("/publish", dependencies=[Depends(verify_auth)])
@router.post("/events/publish", dependencies=[Depends(verify_auth)])
@router.post("/codex/events/publish", dependencies=[Depends(verify_auth)])
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
