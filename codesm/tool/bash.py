"""Bash command tool"""

import asyncio
from pathlib import Path
from .base import Tool


class BashTool(Tool):
    name = "bash"
    description = "Execute shell commands. Use for builds, git, tests, etc."
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 120)",
                },
            },
            "required": ["command"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        command = args["command"]
        cwd = args.get("cwd") or context.get("cwd", ".")
        timeout = args.get("timeout", 120)
        
        # Try Rust core first
        try:
            from codesm_core import execute_command
            stdout, stderr, exit_code = execute_command(command, str(cwd), timeout)
            output = stdout + stderr
            if exit_code != 0:
                output += f"\n\nExit code: {exit_code}"
            return output
        except ImportError:
            pass
        
        # Fallback to asyncio
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            
            output = stdout.decode() + stderr.decode()
            if proc.returncode != 0:
                output += f"\n\nExit code: {proc.returncode}"
            return output
        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"
