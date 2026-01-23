"""Tests for ParallelTaskTool"""

import pytest
from codesm.tool.task import ParallelTaskTool, TaskTool, MAX_PARALLEL_TASKS
from codesm.tool.registry import ToolRegistry


class TestParallelTaskTool:
    """Tests for the parallel_tasks tool"""
    
    def test_tool_exists_in_registry(self):
        """parallel_tasks tool should be registered"""
        registry = ToolRegistry()
        tool = registry.get("parallel_tasks")
        assert tool is not None
        assert isinstance(tool, ParallelTaskTool)
    
    def test_tool_has_parent_tools(self):
        """Tool should have parent_tools set by registry"""
        registry = ToolRegistry()
        tool = registry.get("parallel_tasks")
        assert tool._parent_tools is not None
    
    def test_tool_description_loaded(self):
        """Description should be loaded from .txt file"""
        tool = ParallelTaskTool()
        assert "Launch multiple subagents" in tool.description
        assert "parallel" in tool.description.lower()
    
    def test_parameters_schema(self):
        """Schema should have tasks and fail_fast"""
        tool = ParallelTaskTool()
        schema = tool.get_parameters_schema()
        
        assert "properties" in schema
        assert "tasks" in schema["properties"]
        assert "fail_fast" in schema["properties"]
        
        # Tasks should be array
        tasks_schema = schema["properties"]["tasks"]
        assert tasks_schema["type"] == "array"
        assert tasks_schema["minItems"] == 1
        assert tasks_schema["maxItems"] == 10
        
        # Task items should have required fields
        item_schema = tasks_schema["items"]
        assert "subagent_type" in item_schema["properties"]
        assert "prompt" in item_schema["properties"]
        assert "description" in item_schema["properties"]
    
    def test_max_parallel_tasks_constant(self):
        """MAX_PARALLEL_TASKS should be 10"""
        assert MAX_PARALLEL_TASKS == 10
    
    def test_set_parent(self):
        """set_parent should update internal references"""
        tool = ParallelTaskTool()
        registry = ToolRegistry()
        
        tool.set_parent(registry, "test-model")
        
        assert tool._parent_tools is registry
        assert tool._parent_model == "test-model"


class TestTaskTool:
    """Tests for the single task tool"""
    
    def test_tool_exists_in_registry(self):
        """task tool should be registered"""
        registry = ToolRegistry()
        tool = registry.get("task")
        assert tool is not None
        assert isinstance(tool, TaskTool)
    
    def test_tool_has_parent_tools(self):
        """Tool should have parent_tools set by registry"""
        registry = ToolRegistry()
        tool = registry.get("task")
        assert tool._parent_tools is not None
    
    def test_parameters_schema(self):
        """Schema should have required fields"""
        registry = ToolRegistry()
        tool = registry.get("task")
        schema = tool.get_parameters_schema()
        
        assert "subagent_type" in schema["properties"]
        assert "prompt" in schema["properties"]
        assert "description" in schema["properties"]
        
        required = schema.get("required", [])
        assert "subagent_type" in required
        assert "prompt" in required
        assert "description" in required
