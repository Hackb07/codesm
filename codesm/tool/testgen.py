"""Test Generation Tool - Auto-generates tests for code"""

import os
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from .base import Tool

if TYPE_CHECKING:
    from codesm.tool.registry import ToolRegistry

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "anthropic/claude-sonnet-4-20250514"

# Language-specific test configurations
LANGUAGE_CONFIGS = {
    ".py": {
        "name": "Python",
        "frameworks": ["pytest", "unittest"],
        "test_patterns": ["test_*.py", "*_test.py"],
        "test_dirs": ["tests", "test", "."],
    },
    ".ts": {
        "name": "TypeScript",
        "frameworks": ["jest", "vitest", "mocha"],
        "test_patterns": ["*.test.ts", "*.spec.ts", "__tests__/*.ts"],
        "test_dirs": ["__tests__", "tests", "test", "."],
    },
    ".tsx": {
        "name": "TypeScript React",
        "frameworks": ["jest", "vitest", "testing-library"],
        "test_patterns": ["*.test.tsx", "*.spec.tsx"],
        "test_dirs": ["__tests__", "tests", "."],
    },
    ".js": {
        "name": "JavaScript",
        "frameworks": ["jest", "vitest", "mocha"],
        "test_patterns": ["*.test.js", "*.spec.js"],
        "test_dirs": ["__tests__", "tests", "test", "."],
    },
    ".jsx": {
        "name": "JavaScript React",
        "frameworks": ["jest", "vitest", "testing-library"],
        "test_patterns": ["*.test.jsx", "*.spec.jsx"],
        "test_dirs": ["__tests__", "tests", "."],
    },
    ".rs": {
        "name": "Rust",
        "frameworks": ["cargo test"],
        "test_patterns": ["*_test.rs", "tests/*.rs"],
        "test_dirs": ["tests", "src"],
    },
    ".go": {
        "name": "Go",
        "frameworks": ["testing"],
        "test_patterns": ["*_test.go"],
        "test_dirs": ["."],
    },
}

TESTGEN_SYSTEM_PROMPT = """You are an expert test writer. Your job is to generate comprehensive, high-quality tests for code.

# Guidelines

1. **Detect Framework**: Analyze existing tests to determine the project's testing framework
2. **Match Conventions**: Follow the project's existing test patterns (naming, fixtures, assertions)
3. **Be Comprehensive**: Cover happy path, edge cases, and error handling
4. **Be Practical**: Write tests that actually run and catch bugs
5. **Mock External Dependencies**: Use appropriate mocking for I/O, APIs, databases

# Test Categories

1. **Unit Tests**: Test individual functions/methods in isolation
2. **Edge Cases**: Empty inputs, None/null values, boundary conditions, large data
3. **Error Handling**: Invalid inputs, exceptions, failure modes

# Output Format

Return ONLY the generated test code as a complete, runnable file.
Include all necessary imports at the top.
Use descriptive test names that explain what is being tested.
Add brief comments for complex test scenarios.

Do not include explanatory text outside the code - just return the code."""


class TestGenTool(Tool):
    """Generates test cases for code in multiple languages."""
    
    name = "testgen"
    description = "Generate test cases for code. Supports Python, TypeScript, JavaScript, Rust, and Go."
    
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
                "file_path": {
                    "type": "string",
                    "description": "Path to the source file to generate tests for",
                },
                "function_name": {
                    "type": "string",
                    "description": "Optional specific function, class, or method to test",
                },
                "test_types": {
                    "type": "string",
                    "description": "Comma-separated test types: 'unit', 'edge', 'error' (default: all)",
                },
                "auto_write": {
                    "type": "boolean",
                    "description": "Automatically write tests to file in appropriate location (default: false)",
                },
                "changed_only": {
                    "type": "boolean",
                    "description": "Generate tests only for changed functions (uses git diff)",
                },
            },
            "required": ["file_path"],
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
        import asyncio
        
        file_path = args.get("file_path", "")
        function_name = args.get("function_name")
        test_types = args.get("test_types", "unit,edge,error")
        auto_write = args.get("auto_write", False)
        changed_only = args.get("changed_only", False)
        cwd = context.get("cwd", ".")
        session = context.get("session")
        
        if not file_path:
            return "Error: file_path is required"
        
        path = Path(file_path) if Path(file_path).is_absolute() else Path(cwd) / file_path
        if not path.exists():
            return f"Error: File not found: {path}"
        
        # Check if language is supported
        lang_config = LANGUAGE_CONFIGS.get(path.suffix)
        if not lang_config:
            supported = ", ".join(LANGUAGE_CONFIGS.keys())
            return f"Error: Unsupported file type '{path.suffix}'. Supported: {supported}"
        
        try:
            source_code = path.read_text()
        except Exception as e:
            return f"Error reading file: {e}"
        
        # If changed_only, extract only changed functions
        if changed_only:
            changed_funcs = await self._get_changed_functions(path, cwd)
            if changed_funcs:
                function_name = ",".join(changed_funcs)
        
        # Detect project's test framework
        framework_info = await self._detect_test_framework(path.parent, cwd, lang_config)
        
        prompt = self._build_prompt(
            source_code=source_code,
            file_path=str(path),
            function_name=function_name,
            test_types=test_types,
            framework_info=framework_info,
            language=lang_config["name"],
        )
        
        try:
            client = self._get_client()
            response = await client.post(
                OPENROUTER_URL,
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": TESTGEN_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 8192,
                },
            )
            
            if response.status_code != 200:
                return f"Error: API returned {response.status_code}: {response.text}"
            
            data = response.json()
            result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            test_code = self._clean_response(result)
            
            # Auto-write if requested
            if auto_write:
                test_path = self._determine_test_path(path, lang_config)
                write_result = await self._write_test_file(test_path, test_code, session)
                return write_result
            
            return self._format_output(test_code, str(path), lang_config)
            
        except Exception as e:
            logger.exception("Test generation failed")
            return f"Error generating tests: {e}"
    
    async def _get_changed_functions(self, path: Path, cwd: str) -> list[str]:
        """Extract names of changed functions from git diff."""
        import asyncio
        import re
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "--", str(path),
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode != 0:
                return []
            
            diff = stdout.decode()
            
            # Extract function/class names from diff
            patterns = [
                r'^\+.*def (\w+)\s*\(',  # Python function
                r'^\+.*class (\w+)',  # Python class
                r'^\+.*function (\w+)\s*\(',  # JS function
                r'^\+.*const (\w+)\s*=.*=>',  # Arrow function
                r'^\+.*fn (\w+)\s*\(',  # Rust function
                r'^\+.*func (\w+)\s*\(',  # Go function
            ]
            
            names = set()
            for pattern in patterns:
                matches = re.findall(pattern, diff, re.MULTILINE)
                names.update(matches)
            
            return list(names)
        except Exception:
            return []
    
    async def _detect_test_framework(self, source_dir: Path, cwd: str, lang_config: dict) -> dict:
        """Detect the testing framework used in the project."""
        framework_info = {
            "framework": lang_config["frameworks"][0] if lang_config["frameworks"] else "unknown",
            "patterns": [],
            "imports": [],
            "example_test": "",
            "language": lang_config["name"],
        }
        
        project_root = Path(cwd)
        
        for test_dir in lang_config["test_dirs"]:
            test_path = project_root / test_dir
            if not test_path.exists():
                continue
            
            for pattern in lang_config["test_patterns"]:
                test_files = list(test_path.glob(pattern))
                if test_files:
                    try:
                        example_content = test_files[0].read_text()
                        framework_info["example_test"] = example_content[:2000]
                        
                        # Detect framework from imports
                        for fw in lang_config["frameworks"]:
                            if fw.lower() in example_content.lower():
                                framework_info["framework"] = fw
                                break
                        
                        break
                    except Exception:
                        continue
            
            if framework_info["example_test"]:
                break
        
        return framework_info
    
    def _build_prompt(
        self,
        source_code: str,
        file_path: str,
        function_name: str | None,
        test_types: str,
        framework_info: dict,
        language: str,
    ) -> str:
        """Build the prompt for test generation."""
        parts = [f"# Language: {language}\n# Source File: {file_path}\n\n```\n{source_code}\n```\n"]
        
        parts.append(f"\n# Testing Framework: {framework_info['framework']}")
        
        if framework_info["example_test"]:
            parts.append(f"\n# Example existing test from project:\n```\n{framework_info['example_test']}\n```")
        
        parts.append(f"\n# Test Types to Generate: {test_types}")
        
        if function_name:
            parts.append(f"\n# Focus on: {function_name}")
        
        parts.append(f"""

# Task
Generate comprehensive tests for the {language} source code above.
Follow the project's existing test patterns if available.
Return only the test code, ready to run.
""")
        
        return "\n".join(parts)
    
    def _clean_response(self, response: str) -> str:
        """Clean the LLM response to extract just the code."""
        # Try to extract code from markdown blocks
        for lang in ["python", "typescript", "javascript", "rust", "go", ""]:
            marker = f"```{lang}"
            if marker in response:
                parts = response.split(marker)
                if len(parts) > 1:
                    code = parts[1].split("```")[0]
                    return code.strip()
        
        if "```" in response:
            parts = response.split("```")
            if len(parts) > 1:
                return parts[1].strip()
        
        return response.strip()
    
    def _determine_test_path(self, source_path: Path, lang_config: dict) -> Path:
        """Determine the appropriate path for the test file."""
        source_name = source_path.stem
        suffix = source_path.suffix
        
        # Determine test filename based on language convention
        if suffix in [".py"]:
            test_name = f"test_{source_name}.py"
        elif suffix in [".ts", ".tsx"]:
            test_name = f"{source_name}.test{suffix}"
        elif suffix in [".js", ".jsx"]:
            test_name = f"{source_name}.test{suffix}"
        elif suffix == ".rs":
            test_name = f"{source_name}_test.rs"
        elif suffix == ".go":
            test_name = f"{source_name}_test.go"
        else:
            test_name = f"test_{source_name}{suffix}"
        
        # Find or create tests directory
        project_root = source_path.parent
        test_dirs = lang_config["test_dirs"]
        
        for test_dir in test_dirs:
            test_path = project_root / test_dir
            if test_path.exists() and test_path.is_dir():
                return test_path / test_name
        
        # Default to tests/ directory
        tests_dir = project_root / "tests"
        tests_dir.mkdir(exist_ok=True)
        return tests_dir / test_name
    
    async def _write_test_file(self, test_path: Path, test_code: str, session) -> str:
        """Write the generated test code to a file."""
        try:
            # Check if file exists
            is_new = not test_path.exists()
            old_content = "" if is_new else test_path.read_text()
            
            # Write the file
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text(test_code)
            
            # Record in undo history if session available
            if session:
                history = session.get_undo_history()
                history.record_edit(
                    file_path=str(test_path),
                    before_content=old_content,
                    after_content=test_code,
                    tool_name="testgen",
                    description=f"Generated tests: {test_path.name}",
                )
            
            action = "Created" if is_new else "Updated"
            lines = len(test_code.split("\n"))
            
            return f"""## Tests Generated and Written

**{action}:** `{test_path}`
**Lines:** {lines}

```
{test_code[:1500]}{'...' if len(test_code) > 1500 else ''}
```

**Next steps:**
1. Review the generated tests
2. Run with your test runner to verify
"""
        except Exception as e:
            return f"Error writing test file: {e}\n\nGenerated code:\n```\n{test_code}\n```"
    
    def _format_output(self, test_code: str, source_path: str, lang_config: dict) -> str:
        """Format the output with helpful information."""
        source_file = Path(source_path).stem
        suffix = Path(source_path).suffix
        
        if suffix in [".py"]:
            suggested_name = f"test_{source_file}.py"
            run_cmd = f"pytest {suggested_name}"
        elif suffix in [".ts", ".tsx"]:
            suggested_name = f"{source_file}.test{suffix}"
            run_cmd = f"npm test -- {suggested_name}"
        elif suffix in [".js", ".jsx"]:
            suggested_name = f"{source_file}.test{suffix}"
            run_cmd = f"npm test -- {suggested_name}"
        elif suffix == ".rs":
            suggested_name = f"{source_file}_test.rs"
            run_cmd = "cargo test"
        elif suffix == ".go":
            suggested_name = f"{source_file}_test.go"
            run_cmd = "go test"
        else:
            suggested_name = f"test_{source_file}{suffix}"
            run_cmd = "run your test runner"
        
        return f"""## Generated Tests

**Language:** {lang_config['name']}
**Suggested filename:** `{suggested_name}`

```
{test_code}
```

**Next steps:**
1. Save this file to your tests directory
2. Review and adjust assertions as needed
3. Run with `{run_cmd}`
"""
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
