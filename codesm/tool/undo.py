"""Undo tool - revert the last edit made to a file"""

from pathlib import Path
from typing import Optional
from .base import Tool
from codesm.snapshot import Snapshot


class UndoTool(Tool):
    name = "undo"
    description = "Undo the last edit made to a file, restoring it to its previous state."
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file whose last edit should be undone",
                },
            },
            "required": ["path"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        path = Path(args["path"])
        
        if not path.exists():
            return f"Error: File not found: {path}"
        
        session = context.get("session")
        if not session:
            return "Error: No session context available for undo"
        
        file_str = str(path)
        patches_to_revert = []
        
        for msg in reversed(session.messages):
            msg_patches = msg.get("_patches", [])
            for p in msg_patches:
                if file_str in p.get("files", []):
                    patches_to_revert.append(p)
                    break
            if patches_to_revert:
                break
        
        if not patches_to_revert:
            return f"No recorded changes found for: {path}"
        
        try:
            snapshot = session.get_snapshot()
            
            from codesm.snapshot.snapshot import Patch
            patches = [Patch(hash=p["hash"], files=[file_str]) for p in patches_to_revert]
            
            reverted = await snapshot.revert_files(patches)
            
            if file_str in reverted or str(path.resolve()) in reverted:
                return f"✓ Undid last edit to {path.name}"
            else:
                return f"Could not undo changes to: {path}"
        except Exception as e:
            return f"Error undoing edit: {e}"
