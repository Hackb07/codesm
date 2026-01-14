"""Tests for MCP (Model Context Protocol) support"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from codesm.mcp.client import MCPClient, MCPServerConfig, MCPTool as MCPToolInfo
from codesm.mcp.manager import MCPManager
from codesm.mcp.tool import MCPTool, MCPResourceTool
from codesm.mcp.config import load_mcp_config, _parse_mcp_config


def run_async(coro):
    """Helper to run async functions in sync tests"""
    return asyncio.run(coro)


class TestMCPServerConfig:
    def test_basic_config(self):
        config = MCPServerConfig(
            name="test",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"],
        )
        assert config.name == "test"
        assert config.command == "npx"
        assert config.transport == "stdio"

    def test_config_with_env(self):
        config = MCPServerConfig(
            name="github",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "secret"},
        )
        assert config.env == {"GITHUB_TOKEN": "secret"}


class TestMCPConfigParsing:
    def test_parse_claude_desktop_format(self):
        config = {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                }
            }
        }
        servers = _parse_mcp_config(config)
        assert "filesystem" in servers
        assert servers["filesystem"].command == "npx"

    def test_parse_opencode_format(self):
        config = {
            "mcp": {
                "servers": {
                    "sqlite": {
                        "command": "uvx",
                        "args": ["mcp-server-sqlite"],
                    }
                }
            }
        }
        servers = _parse_mcp_config(config)
        assert "sqlite" in servers

    def test_parse_direct_servers_format(self):
        config = {
            "servers": {
                "test": {
                    "command": "python",
                    "args": ["-m", "mcp_server"],
                }
            }
        }
        servers = _parse_mcp_config(config)
        assert "test" in servers

    def test_parse_root_servers_format(self):
        config = {
            "myserver": {
                "command": "node",
                "args": ["server.js"],
            }
        }
        servers = _parse_mcp_config(config)
        assert "myserver" in servers

    def test_skip_invalid_server(self):
        config = {
            "mcpServers": {
                "valid": {"command": "test"},
                "invalid": {"no_command": True},
            }
        }
        servers = _parse_mcp_config(config)
        assert "valid" in servers
        assert "invalid" not in servers


class TestMCPTool:
    def test_tool_wrapper(self):
        mcp_tool_info = MCPToolInfo(
            name="read_file",
            description="Read a file from the filesystem",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            },
            server_name="filesystem",
        )
        
        mock_client = MagicMock()
        tool = MCPTool(mcp_tool_info, mock_client)
        
        assert tool.name == "mcp_filesystem_read_file"
        assert "Read a file" in tool.description
        
        schema = tool.get_parameters_schema()
        assert schema["type"] == "object"
        assert "path" in schema["properties"]

    def test_tool_execute(self):
        async def _test():
            mcp_tool_info = MCPToolInfo(
                name="test_tool",
                description="Test tool",
                input_schema={"type": "object"},
                server_name="test",
            )
            
            mock_client = AsyncMock()
            mock_client.call_tool = AsyncMock(return_value="result text")
            
            tool = MCPTool(mcp_tool_info, mock_client)
            result = await tool.execute({"arg": "value"}, {})
            
            assert result == "result text"
            mock_client.call_tool.assert_called_once_with("test_tool", {"arg": "value"})
        
        run_async(_test())


class TestMCPResourceTool:
    def test_resource_tool_execute(self):
        async def _test():
            mock_client = AsyncMock()
            mock_client.read_resource = AsyncMock(return_value="file content")
            
            tool = MCPResourceTool("test", mock_client)
            result = await tool.execute({"uri": "file:///test.txt"}, {})
            
            assert result == "file content"
            mock_client.read_resource.assert_called_once_with("file:///test.txt")
        
        run_async(_test())

    def test_resource_tool_missing_uri(self):
        async def _test():
            mock_client = AsyncMock()
            tool = MCPResourceTool("test", mock_client)
            
            result = await tool.execute({}, {})
            assert "Error: uri is required" in result
        
        run_async(_test())


class TestMCPManager:
    def test_add_server(self):
        manager = MCPManager()
        config = MCPServerConfig(name="test", command="echo")
        manager.add_server(config)
        
        servers = manager.list_servers()
        assert len(servers) == 1
        assert servers[0]["name"] == "test"
        assert servers[0]["connected"] is False

    def test_add_servers_from_dict(self):
        manager = MCPManager()
        manager.add_servers_from_dict({
            "server1": {"command": "cmd1", "args": []},
            "server2": {"command": "cmd2", "args": ["-v"]},
        })
        
        servers = manager.list_servers()
        assert len(servers) == 2

    def test_get_tools_empty(self):
        manager = MCPManager()
        tools = manager.get_tools()
        assert tools == []
