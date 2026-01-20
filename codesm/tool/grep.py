"""Grep search tool"""

import asyncio
from pathlib import Path
from .base import Tool


class GrepTool(Tool):
    name = "grep"
    description = "Search for patterns in files using ripgrep."
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Pattern to search for (regex)",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in",
                },
                "glob": {
                    "type": "string",
                    "description": "File glob pattern (e.g., '*.py')",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case sensitive search (default: false)",
                },
            },
            "required": ["pattern"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        pattern = args["pattern"]
        path = args.get("path") or context.get("cwd", ".")
        glob = args.get("glob")
        case_sensitive = args.get("case_sensitive", False)
        
        cmd = ["rg", "--line-number", "--no-heading", "--max-count=50"]
        
        # Exclude common directories that shouldn't be searched
        exclude_dirs = [
            ".venv", "venv", ".env", "env",
            "node_modules", ".git", ".hg", ".svn",
            "__pycache__", ".pytest_cache", ".mypy_cache",
            "dist", "build", ".tox", ".nox",
            "site-packages", ".eggs", "*.egg-info",
            "target", ".cargo",
            ".next", ".nuxt", ".output",
        ]
        for exclude in exclude_dirs:
            cmd.extend(["-g", f"!{exclude}"])
        
        # Exclude binary files
        cmd.append("--binary")  # Don't search binary files
        
        if not case_sensitive:
            cmd.append("-i")
        
        if glob:
            cmd.extend(["-g", glob])
        
        cmd.extend([pattern, path])
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 1:  # No matches
                return "No matches found"
            elif proc.returncode != 0:
                return f"Error: {stderr.decode()}"
            
            return stdout.decode()[:10000]  # Limit output
        except FileNotFoundError:
            return "Error: ripgrep (rg) not installed. Install with: apt install ripgrep"
        except Exception as e:
            return f"Error: {e}"
