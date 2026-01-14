#!/usr/bin/env python
"""
Demo: Code Execution with MCP

This demonstrates the pattern from Anthropic's blog post:
https://www.anthropic.com/engineering/code-execution-with-mcp

Instead of calling MCP tools directly (consuming context tokens),
the agent writes code that calls multiple tools efficiently.
"""

import asyncio
from pathlib import Path

from codesm.mcp import MCPManager, MCPServerConfig, MCPSandbox, generate_tool_tree


async def main():
    # 1. Connect to MCP server
    print("1. Connecting to MCP filesystem server...")
    manager = MCPManager()
    manager.add_server(MCPServerConfig(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp/mcp-demo"],
    ))
    
    await manager.connect_all()
    print(f"   ✓ Connected, {len(manager.list_all_tools())} tools available\n")
    
    # 2. Show tool tree (what agent sees)
    print("2. Tool tree (agent explores this instead of loading all definitions):")
    tree = generate_tool_tree(manager)
    print(tree)
    print()
    
    # 3. Create sandbox for code execution
    print("3. Creating code execution sandbox...")
    workspace = Path("/tmp/mcp-demo")
    sandbox = MCPSandbox(workspace_dir=workspace, timeout=30)
    print("   ✓ Sandbox ready\n")
    
    # 4. Handler for MCP calls from the sandbox
    async def handle_mcp_call(server: str, tool: str, args: dict):
        result = await manager.call_tool(server, tool, args)
        return result
    
    # 5. Execute code that chains multiple MCP calls
    print("4. Executing agent-generated code...")
    print("   Code:")
    
    code = '''
# List files and read each one
files = filesystem.list_directory(path="/tmp/mcp-demo")
print(f"Found files: {files}")

# Filter and process
txt_files = [f for f in str(files).split() if ".txt" in f]
print(f"Text files: {txt_files}")

# Read first file if exists
if txt_files:
    content = filesystem.read_file(path="/tmp/mcp-demo/test.txt")
    print(f"Content preview: {str(content)[:100]}")

__result__ = {"files_found": len(txt_files), "status": "success"}
'''
    
    for line in code.strip().split('\n'):
        print(f"   {line}")
    print()
    
    result = await sandbox.execute(code, handle_mcp_call)
    
    print("5. Execution result:")
    print(f"   Success: {result.success}")
    print(f"   Output:\n   {result.output.replace(chr(10), chr(10) + '   ')}")
    if result.return_value:
        print(f"   Return value: {result.return_value}")
    if result.error:
        print(f"   Error: {result.error}")
    
    # 6. Cleanup
    await manager.disconnect_all()
    print("\n✓ Demo complete!")
    
    # Show the efficiency gain
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EFFICIENCY COMPARISON:

Traditional MCP (direct tool calls):
  • Load 14 tool definitions → ~2000 tokens
  • list_directory result → 500 tokens in context  
  • read_file result → 1000 tokens in context
  • Total: ~3500 tokens through LLM

Code execution with MCP:
  • Agent writes code → ~200 tokens
  • Code executes in sandbox
  • Only final result → ~50 tokens
  • Total: ~250 tokens through LLM
  
Savings: 93% fewer tokens!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


if __name__ == "__main__":
    asyncio.run(main())
