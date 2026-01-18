"""Snapshot system using git for tracking file changes"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import shutil

from codesm.storage.storage import Storage


@dataclass
class Patch:
    """Represents a patch between snapshots"""
    hash: str
    files: list[str] = field(default_factory=list)


@dataclass
class FileDiff:
    """Represents the diff of a single file"""
    file: str
    before: str
    after: str
    additions: int
    deletions: int


class Snapshot:
    """Git-based snapshot system for tracking file changes"""
    
    def __init__(self, work_dir: Path, project_id: Optional[str] = None):
        self.work_dir = Path(work_dir).resolve()
        self.project_id = project_id or self._generate_project_id()
        self._git_dir: Optional[Path] = None
    
    def _generate_project_id(self) -> str:
        """Generate a unique project ID based on the work directory"""
        return hashlib.sha256(str(self.work_dir).encode()).hexdigest()[:16]
    
    @property
    def git_dir(self) -> Path:
        """Get the hidden git directory for snapshots"""
        if self._git_dir is None:
            self._git_dir = Storage.BASE_DIR / "snapshot" / self.project_id
        return self._git_dir
    
    async def _run_git(self, *args: str, check: bool = False) -> tuple[int, str, str]:
        """Run a git command with the snapshot git directory"""
        env = {
            "GIT_DIR": str(self.git_dir),
            "GIT_WORK_TREE": str(self.work_dir),
        }
        
        cmd = ["git"] + list(args)
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.work_dir),
            env={**dict(__import__("os").environ), **env},
        )
        stdout, stderr = await proc.communicate()
        
        if check and proc.returncode != 0:
            raise RuntimeError(f"Git command failed: {stderr.decode()}")
        
        return proc.returncode, stdout.decode(), stderr.decode()
    
    async def _ensure_initialized(self) -> bool:
        """Ensure the snapshot git repository is initialized"""
        if self.git_dir.exists():
            return True
        
        self.git_dir.mkdir(parents=True, exist_ok=True)
        
        code, _, _ = await self._run_git("init")
        if code != 0:
            return False
        
        await self._run_git("config", "core.autocrlf", "false")
        await self._run_git("config", "user.email", "codesm@local")
        await self._run_git("config", "user.name", "codesm")
        
        return True
    
    async def track(self) -> Optional[str]:
        """Track current state of files, returns snapshot hash"""
        if not await self._ensure_initialized():
            return None
        
        await self._run_git("add", ".")
        
        code, stdout, _ = await self._run_git("write-tree")
        if code != 0:
            return None
        
        return stdout.strip()
    
    async def patch(self, from_hash: str) -> Patch:
        """Get list of files changed since the given snapshot"""
        await self._run_git("add", ".")
        
        code, stdout, _ = await self._run_git(
            "-c", "core.autocrlf=false",
            "diff", "--no-ext-diff", "--name-only", from_hash, "--", "."
        )
        
        if code != 0:
            return Patch(hash=from_hash, files=[])
        
        files = [
            str(self.work_dir / f.strip())
            for f in stdout.strip().split("\n")
            if f.strip()
        ]
        
        return Patch(hash=from_hash, files=files)
    
    async def restore(self, snapshot_hash: str) -> bool:
        """Restore files to a snapshot state"""
        code1, _, _ = await self._run_git("read-tree", snapshot_hash)
        if code1 != 0:
            return False
        
        code2, _, _ = await self._run_git("checkout-index", "-a", "-f")
        return code2 == 0
    
    async def revert_files(self, patches: list[Patch]) -> set[str]:
        """Revert specific files from patches"""
        reverted = set()
        
        for patch in patches:
            for file in patch.files:
                if file in reverted:
                    continue
                
                code, _, _ = await self._run_git(
                    "checkout", patch.hash, "--", file
                )
                
                if code != 0:
                    rel_path = Path(file).relative_to(self.work_dir)
                    code2, stdout, _ = await self._run_git(
                        "ls-tree", patch.hash, "--", str(rel_path)
                    )
                    
                    if code2 == 0 and stdout.strip():
                        pass
                    else:
                        try:
                            Path(file).unlink(missing_ok=True)
                        except Exception:
                            pass
                
                reverted.add(file)
        
        return reverted
    
    async def diff(self, from_hash: str) -> str:
        """Get unified diff from a snapshot"""
        await self._run_git("add", ".")
        
        code, stdout, _ = await self._run_git(
            "-c", "core.autocrlf=false",
            "diff", "--no-ext-diff", from_hash, "--", "."
        )
        
        return stdout.strip() if code == 0 else ""
    
    async def diff_full(self, from_hash: str, to_hash: str) -> list[FileDiff]:
        """Get full diff with file contents between two snapshots"""
        result = []
        
        code, stdout, _ = await self._run_git(
            "-c", "core.autocrlf=false",
            "diff", "--no-ext-diff", "--no-renames", "--numstat",
            from_hash, to_hash, "--", "."
        )
        
        if code != 0:
            return result
        
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            
            additions_str, deletions_str, file = parts
            is_binary = additions_str == "-" and deletions_str == "-"
            
            if is_binary:
                before = ""
                after = ""
            else:
                _, before, _ = await self._run_git(
                    "-c", "core.autocrlf=false",
                    "show", f"{from_hash}:{file}"
                )
                _, after, _ = await self._run_git(
                    "-c", "core.autocrlf=false",
                    "show", f"{to_hash}:{file}"
                )
            
            try:
                additions = int(additions_str) if additions_str != "-" else 0
                deletions = int(deletions_str) if deletions_str != "-" else 0
            except ValueError:
                additions = 0
                deletions = 0
            
            result.append(FileDiff(
                file=file,
                before=before,
                after=after,
                additions=additions,
                deletions=deletions,
            ))
        
        return result
    
    async def cleanup(self) -> bool:
        """Remove the snapshot git directory"""
        try:
            if self.git_dir.exists():
                shutil.rmtree(self.git_dir)
            return True
        except Exception:
            return False
