"""Short-lived, single-use authorization tickets for browser EventSource streams."""

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.config import settings


@dataclass
class SseTicket:
    project_id: str
    thread_id: str
    expires_at: datetime


class SseTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, SseTicket] = {}
        self._lock = asyncio.Lock()

    async def issue(self, project_id: str, thread_id: str) -> tuple[str, datetime]:
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(1, min(settings.sse_ticket_ttl_seconds, 300))
        )
        ticket = secrets.token_urlsafe(32)
        async with self._lock:
            now = datetime.now(timezone.utc)
            self._tickets = {
                value: record for value, record in self._tickets.items()
                if record.expires_at >= now
            }
            self._tickets[ticket] = SseTicket(project_id, thread_id, expires_at)
        return ticket, expires_at

    async def consume(self, ticket: str, project_id: str, thread_id: str) -> bool:
        async with self._lock:
            record = self._tickets.get(ticket)
            if not record:
                return False
            now = datetime.now(timezone.utc)
            if record.expires_at < now:
                self._tickets.pop(ticket, None)
                return False

            if not (
                secrets.compare_digest(record.project_id, project_id)
                and secrets.compare_digest(record.thread_id, thread_id)
            ):
                return False

            # Valid consumption is atomic under the store lock. Reconnects must
            # mint a fresh ticket, so copied credentials cannot replay.
            self._tickets.pop(ticket, None)
            return True


sse_ticket_store = SseTicketStore()
