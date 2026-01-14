"""Generate Python tool stubs from MCP server definitions"""

import json
import logging
from pathlib import Path
from typing import Any

from .manager import MCPManager

logger = logging.getLogger(__name__)


def json_schema_to_python_type(schema: dict) -> str:
    """Convert JSON schema type to Python type hint"""
    if not schema:
        return "Any"
    
    type_map = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
    }
    
    json_type = schema.get("type", "any")
    if isinstance(json_type, list):
        json_type = json_type[0]
    
    return type_map.get(json_type, "Any")


def generate_tool_stub(
    server_name: str,
    tool_name: str,
    description: str,
    input_schema: dict,
) -> str:
    """Generate a Python function stub for an MCP tool"""
    
    # Extract parameters from schema
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    
    # Build function signature
    params = []
    param_docs = []
    
    for name, prop in properties.items():
        prop_type = json_schema_to_python_type(prop)
        prop_desc = prop.get("description", "")
        
        if name in required:
            params.append(f"{name}: {prop_type}")
        else:
            default = prop.get("default", "None")
            if prop_type == "str" and default != "None":
                default = f'"{default}"'
            params.append(f"{name}: {prop_type} = {default}")
        
        param_docs.append(f"        {name}: {prop_desc}")
    
    params_str = ", ".join(params) if params else ""
    params_doc = "\n".join(param_docs) if param_docs else "        None"
    
    # Build the function
    func = f'''
def {tool_name}({params_str}) -> dict:
    """
    {description}
    
    Args:
{params_doc}
    
    Returns:
        Tool result as dictionary
    """
    return mcp_call("{server_name}", "{tool_name}", **{{k: v for k, v in locals().items() if v is not None}})
'''
    return func


def generate_server_module(
    server_name: str,
    tools: list[dict],
) -> str:
    """Generate a complete Python module for an MCP server"""
    
    header = f'''"""
MCP Server: {server_name}

Auto-generated tool stubs for the {server_name} MCP server.
These functions call the actual MCP server through the sandbox bridge.

Usage:
    from .{server_name} import list_directory, read_file
    
    files = list_directory(path="/tmp")
    content = read_file(path="/tmp/test.txt")
"""

from typing import Any

# MCP call bridge - injected by sandbox at runtime
def mcp_call(server: str, tool: str, **kwargs) -> dict:
    raise RuntimeError("mcp_call not initialized - run through MCPSandbox")

'''
    
    functions = []
    for tool in tools:
        func = generate_tool_stub(
            server_name=server_name,
            tool_name=tool["name"],
            description=tool.get("description", ""),
            input_schema=tool.get("input_schema", {}),
        )
        functions.append(func)
    
    # Add __all__ export
    all_names = [t["name"] for t in tools]
    all_export = f"\n__all__ = {all_names}\n"
    
    return header + all_export + "\n".join(functions)


def generate_server_index(servers: list[str]) -> str:
    """Generate an index module that lists all available servers"""
    
    imports = "\n".join([f"from . import {s}" for s in servers])
    
    return f'''"""
MCP Servers Index

Available servers:
{chr(10).join(f"  - {s}" for s in servers)}

Usage:
    from servers import filesystem
    files = filesystem.list_directory(path="/tmp")
"""

{imports}

__all__ = {servers}

def list_servers() -> list[str]:
    """List all available MCP servers"""
    return {servers}
'''


async def generate_all_stubs(
    manager: MCPManager,
    output_dir: Path,
) -> dict[str, Path]:
    """
    Generate Python stubs for all connected MCP servers.
    
    Creates a file structure like:
        output_dir/
            __init__.py
            filesystem.py
            github.py
            ...
    
    Returns:
        Dict mapping server name to generated file path
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated = {}
    server_names = []
    
    for name, client in manager._clients.items():
        tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in client.tools
        ]
        
        if not tools:
            continue
        
        # Generate module for this server
        module_code = generate_server_module(name, tools)
        module_path = output_dir / f"{name}.py"
        module_path.write_text(module_code)
        
        generated[name] = module_path
        server_names.append(name)
        
        logger.info(f"Generated {len(tools)} tool stubs for {name} → {module_path}")
    
    # Generate index
    if server_names:
        index_code = generate_server_index(server_names)
        index_path = output_dir / "__init__.py"
        index_path.write_text(index_code)
    
    return generated


def generate_tool_tree(manager: MCPManager) -> str:
    """
    Generate a text tree of all available tools for the agent to explore.
    
    Returns something like:
        servers/
        ├── filesystem/
        │   ├── read_file: Read a file from the filesystem
        │   ├── write_file: Write content to a file
        │   └── list_directory: List directory contents
        └── github/
            ├── create_issue: Create a GitHub issue
            └── list_repos: List repositories
    """
    lines = ["servers/"]
    
    servers = list(manager._clients.items())
    for i, (name, client) in enumerate(servers):
        is_last_server = i == len(servers) - 1
        prefix = "└── " if is_last_server else "├── "
        lines.append(f"{prefix}{name}/")
        
        tools = client.tools
        for j, tool in enumerate(tools):
            is_last_tool = j == len(tools) - 1
            if is_last_server:
                tool_prefix = "    └── " if is_last_tool else "    ├── "
            else:
                tool_prefix = "│   └── " if is_last_tool else "│   ├── "
            
            desc = tool.description[:50] + "..." if len(tool.description) > 50 else tool.description
            lines.append(f"{tool_prefix}{tool.name}: {desc}")
    
    return "\n".join(lines)
