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
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"
