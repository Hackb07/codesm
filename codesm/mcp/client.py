"""MCP Client implementation for connecting to MCP servers"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server"""
    
    name: str
    command: str
    args: list[str] = []
    env: dict[str, str] = {}
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio"
    url: str | None = None  # For SSE/HTTP transports


@dataclass
class MCPTool:
    """Represents a tool exposed by an MCP server"""
    
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


@dataclass
class MCPResource:
    """Represents a resource exposed by an MCP server"""
    
    uri: str
    name: str
    description: str | None
    mime_type: str | None
    server_name: str


@dataclass
class MCPPrompt:
    """Represents a prompt exposed by an MCP server"""
    
    name: str
    description: str | None
    arguments: list[dict[str, Any]]
    server_name: str


class MCPClient:
    """Client for communicating with MCP servers via stdio transport"""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None
        self._initialized = False
        self._tools: list[MCPTool] = []
        self._resources: list[MCPResource] = []
        self._prompts: list[MCPPrompt] = []
        self._server_info: dict[str, Any] = {}
    
    async def connect(self) -> bool:
        """Connect to the MCP server"""
        if self.config.transport != "stdio":
            logger.warning(f"Transport {self.config.transport} not yet implemented, using stdio")
        
        try:
            import os
            # Merge config env with parent environment
            env = {**os.environ, **self.config.env} if self.config.env else None
            
            self._process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            
            # Start reading responses
            self._read_task = asyncio.create_task(self._read_loop())
            
            # Initialize the connection with timeout
            try:
                await asyncio.wait_for(self._initialize(), timeout=15.0)
            except asyncio.TimeoutError:
                logger.error(f"MCP server {self.config.name} initialization timed out")
                await self.disconnect()
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.config.name}: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None
        
        self._initialized = False
    
    async def _initialize(self):
        """Send initialize request to MCP server"""
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {},
            },
            "clientInfo": {
                "name": "codesm",
                "version": "0.1.0",
            },
        })
        
        self._server_info = result.get("serverInfo", {})
        logger.info(f"Connected to MCP server: {self._server_info.get('name', self.config.name)}")
        
        # Send initialized notification
        await self._send_notification("notifications/initialized", {})
        
        self._initialized = True
        
        # Discover capabilities
        await self._discover_tools()
        await self._discover_resources()
        await self._discover_prompts()
    
    async def _discover_tools(self):
        """Discover available tools from the server"""
        try:
            result = await self._send_request("tools/list", {})
            tools = result.get("tools", [])
            
            self._tools = [
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    server_name=self.config.name,
                )
                for t in tools
            ]
            
            logger.info(f"Discovered {len(self._tools)} tools from {self.config.name}")
            
        except Exception as e:
            logger.debug(f"Failed to list tools from {self.config.name}: {e}")
    
    async def _discover_resources(self):
        """Discover available resources from the server"""
        try:
            result = await self._send_request("resources/list", {})
            resources = result.get("resources", [])
            
            self._resources = [
                MCPResource(
                    uri=r["uri"],
                    name=r.get("name", r["uri"]),
                    description=r.get("description"),
                    mime_type=r.get("mimeType"),
                    server_name=self.config.name,
                )
                for r in resources
            ]
            
            logger.info(f"Discovered {len(self._resources)} resources from {self.config.name}")
            
        except Exception as e:
            logger.debug(f"Failed to list resources from {self.config.name}: {e}")
    
    async def _discover_prompts(self):
        """Discover available prompts from the server"""
        try:
            result = await self._send_request("prompts/list", {})
            prompts = result.get("prompts", [])
            
            self._prompts = [
                MCPPrompt(
                    name=p["name"],
                    description=p.get("description"),
                    arguments=p.get("arguments", []),
                    server_name=self.config.name,
                )
                for p in prompts
            ]
            
            logger.info(f"Discovered {len(self._prompts)} prompts from {self.config.name}")
            
        except Exception as e:
            logger.debug(f"Failed to list prompts from {self.config.name}: {e}")
    
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the MCP server"""
        if not self._initialized:
            raise RuntimeError("MCP client not initialized")
        
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        
        # Extract content from result
        content = result.get("content", [])
        if not content:
            return ""
        
        # Combine text content
        text_parts = []
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif item.get("type") == "image":
                text_parts.append(f"[Image: {item.get('mimeType', 'image')}]")
            elif item.get("type") == "resource":
                text_parts.append(f"[Resource: {item.get('uri', '')}]")
        
        return "\n".join(text_parts)
    
    async def read_resource(self, uri: str) -> str:
        """Read a resource from the MCP server"""
        if not self._initialized:
            raise RuntimeError("MCP client not initialized")
        
        result = await self._send_request("resources/read", {"uri": uri})
        
        contents = result.get("contents", [])
        if not contents:
            return ""
        
        # Return first content's text
        return contents[0].get("text", "")
    
    async def get_prompt(self, name: str, arguments: dict[str, str] | None = None) -> str:
        """Get a prompt from the MCP server"""
        if not self._initialized:
            raise RuntimeError("MCP client not initialized")
        
        result = await self._send_request("prompts/get", {
            "name": name,
            "arguments": arguments or {},
        })
        
        messages = result.get("messages", [])
        if not messages:
            return ""
        
        # Combine message contents
        parts = []
        for msg in messages:
            content = msg.get("content", {})
            if content.get("type") == "text":
                parts.append(content.get("text", ""))
        
        return "\n".join(parts)
    
    @property
    def tools(self) -> list[MCPTool]:
        """Get discovered tools"""
        return self._tools
    
    @property
    def resources(self) -> list[MCPResource]:
        """Get discovered resources"""
        return self._resources
    
    @property
    def prompts(self) -> list[MCPPrompt]:
        """Get discovered prompts"""
        return self._prompts
    
    async def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response"""
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP server not connected")
        
        self._request_id += 1
        request_id = self._request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        
        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        # Send request
        message = json.dumps(request) + "\n"
        self._process.stdin.write(message.encode())
        await self._process.stdin.drain()
        
        try:
            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"MCP request {method} timed out")
    
    async def _send_notification(self, method: str, params: dict[str, Any]):
        """Send a JSON-RPC notification (no response expected)"""
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP server not connected")
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        
        message = json.dumps(notification) + "\n"
        self._process.stdin.write(message.encode())
        await self._process.stdin.drain()
    
    async def _read_loop(self):
        """Read responses from the MCP server"""
        if not self._process or not self._process.stdout:
            return
        
        buffer = b""
        
        try:
            while True:
                # Read chunks instead of lines to handle large responses
                chunk = await self._process.stdout.read(65536)  # 64KB chunks
                if not chunk:
                    break
                
                buffer += chunk
                
                # Process complete JSON messages (newline-delimited)
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    
                    try:
                        message = json.loads(line.decode().strip())
                        await self._handle_message(message)
                    except json.JSONDecodeError as e:
                        logger.debug(f"Invalid JSON from MCP server: {e}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading from MCP server: {e}")
    
    async def _handle_message(self, message: dict[str, Any]):
        """Handle an incoming JSON-RPC message"""
        if "id" in message:
            # This is a response
            request_id = message["id"]
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                
                if "error" in message:
                    error = message["error"]
                    future.set_exception(
                        RuntimeError(f"MCP error: {error.get('message', 'Unknown error')}")
                    )
                else:
                    future.set_result(message.get("result", {}))
        else:
            # This is a notification
            method = message.get("method", "")
            logger.debug(f"MCP notification: {method}")
