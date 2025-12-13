"""
core/proto.py - Request/Response Protocol Schemas

This module defines the API protocol schemas for agent requests and responses.
These schemas are used by the API layer to communicate with clients.

Key schemas:
- AgentRequest: Incoming request to the agent
- AgentResponse: Response from the agent
- StreamChunk: Incremental response chunk for streaming

Rules:
- Only depends on core/types.py
- Uses Pydantic for validation and serialization
- Schemas match standard OpenAI-compatible formats where possible
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

from .types import Message, Tool, ToolCall, ToolResult


class ResponseType(str, Enum):
    """Types of agent responses."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    ERROR = "error"
    TOOL_CALL = "tool_call"


@dataclass
class AgentRequest:
    """Incoming request to the agent.
    
    Attributes:
        messages: Conversation history
        tools: Available tools for this request
        model: Model identifier to use
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        stream: Whether to stream the response
        metadata: Optional request metadata
    """
    messages: List[Message]
    tools: Optional[List[Tool]] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentResponse:
    """Response from the agent.
    
    Attributes:
        response_type: Type of response (complete, partial, error, tool_call)
        content: The response content (assistant message)
        tool_calls: Optional tool calls the agent wants to make
        finish_reason: Why generation stopped (stop, length, tool_calls)
        usage: Token usage statistics
        metadata: Optional response metadata
    """
    response_type: ResponseType
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class StreamChunk:
    """Incremental response chunk for streaming.
    
    Attributes:
        delta: The incremental content
        chunk_type: Type of chunk (text, tool_call, done)
        tool_call: Optional partial tool call
        finish_reason: Optional finish reason (if done)
    """
    delta: str
    chunk_type: str = "text"
    tool_call: Optional[ToolCall] = None
    finish_reason: Optional[str] = None


@dataclass
class ToolExecutionRequest:
    """Request to execute a tool.
    
    Attributes:
        tool_call: The tool call to execute
        context: Optional execution context
    """
    tool_call: ToolCall
    context: Optional[Dict[str, Any]] = None


@dataclass
class ToolExecutionResponse:
    """Response from tool execution.
    
    Attributes:
        result: The tool result
        execution_time: Time taken to execute (seconds)
        error: Optional error details
    """
    result: ToolResult
    execution_time: float
    error: Optional[str] = None
