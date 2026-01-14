"""MCP Manager - manages multiple MCP server connections"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from .client import MCPClient, MCPServerConfig, MCPTool as MCPToolInfo
from .tool import MCPTool, MCPResourceTool
from ..tool.base import Tool

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages connections to multiple MCP servers"""
    
    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._tools: list[Tool] = []
        self._configs: list[MCPServerConfig] = []
    
    def add_server(self, config: MCPServerConfig):
        """Add an MCP server configuration"""
        self._configs.append(config)
    
    def add_servers_from_dict(self, servers: dict[str, dict[str, Any]]):
        """Add servers from a dictionary (like Claude's mcp_servers config format)"""
        for name, config in servers.items():
            server_config = MCPServerConfig(
                name=name,
                command=config.get("command", ""),
                args=config.get("args", []),
                env=config.get("env", {}),
                transport=config.get("transport", "stdio"),
                url=config.get("url"),
            )
            self.add_server(server_config)
    
    async def connect_all(self) -> dict[str, bool]:
        """Connect to all configured MCP servers"""
        results = {}
        
        for config in self._configs:
            if config.name in self._clients:
                results[config.name] = True
                continue
            
            client = MCPClient(config)
            success = await client.connect()
            
            if success:
                self._clients[config.name] = client
                self._register_tools(client)
            
            results[config.name] = success
        
        return results
    
    async def connect_server(self, name: str) -> bool:
        """Connect to a specific MCP server by name"""
        config = next((c for c in self._configs if c.name == name), None)
        if not config:
            logger.error(f"No configuration found for MCP server: {name}")
            return False
        
        if name in self._clients:
            return True
        
        client = MCPClient(config)
        success = await client.connect()
        
        if success:
            self._clients[name] = client
            self._register_tools(client)
        
        return success
    
    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        for client in self._clients.values():
            await client.disconnect()
        
        self._clients.clear()
        self._tools.clear()
    
    async def disconnect_server(self, name: str):
        """Disconnect from a specific MCP server"""
        if name in self._clients:
            await self._clients[name].disconnect()
            del self._clients[name]
            
            # Remove tools from this server
            self._tools = [
                t for t in self._tools 
                if not t.name.startswith(f"mcp_{name}_")
            ]
    
    def _register_tools(self, client: MCPClient):
        """Register tools from an MCP client"""
        # Register each tool from the server
        for mcp_tool in client.tools:
            tool = MCPTool(mcp_tool, client)
            self._tools.append(tool)
        
        # Register resource reader if server has resources
        if client.resources:
            resource_tool = MCPResourceTool(client.config.name, client)
            self._tools.append(resource_tool)
    
    def get_tools(self) -> list[Tool]:
        """Get all tools from connected MCP servers"""
        return self._tools
    
    def get_tool(self, name: str) -> Tool | None:
        """Get a specific tool by name"""
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on a specific MCP server"""
        client = self._clients.get(server_name)
        if not client:
            return f"Error: MCP server '{server_name}' not connected"
        
        try:
            result = await client.call_tool(tool_name, arguments)
            return str(result)
        except Exception as e:
            return f"Error calling MCP tool: {e}"
    
    async def read_resource(self, server_name: str, uri: str) -> str:
        """Read a resource from a specific MCP server"""
        client = self._clients.get(server_name)
        if not client:
            return f"Error: MCP server '{server_name}' not connected"
        
        try:
            return await client.read_resource(uri)
        except Exception as e:
            return f"Error reading MCP resource: {e}"
    
    def list_servers(self) -> list[dict[str, Any]]:
        """List all configured servers and their status"""
        return [
            {
                "name": config.name,
                "command": config.command,
                "connected": config.name in self._clients,
                "tools": len(self._clients[config.name].tools) if config.name in self._clients else 0,
                "resources": len(self._clients[config.name].resources) if config.name in self._clients else 0,
            }
            for config in self._configs
        ]
    
    def list_all_tools(self) -> list[dict[str, Any]]:
        """List all available tools from all connected servers"""
        tools = []
        for client in self._clients.values():
            for tool in client.tools:
                tools.append({
                    "server": client.config.name,
                    "name": tool.name,
                    "description": tool.description,
                    "full_name": f"mcp_{client.config.name}_{tool.name}",
                })
        return tools
    
    def list_all_resources(self) -> list[dict[str, Any]]:
        """List all available resources from all connected servers"""
        resources = []
        for client in self._clients.values():
            for resource in client.resources:
                resources.append({
                    "server": client.config.name,
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mime_type": resource.mime_type,
                })
        return resources


# Global MCP manager instance
_mcp_manager: MCPManager | None = None


def get_mcp_manager() -> MCPManager:
    """Get the global MCP manager instance"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager
