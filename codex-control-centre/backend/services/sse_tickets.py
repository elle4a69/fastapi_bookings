"""Short-lived, single-use authorization tickets for browser EventSource streams."""

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.config import settings


@dataclass
class SseTicket:
    project_id: str
    thread_id: str
    expires_at: datetime
    consumed_at: Optional[datetime] = None


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

            # Allow a short grace window (15s) after first use for browser retry / reconnection / StrictMode
            if record.consumed_at is not None:
                if (now - record.consumed_at).total_seconds() > 15:
                    self._tickets.pop(ticket, None)
                    return False
            else:
                record.consumed_at = now
            return True


sse_ticket_store = SseTicketStore()
