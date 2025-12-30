"""Tool registry"""

from typing import Any
from .base import Tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._register_defaults()
    
    def _register_defaults(self):
        """Register built-in tools"""
        from .read import ReadTool
        from .write import WriteTool
        from .edit import EditTool
        from .bash import BashTool
        from .grep import GrepTool
        from .glob import GlobTool
        from .web import WebTool

        for tool_class in [ReadTool, WriteTool, EditTool, BashTool, GrepTool, GlobTool, WebTool]:
            tool = tool_class()
            self._tools[tool.name] = tool
    
    def register(self, tool: Tool):
        """Register a tool"""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def get_schemas(self) -> list[dict]:
        """Get all tool schemas for LLM"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.get_parameters_schema(),
            }
            for tool in self._tools.values()
        ]
    
    async def execute(self, name: str, args: dict, context: dict) -> str:
        """Execute a tool by name"""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'"
        
        try:
            return await tool.execute(args, context)
        except Exception as e:
            return f"Error executing {name}: {e}"
