"""Semantic code search tool using OpenAI embeddings"""

import asyncio
import hashlib
import json
import os
import pickle
from pathlib import Path
from typing import Optional
from .base import Tool
from codesm.util.citations import file_link_with_path
from codesm.index import ProjectIndexer
from codesm.search.embeddings import get_embeddings

# Cache directory for embeddings (used for fallback with custom patterns)
CACHE_DIR = Path.home() / ".cache" / "codesm" / "embeddings"


class CodeSearchTool(Tool):
    name = "codesearch"
    description = "Semantic code search - find code by meaning, not just keywords."
    
    _client = None
    _index_cache: dict[str, list[dict]] = {}
    
    @classmethod
    def _get_cache_path(cls, cache_key: str) -> Path:
        """Get path for disk cache file"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR / f"{cache_key}.pkl"
    
    @classmethod
    def _get_file_hash(cls, files: list[Path]) -> str:
        """Get hash of file modification times for cache invalidation"""
        mtimes = []
        for f in sorted(files):
            try:
                mtimes.append(f"{f}:{f.stat().st_mtime}")
            except OSError:
                pass
        return hashlib.md5("\n".join(mtimes).encode()).hexdigest()
    
    @classmethod
    def _load_disk_cache(cls, cache_key: str, files_hash: str) -> Optional[list[dict]]:
        """Load cached embeddings from disk if valid"""
        import numpy as np
        cache_path = cls._get_cache_path(cache_key)
        if not cache_path.exists():
            return None
        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)
            if data.get("files_hash") != files_hash:
                return None  # Files changed, invalidate cache
            # Convert embeddings back to numpy arrays
            for chunk in data["chunks"]:
                chunk["embedding"] = np.array(chunk["embedding"])
            return data["chunks"]
        except Exception:
            return None
    
    @classmethod
    def _save_disk_cache(cls, cache_key: str, files_hash: str, chunks: list[dict]):
        """Save embeddings to disk cache"""
        cache_path = cls._get_cache_path(cache_key)
        try:
            # Convert numpy arrays to lists for pickling
            chunks_to_save = []
            for chunk in chunks:
                chunk_copy = chunk.copy()
                chunk_copy["embedding"] = chunk["embedding"].tolist()
                chunks_to_save.append(chunk_copy)
            with open(cache_path, "wb") as f:
                pickle.dump({"files_hash": files_hash, "chunks": chunks_to_save}, f)
        except Exception:
            pass  # Silently fail on cache write errors
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language description of what you're looking for (e.g., 'function that validates email addresses')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (defaults to project root)",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File glob pattern (e.g., '*.py', '*.ts')",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                },
            },
            "required": ["query"],
        }
    
    @classmethod
    def _get_client(cls):
        """Get OpenAI client for embeddings"""
        if cls._client is None:
            import openai
            from ..auth.credentials import CredentialStore
            
            # Check environment variable first
            api_key = os.environ.get("OPENAI_API_KEY")
            
            # Fall back to credential store
            if not api_key:
                store = CredentialStore()
                api_key = store.get_api_key("openai")
            
            if not api_key:
                raise RuntimeError(
                    "OpenAI API key not found. Please set OPENAI_API_KEY environment variable or configure it in the app."
                )
            cls._client = openai.OpenAI(api_key=api_key)
        return cls._client
    
    @classmethod
    async def _get_embeddings(cls, texts: list[str]) -> list[list[float]]:
        """Get embeddings from OpenAI API - delegates to shared embeddings module"""
        return await get_embeddings(texts)
    
    def _get_code_files(self, root: Path, pattern: Optional[str] = None) -> list[Path]:
        """Get all code files in directory"""
        code_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
            ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
            ".scala", ".clj", ".ex", ".exs", ".lua", ".sh", ".bash",
        }
        
        files = []
        for path in root.rglob("*"):
            # Skip hidden dirs and common non-code dirs
            parts = path.parts
            if any(p.startswith(".") or p in {"node_modules", "__pycache__", "venv", ".venv", "dist", "build", "target"} for p in parts):
                continue
            
            if path.is_file():
                if pattern:
                    import fnmatch
                    if fnmatch.fnmatch(path.name, pattern):
                        files.append(path)
                elif path.suffix in code_extensions:
                    files.append(path)
        
        return files
    
    def _extract_chunks(self, file_path: Path, content: str) -> list[dict]:
        """Extract meaningful code chunks from a file"""
        chunks = []
        lines = content.split("\n")
        
        # Simple chunking: extract functions/classes with context
        current_chunk = []
        chunk_start = 0
        in_block = False
        block_indent = 0
        
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            # Detect function/class definitions
            is_def = stripped.startswith(("def ", "class ", "async def ", "function ", "const ", "let ", "var ", "fn ", "func ", "pub fn ", "impl "))
            
            if is_def and not in_block:
                # Save previous chunk if exists
                if current_chunk:
                    chunk_text = "\n".join(current_chunk)
                    if len(chunk_text.strip()) > 20:  # Minimum size
                        chunks.append({
                            "file": str(file_path),
                            "start_line": chunk_start + 1,
                            "end_line": i,
                            "content": chunk_text[:2000],  # Limit chunk size
                        })
                
                current_chunk = [line]
                chunk_start = i
                in_block = True
                block_indent = indent
            elif in_block:
                current_chunk.append(line)
                
                # End block when we return to same or lower indent (with content)
                if stripped and indent <= block_indent and not is_def and len(current_chunk) > 1:
                    chunk_text = "\n".join(current_chunk[:-1])
                    if len(chunk_text.strip()) > 20:
                        chunks.append({
                            "file": str(file_path),
                            "start_line": chunk_start + 1,
                            "end_line": i,
                            "content": chunk_text[:2000],
                        })
                    current_chunk = [line]
                    chunk_start = i
                    in_block = stripped.startswith(("def ", "class ", "async def "))
        
        # Don't forget last chunk
        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            if len(chunk_text.strip()) > 20:
                chunks.append({
                    "file": str(file_path),
                    "start_line": chunk_start + 1,
                    "end_line": len(lines),
                    "content": chunk_text[:2000],
                })
        
        # If no structured chunks found, use sliding window
        if not chunks and len(content) > 50:
            # Chunk by ~50 lines with overlap
            window_size = 50
            step = 30
            for i in range(0, len(lines), step):
                chunk_lines = lines[i:i + window_size]
                chunk_text = "\n".join(chunk_lines)
                if len(chunk_text.strip()) > 20:
                    chunks.append({
                        "file": str(file_path),
                        "start_line": i + 1,
                        "end_line": min(i + window_size, len(lines)),
                        "content": chunk_text[:2000],
                    })
        
        return chunks
    
    def _get_cache_key(self, root: Path, pattern: Optional[str]) -> str:
        """Generate cache key for index"""
        key = f"{root}:{pattern or '*'}"
        return hashlib.md5(key.encode()).hexdigest()
    
    async def _build_index(self, root: Path, pattern: Optional[str]) -> list[dict]:
        """Build or load cached embedding index"""
        import numpy as np
        
        cache_key = self._get_cache_key(root, pattern)
        
        # Check memory cache first
        if cache_key in self._index_cache:
            return self._index_cache[cache_key]
        
        # Get all code files
        files = self._get_code_files(root, pattern)
        if not files:
            return []
        
        # Check disk cache (with file hash for invalidation)
        files_hash = self._get_file_hash(files)
        cached = self._load_disk_cache(cache_key, files_hash)
        if cached:
            self._index_cache[cache_key] = cached
            return cached
        
        # Extract chunks from all files
        all_chunks = []
        for file_path in files:
            try:
                content = file_path.read_text(errors="ignore")
                chunks = self._extract_chunks(file_path, content)
                all_chunks.extend(chunks)
            except Exception:
                continue
        
        if not all_chunks:
            return []
        
        # Generate embeddings
        texts = [c["content"] for c in all_chunks]
        embeddings_list = await self._get_embeddings(texts)
        embeddings = np.array(embeddings_list)
        
        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms
        
        # Add embeddings to chunks
        for i, chunk in enumerate(all_chunks):
            chunk["embedding"] = embeddings[i]
        
        # Cache in memory and on disk
        self._index_cache[cache_key] = all_chunks
        self._save_disk_cache(cache_key, files_hash, all_chunks)
        
        return all_chunks
    
    async def execute(self, args: dict, context: dict) -> str:
        query = args["query"]
        path = args.get("path") or context.get("cwd", ".")
        pattern = args.get("file_pattern")
        top_k = args.get("top_k", 5)
        
        root = Path(path).resolve()
        if not root.exists():
            return f"Error: Path '{path}' does not exist"
        
        try:
            # Use pre-built index for standard searches, fallback for custom patterns
            if pattern:
                # Custom pattern - use legacy on-demand indexing
                search_results = await self._search_with_pattern(root, pattern, query, top_k)
            else:
                # Use ProjectIndexer for standard searches
                indexer = ProjectIndexer(root)
                await indexer.ensure_index()
                search_results = await indexer.search(query, top_k)
            
            if not search_results:
                return "No relevant code found for the query"
            
            # Format results
            results = []
            for item in search_results:
                file_path = Path(item["file"])
                link = file_link_with_path(file_path, item['start_line'], item['end_line'])
                
                preview = item["content"][:500]
                if len(item["content"]) > 500:
                    preview += "\n..."
                
                score = item.get("score", 0)
                results.append(
                    f"### {link} (score: {score:.3f})\n"
                    f"```\n{preview}\n```"
                )
            
            return f"Found {len(results)} relevant code sections:\n\n" + "\n\n".join(results)
            
        except ImportError as e:
            return str(e)
        except Exception as e:
            return f"Error during search: {e}"
    
    async def _search_with_pattern(self, root: Path, pattern: str, query: str, top_k: int) -> list[dict]:
        """Fallback search with custom file pattern - uses legacy on-demand indexing"""
        import numpy as np
        
        index = await self._build_index(root, pattern)
        if not index:
            return []
        
        query_embeddings = await self._get_embeddings([query])
        query_embedding = np.array(query_embeddings[0])
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        similarities = []
        for chunk in index:
            sim = float(np.dot(query_embedding, chunk["embedding"]))
            similarities.append((sim, chunk))
        
        similarities.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        seen_files = set()
        
        for sim, chunk in similarities[:top_k * 2]:
            if len(results) >= top_k:
                break
            
            key = f"{chunk['file']}:{chunk['start_line']}"
            if key in seen_files:
                continue
            seen_files.add(key)
            
            results.append({
                "file": chunk["file"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "content": chunk["content"],
                "score": sim,
            })
        
        return results
