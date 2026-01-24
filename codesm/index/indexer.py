"""Main indexing logic for codebase search"""

from datetime import datetime
from pathlib import Path

import numpy as np

from ..search.embeddings import get_embeddings
from ..util.project_id import get_project_id
from .chunking import extract_chunks, get_code_files
from .index_store import CHUNKING_VERSION, EMBEDDING_MODEL, IndexStore


class ProjectIndexer:
    """Indexes a project for semantic code search"""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.project_id = get_project_id(self.root)
        self._chunks: list[dict] | None = None

    def is_stale(self) -> bool:
        """Check if index needs rebuild due to version/model change"""
        meta = IndexStore.load_meta(self.project_id)
        if not meta:
            return True
        if meta.get("chunking_version") != CHUNKING_VERSION:
            return True
        if meta.get("embedding_model") != EMBEDDING_MODEL:
            return True
        return False

    def _get_current_file_state(self) -> dict[str, dict]:
        """Get current mtime/size for all code files"""
        files = get_code_files(self.root)
        state = {}
        for f in files:
            try:
                stat = f.stat()
                state[str(f)] = {"mtime": stat.st_mtime, "size": stat.st_size}
            except OSError:
                pass
        return state

    def _detect_changes(self, old_state: dict[str, dict]) -> tuple[list[Path], list[str]]:
        """Detect changed/new files and deleted files"""
        current_state = self._get_current_file_state()
        
        changed = []
        for path_str, info in current_state.items():
            old_info = old_state.get(path_str)
            if not old_info or old_info["mtime"] != info["mtime"] or old_info["size"] != info["size"]:
                changed.append(Path(path_str))

        deleted = [p for p in old_state if p not in current_state]
        
        return changed, deleted

    async def ensure_index(self, force: bool = False) -> list[dict]:
        """Build index if missing, stale, or forced"""
        if not force and not self.is_stale():
            chunks = IndexStore.load_chunks(self.project_id)
            if chunks:
                self._chunks = chunks
                return chunks

        return await self._build_full_index()

    async def _build_full_index(self) -> list[dict]:
        """Build complete index from scratch"""
        files = get_code_files(self.root)
        if not files:
            self._chunks = []
            return []

        all_chunks = []
        file_state = {}

        for file_path in files:
            try:
                stat = file_path.stat()
                file_state[str(file_path)] = {"mtime": stat.st_mtime, "size": stat.st_size}
                content = file_path.read_text(errors="ignore")
                chunks = extract_chunks(file_path, content)
                all_chunks.extend(chunks)
            except Exception:
                continue

        if all_chunks:
            texts = [c["content"] for c in all_chunks]
            embeddings_list = await get_embeddings(texts)
            embeddings = np.array(embeddings_list)
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms

            for i, chunk in enumerate(all_chunks):
                chunk["embedding"] = embeddings[i]

        meta = {
            "root": str(self.root),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "embedding_model": EMBEDDING_MODEL,
            "chunking_version": CHUNKING_VERSION,
            "file_state": file_state,
        }

        IndexStore.save_meta(self.project_id, meta)
        IndexStore.save_chunks(self.project_id, all_chunks)

        self._chunks = all_chunks
        return all_chunks

    async def update_incremental(self) -> list[dict]:
        """Update index for changed files only"""
        meta = IndexStore.load_meta(self.project_id)
        if not meta or self.is_stale():
            return await self._build_full_index()

        old_state = meta.get("file_state", {})
        changed_files, deleted_files = self._detect_changes(old_state)

        if not changed_files and not deleted_files:
            if self._chunks is None:
                self._chunks = IndexStore.load_chunks(self.project_id) or []
            return self._chunks

        chunks = IndexStore.load_chunks(self.project_id) or []

        deleted_set = set(deleted_files)
        changed_set = {str(f) for f in changed_files}
        chunks = [c for c in chunks if c["file"] not in deleted_set and c["file"] not in changed_set]

        new_chunks = []
        new_file_state = {k: v for k, v in old_state.items() if k not in deleted_set}

        for file_path in changed_files:
            try:
                stat = file_path.stat()
                new_file_state[str(file_path)] = {"mtime": stat.st_mtime, "size": stat.st_size}
                content = file_path.read_text(errors="ignore")
                file_chunks = extract_chunks(file_path, content)
                new_chunks.extend(file_chunks)
            except Exception:
                continue

        if new_chunks:
            texts = [c["content"] for c in new_chunks]
            embeddings_list = await get_embeddings(texts)
            embeddings = np.array(embeddings_list)
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms

            for i, chunk in enumerate(new_chunks):
                chunk["embedding"] = embeddings[i]

            chunks.extend(new_chunks)

        meta["updated_at"] = datetime.now().isoformat()
        meta["file_state"] = new_file_state

        IndexStore.save_meta(self.project_id, meta)
        IndexStore.save_chunks(self.project_id, chunks)

        self._chunks = chunks
        return chunks

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search index for relevant code chunks"""
        if self._chunks is None:
            self._chunks = await self.ensure_index()

        if not self._chunks:
            return []

        query_embeddings = await get_embeddings([query])
        query_embedding = np.array(query_embeddings[0])
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        similarities = []
        for chunk in self._chunks:
            if "embedding" not in chunk:
                continue
            sim = float(np.dot(query_embedding, chunk["embedding"]))
            similarities.append((sim, chunk))

        similarities.sort(key=lambda x: x[0], reverse=True)

        results = []
        seen = set()
        for sim, chunk in similarities:
            if len(results) >= top_k:
                break
            key = f"{chunk['file']}:{chunk['start_line']}"
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "file": chunk["file"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "content": chunk["content"],
                "score": sim,
            })

        return results
