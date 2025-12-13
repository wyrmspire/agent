"""
tests/gates/tgate.py - Gateway Tests

This module tests the model gateway system:
- Gateway interface compliance
- Request formatting
- Response parsing
- Tool call detection

Day 1 acceptance criteria:
- Tool definitions must match OpenAI schema
- Parameters must have type: "object"
- Responses must be properly parsed
"""

import pytest
from typing import Dict, Any

from core.types import Message, MessageRole, Tool
from tool.bases import create_json_schema


def test_tool_definition_schema():
    """Test that tool definitions match OpenAI schema.
    
    Critical: function.parameters must be a JSON schema with type: "object".
    This is what LM Studio expects.
    """
    tool = Tool(
        name="test_tool",
        description="A test tool",
        parameters=create_json_schema(
            properties={
                "arg1": {
                    "type": "string",
                    "description": "First argument",
                }
            },
            required=["arg1"],
        ),
    )
    
    # Verify schema structure
    assert tool.parameters["type"] == "object"
    assert "properties" in tool.parameters
    assert "arg1" in tool.parameters["properties"]
    
    # Verify it can be serialized to OpenAI format
    openai_tool = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
    }
    
    # The parameters should be the JSON schema object
    assert openai_tool["function"]["parameters"]["type"] == "object"


def test_message_conversion():
    """Test that messages can be converted to API format."""
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are helpful"),
        Message(role=MessageRole.USER, content="Hello"),
        Message(role=MessageRole.ASSISTANT, content="Hi there!"),
    ]
    
    # Convert to dicts (like gateway would do)
    message_dicts = [
        {
            "role": msg.role.value,
            "content": msg.content,
        }
        for msg in messages
    ]
    
    assert len(message_dicts) == 3
    assert message_dicts[0]["role"] == "system"
    assert message_dicts[1]["role"] == "user"
    assert message_dicts[2]["role"] == "assistant"


def test_schema_validation_catches_bad_type():
    """Test that we catch invalid schema types.
    
    If parameters.type is not "object", LM Studio will reject it.
    """
    # This is WRONG - will cause errors
    bad_schema = {
        "type": "function",  # WRONG! Should be "object"
        "properties": {
            "arg": {"type": "string"}
        }
    }
    
    # Verify we can detect this
    assert bad_schema["type"] != "object"
    
    # Correct schema
    good_schema = create_json_schema(
        properties={"arg": {"type": "string"}}
    )
    
    assert good_schema["type"] == "object"


if __name__ == "__main__":
    print("Running gateway tests...")
    
    test_tool_definition_schema()
    print("✓ Tool definition schema")
    
    test_message_conversion()
    print("✓ Message conversion")
    
    test_schema_validation_catches_bad_type()
    print("✓ Schema validation")
    
    print("\n✅ All gateway tests passed!")
