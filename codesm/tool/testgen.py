"""Test Generation Tool - Auto-generate tests for code"""

import os
import logging
from pathlib import Path
from typing import Optional

import httpx

from .base import Tool

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TESTGEN_MODEL = "anthropic/claude-sonnet-4-20250514"

TESTGEN_SYSTEM_PROMPT = """You are an expert test engineer. Generate comprehensive tests for the provided code.

## Guidelines
1. **Detect Framework**: Look at existing tests to match the testing framework (pytest, unittest, jest, go test, etc.)
2. **Test Coverage**:
   - Happy path: Normal expected inputs
   - Edge cases: Empty inputs, boundaries, special characters
   - Error handling: Invalid inputs, exceptions
   - Integration points: Mock external dependencies
3. **Test Quality**:
   - Clear test names describing what's being tested
   - One assertion concept per test
   - Proper setup and teardown
   - Use fixtures/mocks appropriately
4. **Match Style**: Follow the code style and patterns of existing tests

## Output Format
Return ONLY the test code, ready to save to a file. Include necessary imports.
Start with a brief comment explaining what's being tested.

If you see existing test patterns, follow them exactly."""


class TestGenTool(Tool):
    name = "testgen"
    description = "Auto-generate tests for a file or function. Detects framework and generates comprehensive test cases."
    
    def __init__(self, parent_tools=None):
        super().__init__()
        self._client: Optional[httpx.AsyncClient] = None
        self._parent_tools = parent_tools
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Path to the file to generate tests for",
                },
                "function": {
                    "type": "string",
                    "description": "Optional: specific function/class name to test",
                },
                "framework": {
                    "type": "string",
                    "description": "Optional: test framework to use (pytest, unittest, jest, etc.). Auto-detected if not specified.",
                },
                "output_file": {
                    "type": "string",
                    "description": "Optional: path to write tests to. If not specified, returns test code only.",
                },
            },
            "required": ["file"],
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
                    "HTTP-Referer": "https://github.com/Aditya-PS-05",
                    "X-Title": "codesm-testgen",
                },
            )
        return self._client
    
    async def execute(self, args: dict, context: dict) -> str:
        file_path = args.get("file")
        function_name = args.get("function")
        framework = args.get("framework")
        output_file = args.get("output_file")
        cwd = Path(context.get("cwd", Path.cwd()))
        
        if not file_path:
            return "Error: 'file' parameter is required"
        
        path = Path(file_path)
        if not path.is_absolute():
            path = cwd / path
        
        if not path.exists():
            return f"Error: File not found: {path}"
        
        try:
            source_code = path.read_text()
        except Exception as e:
            return f"Error reading file: {e}"
        
        existing_tests = self._find_existing_tests(path, cwd)
        detected_framework = framework or self._detect_framework(path, existing_tests, cwd)
        
        try:
            test_code = await self._generate_tests(
                source_code=source_code,
                file_path=str(path),
                function_name=function_name,
                framework=detected_framework,
                existing_tests=existing_tests,
            )
        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            return f"Test generation failed: {e}"
        
        if output_file:
            output_path = Path(output_file)
            if not output_path.is_absolute():
                output_path = cwd / output_path
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(test_code)
                return f"Tests written to {output_path}\n\n```\n{test_code}\n```"
            except Exception as e:
                return f"Error writing tests: {e}\n\nGenerated code:\n```\n{test_code}\n```"
        
        return f"Generated tests for {path.name}:\n\n```python\n{test_code}\n```"
    
    def _find_existing_tests(self, source_path: Path, cwd: Path) -> str:
        """Find existing test files for context"""
        test_patterns = [
            source_path.parent / f"test_{source_path.name}",
            source_path.parent / f"{source_path.stem}_test{source_path.suffix}",
            cwd / "tests" / f"test_{source_path.name}",
            cwd / "test" / f"test_{source_path.name}",
        ]
        
        for pattern in test_patterns:
            if pattern.exists():
                try:
                    content = pattern.read_text()
                    if len(content) > 5000:
                        content = content[:5000] + "\n... (truncated)"
                    return f"# Existing tests from {pattern.name}:\n{content}"
                except:
                    pass
        
        for test_dir in [cwd / "tests", cwd / "test"]:
            if test_dir.exists():
                for test_file in list(test_dir.glob("test_*.py"))[:2]:
                    try:
                        content = test_file.read_text()
                        if len(content) > 2000:
                            content = content[:2000] + "\n... (truncated)"
                        return f"# Example test from {test_file.name}:\n{content}"
                    except:
                        pass
        
        return ""
    
    def _detect_framework(self, source_path: Path, existing_tests: str, cwd: Path) -> str:
        """Detect testing framework from file extension and existing tests"""
        suffix = source_path.suffix.lower()
        
        if existing_tests:
            if "import pytest" in existing_tests or "@pytest" in existing_tests:
                return "pytest"
            if "from unittest" in existing_tests or "import unittest" in existing_tests:
                return "unittest"
            if "describe(" in existing_tests or "it(" in existing_tests:
                return "jest"
            if "func Test" in existing_tests:
                return "go"
        
        framework_map = {
            ".py": "pytest",
            ".js": "jest",
            ".ts": "jest",
            ".jsx": "jest",
            ".tsx": "jest",
            ".go": "go",
            ".rs": "rust",
            ".rb": "rspec",
        }
        
        return framework_map.get(suffix, "pytest")
    
    async def _generate_tests(
        self,
        source_code: str,
        file_path: str,
        function_name: Optional[str],
        framework: str,
        existing_tests: str,
    ) -> str:
        """Generate tests using LLM"""
        client = self._get_client()
        
        prompt_parts = [
            f"Generate {framework} tests for this code:\n",
            f"File: {file_path}\n",
        ]
        
        if function_name:
            prompt_parts.append(f"Focus on: {function_name}\n")
        
        prompt_parts.append(f"\n```\n{source_code}\n```\n")
        
        if existing_tests:
            prompt_parts.append(f"\n{existing_tests}\n\nMatch the style of existing tests.")
        
        response = await client.post(
            OPENROUTER_URL,
            json={
                "model": TESTGEN_MODEL,
                "messages": [
                    {"role": "system", "content": TESTGEN_SYSTEM_PROMPT},
                    {"role": "user", "content": "".join(prompt_parts)},
                ],
                "temperature": 0.2,
                "max_tokens": 4096,
            },
        )
        
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code}")
        
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if "```" in content:
            import re
            match = re.search(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return content.strip()
