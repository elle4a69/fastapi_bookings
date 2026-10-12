import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.database import engine, init_db
from backend.services.event_service import broker
from backend.services.worker_manager import worker_manager
from backend.middleware.logging import CorrelationLoggingMiddleware, RedactingFilter
from backend.middleware.auth import verify_auth
from backend.routers import events, threads, turns, worktrees, governance, diagnostics, projects, settings as settings_router
from backend.services.telemetry import init_telemetry, shutdown_telemetry

# Configure root logger with RedactingFilter to ensure secrets are never leaked
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
for handler in logging.root.handlers:
    handler.addFilter(RedactingFilter())

logger = logging.getLogger("codex.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Codex Control Centre API starting up...")
    try:
        init_db()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

    try:
        init_telemetry(app)
    except Exception as e:
        logger.error(f"Error initializing OpenTelemetry: {e}")

    # Startup sweep: mark orphaned active turns as interrupted
    try:
        from datetime import datetime, timezone
        from backend.database import SessionLocal
        from backend.models.codex import Turn
        with SessionLocal() as db:
            active_turns = db.query(Turn).filter(Turn.status == "active").all()
            if active_turns:
                logger.info("Startup sweep: found %d orphaned active turn(s); marking as interrupted.", len(active_turns))
                for turn in active_turns:
                    worker = worker_manager.get_active_worker_for_thread(turn.thread_id)
                    if not worker or not worker_manager._is_running(worker):
                        turn.status = "interrupted"
                        turn.completed_at = datetime.now(timezone.utc)
                db.commit()
    except Exception as e:
        logger.error(f"Error during orphaned turn startup sweep: {e}")

    yield
    # Graceful Shutdown
    logger.info("Initiating graceful shutdown for Codex Control Centre API...")
    try:
        shutdown_telemetry()
    except Exception as e:
        logger.error(f"Error shutting down OpenTelemetry: {e}")
    # 1. Close all active SSE subscribers to break client streams immediately
    try:
        await broker.close_all()
    except Exception as e:
        logger.error(f"Error closing SSE subscribers: {e}")

    # 2. Terminate any running worker supervisor child processes cleanly
    try:
        await worker_manager.stop()
    except Exception as e:
        logger.error(f"Error stopping worker manager: {e}")

    # 3. Dispose SQLAlchemy database engine connection pool
    try:
        engine.dispose()
    except Exception as e:
        logger.error(f"Error disposing database engine: {e}")

    logger.info("Codex Control Centre API shutdown complete.")


app = FastAPI(title="Codex Control Centre", lifespan=lifespan)

# Add Correlation and Structured Logging Middleware
app.add_middleware(CorrelationLoggingMiddleware)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4600",
        "http://127.0.0.1:4600",
        "http://localhost:5180",
        "http://127.0.0.1:5180",
        "http://localhost:4500",
        "http://127.0.0.1:4500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# EventSource cannot attach an Authorization header.  The event stream has its
# own one-time ticket dependency; the ticket-minting and publish routes retain
# bearer authentication in their route declarations.
app.include_router(events.router)
app.include_router(threads.router, dependencies=[Depends(verify_auth)])
app.include_router(turns.router, dependencies=[Depends(verify_auth)])
app.include_router(worktrees.router, dependencies=[Depends(verify_auth)])
app.include_router(governance.router, dependencies=[Depends(verify_auth)])
app.include_router(projects.router, dependencies=[Depends(verify_auth)])
app.include_router(settings_router.router, dependencies=[Depends(verify_auth)])
app.include_router(diagnostics.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Codex Control Centre API"}
