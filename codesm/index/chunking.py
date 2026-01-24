"""Code chunking utilities for extracting searchable code segments"""

import fnmatch
from pathlib import Path

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
    ".scala", ".clj", ".ex", ".exs", ".lua", ".sh", ".bash",
}

SKIP_DIRS = {
    "node_modules", "__pycache__", "venv", ".venv", "dist", "build", "target"
}


def get_code_files(root: Path, pattern: str | None = None) -> list[Path]:
    """Get all code files in directory"""
    files = []
    for path in root.rglob("*"):
        parts = path.parts
        if any(p.startswith(".") or p in SKIP_DIRS for p in parts):
            continue

        if path.is_file():
            if pattern:
                if fnmatch.fnmatch(path.name, pattern):
                    files.append(path)
            elif path.suffix in CODE_EXTENSIONS:
                files.append(path)

    return files


def extract_chunks(file_path: Path, content: str) -> list[dict]:
    """Extract meaningful code chunks from a file.
    
    Each chunk has: file, start_line, end_line, content
    """
    chunks = []
    lines = content.split("\n")

    current_chunk = []
    chunk_start = 0
    in_block = False
    block_indent = 0

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        is_def = stripped.startswith((
            "def ", "class ", "async def ", "function ", "const ", "let ",
            "var ", "fn ", "func ", "pub fn ", "impl "
        ))

        if is_def and not in_block:
            if current_chunk:
                chunk_text = "\n".join(current_chunk)
                if len(chunk_text.strip()) > 20:
                    chunks.append({
                        "file": str(file_path),
                        "start_line": chunk_start + 1,
                        "end_line": i,
                        "content": chunk_text[:2000],
                    })

            current_chunk = [line]
            chunk_start = i
            in_block = True
            block_indent = indent
        elif in_block:
            current_chunk.append(line)

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

    if current_chunk:
        chunk_text = "\n".join(current_chunk)
        if len(chunk_text.strip()) > 20:
            chunks.append({
                "file": str(file_path),
                "start_line": chunk_start + 1,
                "end_line": len(lines),
                "content": chunk_text[:2000],
            })

    if not chunks and len(content) > 50:
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
