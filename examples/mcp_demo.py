#!/usr/bin/env python
"""
MCP Demo - Shows how to use MCP servers with codesm

This example:
1. Connects to the filesystem MCP server
2. Lists available tools
3. Calls a tool to list directory contents
4. Reads a file through MCP
"""

import asyncio
from pathlib import Path

from codesm.mcp import MCPManager, MCPServerConfig


async def main():
    # Create MCP manager
    manager = MCPManager()
    
    # Add filesystem server config (same as in example-mcp.json)
    manager.add_server(MCPServerConfig(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp/mcp-demo"],
    ))
    
    print("Connecting to MCP server...")
    results = await manager.connect_all()
    
    if not results.get("filesystem"):
        print("Failed to connect!")
        return
    
    print(f"✓ Connected to filesystem server")
    
    # List all discovered tools
    tools = manager.list_all_tools()
    print(f"\n📦 Discovered {len(tools)} tools:")
    for tool in tools[:5]:  # Show first 5
        print(f"  • {tool['name']}: {tool['description'][:50]}...")
    
    # Call a tool directly
    print("\n📂 Calling list_directory tool...")
    result = await manager.call_tool("filesystem", "list_directory", {
        "path": "/tmp/mcp-demo"
    })
    print(f"Directory contents:\n{result}")
    
    # Read a file through MCP
    print("\n📄 Reading hello.txt through MCP...")
    result = await manager.call_tool("filesystem", "read_file", {
        "path": "/tmp/mcp-demo/hello.txt"
    })
    print(f"File contents: {result}")
    
    # Cleanup
    await manager.disconnect_all()
    print("\n✓ Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
