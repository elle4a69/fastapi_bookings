import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Set, Optional
from collections import deque
from pydantic import BaseModel, Field

class EventEnvelope(BaseModel):
    id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")
    schema_version: str = "1.0"
    project_id: str
    thread_id: str
    sequence: int = 0
    type: str
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict

class EventBroker:
    def __init__(self):
        # thread_id -> Set of asyncio.Queue
        self.subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # thread_id -> deque of EventEnvelope
        self.history: Dict[str, deque] = {}
        # thread_id -> int (next sequence number)
        self.sequences: Dict[str, int] = {}
        self.history_size = 100

    def publish_event(self, event: EventEnvelope) -> EventEnvelope:
        thread_id = event.thread_id
        
        # Initialize thread state if needed
        if thread_id not in self.sequences:
            self.sequences[thread_id] = 1
            self.history[thread_id] = deque(maxlen=self.history_size)
        if thread_id not in self.subscribers:
            self.subscribers[thread_id] = set()

        # Assign sequence
        event.sequence = self.sequences[thread_id]
        self.sequences[thread_id] += 1
        
        self.history[thread_id].append(event)
        
        # Broadcast to subscribers
        for queue in self.subscribers.get(thread_id, set()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

        return event

    def subscribe(self, thread_id: str) -> asyncio.Queue:
        if thread_id not in self.subscribers:
            self.subscribers[thread_id] = set()
        
        queue = asyncio.Queue(maxsize=100)
        self.subscribers[thread_id].add(queue)
        return queue

    def unsubscribe(self, thread_id: str, queue: asyncio.Queue):
        if thread_id in self.subscribers and queue in self.subscribers[thread_id]:
            self.subscribers[thread_id].remove(queue)

    def get_history(self, thread_id: str, last_event_id: Optional[str] = None) -> list[EventEnvelope]:
        if thread_id not in self.history:
            return []
        
        events = list(self.history[thread_id])
        if not last_event_id:
            return events
            
        for i, event in enumerate(events):
            if event.id == last_event_id:
                return events[i+1:]
                
        # If not found in history (buffer overflow or invalid id), returning all history is safer or none. 
        # We'll return all history to avoid missing if they disconnected a while ago.
        return events

    async def close_all(self):
        """Signals all active SSE subscriber queues to terminate immediately and clears subscriber map."""
        close_event = EventEnvelope(
            project_id="system",
            thread_id="system",
            type="__close__",
            payload={"reason": "server_shutdown"}
        )
        for thread_id, queue_set in list(self.subscribers.items()):
            for q in list(queue_set):
                try:
                    q.put_nowait(close_event)
                except Exception:
                    pass
        self.subscribers.clear()

    def publish_codex_notification(
        self,
        method: str,
        params: dict,
        project_id: str = "default",
        thread_id: str = "",
        turn_id: Optional[int] = None
    ) -> Optional[EventEnvelope]:
        from backend.services.protocol import normalize_codex_notification
        envelope = normalize_codex_notification(method, params, project_id, thread_id, turn_id)
        if envelope:
            return self.publish_event(envelope)
        return None

broker = EventBroker()


def normalize_codex_notification(
    method: str,
    params: dict,
    project_id: str = "default",
    thread_id: str = "",
    turn_id: Optional[int] = None
) -> Optional[EventEnvelope]:
    from backend.services.protocol import normalize_codex_notification as _norm
    return _norm(method, params, project_id, thread_id, turn_id)
