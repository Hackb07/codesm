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
    
    async def execute(self, args: dict, context: dict) -> str:
        pattern = args["pattern"]
        root = Path(args.get("path") or context.get("cwd", "."))
        limit = args.get("limit", 100)
        
        # Try Rust core first
        try:
            from codesm_core import list_files
            files = list_files(str(root))
            # Filter by glob pattern
            import fnmatch
            matches = [f for f in files if fnmatch.fnmatch(f, pattern)][:limit]
            return "\n".join(matches) if matches else "No files found"
        except ImportError:
            pass
        
        # Fallback to Python
        try:
            matches = list(root.glob(pattern))[:limit]
            if not matches:
                return "No files found"
            return "\n".join(str(m) for m in matches)
        except Exception as e:
            return f"Error: {e}"
