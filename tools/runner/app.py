from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER_DIR = Path(__file__).resolve().parent
SWEEP_DIR = PROJECT_ROOT / "tools" / "postman-sweep"
SWEEP_SCRIPT = SWEEP_DIR / "launch-and-save-authenticated-sweep.ps1"
STATE_DIR = RUNNER_DIR / "state"
JOBS_DIR = STATE_DIR / "jobs"

STATE_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()




@dataclass
class Job:
    id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    pid: int | None = None
    command: list[str] = field(default_factory=list)
    log_path: str = ""
    result_dir: str | None = None
    error: str | None = None


class RunSweepRequest(BaseModel):
    start_delay_seconds: int = Field(default=5, ge=0, le=120)
    request_delay_milliseconds: int = Field(default=100, ge=0, le=5000)


class JobResponse(BaseModel):
    id: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    pid: int | None = None
    log_path: str
    result_dir: str | None = None
    error: str | None = None


app = FastAPI(
    title="FastAPI Bookings Local Runner",
    version="1.0.0",
    description="Restricted local runner for the authenticated Postman/Newman API sweep.",
)

_jobs: dict[str, Job] = {}
_processes: dict[str, subprocess.Popen[str]] = {}
_lock = threading.RLock()




def persist_job(job: Job) -> None:
    (JOBS_DIR / f"{job.id}.json").write_text(json.dumps(asdict(job), indent=2), encoding="utf-8")


def public_job(job: Job) -> JobResponse:
    return JobResponse(**{key: value for key, value in asdict(job).items() if key != "command"})


def find_latest_result_dir(started_after: float) -> Path | None:
    reports_dir = SWEEP_DIR / "reports"
    if not reports_dir.exists():
        return None
    candidates = [
        path
        for path in reports_dir.glob("run-*")
        if path.is_dir() and path.stat().st_mtime >= started_after - 2
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def run_job(job_id: str, payload: RunSweepRequest) -> None:
    started_epoch = time.time()
    log_file = JOBS_DIR / f"{job_id}.log"
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SWEEP_SCRIPT),
        "-StartDelaySeconds",
        str(payload.start_delay_seconds),
        "-RequestDelayMilliseconds",
        str(payload.request_delay_milliseconds),
    ]

    with _lock:
        job = _jobs[job_id]
        job.status = "running"
        job.started_at = utc_now()
        job.command = command
        persist_job(job)

    try:
        with log_file.open("w", encoding="utf-8", errors="replace") as stream:
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            with _lock:
                _processes[job_id] = process
                job.pid = process.pid
                persist_job(job)
            exit_code = process.wait()

        result_dir = find_latest_result_dir(started_epoch)
        with _lock:
            job.exit_code = exit_code
            job.finished_at = utc_now()
            job.result_dir = str(result_dir) if result_dir else None
            if job.status != "cancelled":
                job.status = "completed" if exit_code == 0 else "failed"
            persist_job(job)
    except Exception as exc:
        with _lock:
            job.status = "failed"
            job.finished_at = utc_now()
            job.error = f"{type(exc).__name__}: {exc}"
            persist_job(job)
    finally:
        with _lock:
            _processes.pop(job_id, None)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "fastapi-bookings-runner",
        "sweep_script_exists": SWEEP_SCRIPT.exists(),
    }


@app.post("/run/postman-sweep", response_model=JobResponse)
def start_postman_sweep(payload: RunSweepRequest) -> JobResponse:
    if not SWEEP_SCRIPT.exists():
        raise HTTPException(status_code=500, detail=f"Sweep script not found: {SWEEP_SCRIPT}")

    with _lock:
        active = next((job for job in _jobs.values() if job.status in {"queued", "running"}), None)
        if active:
            raise HTTPException(status_code=409, detail=f"Job {active.id} is already {active.status}")

        job_id = uuid.uuid4().hex
        log_path = JOBS_DIR / f"{job_id}.log"
        job = Job(
            id=job_id,
            status="queued",
            created_at=utc_now(),
            log_path=str(log_path),
        )
        _jobs[job_id] = job
        persist_job(job)

    thread = threading.Thread(target=run_job, args=(job_id, payload), daemon=True)
    thread.start()
    return public_job(job)


@app.get("/status/{job_id}", response_model=JobResponse)
def get_status(job_id: str) -> JobResponse:
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        job_file = JOBS_DIR / f"{job_id}.json"
        if not job_file.exists():
            raise HTTPException(status_code=404, detail="Job not found")
        data = json.loads(job_file.read_text(encoding="utf-8"))
        job = Job(**data)
    return public_job(job)


@app.get("/jobs", response_model=list[JobResponse])
def list_jobs(limit: int = Query(default=20, ge=1, le=100)) -> list[JobResponse]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda item: item.created_at, reverse=True)
    return [public_job(job) for job in jobs[:limit]]


@app.get("/logs/{job_id}", response_class=PlainTextResponse)
def get_logs(job_id: str, tail_lines: int = Query(default=300, ge=1, le=5000)) -> str:
    log_path = JOBS_DIR / f"{job_id}.log"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log not found")
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-tail_lines:])


@app.post("/cancel/{job_id}", response_model=JobResponse)
def cancel_job(job_id: str) -> JobResponse:
    with _lock:
        job = _jobs.get(job_id)
        process = _processes.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail=f"Job is already {job.status}")

    if process and process.poll() is None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, capture_output=True)
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        finally:
            pass

    with _lock:
        job.status = "cancelled"
        job.finished_at = utc_now()
        persist_job(job)
    return public_job(job)


def latest_completed_job() -> Job:
    with _lock:
        completed = [job for job in _jobs.values() if job.result_dir]
    if completed:
        return max(completed, key=lambda item: item.finished_at or item.created_at)

    job_files = sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for job_file in job_files:
        data = json.loads(job_file.read_text(encoding="utf-8"))
        if data.get("result_dir"):
            return Job(**data)
    raise HTTPException(status_code=404, detail="No completed sweep result found")


@app.get("/results/latest")
def latest_results() -> dict[str, object]:
    job = latest_completed_job()
    result_dir = Path(job.result_dir or "")
    files = sorted(str(path) for path in result_dir.iterdir()) if result_dir.exists() else []
    summary_file = next(result_dir.glob("*summary*.json"), None) if result_dir.exists() else None
    summary: object | None = None
    if summary_file:
        try:
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary = summary_file.read_text(encoding="utf-8", errors="replace")
    return {"job": public_job(job).model_dump(), "files": files, "summary": summary}


@app.get("/results/{job_id}/file/{filename}")
def download_result_file(job_id: str, filename: str) -> FileResponse:
    job = get_status(job_id)
    if not job.result_dir:
        raise HTTPException(status_code=404, detail="Job has no result directory")
    result_dir = Path(job.result_dir).resolve()
    requested = (result_dir / filename).resolve()
    if requested.parent != result_dir or not requested.is_file():
        raise HTTPException(status_code=404, detail="Result file not found")
    return FileResponse(requested)
