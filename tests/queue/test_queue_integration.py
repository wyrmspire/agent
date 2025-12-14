
import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from core.taskqueue import TaskQueue, TaskStatus
from flow.loops import AgentLoop
from tool.queue import QueueAddTool, QueueNextTool
from core.state import AgentState, ExecutionContext, ConversationState
from core.types import Message, MessageRole, ToolCall, ToolResult
from core.rules import RuleEngine
from tool.index import ToolRegistry

@pytest.fixture
def temp_workspace(tmp_path):
    """Setup temp workspace with queue structure."""
    ws = tmp_path / "workspace"
    queue_dir = ws / "queue"
    queue_dir.mkdir(parents=True)
    return ws

@pytest.mark.asyncio
async def test_queue_budget_enforcement(temp_workspace):
    """Test that agent loop strictly enforces task budget."""
    
    # 1. Add Task
    queue = TaskQueue(workspace_path=str(temp_workspace))
    task_id = queue.add_task(
        objective="Do something invalid",
        max_tool_calls=2,  # Very low budget
        max_steps=5
    )
    
    # 2. Activate Task (Simulate queue_next being called)
    # Ideally we'd use QueueNextTool, but let's manual-activate for precision
    task = queue.get_next() 
    assert task is not None
    assert task.status == TaskStatus.RUNNING
    
    active_task_file = temp_workspace / "queue" / "active_task.json"
    active_task_file.write_text(json.dumps(task.__dict__, default=str)) # Use default=str for datetime
    
    # 3. Setup Agent Loop
    gateway = MagicMock()
    # Mock gateway to ALWAYS return tool calls
    gateway.complete = AsyncMock(return_value=MagicMock(
        content="I will run a tool",
        tool_calls=[ToolCall(id="1", name="shell", arguments={"cmd": "echo hi"})]
    ))
    
    registry = ToolRegistry()
    # Mock shell tool
    mock_shell = MagicMock()
    mock_shell.name = "shell"
    mock_shell.call = AsyncMock(return_value=ToolResult("1", "hi", True))
    registry.register(mock_shell)
    
    # Mock queue tools (so we don't crash if agent tries to use them, though it shouldn't here)
    
    rule_engine = RuleEngine()
    
    loop = AgentLoop(
        gateway=gateway,
        tools=registry,
        rule_engine=rule_engine,
        max_steps=10 # Higher than task budget
    )
    # Patch workspace root for loop
    loop.workspace_root = temp_workspace
    loop.active_task_file = active_task_file
    
    # 4. Run Loop
    state = AgentState(
        conversation=ConversationState(id="test_conv"),
        execution=ExecutionContext(run_id="test_run", conversation_id="test_conv")
    )
    
    # We expect the loop to run tools until budget hit (2 calls)
    # Step 1: Tool 1 (Accum: 1)
    # Step 2: Tool 1 (Accum: 2) -> Budget Hit!
    
    # Actually loops.py logic:
    # "if current_tool_usage >= max_tool_usage" BEFORE execution check
    # But updated logic checks accumulated.
    
    result = await loop.run(state, "Start working")
    
    # 5. Assertions
    
    # Should have failed
    # result.success might be True (handled error) or False depending on loop implementation
    # But final answer should indicate stop
    assert "Stopped" in result.final_answer or "stopped" in result.final_answer
    
    # Queue Status should be FAILED
    # Reload queue
    queue = TaskQueue(workspace_path=str(temp_workspace))
    updated_task = queue.get_task(task_id)
    assert updated_task.status == TaskStatus.FAILED
    assert "BUDGET_EXHAUSTED" in updated_task.metadata.get("error", "")
    
    # Checkpoint should exist and contain reason
    checkpoint_file = temp_workspace / "queue" / "checkpoints" / f"{task_id}.md"
    assert checkpoint_file.exists()
    content = checkpoint_file.read_text()
    assert "BUDGET_EXHAUSTED" in content
    
    # Active Task file should be GONE
    assert not active_task_file.exists()
