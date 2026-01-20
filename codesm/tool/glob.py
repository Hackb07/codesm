"""Glob file search tool"""

from pathlib import Path
from .base import Tool


class GlobTool(Tool):
    name = "glob"
    description = "Find files matching a glob pattern."
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '**/*.py')",
                },
                "path": {
                    "type": "string",
                    "description": "Root directory to search in",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                },
            },
            "required": ["pattern"],
        }
    
    # Directories to exclude from glob results
    EXCLUDE_DIRS = {
        ".venv", "venv", ".env", "env",
        "node_modules", ".git", ".hg", ".svn",
        "__pycache__", ".pytest_cache", ".mypy_cache",
        "dist", "build", ".tox", ".nox",
        "site-packages", ".eggs",
        "target", ".cargo",
        ".next", ".nuxt", ".output",
    }
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded."""
        parts = path.parts
        return any(part in self.EXCLUDE_DIRS or part.endswith(".egg-info") for part in parts)
    
    async def execute(self, args: dict, context: dict) -> str:
        pattern = args["pattern"]
        root = Path(args.get("path") or context.get("cwd", "."))
        limit = args.get("limit", 100)
        
        # Try Rust core first
        try:
            from codesm_core import list_files
            files = list_files(str(root))
            # Filter by glob pattern and exclude unwanted dirs
            import fnmatch
            matches = [
                f for f in files 
                if fnmatch.fnmatch(f, pattern) and not self._should_exclude(Path(f))
            ][:limit]
            return "\n".join(matches) if matches else "No files found"
        except ImportError:
            pass
        
        # Fallback to Python
        try:
            matches = [
                m for m in root.glob(pattern) 
                if not self._should_exclude(m)
            ][:limit]
            if not matches:
                return "No files found"
            return "\n".join(str(m) for m in matches)
        except Exception as e:
            return f"Error: {e}"
