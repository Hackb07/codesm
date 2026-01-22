"""Bug Localization Tool - Find root cause of errors"""

import os
import re
import logging
import subprocess
from pathlib import Path
from typing import Optional

import httpx

from .base import Tool

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
BUG_MODEL = "anthropic/claude-sonnet-4-20250514"

BUG_SYSTEM_PROMPT = """You are an expert debugger. Given an error, stack trace, or symptom description, find the root cause.

## Analysis Process
1. **Parse Stack Trace**: Extract file paths, line numbers, function names
2. **Identify Error Type**: Understand the category of error
3. **Trace Data Flow**: Follow the execution path that led to the error
4. **Find Root Cause**: Distinguish symptoms from the actual bug location

## Output Format

### Error Analysis
Brief description of what the error means.

### Root Cause
**Location**: `file:line` (most likely location)
**Confidence**: high | medium | low
**Explanation**: Why this is the root cause

### Related Locations
List other files/locations that may be involved:
1. `file:line` - reason
2. `file:line` - reason

### Suggested Fix
Concrete steps or code changes to fix the issue.

### Investigation Commands
Commands to run for more information (if needed)."""


class BugLocalizeTool(Tool):
    name = "bug_localize"
    description = "Find root cause of an error given a stack trace, error message, or symptom description."
    
    def __init__(self, parent_tools=None):
        super().__init__()
        self._client: Optional[httpx.AsyncClient] = None
        self._parent_tools = parent_tools
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string",
                    "description": "Error message, stack trace, or symptom description",
                },
                "context": {
                    "type": "string",
                    "description": "Optional: additional context (what you were doing, recent changes, etc.)",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: specific files to examine",
                },
            },
            "required": ["error"],
        }
    
    def _get_client(self) -> httpx.AsyncClient:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/codesm",
                    "X-Title": "codesm-bug-localize",
                },
            )
        return self._client
    
    async def execute(self, args: dict, context: dict) -> str:
        error = args.get("error", "")
        extra_context = args.get("context", "")
        specified_files = args.get("files", [])
        cwd = Path(context.get("cwd", Path.cwd()))
        
        if not error:
            return "Error: 'error' parameter is required (stack trace or error message)"
        
        extracted_files = self._extract_files_from_stacktrace(error, cwd)
        all_files = list(set(extracted_files + specified_files))
        
        file_contents = {}
        for file_path in all_files[:10]:
            path = Path(file_path)
            if not path.is_absolute():
                path = cwd / path
            if path.exists() and path.is_file():
                try:
                    content = path.read_text()
                    if len(content) > 10000:
                        content = content[:10000] + "\n... (truncated)"
                    file_contents[str(path)] = content
                except Exception as e:
                    logger.warning(f"Could not read {path}: {e}")
        
        related_code = await self._search_related_code(error, cwd)
        
        try:
            analysis = await self._analyze_error(
                error=error,
                extra_context=extra_context,
                file_contents=file_contents,
                related_code=related_code,
            )
            return analysis
        except Exception as e:
            logger.error(f"Bug localization failed: {e}")
            return f"Bug localization failed: {e}"
    
    def _extract_files_from_stacktrace(self, error: str, cwd: Path) -> list[str]:
        """Extract file paths from stack traces"""
        files = []
        
        patterns = [
            r'File "([^"]+)", line \d+',
            r'at .*?\(([^:)]+):\d+:\d+\)',
            r'^\s+at\s+.*?([^\s:]+\.\w+):\d+',
            r'([^\s:]+\.(?:py|js|ts|go|rs|rb|java)):\d+',
            r'in\s+([^\s:]+\.(?:py|js|ts|go|rs)):\d+',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, error, re.MULTILINE)
            for match in matches:
                if match and not match.startswith('<'):
                    path = Path(match)
                    if not path.is_absolute():
                        full_path = cwd / match
                        if full_path.exists():
                            files.append(str(full_path))
                    elif path.exists():
                        files.append(str(path))
        
        return files
    
    async def _search_related_code(self, error: str, cwd: Path) -> str:
        """Search for related code patterns in the codebase"""
        search_terms = []
        
        error_patterns = [
            r"(?:Error|Exception|Failed):\s*(.+?)(?:\n|$)",
            r"'(\w+)'.*(?:not defined|undefined|null)",
            r"(?:function|method|attribute)\s+'(\w+)'",
            r"(\w+Error|\w+Exception)",
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, error)
            search_terms.extend(matches)
        
        search_terms = list(set(search_terms))[:5]
        
        if not search_terms:
            return ""
        
        results = []
        for term in search_terms:
            if len(term) < 3:
                continue
            try:
                result = subprocess.run(
                    ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.ts", 
                     "-l", term],
                    capture_output=True, text=True, cwd=cwd, timeout=10
                )
                if result.stdout:
                    files = result.stdout.strip().split("\n")[:3]
                    results.append(f"Files containing '{term}': {', '.join(files)}")
            except:
                pass
        
        return "\n".join(results)
    
    async def _analyze_error(
        self,
        error: str,
        extra_context: str,
        file_contents: dict[str, str],
        related_code: str,
    ) -> str:
        """Analyze error using LLM"""
        client = self._get_client()
        
        prompt_parts = ["Analyze this error and find the root cause:\n\n"]
        prompt_parts.append(f"## Error/Stack Trace\n```\n{error}\n```\n\n")
        
        if extra_context:
            prompt_parts.append(f"## Additional Context\n{extra_context}\n\n")
        
        if file_contents:
            prompt_parts.append("## Relevant Files\n")
            for path, content in file_contents.items():
                prompt_parts.append(f"### {path}\n```\n{content}\n```\n\n")
        
        if related_code:
            prompt_parts.append(f"## Related Code Search\n{related_code}\n\n")
        
        response = await client.post(
            OPENROUTER_URL,
            json={
                "model": BUG_MODEL,
                "messages": [
                    {"role": "system", "content": BUG_SYSTEM_PROMPT},
                    {"role": "user", "content": "".join(prompt_parts)},
                ],
                "temperature": 0.1,
                "max_tokens": 4096,
            },
        )
        
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code}")
        
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "No analysis")
