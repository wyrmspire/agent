"""
gate/mock.py - Mock Gateway for Testing

This module implements a Mock ModelGateway that returns success or predefined interactions
without needing a real model server running. Useful for tool development and smoke testing.
"""

import json
import logging
from typing import AsyncIterator, List, Optional, Dict, Any

from core.types import Message, Tool, ToolCall
from core.proto import AgentResponse, StreamChunk, ResponseType
from .bases import ModelGateway

logger = logging.getLogger("mock_gate")

class MockGateway(ModelGateway):
    """A mock gateway that returns success or scripted responses."""
    
    def __init__(self, model: str = "mock-model"):
        super().__init__(model)
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentResponse:
        """Generate a mock completion."""
        last_msg = messages[-1].content
        
        # 1. Check for explicit tool command override
        # Format: /tool <name> <json_args>
        if last_msg.strip().startswith("/tool"):
            try:
                # remove prefix
                rest = last_msg.strip()[6:].strip()
                name, args_str = rest.split(" ", 1)
                args = json.loads(args_str)
                
                tool_call = ToolCall(
                    id="mock_call_1",
                    name=name,
                    arguments=args
                )
                
                return AgentResponse(
                    response_type=ResponseType.TOOL_CALL,
                    content="Executing mock tool invocation.",
                    tool_calls=[tool_call],
                    finish_reason="tool_calls"
                )
            except Exception as e:
                return AgentResponse(
                    response_type=ResponseType.COMPLETE,
                    content=f"Error parsing mock tool command: {e}",
                    finish_reason="stop"
                )

        # 2. Check for simple heuristic for standard tools (Day 1 tools)
        lower_msg = last_msg.lower()
        
        if "list file" in lower_msg or "ls" == lower_msg.strip():
             return AgentResponse(
                response_type=ResponseType.TOOL_CALL,
                content="Listing files...",
                tool_calls=[ToolCall(id="mock_ls", name="list_files", arguments={"path": "."})],
                finish_reason="tool_calls"
            )

        if "write" in lower_msg and "file" in lower_msg:
             # Very dumb default for testing
             return AgentResponse(
                response_type=ResponseType.TOOL_CALL,
                content="Writing test file...",
                tool_calls=[ToolCall(id="mock_write", name="write_file", arguments={"path": "mock_test.txt", "content": "mock content"})],
                finish_reason="tool_calls"
            )

        # 3. Default text response
        return AgentResponse(
            response_type=ResponseType.COMPLETE,
            content="MOCK SUCCESS: I received your message. I am a mock agent. Use /tool <name> <json> to force a tool call.",
            finish_reason="stop"
        )

    async def stream_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a mock completion."""
        response = await self.complete(messages, tools)
        
        yield StreamChunk(
            delta=response.content or "",
            chunk_type="text",
            finish_reason=response.finish_reason
        )

    async def health_check(self) -> bool:
        """Always healthy."""
        return True

    async def close(self) -> None:
        pass
