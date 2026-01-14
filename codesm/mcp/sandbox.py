"""Secure sandbox for executing agent-generated code that calls MCP tools"""

import asyncio
import json
import logging
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of code execution"""
    success: bool
    output: str
    error: str | None = None
    return_value: Any = None


class MCPSandbox:
    """
    Executes agent-generated Python code that can call MCP tools.
    
    The code runs in a subprocess with:
    - Timeout limits
    - Access to generated MCP tool stubs
    - Isolated from main process
    """
    
    def __init__(
        self,
        workspace_dir: Path,
        timeout: int = 30,
    ):
        self.workspace_dir = Path(workspace_dir)
        self.timeout = timeout
        self.servers_dir = self.workspace_dir / ".mcp" / "servers"
        self.skills_dir = self.workspace_dir / ".mcp" / "skills"
        
        # Ensure directories exist
        self.servers_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
    
    async def execute(
        self,
        code: str,
        mcp_call_handler: callable,
    ) -> ExecutionResult:
        """
        Execute Python code that can call MCP tools.
        
        Args:
            code: Python code to execute
            mcp_call_handler: Async function to handle MCP tool calls
                              Signature: (server: str, tool: str, args: dict) -> str
        
        Returns:
            ExecutionResult with output, errors, and return value
        """
        # Create a temporary script that wraps the user code
        script = self._build_script(code)
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            dir=self.workspace_dir,
            delete=False
        ) as f:
            f.write(script)
            script_path = Path(f.name)
        
        try:
            # Run the script and capture MCP calls
            result = await self._run_with_mcp_bridge(
                script_path,
                mcp_call_handler,
            )
            return result
            
        finally:
            # Cleanup
            script_path.unlink(missing_ok=True)
    
    def _build_script(self, user_code: str) -> str:
        """Build the executable script with MCP bridge"""
        return textwrap.dedent(f'''\
            import sys
            import json
            
            # MCP tool call bridge - sends requests to parent process
            def mcp_call(server: str, tool: str, **kwargs):
                """Call an MCP tool. Returns the result as a dict if possible, string otherwise."""
                request = json.dumps({{"server": server, "tool": tool, "args": kwargs}})
                print(f"__MCP_CALL__{{request}}__MCP_END__", flush=True)
                # Read result from stdin
                result_line = sys.stdin.readline().strip()
                if result_line.startswith("__MCP_RESULT__"):
                    result_json = result_line[14:-12]  # Strip markers
                    try:
                        parsed = json.loads(result_json)
                        # If it's a string that looks like JSON, try to parse it again
                        if isinstance(parsed, str):
                            try:
                                return json.loads(parsed)
                            except:
                                return parsed
                        return parsed
                    except json.JSONDecodeError:
                        # Return as plain string if not valid JSON
                        return result_json
                elif result_line.startswith("__MCP_ERROR__"):
                    error = result_line[13:-12]
                    raise Exception(f"MCP error: {{error}}")
                return result_line
            
            # Convenience wrapper for common pattern
            class MCPServer:
                def __init__(self, name: str):
                    self.name = name
                
                def __getattr__(self, tool: str):
                    def call(*args, **kwargs):
                        # Support both positional and keyword args
                        # If first positional arg, treat as main param
                        if args and not kwargs:
                            # Common patterns: repo, path, query, etc
                            param_names = ['repo', 'owner', 'path', 'query', 'url', 'name', 'id']
                            for i, arg in enumerate(args):
                                if i < len(param_names):
                                    kwargs[param_names[i]] = arg
                        return mcp_call(self.name, tool, **kwargs)
                    return call
            
            # Pre-configured servers (agent can discover more)
            # Multiple aliases for common naming patterns
            filesystem = MCPServer("filesystem")
            github = MCPServer("github")
            mcp_filesystem = filesystem
            mcp_github = github
            
            # User code starts here
            __result__ = None
            __locals_before__ = set(dir())
            try:
{textwrap.indent(user_code, "                ")}
            except Exception as e:
                print(f"__ERROR__{{str(e)}}__END__", file=sys.stderr)
                sys.exit(1)
            
            # Print final result if any
            if __result__ is not None:
                print(f"__RESULT__{{json.dumps(__result__)}}__END__")
            else:
                # Auto-print any new variables that were created
                __new_vars__ = set(dir()) - __locals_before__ - {{'__locals_before__', '__result__'}}
                for var_name in __new_vars__:
                    if not var_name.startswith('_'):
                        val = locals().get(var_name)
                        if val is not None:
                            print(f"{{var_name}} = {{val}}")
        ''')
    
    async def _run_with_mcp_bridge(
        self,
        script_path: Path,
        mcp_call_handler: callable,
    ) -> ExecutionResult:
        """Run script and bridge MCP calls"""
        
        process = await asyncio.create_subprocess_exec(
            "python", str(script_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_dir,
        )
        
        output_lines = []
        error_lines = []
        return_value = None
        
        try:
            # Read stdout line by line, handling MCP calls
            while True:
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    return ExecutionResult(
                        success=False,
                        output="\n".join(output_lines),
                        error=f"Execution timed out after {self.timeout}s",
                    )
                
                if not line:
                    break
                
                line_str = line.decode().rstrip()
                
                # Handle MCP call requests
                if "__MCP_CALL__" in line_str:
                    start = line_str.index("__MCP_CALL__") + 12
                    end = line_str.index("__MCP_END__")
                    request = json.loads(line_str[start:end])
                    
                    try:
                        result = await mcp_call_handler(
                            request["server"],
                            request["tool"],
                            request["args"],
                        )
                        # Ensure result is JSON-serializable
                        if isinstance(result, str):
                            # Try to parse if it looks like JSON, otherwise wrap it
                            try:
                                json.loads(result)
                                response = f"__MCP_RESULT__{result}__MCP_END__\n"
                            except:
                                response = f"__MCP_RESULT__{json.dumps(result)}__MCP_END__\n"
                        else:
                            response = f"__MCP_RESULT__{json.dumps(result)}__MCP_END__\n"
                    except Exception as e:
                        response = f"__MCP_ERROR__{str(e)}__MCP_END__\n"
                    
                    process.stdin.write(response.encode())
                    await process.stdin.drain()
                
                # Handle result
                elif "__RESULT__" in line_str:
                    start = line_str.index("__RESULT__") + 10
                    end = line_str.index("__END__")
                    return_value = json.loads(line_str[start:end])
                
                # Regular output
                else:
                    output_lines.append(line_str)
            
            # Get stderr
            stderr = await process.stderr.read()
            if stderr:
                stderr_str = stderr.decode()
                if "__ERROR__" in stderr_str:
                    start = stderr_str.index("__ERROR__") + 9
                    end = stderr_str.index("__END__")
                    error_lines.append(stderr_str[start:end])
                else:
                    error_lines.append(stderr_str)
            
            await process.wait()
            
            return ExecutionResult(
                success=process.returncode == 0,
                output="\n".join(output_lines),
                error="\n".join(error_lines) if error_lines else None,
                return_value=return_value,
            )
            
        except Exception as e:
            process.kill()
            return ExecutionResult(
                success=False,
                output="\n".join(output_lines),
                error=str(e),
            )


class SkillsManager:
    """Manages saved code patterns (skills) that agents can reuse"""
    
    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
    
    def save_skill(self, name: str, code: str, description: str = ""):
        """Save a code pattern as a reusable skill"""
        skill_file = self.skills_dir / f"{name}.py"
        
        header = f'"""\nSkill: {name}\n{description}\n"""\n\n'
        skill_file.write_text(header + code)
        
        logger.info(f"Saved skill: {name}")
    
    def get_skill(self, name: str) -> str | None:
        """Get a saved skill by name"""
        skill_file = self.skills_dir / f"{name}.py"
        if skill_file.exists():
            return skill_file.read_text()
        return None
    
    def list_skills(self) -> list[dict]:
        """List all saved skills"""
        skills = []
        for f in self.skills_dir.glob("*.py"):
            content = f.read_text()
            # Extract description from docstring
            desc = ""
            if content.startswith('"""'):
                end = content.index('"""', 3)
                desc = content[3:end].strip()
            
            skills.append({
                "name": f.stem,
                "description": desc,
                "path": str(f),
            })
        return skills
