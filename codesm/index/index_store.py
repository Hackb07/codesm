"""Persistent storage for codebase index"""

import pickle
from pathlib import Path
from typing import Any

from ..storage.storage import Storage

CHUNKING_VERSION = 1
EMBEDDING_MODEL = "text-embedding-3-small"

CACHE_DIR = Path.home() / ".cache" / "codesm" / "index"


class IndexStore:
    """Handles persistent storage for index metadata and embeddings"""

    @staticmethod
    def _meta_key(project_id: str) -> list[str]:
        return ["index", "project", project_id, "meta"]

    @staticmethod
    def get_cache_path(project_id: str) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR / f"{project_id}.pkl"

    @classmethod
    def load_meta(cls, project_id: str) -> dict | None:
        return Storage.read(cls._meta_key(project_id))

    @classmethod
    def save_meta(cls, project_id: str, meta: dict):
        Storage.write(cls._meta_key(project_id), meta)

    @classmethod
    def load_chunks(cls, project_id: str) -> list[dict] | None:
        """Load chunks with embeddings from pickle cache"""
        import numpy as np

        cache_path = cls.get_cache_path(project_id)
        if not cache_path.exists():
            return None
        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)
            for chunk in data:
                if "embedding" in chunk:
                    chunk["embedding"] = np.array(chunk["embedding"])
            return data
        except Exception:
            return None

    @classmethod
    def save_chunks(cls, project_id: str, chunks: list[dict]):
        """Save chunks with embeddings to pickle cache"""
        cache_path = cls.get_cache_path(project_id)
        try:
            chunks_to_save = []
            for chunk in chunks:
                chunk_copy = chunk.copy()
                if "embedding" in chunk_copy:
                    emb = chunk_copy["embedding"]
                    chunk_copy["embedding"] = emb.tolist() if hasattr(emb, "tolist") else emb
                chunks_to_save.append(chunk_copy)
            with open(cache_path, "wb") as f:
                pickle.dump(chunks_to_save, f)
        except Exception:
            pass
