"""
MCP Execute Tool - Lets the agent write code that calls MCP tools

This implements the "code execution with MCP" pattern from:
https://www.anthropic.com/engineering/code-execution-with-mcp

Instead of calling MCP tools directly (which consumes context),
the agent writes Python code that:
1. Calls multiple MCP tools in sequence
2. Filters/transforms data before returning
3. Uses loops and conditionals
4. Keeps intermediate data out of context
"""

from pathlib import Path
from .base import Tool


class MCPExecuteTool(Tool):
    """Execute Python code that can call MCP tools"""
    
    name = "mcp_execute"
    description = """Execute Python code that calls MCP tools efficiently.

Use this instead of calling MCP tools directly when you need to:
- Chain multiple tool calls together
- Filter or transform large datasets
- Use loops or conditionals
- Keep intermediate results out of context

Available MCP servers are pre-configured as objects:
- filesystem.read_file(path="/tmp/file.txt")
- filesystem.list_directory(path="/tmp")
- filesystem.write_file(path="/tmp/out.txt", content="...")

Or use mcp_call() directly:
- mcp_call("server_name", "tool_name", arg1="value1", arg2="value2")

Example - read multiple files and combine:
```python
files = filesystem.list_directory(path="/tmp/data")
contents = []
for f in files.get("entries", []):
    if f.endswith(".txt"):
        content = filesystem.read_file(path=f"/tmp/data/{f}")
        contents.append(content)
print(f"Combined {len(contents)} files")
__result__ = {"count": len(contents), "preview": contents[0][:100] if contents else ""}
```

Set __result__ to return structured data to the conversation.
Use print() for progress/debug output that will be shown.
"""
    
    def __init__(self, mcp_manager=None, workspace_dir: Path = None):
        super().__init__()
        self._mcp_manager = mcp_manager
        self._workspace_dir = workspace_dir or Path.cwd()
        self._sandbox = None
    
    def set_mcp_manager(self, manager):
        """Set the MCP manager for tool calls"""
        self._mcp_manager = manager
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Can call MCP tools via server objects or mcp_call().",
                },
                "save_as_skill": {
                    "type": "string",
                    "description": "Optional: save this code as a reusable skill with this name",
                },
            },
            "required": ["code"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        code = args.get("code", "")
        save_as = args.get("save_as_skill")
        
        if not code.strip():
            return "Error: No code provided"
        
        if not self._mcp_manager:
            return """Error: MCP not initialized. No MCP servers connected.

To use mcp_execute, you need to:
1. Create mcp-servers.json in the working directory with your MCP server config
2. The agent will auto-connect on startup

Example mcp-servers.json:
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  }
}

Use the regular 'bash' or 'read' tools instead for now."""
        
        # Lazy import to avoid circular deps
        from ..mcp.sandbox import MCPSandbox, SkillsManager
        
        # Create sandbox if needed
        if not self._sandbox:
            self._sandbox = MCPSandbox(
                workspace_dir=self._workspace_dir,
                timeout=60,
            )
        
        # MCP call handler
        async def handle_mcp_call(server: str, tool: str, args: dict):
            result = await self._mcp_manager.call_tool(server, tool, args)
            # Try to parse as JSON, otherwise return as string
            try:
                import json
                return json.loads(result) if result.startswith('{') or result.startswith('[') else result
            except:
                return result
        
        # Execute
        result = await self._sandbox.execute(code, handle_mcp_call)
        
        # Build response
        output_parts = []
        
        if result.output:
            output_parts.append(f"Output:\n{result.output}")
        
        if result.return_value is not None:
            import json
            output_parts.append(f"Result:\n{json.dumps(result.return_value, indent=2)}")
        
        if result.error:
            output_parts.append(f"Error:\n{result.error}")
        
        if not output_parts:
            output_parts.append("Code executed successfully (no output)")
        
        # Save as skill if requested
        if save_as and result.success:
            skills = SkillsManager(self._sandbox.skills_dir)
            skills.save_skill(save_as, code, f"Auto-saved skill from mcp_execute")
            output_parts.append(f"\n✓ Saved as skill: {save_as}")
        
        status = "✓" if result.success else "✗"
        return f"{status} Code execution {'completed' if result.success else 'failed'}\n\n" + "\n\n".join(output_parts)


class MCPToolsListTool(Tool):
    """List available MCP tools as a file tree"""
    
    name = "mcp_tools"
    description = """List available MCP tools from connected servers.

Returns a tree view of servers and their tools:
    servers/
    ├── filesystem/
    │   ├── read_file: Read a file
    │   └── list_directory: List directory
    └── github/
        └── create_issue: Create an issue

Use this to discover what MCP tools are available before writing code with mcp_execute.
"""
    
    def __init__(self, mcp_manager=None):
        super().__init__()
        self._mcp_manager = mcp_manager
    
    def set_mcp_manager(self, manager):
        self._mcp_manager = manager
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "Optional: show detailed tools for a specific server only",
                },
            },
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        if not self._mcp_manager:
            return "No MCP servers connected."
        
        server_filter = args.get("server")
        
        from ..mcp.codegen import generate_tool_tree
        
        if server_filter:
            # Show detailed info for one server
            client = self._mcp_manager._clients.get(server_filter)
            if not client:
                return f"Server '{server_filter}' not found. Available: {list(self._mcp_manager._clients.keys())}"
            
            lines = [f"Server: {server_filter}", f"Tools ({len(client.tools)}):", ""]
            for tool in client.tools:
                lines.append(f"  {tool.name}:")
                lines.append(f"    {tool.description}")
                if tool.input_schema.get("properties"):
                    lines.append("    Parameters:")
                    for pname, pschema in tool.input_schema["properties"].items():
                        req = "(required)" if pname in tool.input_schema.get("required", []) else ""
                        lines.append(f"      - {pname}: {pschema.get('type', 'any')} {req}")
                        if pschema.get("description"):
                            lines.append(f"        {pschema['description']}")
                lines.append("")
            
            return "\n".join(lines)
        
        # Show tree of all servers
        return generate_tool_tree(self._mcp_manager)


class MCPSkillsTool(Tool):
    """List and use saved MCP code skills"""
    
    name = "mcp_skills"
    description = """List or retrieve saved MCP code skills.

Skills are reusable code patterns saved from previous mcp_execute calls.
Use this to see what skills are available and get their code.
"""
    
    def __init__(self, workspace_dir: Path = None):
        super().__init__()
        self._workspace_dir = workspace_dir or Path.cwd()
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "get"],
                    "description": "list = show all skills, get = retrieve a specific skill's code",
                },
                "name": {
                    "type": "string",
                    "description": "Skill name (required for 'get' action)",
                },
            },
            "required": ["action"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        from ..mcp.sandbox import SkillsManager
        
        skills_dir = self._workspace_dir / ".mcp" / "skills"
        manager = SkillsManager(skills_dir)
        
        action = args.get("action", "list")
        
        if action == "list":
            skills = manager.list_skills()
            if not skills:
                return "No saved skills yet. Use mcp_execute with save_as_skill to create one."
            
            lines = ["Available skills:", ""]
            for skill in skills:
                lines.append(f"  • {skill['name']}")
                if skill['description']:
                    lines.append(f"    {skill['description'][:100]}")
            
            return "\n".join(lines)
        
        elif action == "get":
            name = args.get("name")
            if not name:
                return "Error: 'name' required for get action"
            
            code = manager.get_skill(name)
            if not code:
                return f"Skill '{name}' not found"
            
            return f"Skill: {name}\n\n```python\n{code}\n```"
        
        return f"Unknown action: {action}"
