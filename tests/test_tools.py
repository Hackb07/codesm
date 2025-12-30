"""Tests for tool implementations"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def context(temp_dir):
    """Create a test context"""
    return {"cwd": temp_dir, "session": None}


class TestReadTool:
    @pytest.mark.asyncio
    async def test_read_file(self, temp_dir, context):
        from codesm.tool.read import ReadTool
        
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("line 1\nline 2\nline 3\n")
        
        tool = ReadTool()
        result = await tool.execute({"path": str(test_file)}, context)
        
        assert "1: line 1" in result
        assert "2: line 2" in result
        assert "3: line 3" in result
    
    @pytest.mark.asyncio
    async def test_read_file_with_range(self, temp_dir, context):
        from codesm.tool.read import ReadTool
        
        test_file = temp_dir / "test.txt"
        test_file.write_text("line 1\nline 2\nline 3\nline 4\n")
        
        tool = ReadTool()
        result = await tool.execute({
            "path": str(test_file),
            "start_line": 2,
            "end_line": 3,
        }, context)
        
        assert "2: line 2" in result
        assert "3: line 3" in result
        assert "1: line 1" not in result
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, temp_dir, context):
        from codesm.tool.read import ReadTool
        
        tool = ReadTool()
        result = await tool.execute({
            "path": str(temp_dir / "nonexistent.txt")
        }, context)
        
        assert "Error" in result


class TestWriteTool:
    @pytest.mark.asyncio
    async def test_write_file(self, temp_dir, context):
        from codesm.tool.write import WriteTool
        
        test_file = temp_dir / "new_file.txt"
        
        tool = WriteTool()
        result = await tool.execute({
            "path": str(test_file),
            "content": "Hello, world!",
        }, context)
        
        assert "Successfully" in result
        assert test_file.read_text() == "Hello, world!"
    
    @pytest.mark.asyncio
    async def test_write_creates_directories(self, temp_dir, context):
        from codesm.tool.write import WriteTool
        
        test_file = temp_dir / "subdir" / "nested" / "file.txt"
        
        tool = WriteTool()
        result = await tool.execute({
            "path": str(test_file),
            "content": "nested content",
        }, context)
        
        assert "Successfully" in result
        assert test_file.exists()


class TestEditTool:
    @pytest.mark.asyncio
    async def test_edit_file(self, temp_dir, context):
        from codesm.tool.edit import EditTool
        
        test_file = temp_dir / "edit_test.txt"
        test_file.write_text("Hello, world!")
        
        tool = EditTool()
        result = await tool.execute({
            "path": str(test_file),
            "old_content": "world",
            "new_content": "Python",
        }, context)
        
        assert "Successfully" in result
        assert test_file.read_text() == "Hello, Python!"
    
    @pytest.mark.asyncio
    async def test_edit_content_not_found(self, temp_dir, context):
        from codesm.tool.edit import EditTool
        
        test_file = temp_dir / "edit_test.txt"
        test_file.write_text("Hello, world!")
        
        tool = EditTool()
        result = await tool.execute({
            "path": str(test_file),
            "old_content": "nonexistent",
            "new_content": "replacement",
        }, context)
        
        assert "Error" in result


class TestGlobTool:
    @pytest.mark.asyncio
    async def test_glob_files(self, temp_dir, context):
        from codesm.tool.glob import GlobTool
        
        # Create test files
        (temp_dir / "file1.py").write_text("# python")
        (temp_dir / "file2.py").write_text("# python")
        (temp_dir / "file.txt").write_text("text")
        
        tool = GlobTool()
        result = await tool.execute({
            "pattern": "*.py",
            "path": str(temp_dir),
        }, context)
        
        assert "file1.py" in result
        assert "file2.py" in result
        assert "file.txt" not in result


class TestToolRegistry:
    def test_registry_loads_all_tools(self):
        from codesm.tool.registry import ToolRegistry
        
        registry = ToolRegistry()
        schemas = registry.get_schemas()
        
        tool_names = [s["name"] for s in schemas]
        
        assert "read" in tool_names
        assert "write" in tool_names
        assert "edit" in tool_names
        assert "bash" in tool_names
        assert "grep" in tool_names
        assert "glob" in tool_names
        assert "web" in tool_names
    
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        from codesm.tool.registry import ToolRegistry
        
        registry = ToolRegistry()
        result = await registry.execute("unknown_tool", {}, {})
        
        assert "Error" in result
        assert "Unknown tool" in result
