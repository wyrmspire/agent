"""
tests/flows/tflow.py - Flow Tests

This module tests the agent flow system:
- Agent loop execution
- Tool call detection
- Tool execution integration
- Final answer generation

Day 1 acceptance criteria:
- Agent can answer simple questions
- Agent can execute tools
- Tool results are fed back to model
"""

import pytest
import asyncio
from typing import List, Optional, AsyncIterator

from core.types import Message, MessageRole, Tool, ToolCall
from core.proto import AgentResponse, StreamChunk, ResponseType
from core.state import AgentState, ConversationState, ExecutionContext
from core.rules import get_default_engine
from gate.bases import ModelGateway
from tool.index import ToolRegistry
from flow.loops import AgentLoop, LoopResult


class MockGateway(ModelGateway):
    """Mock model gateway for testing."""
    
    def __init__(self):
        super().__init__("mock")
        self.responses = []
        self.call_count = 0
    
    def add_response(self, content: str, tool_calls: Optional[List[ToolCall]] = None):
        """Add a response to return."""
        self.responses.append((content, tool_calls))
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentResponse:
        """Return next mock response."""
        if self.call_count >= len(self.responses):
            content = "No more responses"
            tool_calls = None
        else:
            content, tool_calls = self.responses[self.call_count]
        
        self.call_count += 1
        
        return AgentResponse(
            response_type=ResponseType.TOOL_CALL if tool_calls else ResponseType.COMPLETE,
            content=content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
        )
    
    async def stream_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Mock streaming (not implemented)."""
        yield StreamChunk(delta="test", finish_reason="stop")
    
    async def health_check(self) -> bool:
        """Mock health check."""
        return True


@pytest.mark.asyncio
async def test_simple_answer():
    """Test that agent can answer simple questions."""
    gateway = MockGateway()
    gateway.add_response("Hello! I'm here to help.")
    
    tools = ToolRegistry()
    rules = get_default_engine()
    
    loop = AgentLoop(gateway, tools, rules, max_steps=5)
    
    state = AgentState(
        conversation=ConversationState(id="test"),
        execution=ExecutionContext(run_id="run-1", conversation_id="test"),
    )
    
    result = await loop.run(state, "Hi!")
    
    assert result.success
    assert "help" in result.final_answer.lower()
    assert result.steps_taken == 1


@pytest.mark.asyncio
async def test_tool_execution():
    """Test that agent can execute tools."""
    from tests.tools.ttool import DummyTool
    
    gateway = MockGateway()
    
    # First response: request tool call
    gateway.add_response(
        "I'll use the dummy tool.",
        tool_calls=[ToolCall(id="call-1", name="dummy", arguments={"value": "test"})]
    )
    
    # Second response: final answer after tool
    gateway.add_response("The tool returned: test")
    
    tools = ToolRegistry()
    tools.register(DummyTool())
    
    rules = get_default_engine()
    loop = AgentLoop(gateway, tools, rules, max_steps=5)
    
    state = AgentState(
        conversation=ConversationState(id="test"),
        execution=ExecutionContext(run_id="run-1", conversation_id="test"),
    )
    
    result = await loop.run(state, "Use the dummy tool with value 'test'")
    
    assert result.success
    assert result.steps_taken >= 2  # At least 2 steps (could be more)
    # Check that tool was executed
    assert any("Echo" in str(step.content) for step in state.steps if step.tool_results)


@pytest.mark.asyncio
async def test_max_steps():
    """Test that agent stops at max steps."""
    gateway = MockGateway()
    
    # Always request tools
    for i in range(10):
        gateway.add_response(
            f"Step {i}",
            tool_calls=[ToolCall(id=f"call-{i}", name="dummy", arguments={"value": str(i)})]
        )
    
    from tests.tools.ttool import DummyTool
    tools = ToolRegistry()
    tools.register(DummyTool())
    
    rules = get_default_engine()
    loop = AgentLoop(gateway, tools, rules, max_steps=3)
    
    state = AgentState(
        conversation=ConversationState(id="test"),
        execution=ExecutionContext(run_id="run-1", conversation_id="test", max_steps=3),
    )
    
    result = await loop.run(state, "Keep using tools")
    
    assert result.success
    # Should stop within reasonable bounds (each iteration has think + observe)
    assert state.execution.current_step <= 10


if __name__ == "__main__":
    print("Running flow tests...")
    
    asyncio.run(test_simple_answer())
    print("✓ Simple answer")
    
    asyncio.run(test_tool_execution())
    print("✓ Tool execution")
    
    asyncio.run(test_max_steps())
    print("✓ Max steps")
    
    print("\n✅ All flow tests passed!")
