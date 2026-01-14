"""List directory tool - shows directory tree structure"""

from pathlib import Path
from .base import Tool

IGNORE_PATTERNS = [
    "node_modules",
    "__pycache__",
    ".git",
    "dist",
    "build",
    "target",
    "vendor",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    ".coverage",
    "coverage",
    ".cache",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
]


class ListTool(Tool):
    name = "ls"
    description = "List directory contents as a tree structure. Use to understand project layout."
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the directory to list",
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum depth to traverse (default: 3)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to show (default: 100)",
                },
            },
            "required": [],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        path_str = args.get("path") or str(context.get("cwd", "."))
        max_depth = args.get("depth", 3)
        limit = args.get("limit", 100)
        
        root = Path(path_str)
        if not root.exists():
            return f"Error: Directory not found: {path_str}"
        if not root.is_dir():
            return f"Error: Not a directory: {path_str}"
        
        try:
            lines = []
            count = 0
            
            def should_ignore(name: str) -> bool:
                for pattern in IGNORE_PATTERNS:
                    if pattern.startswith("*"):
                        if name.endswith(pattern[1:]):
                            return True
                    elif name == pattern:
                        return True
                return False
            
            def render_tree(dir_path: Path, prefix: str = "", depth: int = 0) -> None:
                nonlocal count
                if count >= limit or depth > max_depth:
                    return
                
                try:
                    entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                except PermissionError:
                    return
                
                # Filter ignored entries
                entries = [e for e in entries if not should_ignore(e.name)]
                
                for i, entry in enumerate(entries):
                    if count >= limit:
                        lines.append(f"{prefix}... (truncated, {limit} entries shown)")
                        return
                    
                    is_last = i == len(entries) - 1
                    connector = "└── " if is_last else "├── "
                    
                    if entry.is_dir():
                        lines.append(f"{prefix}{connector}{entry.name}/")
                        count += 1
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        render_tree(entry, next_prefix, depth + 1)
                    else:
                        lines.append(f"{prefix}{connector}{entry.name}")
                        count += 1
            
            lines.append(f"{root}/")
            render_tree(root)
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Error listing directory: {e}"
