"""
tool/bases.py - Tool Interface

This module defines the abstract interface for tools.
Tools are actions the agent can take in the real world.

Responsibilities:
- Define standard tool interface
- Tool registration and discovery
- Parameter validation

Rules:
- Tools do NOT reason or make decisions
- Tools only execute and return data
- Tools must be deterministic and safe
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import jsonschema
from jsonschema import validate, ValidationError

from core.types import Tool, ToolCall, ToolResult


class BaseTool(ABC):
    """Abstract base class for tools.
    
    Each tool must implement:
    - name: Unique identifier
    - description: What the tool does
    - parameters: JSON schema for parameters
    - execute: The actual tool logic
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON schema describing tool parameters."""
        pass
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool with given arguments.
        
        Args:
            arguments: Tool arguments (validated against schema)
            
        Returns:
            ToolResult with output or error
        """
        pass
    
    def to_tool_definition(self) -> Tool:
        """Convert this tool to a Tool definition.
        
        Returns:
            Tool object that can be sent to the model
        """
        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            function=self.execute,
        )
    
    async def call(self, tool_call: ToolCall) -> ToolResult:
        """Call the tool with a ToolCall object.
        
        This method validates arguments against the tool's schema before execution.
        This catches hallucinations and type errors early with clear error messages.
        
        Args:
            tool_call: Tool call from the model
            
        Returns:
            ToolResult with output or error
        """
        try:
            # Validate arguments against schema before execution
            try:
                validate(instance=tool_call.arguments, schema=self.parameters)
            except ValidationError as ve:
                # Return clean validation error instead of letting tool crash
                return ToolResult(
                    tool_call_id=tool_call.id,
                    output="",
                    error=f"Invalid arguments: {ve.message}",
                    success=False,
                )
            
            # Execute tool with validated arguments
            result = await self.execute(tool_call.arguments)
            result.tool_call_id = tool_call.id
            return result
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                output="",
                error=str(e),
                success=False,
            )


def create_json_schema(
    properties: Dict[str, Dict[str, Any]],
    required: Optional[list] = None,
) -> Dict[str, Any]:
    """Helper to create JSON schema for tool parameters.
    
    Args:
        properties: Parameter definitions
        required: List of required parameter names
        
    Returns:
        JSON schema object
    """
    schema = {
        "type": "object",
        "properties": properties,
    }
    
    if required:
        schema["required"] = required
    
    return schema
