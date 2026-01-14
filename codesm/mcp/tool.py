"""MCP Tool wrapper for codesm tool system"""

from typing import Any

from ..tool.base import Tool
from .client import MCPClient, MCPTool as MCPToolInfo


class MCPTool(Tool):
    """Wrapper that exposes an MCP server tool as a codesm Tool"""
    
    def __init__(self, mcp_tool: MCPToolInfo, client: MCPClient):
        self._mcp_tool = mcp_tool
        self._client = client
        
        # Set name with server prefix to avoid conflicts
        self.name = f"mcp_{mcp_tool.server_name}_{mcp_tool.name}"
        self.description = mcp_tool.description or f"MCP tool: {mcp_tool.name}"
        
        # Don't call super().__init__() as we set description directly
    
    def get_parameters_schema(self) -> dict:
        """Return JSON schema for parameters from MCP tool"""
        schema = self._mcp_tool.input_schema.copy()
        
        # Ensure it has required fields
        if "type" not in schema:
            schema["type"] = "object"
        if "properties" not in schema:
            schema["properties"] = {}
        
        return schema
    
    async def execute(self, args: dict, context: dict) -> str:
        """Execute the MCP tool"""
        try:
            result = await self._client.call_tool(self._mcp_tool.name, args)
            return str(result)
        except Exception as e:
            return f"Error calling MCP tool {self._mcp_tool.name}: {e}"


class MCPResourceTool(Tool):
    """Tool for reading MCP resources"""
    
    def __init__(self, server_name: str, client: MCPClient):
        self._client = client
        self._server_name = server_name
        
        self.name = f"mcp_{server_name}_read_resource"
        self.description = f"Read a resource from the {server_name} MCP server"
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "The URI of the resource to read",
                },
            },
            "required": ["uri"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        """Read the MCP resource"""
        uri = args.get("uri", "")
        if not uri:
            return "Error: uri is required"
        
        try:
            result = await self._client.read_resource(uri)
            return result
        except Exception as e:
            return f"Error reading MCP resource {uri}: {e}"
