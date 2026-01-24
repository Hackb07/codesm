"""Semantic memory retrieval"""

import numpy as np

from ..search.embeddings import get_embeddings
from .models import MemoryItem
from .store import MemoryStore


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class MemoryRetrieval:
    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    async def query(
        self,
        query_text: str,
        project_id: str | None = None,
        top_k: int = 5,
        include_global: bool = True,
        types: list[str] | None = None,
    ) -> list[MemoryItem]:
        items: list[MemoryItem] = []

        if project_id is not None:
            items.extend(self.store.list(project_id))

        if include_global:
            items.extend(self.store.list(None))

        if types:
            items = [item for item in items if item.type in types]

        if not items:
            return []

        items_needing_embedding = [item for item in items if item.embedding is None]
        if items_needing_embedding:
            texts = [item.text for item in items_needing_embedding]
            embeddings = await get_embeddings(texts)
            for item, embedding in zip(items_needing_embedding, embeddings):
                item.embedding = embedding
                self.store.upsert(item)

        query_embedding = (await get_embeddings([query_text]))[0]

        scored: list[tuple[float, MemoryItem]] = []
        for item in items:
            if item.embedding:
                score = cosine_similarity(query_embedding, item.embedding)
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [item for _, item in scored[:top_k]]
