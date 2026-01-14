"""MCP (Model Context Protocol) support for codesm

This module provides:
- MCPClient: Connect to MCP servers via stdio/SSE
- MCPManager: Manage multiple MCP server connections
- MCPSandbox: Execute agent-generated code that calls MCP tools
- Code generation: Generate Python stubs from MCP tool definitions

The "code execution with MCP" pattern allows agents to:
- Call multiple MCP tools in a single code block
- Filter/transform data before returning to context
- Use loops and conditionals efficiently
- Save reusable code patterns as skills
"""

from .client import MCPClient, MCPServerConfig
from .manager import MCPManager, get_mcp_manager
from .tool import MCPTool, MCPResourceTool
from .config import load_mcp_config, create_example_config
from .sandbox import MCPSandbox, SkillsManager, ExecutionResult
from .codegen import generate_all_stubs, generate_tool_tree

__all__ = [
    # Client
    "MCPClient",
    "MCPServerConfig", 
    "MCPManager",
    "get_mcp_manager",
    # Tools
    "MCPTool",
    "MCPResourceTool",
    # Config
    "load_mcp_config",
    "create_example_config",
    # Code execution
    "MCPSandbox",
    "SkillsManager",
    "ExecutionResult",
    "generate_all_stubs",
    "generate_tool_tree",
]
