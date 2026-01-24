"""Codebase indexing system for semantic code search"""

from .indexer import ProjectIndexer

__all__ = ["ProjectIndexer", "search"]


async def search(root, query: str, top_k: int = 5) -> list[dict]:
    """Convenience function to search a project"""
    from pathlib import Path
    indexer = ProjectIndexer(Path(root))
    return await indexer.search(query, top_k)
