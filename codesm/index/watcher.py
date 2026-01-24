"""Background polling watcher for incremental index updates"""

import asyncio
from pathlib import Path

from .indexer import ProjectIndexer


class IndexWatcher:
    """Polls for file changes and updates index incrementally"""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False
        self._indexer: ProjectIndexer | None = None

    def start(self, root: Path, interval: int = 300):
        """Start background polling task"""
        if self._task is not None:
            return

        self._indexer = ProjectIndexer(root)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(interval))

    def stop(self):
        """Stop polling"""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self, interval: int):
        """Main polling loop"""
        while self._running:
            try:
                if self._indexer:
                    await self._indexer.update_incremental()
            except Exception:
                pass
            await asyncio.sleep(interval)
