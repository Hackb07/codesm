"""Write file tool"""

from pathlib import Path
from .base import Tool


class WriteTool(Tool):
    name = "write"
    description = "Create or overwrite a file with the given content."
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        path = Path(args["path"])
        content = args["content"]
        
        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            result = f"Successfully wrote {len(content)} bytes to {path}"
            
            # Get LSP diagnostics for the written file
            diagnostics_output = await self._get_diagnostics(str(path))
            if diagnostics_output:
                result += f"\n\n{diagnostics_output}"
            
            return result
        except Exception as e:
            return f"Error writing file: {e}"
    
    async def _get_diagnostics(self, path: str) -> str:
        """Get diagnostics for a file after writing."""
        try:
            from codesm import lsp
            from .diagnostics import format_diagnostics
            
            diagnostics = await lsp.touch_file(path)
            errors = [d for d in diagnostics if d.severity == "error"]
            
            if errors:
                return f"⚠️ Errors detected:\n{format_diagnostics(errors)}"
            return ""
        except Exception:
            return ""
