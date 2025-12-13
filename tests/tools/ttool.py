"""
tests/tools/ttool.py - Tool Tests

This module tests the tool system:
- Tool schema validation
- Tool execution
- Error handling
- Registry operations

Day 1 acceptance criteria:
- Tool schema must be valid JSON schema object
- Tool execution must return structured results
- Errors must be caught and converted to results
"""

import pytest
import asyncio
from typing import Dict, Any

from core.types import ToolCall, ToolResult
from tool.bases import BaseTool, create_json_schema
from tool.index import ToolRegistry, create_default_registry


class DummyTool(BaseTool):
    """Simple tool for testing."""
    
    @property
    def name(self) -> str:
        return "dummy"
    
    @property
    def description(self) -> str:
        return "A dummy tool for testing"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "value": {
                    "type": "string",
                    "description": "A value to echo",
                }
            },
            required=["value"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Echo the value."""
        return ToolResult(
            tool_call_id="",
            output=f"Echo: {arguments['value']}",
            success=True,
        )


class FailingTool(BaseTool):
    """Tool that always fails (for testing error handling)."""
    
    @property
    def name(self) -> str:
        return "fail"
    
    @property
    def description(self) -> str:
        return "A tool that always fails"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(properties={})
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Always fail."""
        return ToolResult(
            tool_call_id="",
            output="",
            error="This tool always fails",
            success=False,
        )


def test_tool_schema_validation():
    """Test that tool schemas are valid JSON schemas.
    
    Critical: parameters must have type: "object" at root level.
    """
    tool = DummyTool()
    schema = tool.parameters
    
    # Must be an object
    assert schema["type"] == "object"
    
    # Must have properties
    assert "properties" in schema
    
    # Properties must be a dict
    assert isinstance(schema["properties"], dict)


def test_tool_definition_creation():
    """Test that tools can be converted to Tool definitions."""
    tool = DummyTool()
    tool_def = tool.to_tool_definition()
    
    assert tool_def.name == "dummy"
    assert tool_def.description == "A dummy tool for testing"
    assert tool_def.parameters["type"] == "object"


@pytest.mark.asyncio
async def test_tool_execution():
    """Test that tools execute and return results."""
    tool = DummyTool()
    
    tool_call = ToolCall(
        id="test-1",
        name="dummy",
        arguments={"value": "hello"},
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "hello" in result.output
    assert result.tool_call_id == "test-1"


@pytest.mark.asyncio
async def test_tool_error_handling():
    """Test that tool errors are caught and converted to results."""
    tool = FailingTool()
    
    tool_call = ToolCall(
        id="test-2",
        name="fail",
        arguments={},
    )
    
    result = await tool.call(tool_call)
    
    # Should not raise exception
    assert not result.success
    assert result.error
    assert result.tool_call_id == "test-2"


def test_registry_registration():
    """Test tool registry registration."""
    registry = ToolRegistry()
    tool = DummyTool()
    
    # Register tool
    registry.register(tool)
    
    assert registry.count == 1
    assert registry.has("dummy")
    assert registry.get("dummy") == tool


def test_registry_duplicate_prevention():
    """Test that duplicate tool names are rejected."""
    registry = ToolRegistry()
    tool1 = DummyTool()
    tool2 = DummyTool()
    
    registry.register(tool1)
    
    with pytest.raises(ValueError):
        registry.register(tool2)


def test_default_registry():
    """Test that default registry has common tools."""
    registry = create_default_registry()
    
    assert registry.count > 0
    assert registry.has("list_files")
    assert registry.has("read_file")
    assert registry.has("write_file")
    assert registry.has("shell")
    assert registry.has("fetch")


if __name__ == "__main__":
    # Run tests
    print("Running tool tests...")
    
    test_tool_schema_validation()
    print("✓ Schema validation")
    
    test_tool_definition_creation()
    print("✓ Tool definition creation")
    
    asyncio.run(test_tool_execution())
    print("✓ Tool execution")
    
    asyncio.run(test_tool_error_handling())
    print("✓ Error handling")
    
    test_registry_registration()
    print("✓ Registry registration")
    
    test_registry_duplicate_prevention()
    print("✓ Duplicate prevention")
    
    test_default_registry()
    print("✓ Default registry")
    
    print("\n✅ All tool tests passed!")
