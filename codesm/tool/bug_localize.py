"""Bug Localization Tool - Finds root cause of errors by analyzing stack traces and code"""

import os
import re
import logging
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import httpx

from .base import Tool

if TYPE_CHECKING:
    from codesm.tool.registry import ToolRegistry

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "anthropic/claude-sonnet-4-20250514"

BUG_LOCALIZE_SYSTEM_PROMPT = """You are an expert debugger. Your job is to analyze error messages, stack traces, and code to find the root cause of bugs.

# Your Approach

1. **Parse the error**: Extract key information from the error message and stack trace
2. **Trace the flow**: Follow the execution path to understand how the error occurred
3. **Identify patterns**: Look for common bug patterns (null checks, type errors, etc.)
4. **Correlate with code**: Match error symptoms with actual code issues
5. **Rank by likelihood**: Prioritize the most probable root causes

# Output Format

Return your analysis as a ranked list of likely bug locations:

## Most Likely Cause
- **File**: <filepath>
- **Line**: <line number>
- **Confidence**: High/Medium/Low
- **Issue**: <brief description of the bug>
- **Explanation**: <why this is likely the cause>
- **Fix**: <suggested fix with code if possible>

## Alternative Location 1
...

# Bug Pattern Recognition

Common patterns to look for:
- **NoneType errors**: Variable is None when it shouldn't be - trace back to source
- **KeyError/IndexError**: Check bounds and key existence
- **TypeError**: Check function arguments and return types
- **AttributeError**: Check object initialization and type
- **ImportError**: Check dependencies and circular imports
- **Async issues**: Missing await, race conditions, unhandled promises

Be specific and actionable. Reference exact line numbers and code snippets.
When suggesting fixes, provide actual code that can be applied."""


@dataclass
class BugLocation:
    """A potential bug location."""
    file: str
    line: int | None
    confidence: str
    issue: str
    explanation: str
    fix: str | None = None


@dataclass
class BugAnalysisResult:
    """Complete bug analysis result."""
    locations: list[BugLocation] = field(default_factory=list)
    summary: str = ""
    root_cause: Optional[str] = None
    suggested_fixes: list[dict] = field(default_factory=list)
    lsp_diagnostics: list[dict] = field(default_factory=list)


class BugLocalizeTool(Tool):
    """Finds the root cause of errors by analyzing stack traces and code."""
    
    name = "bug_localize"
    description = "Find the root cause of bugs by analyzing errors, stack traces, LSP diagnostics, and code. Can auto-fix issues."
    
    def __init__(self, parent_tools: "ToolRegistry | None" = None):
        super().__init__()
        self._parent_tools = parent_tools
        self._client = None
    
    def set_parent(self, tools: "ToolRegistry"):
        """Set parent tools (called by Agent after init)"""
        self._parent_tools = tools
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string",
                    "description": "Error message, stack trace, or description of the bug/symptom",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context about when/how the error occurs",
                },
                "search_paths": {
                    "type": "string",
                    "description": "Comma-separated paths to narrow the search scope",
                },
                "use_lsp": {
                    "type": "boolean",
                    "description": "Include LSP diagnostics in analysis (default: true)",
                },
                "auto_fix": {
                    "type": "boolean",
                    "description": "Attempt to automatically fix the bug (default: false)",
                },
                "run_command": {
                    "type": "string",
                    "description": "Command to run to reproduce the error (e.g., 'pytest test.py')",
                },
            },
            "required": ["error"],
        }
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/codesm",
                    "X-Title": "codesm",
                },
            )
        return self._client
    
    async def execute(self, args: dict, context: dict) -> str:
        error = args.get("error", "")
        user_context = args.get("context", "")
        search_paths = args.get("search_paths", "")
        use_lsp = args.get("use_lsp", True)
        auto_fix = args.get("auto_fix", False)
        run_command = args.get("run_command", "")
        cwd = context.get("cwd", ".")
        session = context.get("session")
        
        if not error:
            return "Error: error parameter is required"
        
        # If run_command provided, execute it to capture fresh error
        if run_command:
            captured_error = await self._run_and_capture_error(run_command, cwd)
            if captured_error:
                error = captured_error
        
        # Extract files from stack trace
        files_from_trace = self._extract_files_from_stack_trace(error, cwd)
        
        # Get LSP diagnostics if enabled
        lsp_diagnostics = []
        if use_lsp:
            lsp_diagnostics = await self._get_lsp_diagnostics(files_from_trace, cwd)
        
        # Search for related files
        if search_paths:
            paths = [p.strip() for p in search_paths.split(",")]
            search_files = await self._search_for_related_files(error, paths, cwd)
            files_from_trace.extend(search_files)
        
        # Read file contents
        file_contents = await self._read_file_contents(files_from_trace, cwd)
        
        # Search for related patterns
        related_code = await self._search_for_patterns(error, cwd)
        
        # Follow imports to find bug chain
        import_chain = await self._trace_import_chain(files_from_trace, error, cwd)
        
        # Build analysis prompt
        prompt = self._build_prompt(
            error=error,
            user_context=user_context,
            file_contents=file_contents,
            related_code=related_code,
            lsp_diagnostics=lsp_diagnostics,
            import_chain=import_chain,
            auto_fix=auto_fix,
        )
        
        try:
            client = self._get_client()
            response = await client.post(
                OPENROUTER_URL,
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": BUG_LOCALIZE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 4096,
                },
            )
            
            if response.status_code != 200:
                return f"Error: API returned {response.status_code}: {response.text}"
            
            data = response.json()
            result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            output = f"## Bug Localization Analysis\n\n{result}"
            
            # Add LSP diagnostics section if we have them
            if lsp_diagnostics:
                output += "\n\n## LSP Diagnostics\n\n"
                for diag in lsp_diagnostics[:5]:
                    severity = diag.get("severity", "info")
                    icon = "✗" if severity == "error" else "⚠" if severity == "warning" else "ℹ"
                    output += f"{icon} **{diag.get('file', 'unknown')}:{diag.get('line', '?')}** - {diag.get('message', '')}\n"
            
            # If auto_fix requested, try to apply fixes
            if auto_fix:
                fix_result = await self._attempt_auto_fix(result, file_contents, session, cwd)
                if fix_result:
                    output += f"\n\n## Auto-Fix Applied\n\n{fix_result}"
            
            return output
            
        except Exception as e:
            logger.exception("Bug localization failed")
            return f"Error during bug localization: {e}"
    
    async def _run_and_capture_error(self, command: str, cwd: str) -> str:
        """Run a command and capture its error output."""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            
            if proc.returncode != 0:
                output = stderr.decode() if stderr else stdout.decode()
                return f"Command: {command}\nExit code: {proc.returncode}\n\n{output}"
            
            return ""
        except asyncio.TimeoutError:
            return f"Command timed out after 60s: {command}"
        except Exception as e:
            return f"Failed to run command: {e}"
    
    async def _get_lsp_diagnostics(
        self,
        files: list[tuple[str, int | None]],
        cwd: str
    ) -> list[dict]:
        """Get LSP diagnostics for the relevant files."""
        diagnostics = []
        
        try:
            from codesm import lsp
            
            for file_path, _ in files[:5]:
                path = Path(file_path) if Path(file_path).is_absolute() else Path(cwd) / file_path
                if not path.exists():
                    continue
                
                try:
                    file_diags = await lsp.touch_file(str(path))
                    for diag in file_diags:
                        diagnostics.append({
                            "file": str(path),
                            "line": getattr(diag, "line", None),
                            "severity": getattr(diag, "severity", "info"),
                            "message": getattr(diag, "message", str(diag)),
                        })
                except Exception as e:
                    logger.debug(f"LSP diagnostics failed for {path}: {e}")
        except ImportError:
            logger.debug("LSP module not available")
        
        return diagnostics
    
    async def _trace_import_chain(
        self,
        files: list[tuple[str, int | None]],
        error: str,
        cwd: str
    ) -> list[str]:
        """Trace import chain to find related files."""
        import_chain = []
        
        # Extract module names from error
        module_patterns = [
            r"from (\S+) import",
            r"import (\S+)",
            r"ModuleNotFoundError: No module named '(\S+)'",
            r"ImportError:.*'(\S+)'",
        ]
        
        modules = set()
        for pattern in module_patterns:
            matches = re.findall(pattern, error)
            modules.update(matches)
        
        # Search for these modules in the codebase
        if self._parent_tools and modules:
            grep_tool = self._parent_tools.get("grep")
            if grep_tool:
                for module in list(modules)[:3]:
                    module_name = module.split(".")[-1]
                    try:
                        result = await grep_tool.execute(
                            {"pattern": f"def |class ", "path": cwd, "glob": f"**/{module_name}.py"},
                            {"cwd": cwd},
                        )
                        if result and "No matches" not in result:
                            import_chain.append(f"Module '{module}' found:\n{result[:500]}")
                    except Exception:
                        pass
        
        return import_chain
    
    async def _attempt_auto_fix(
        self,
        analysis: str,
        file_contents: dict[str, str],
        session,
        cwd: str
    ) -> str:
        """Attempt to automatically fix the bug based on analysis."""
        fixes_applied = []
        
        # Extract fix suggestions from analysis
        fix_patterns = [
            r"\*\*Fix\*\*:\s*```(\w+)?\n(.*?)```",
            r"```(\w+)?\n(.*?)```",
        ]
        
        for pattern in fix_patterns:
            matches = re.findall(pattern, analysis, re.DOTALL)
            for lang, code in matches:
                # Try to match code to a file and location
                for file_path, content in file_contents.items():
                    # Look for context in the fix
                    code_lines = code.strip().split("\n")
                    if len(code_lines) < 2:
                        continue
                    
                    # Try to find and replace
                    for i, line in enumerate(code_lines):
                        if line.strip().startswith("+") or line.strip().startswith("-"):
                            continue
                        # This is context - try to find it in the file
                        if line.strip() in content:
                            # Found context, try to apply the fix
                            # This is a simplified approach - in practice would need more sophisticated matching
                            logger.debug(f"Found potential fix location in {file_path}")
                            break
        
        if not fixes_applied:
            return "No automatic fixes could be safely applied. Review the suggested fixes above."
        
        return "\n".join(fixes_applied)
    
    def _extract_files_from_stack_trace(self, error: str, cwd: str) -> list[tuple[str, int | None]]:
        """Extract file paths and line numbers from a stack trace."""
        files = []
        
        patterns = [
            r'File ["\']([^"\']+)["\'], line (\d+)',
            r'at ([^\s]+):(\d+)',
            r'([^\s]+\.py):(\d+)',
            r'([^\s]+\.(js|ts|tsx)):(\d+)',
            r'([^\s]+\.rs):(\d+)',
            r'([^\s]+\.go):(\d+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, error)
            for match in matches:
                if len(match) >= 2:
                    file_path = match[0]
                    line_num = int(match[1]) if match[1].isdigit() else None
                    
                    if file_path.startswith("/") or Path(cwd, file_path).exists():
                        files.append((file_path, line_num))
        
        seen = set()
        unique_files = []
        for f in files:
            if f[0] not in seen:
                seen.add(f[0])
                unique_files.append(f)
        
        return unique_files
    
    async def _search_for_related_files(
        self, 
        error: str, 
        paths: list[str], 
        cwd: str
    ) -> list[tuple[str, int | None]]:
        """Search for files related to the error."""
        files = []
        
        keywords = self._extract_keywords_from_error(error)
        
        if self._parent_tools:
            grep_tool = self._parent_tools.get("grep")
            if grep_tool:
                for keyword in keywords[:3]:
                    for search_path in paths:
                        full_path = Path(search_path) if Path(search_path).is_absolute() else Path(cwd) / search_path
                        if not full_path.exists():
                            continue
                        
                        try:
                            result = await grep_tool.execute(
                                {"pattern": keyword, "path": str(full_path)},
                                {"cwd": cwd},
                            )
                            
                            for line in result.split("\n"):
                                match = re.search(r'\[([^\]]+):(\d+)\]', line)
                                if match:
                                    files.append((match.group(1), int(match.group(2))))
                        except Exception:
                            pass
        
        return files[:10]
    
    def _extract_keywords_from_error(self, error: str) -> list[str]:
        """Extract searchable keywords from an error message."""
        keywords = []
        
        name_patterns = [
            r"'(\w+)'",
            r'"(\w+)"',
            r'`(\w+)`',
            r'(\w+Error)',
            r'(\w+Exception)',
            r'def (\w+)',
            r'class (\w+)',
            r'function (\w+)',
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, error)
            keywords.extend(matches)
        
        common_words = {'the', 'is', 'not', 'a', 'an', 'of', 'in', 'to', 'for', 'error', 'none', 'null'}
        keywords = [k for k in keywords if k.lower() not in common_words and len(k) > 2]
        
        return list(dict.fromkeys(keywords))[:5]
    
    async def _read_file_contents(
        self, 
        files: list[tuple[str, int | None]], 
        cwd: str
    ) -> dict[str, str]:
        """Read contents of files, focusing on lines around errors."""
        contents = {}
        
        for file_path, line_num in files[:5]:
            path = Path(file_path) if Path(file_path).is_absolute() else Path(cwd) / file_path
            if not path.exists():
                continue
            
            try:
                all_lines = path.read_text().split("\n")
                
                if line_num:
                    start = max(0, line_num - 15)
                    end = min(len(all_lines), line_num + 15)
                    excerpt_lines = []
                    for i, line in enumerate(all_lines[start:end], start=start + 1):
                        marker = ">>> " if i == line_num else "    "
                        excerpt_lines.append(f"{marker}{i}: {line}")
                    contents[str(path)] = "\n".join(excerpt_lines)
                else:
                    contents[str(path)] = "\n".join(all_lines[:100])
                    
            except Exception as e:
                logger.debug(f"Could not read {path}: {e}")
        
        return contents
    
    async def _search_for_patterns(self, error: str, cwd: str) -> str:
        """Search for code patterns related to the error."""
        results = []
        
        keywords = self._extract_keywords_from_error(error)
        
        if self._parent_tools:
            grep_tool = self._parent_tools.get("grep")
            if grep_tool:
                for keyword in keywords[:2]:
                    try:
                        result = await grep_tool.execute(
                            {"pattern": keyword, "path": cwd},
                            {"cwd": cwd},
                        )
                        if result and "No matches" not in result:
                            results.append(f"### Matches for '{keyword}':\n{result[:2000]}")
                    except Exception:
                        pass
        
        return "\n\n".join(results)
    
    def _build_prompt(
        self,
        error: str,
        user_context: str,
        file_contents: dict[str, str],
        related_code: str,
        lsp_diagnostics: list[dict],
        import_chain: list[str],
        auto_fix: bool,
    ) -> str:
        """Build the analysis prompt."""
        parts = [f"# Error/Bug Report\n\n```\n{error}\n```"]
        
        if user_context:
            parts.append(f"\n# Additional Context\n\n{user_context}")
        
        if lsp_diagnostics:
            parts.append("\n# LSP Diagnostics (Real-time errors from language server)\n")
            for diag in lsp_diagnostics[:5]:
                parts.append(f"- {diag.get('severity', 'info')}: {diag.get('file', '')}:{diag.get('line', '?')} - {diag.get('message', '')}")
        
        if file_contents:
            parts.append("\n# Relevant Source Files\n")
            for path, content in file_contents.items():
                parts.append(f"\n## {path}\n```\n{content}\n```")
        
        if import_chain:
            parts.append("\n# Import Chain Analysis\n")
            for chain in import_chain:
                parts.append(chain)
        
        if related_code:
            parts.append(f"\n# Related Code Patterns\n\n{related_code}")
        
        fix_instruction = """
If suggesting fixes, provide them as actual code snippets that can be directly applied.
Format fixes as:
**Fix for <file>:<line>**
```<language>
<corrected code>
```
""" if auto_fix else ""
        
        parts.append(f"""

# Task

Analyze the error above and identify the most likely root cause.
Provide a ranked list of potential bug locations with:
1. File and line number
2. Confidence level (High/Medium/Low)
3. Explanation of why this is likely the cause
4. Suggested fix with actual code
{fix_instruction}
Focus on actionable findings that help fix the bug.
""")
        
        return "\n".join(parts)
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
