"""Edit file tool"""

from pathlib import Path
from .base import Tool


class EditTool(Tool):
    name = "edit"
    description = "Edit a file by replacing old content with new content."
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file",
                },
                "old_content": {
                    "type": "string",
                    "description": "Exact content to replace (must match exactly)",
                },
                "new_content": {
                    "type": "string",
                    "description": "New content to insert",
                },
            },
            "required": ["path", "old_content", "new_content"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        path = Path(args["path"])
        old_content = args["old_content"]
        new_content = args["new_content"]
        
        if not path.exists():
            return f"Error: File not found: {path}"
        
        try:
            content = path.read_text()
            
            if old_content not in content:
                return f"Error: Could not find the specified content to replace"
            
            # Use Rust core for diffing if available
            try:
                from codesm_core import apply_edit, diff_files
                updated = apply_edit(content, old_content, new_content)
                diff = diff_files(content, updated, str(path))
            except ImportError:
                # Fallback to Python
                updated = content.replace(old_content, new_content, 1)
                diff = f"-{old_content}\n+{new_content}"
            
            path.write_text(updated)
            return f"Successfully edited {path}\n\n{diff}"
        except Exception as e:
            return f"Error editing file: {e}"
