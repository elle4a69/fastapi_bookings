import asyncio
import shutil
import tempfile
from typing import Optional
from pathlib import Path

class WorkspaceManager:
    def __init__(self, base_repo_path: str):
        self.base_repo_path = Path(base_repo_path).resolve()

    async def _run_git(self, *args, cwd: Optional[Path] = None) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=cwd or self.base_repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}\n{stderr.decode()}")
        return stdout.decode().strip()

    async def create_worktree(self, branch_name: str) -> Path:
        """Create a new worktree and branch for an agent task."""
        worktree_path = Path(tempfile.mkdtemp(prefix=f"codex_wt_{branch_name}_"))
        
        try:
            await self._run_git("worktree", "add", "-b", branch_name, str(worktree_path))
        except RuntimeError as e:
            shutil.rmtree(worktree_path, ignore_errors=True)
            raise e
            
        return worktree_path

    async def cleanup_worktree(self, worktree_path: Path, branch_name: str, force: bool = True):
        """Remove worktree and delete the branch."""
        try:
            if force:
                await self._run_git("worktree", "remove", "-f", str(worktree_path))
            else:
                await self._run_git("worktree", "remove", str(worktree_path))
        except RuntimeError:
            pass 
            
        try:
            if force:
                await self._run_git("branch", "-D", branch_name)
            else:
                await self._run_git("branch", "-d", branch_name)
        except RuntimeError:
            pass
            
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)
