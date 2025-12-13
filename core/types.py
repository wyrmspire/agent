"""
core/types.py - Message, Tool, and Step Types

This module defines the fundamental data types used throughout the agent system.
These are the contracts that all other modules depend on.

Core types:
- Message: A single message in a conversation (user, assistant, system, tool)
- Tool: Definition of a tool including name, description, and parameter schema
- Step: A single step in agent execution (think, call_tool, observe, respond)
- ToolCall: A parsed tool invocation with name and arguments
- ToolResult: The result of executing a tool

Rules:
- This module has NO dependencies on other agent modules
- All types are immutable where possible
- Types use dataclasses or Pydantic for validation
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional
from enum import Enum


class MessageRole(str, Enum):
    """Valid message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class StepType(str, Enum):
    """Types of steps in agent execution."""
    THINK = "think"
    CALL_TOOL = "call_tool"
    OBSERVE = "observe"
    RESPOND = "respond"
    ERROR = "error"


@dataclass(frozen=True)
class Message:
    """A single message in a conversation.
    
    Attributes:
        role: Who sent the message (system, user, assistant, tool)
        content: The text content of the message
        name: Optional name (used for tool messages to identify which tool)
        tool_calls: Optional list of tool calls (for assistant messages)
    """
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass(frozen=True)
class Tool:
    """Definition of a tool the agent can use.
    
    Attributes:
        name: Unique identifier for the tool
        description: What the tool does (shown to the model)
        parameters: JSON schema describing the tool's parameters
        function: Optional callable that executes the tool
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Optional[Any] = None


@dataclass
class ToolCall:
    """A parsed tool invocation.
    
    Attributes:
        id: Unique identifier for this tool call
        name: Name of the tool to invoke
        arguments: Dictionary of arguments to pass to the tool
    """
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """The result of executing a tool.
    
    Attributes:
        tool_call_id: ID of the tool call this is responding to
        output: The output from the tool (as string)
        error: Optional error message if tool failed
        success: Whether the tool executed successfully
    """
    tool_call_id: str
    output: str
    error: Optional[str] = None
    success: bool = True


@dataclass
class Step:
    """A single step in agent execution.
    
    Attributes:
        step_type: What kind of step this is
        content: The content/data for this step
        tool_calls: Optional tool calls (for call_tool steps)
        tool_results: Optional tool results (for observe steps)
        metadata: Optional additional metadata
    """
    step_type: StepType
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_results: Optional[List[ToolResult]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# Type aliases for clarity
Messages = List[Message]
Tools = List[Tool]
Steps = List[Step]
