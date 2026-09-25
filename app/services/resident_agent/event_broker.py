"""Server-Sent Events (SSE) broker for Resident Autonomous Agent.

Streams live agent thought tokens, audit progress, diagnostic events,
and command executions to the frontend console in real time.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResidentAgentEventBroker:
    """In-memory pub/sub broker for SSE streaming."""

    def __init__(self, max_history: int = 150) -> None:
        self._subscribers: List[asyncio.Queue] = []
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()

    async def publish(
        self,
        event_type: str,
        data: Any,
        title: str = "",
        severity: str = "INFO",
    ) -> Dict[str, Any]:
        """Broadcast an event to all active SSE subscribers and store in history."""
        event: Dict[str, Any] = {
            "type": event_type,  # 'thought', 'step', 'command', 'audit', 'telemetry', 'fix'
            "title": title,
            "data": data,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)

            # Distribute to queues
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Subscriber queue is full, dropping event")

        return event

    async def subscribe(self, replay_count: int = 30) -> AsyncGenerator[str, None]:
        """Subscribe to the SSE stream.

        Replays recent history events first, then keeps the connection alive
        yielding newly published events.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=300)

        async with self._lock:
            # Replay recent history
            history_snapshot = self._history[-replay_count:] if replay_count > 0 else []
            for item in history_snapshot:
                queue.put_nowait(item)
            self._subscribers.append(queue)

        try:
            while True:
                # Yield ping heartbeat if no event for 20 seconds
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    ping = {
                        "type": "ping",
                        "title": "Heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    yield f": {json.dumps(ping)}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    def get_recent_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return a copy of the recent event history."""
        return list(self._history[-limit:])

    def clear_history(self) -> None:
        """Clear historical events."""
        self._history.clear()


# Global broker singleton
event_broker = ResidentAgentEventBroker()
