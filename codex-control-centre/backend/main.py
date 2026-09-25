import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.database import engine
from backend.services.event_service import broker
from backend.services.worker_manager import worker_manager
from backend.middleware.logging import CorrelationLoggingMiddleware, RedactingFilter
from backend.middleware.auth import verify_auth
from backend.routers import events, threads, turns, worktrees, governance, diagnostics, projects
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
        init_telemetry(app)
    except Exception as e:
        logger.error(f"Error initializing OpenTelemetry: {e}")
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
    allow_origins=["http://127.0.0.1:5180", "http://localhost:5180", "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(events.router, dependencies=[Depends(verify_auth)])
app.include_router(threads.router, dependencies=[Depends(verify_auth)])
app.include_router(turns.router, dependencies=[Depends(verify_auth)])
app.include_router(worktrees.router, dependencies=[Depends(verify_auth)])
app.include_router(governance.router, dependencies=[Depends(verify_auth)])
app.include_router(projects.router, dependencies=[Depends(verify_auth)])
app.include_router(diagnostics.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Codex Control Centre API"}
