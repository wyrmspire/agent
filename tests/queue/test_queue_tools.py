"""
tests/queue/test_queue_tools.py - Queue Tools Tests

Tests for the queue_add, queue_next, queue_done, and queue_fail tools.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from tool.queue import QueueAddTool, QueueNextTool, QueueDoneTool, QueueFailTool
from core.sandb import Workspace


class TestQueueTools:
    """Tests for queue tools."""
    
    @pytest.fixture
    def workspace(self):
        """Create a temporary workspace."""
        tmp_dir = tempfile.mkdtemp()
        tmp_path = Path(tmp_dir)
        
        try:
            ws_path = tmp_path / "workspace"
            ws_path.mkdir()
            workspace = Workspace(workspace_root=str(ws_path))
            yield workspace
        finally:
            shutil.rmtree(tmp_dir)
    
    @pytest.mark.asyncio
    async def test_queue_add(self, workspace):
        """Test queue_add tool."""
        tool = QueueAddTool(workspace=workspace)
        
        result = await tool.execute({
            "objective": "Test task objective",
            "inputs": ["chunk_abc", "file.py"],
            "acceptance": "Task should complete without errors",
            "max_tool_calls": 10,
            "max_steps": 5,
        })
        
        assert result.success is True
        assert "task_0001" in result.output
        assert "Test task objective" in result.output
        assert "queued" in result.output
    
    @pytest.mark.asyncio
    async def test_queue_next_empty(self, workspace):
        """Test queue_next when queue is empty."""
        tool = QueueNextTool(workspace=workspace)
        
        result = await tool.execute({})
        
        assert result.success is True
        assert "No queued tasks" in result.output or "empty" in result.output.lower()
    
    @pytest.mark.asyncio
    async def test_queue_next_with_task(self, workspace):
        """Test queue_next with a queued task."""
        # Add a task first
        add_tool = QueueAddTool(workspace=workspace)
        await add_tool.execute({
            "objective": "Task to retrieve",
            "acceptance": "Should be retrieved",
        })
        
        # Get next task
        next_tool = QueueNextTool(workspace=workspace)
        result = await next_tool.execute({})
        
        assert result.success is True
        assert "task_0001" in result.output
        assert "Task to retrieve" in result.output
        assert "running" in result.output
    
    @pytest.mark.asyncio
    async def test_queue_done(self, workspace):
        """Test queue_done tool."""
        # Add and get a task
        add_tool = QueueAddTool(workspace=workspace)
        await add_tool.execute({"objective": "Task to complete"})
        
        next_tool = QueueNextTool(workspace=workspace)
        await next_tool.execute({})
        
        # Mark as done
        done_tool = QueueDoneTool(workspace=workspace)
        result = await done_tool.execute({
            "task_id": "task_0001",
            "what_was_done": "Completed successfully",
            "what_changed": ["file1.py"],
            "what_next": "Nothing more to do",
            "citations": ["chunk_xyz"],
        })
        
        assert result.success is True
        assert "task_0001" in result.output
        assert "done" in result.output
        assert "Checkpoint saved" in result.output
    
    @pytest.mark.asyncio
    async def test_queue_fail(self, workspace):
        """Test queue_fail tool."""
        # Add and get a task
        add_tool = QueueAddTool(workspace=workspace)
        await add_tool.execute({"objective": "Task to fail"})
        
        next_tool = QueueNextTool(workspace=workspace)
        await next_tool.execute({})
        
        # Mark as failed
        fail_tool = QueueFailTool(workspace=workspace)
        result = await fail_tool.execute({
            "task_id": "task_0001",
            "error": "Database connection failed",
            "what_was_done": "Attempted to connect",
            "blockers": ["Network error", "Timeout"],
        })
        
        assert result.success is True
        assert "task_0001" in result.output
        assert "failed" in result.output
        assert "Database connection failed" in result.output
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, workspace):
        """Test complete workflow: add → next → done."""
        # Step 1: Add task
        add_tool = QueueAddTool(workspace=workspace)
        add_result = await add_tool.execute({
            "objective": "Complete workflow test",
            "inputs": ["data.csv"],
            "acceptance": "Data processed",
        })
        assert add_result.success is True
        
        # Step 2: Get next
        next_tool = QueueNextTool(workspace=workspace)
        next_result = await next_tool.execute({})
        assert next_result.success is True
        assert "Complete workflow test" in next_result.output
        
        # Step 3: Mark done
        done_tool = QueueDoneTool(workspace=workspace)
        done_result = await done_tool.execute({
            "task_id": "task_0001",
            "what_was_done": "Processed data.csv successfully",
            "what_changed": ["output.csv"],
            "what_next": "Review output",
        })
        assert done_result.success is True
        
        # Step 4: Verify no more tasks
        next_result2 = await next_tool.execute({})
        assert "No queued tasks" in next_result2.output or "empty" in next_result2.output.lower()
    
    @pytest.mark.asyncio
    async def test_multiple_tasks_lifecycle(self, workspace):
        """Test processing multiple tasks sequentially."""
        add_tool = QueueAddTool(workspace=workspace)
        next_tool = QueueNextTool(workspace=workspace)
        done_tool = QueueDoneTool(workspace=workspace)
        
        # Add 3 tasks
        await add_tool.execute({"objective": "Task 1"})
        await add_tool.execute({"objective": "Task 2"})
        await add_tool.execute({"objective": "Task 3"})
        
        # Process task 1
        result = await next_tool.execute({})
        assert "Task 1" in result.output
        await done_tool.execute({
            "task_id": "task_0001",
            "what_was_done": "Done 1",
            "what_next": "Next",
        })
        
        # Process task 2
        result = await next_tool.execute({})
        assert "Task 2" in result.output
        await done_tool.execute({
            "task_id": "task_0002",
            "what_was_done": "Done 2",
            "what_next": "Next",
        })
        
        # Process task 3
        result = await next_tool.execute({})
        assert "Task 3" in result.output
        await done_tool.execute({
            "task_id": "task_0003",
            "what_was_done": "Done 3",
            "what_next": "Complete",
        })
        
        # Verify queue is empty
        result = await next_tool.execute({})
        assert "No queued tasks" in result.output or "empty" in result.output.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, workspace):
        """Test error handling in tools."""
        # Test queue_add without objective
        add_tool = QueueAddTool(workspace=workspace)
        result = await add_tool.execute({})
        assert result.success is False
        assert "objective" in result.error.lower()
        
        # Test queue_done without task_id
        done_tool = QueueDoneTool(workspace=workspace)
        result = await done_tool.execute({
            "what_was_done": "Something",
            "what_next": "Next",
        })
        assert result.success is False
        assert "task_id" in result.error.lower()
        
        # Test queue_fail without error
        fail_tool = QueueFailTool(workspace=workspace)
        result = await fail_tool.execute({
            "task_id": "task_0001",
        })
        assert result.success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
