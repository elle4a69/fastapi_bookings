"""Explicit process entrypoint for background queue ownership."""

import asyncio
import logging
import signal
import sys
from contextlib import suppress
from typing import Awaitable, Callable

from .core.config import settings
from .services.outbox_worker import start_outbox_worker, start_sms_outbox_worker


logger = logging.getLogger(__name__)


async def _supervise_worker(
    worker: Callable[[asyncio.Event], Awaitable[None]],
    stop_event: asyncio.Event,
    *,
    grace_seconds: float,
) -> None:
    """Stop accepting work, then bound the current operation by a grace period."""
    worker_task = asyncio.create_task(worker(stop_event))
    stop_waiter = asyncio.create_task(stop_event.wait())
    done, _pending = await asyncio.wait(
        {worker_task, stop_waiter}, return_when=asyncio.FIRST_COMPLETED
    )
    if worker_task in done:
        stop_waiter.cancel()
        with suppress(asyncio.CancelledError):
            await stop_waiter
        await worker_task
        return

    try:
        await asyncio.wait_for(asyncio.shield(worker_task), timeout=grace_seconds)
    except asyncio.TimeoutError:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
    finally:
        stop_waiter.cancel()
        with suppress(asyncio.CancelledError):
            await stop_waiter


async def run(role: str) -> None:
    if role not in {"generic", "sms"}:
        raise ValueError("worker role must be generic or sms")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        stop_event.set()

    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, request_stop)
        except (NotImplementedError, RuntimeError):
            signal.signal(signal_name, lambda *_args: loop.call_soon_threadsafe(request_stop))

    worker = start_outbox_worker if role == "generic" else start_sms_outbox_worker
    await _supervise_worker(
        worker,
        stop_event,
        grace_seconds=settings.OUTBOX_SHUTDOWN_GRACE_SECONDS,
    )


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"generic", "sms"}:
        raise SystemExit("usage: python -m app.worker {generic|sms}")
    try:
        asyncio.run(run(sys.argv[1]))
    except KeyboardInterrupt:
        logger.info("worker_interrupted")


if __name__ == "__main__":
    main()
