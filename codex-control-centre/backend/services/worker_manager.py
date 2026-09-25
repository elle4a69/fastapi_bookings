import logging
from typing import Optional, List, Dict
from backend.services.worker import (
    WorkerProcess,
    CodexWorker,
    resolve_codex_binary,
    resolve_codex_command,
)

__all__ = [
    "WorkerProcess",
    "CodexWorker",
    "WorkerManager",
    "resolve_codex_binary",
    "resolve_codex_command",
    "worker_manager",
]

logger = logging.getLogger(__name__)


class WorkerManager:
    def __init__(
        self,
        command: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        perform_handshake: bool = True,
    ):
        self.command = command or resolve_codex_command()
        self.env = env
        self.perform_handshake = perform_handshake
        self.worker: Optional[WorkerProcess] = None
        self.workers: Dict[str, WorkerProcess] = {}
        self.thread_map: Dict[str, str] = {}
        self.reverse_thread_map: Dict[str, str] = {}

    def register_thread_mapping(self, thread_id: str, codex_thread_id: str):
        self.thread_map[thread_id] = codex_thread_id
        self.reverse_thread_map[codex_thread_id] = thread_id

    async def get_worker(self, cwd: Optional[str] = None) -> WorkerProcess:
        if (
            not self.worker
            or not self.worker.running
            or (self.worker.process and self.worker.process.returncode is not None)
            or (cwd and self.worker.cwd != cwd)
        ):
            if self.worker:
                await self.worker.stop()
            self.worker = WorkerProcess(
                command=self.command,
                env=self.env,
                perform_handshake=self.perform_handshake,
                cwd=cwd,
            )
            await self.worker.start()
        return self.worker

    async def get_worker_for_thread(
        self,
        thread_id: str,
        repo_path: Optional[str] = None,
        base_branch: str = "main"
    ) -> WorkerProcess:
        """
        Retrieves or spawns a dedicated worker process strictly configured with cwd
        bound to the isolated git worktree directory for this thread: worktrees/wt-<threadId>.
        """
        from backend.config import settings
        from backend.services.worktree_service import ensure_thread_worktree

        target_repo = repo_path or str(settings.repo_root)
        wt_path = ensure_thread_worktree(target_repo, thread_id, default_branch=base_branch)
        wt_str = str(wt_path.resolve())

        existing_worker = self.workers.get(thread_id)
        if (
            existing_worker
            and existing_worker.running
            and (not existing_worker.process or existing_worker.process.returncode is None)
        ):
            self.worker = existing_worker
            return existing_worker

        if existing_worker:
            await existing_worker.stop()

        worker = WorkerProcess(
            command=self.command,
            env=self.env,
            perform_handshake=self.perform_handshake,
            cwd=wt_str,
        )
        worker.thread_id = thread_id
        await worker.start()
        self.workers[thread_id] = worker
        self.worker = worker
        return worker

    async def stop(self):
        for w in list(self.workers.values()):
            try:
                await w.stop()
            except Exception as e:
                logger.debug(f"Error stopping thread worker: {e}")
        self.workers.clear()
        if self.worker:
            try:
                await self.worker.stop()
            except Exception as e:
                logger.debug(f"Error stopping default worker: {e}")
            self.worker = None


# Default singleton worker manager using configured Codex App-Server binary and settings
worker_manager = WorkerManager()
