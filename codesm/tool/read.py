"""Read file tool"""

from pathlib import Path
from .base import Tool


class ReadTool(Tool):
    name = "read"
    description = "Read file contents. Returns line-numbered output."
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Start line (1-indexed)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "End line (1-indexed)",
                },
            },
            "required": ["path"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        path = Path(args["path"])
        start = args.get("start_line", 1)
        end = args.get("end_line")
        
        if not path.exists():
            return f"Error: File not found: {path}"
        
        if not path.is_file():
            return f"Error: Not a file: {path}"
        
        try:
            content = path.read_text()
            lines = content.split("\n")
            
            end = end or len(lines)
            selected = lines[start - 1:end]
            
            numbered = [
                f"{start + i}: {line}" 
                for i, line in enumerate(selected)
            ]
            return "\n".join(numbered)
        except Exception as e:
            return f"Error reading file: {e}"
