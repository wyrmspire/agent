"""
tests/queue/test_taskqueue.py - Task Queue Core Tests

Tests for the TaskQueue class and task lifecycle management.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from core.taskqueue import TaskQueue, TaskStatus, Checkpoint


class TestTaskQueue:
    """Tests for TaskQueue core functionality."""
    
    @pytest.fixture
    def queue(self):
        """Create a TaskQueue instance with temp workspace."""
        tmp_dir = tempfile.mkdtemp()
        tmp_path = Path(tmp_dir)
        
        try:
            ws = tmp_path / "workspace"
            ws.mkdir()
            queue = TaskQueue(workspace_path=str(ws))
            yield queue
        finally:
            shutil.rmtree(tmp_dir)
    
    def test_add_task(self, queue):
        """Test adding a task to the queue."""
        task_id = queue.add_task(
            objective="Test task",
            inputs=["input1", "input2"],
            acceptance="Task should complete",
            max_tool_calls=15,
            max_steps=5,
        )
        
        assert task_id.startswith("task_")
        
        # Verify task was added
        task = queue.get_task(task_id)
        assert task is not None
        assert task.objective == "Test task"
        assert task.status == TaskStatus.QUEUED
        assert task.budget["max_tool_calls"] == 15
        assert task.budget["max_steps"] == 5
        assert len(task.inputs) == 2
    
    def test_get_next(self, queue):
        """Test getting the next queued task."""
        # Add two tasks
        task_id1 = queue.add_task("Task 1")
        task_id2 = queue.add_task("Task 2")
        
        # Get first task
        task = queue.get_next()
        assert task is not None
        assert task.task_id == task_id1
        assert task.status == TaskStatus.RUNNING
        
        # Get second task
        task = queue.get_next()
        assert task is not None
        assert task.task_id == task_id2
        assert task.status == TaskStatus.RUNNING
        
        # No more tasks
        task = queue.get_next()
        assert task is None
    
    def test_mark_done(self, queue):
        """Test marking a task as done."""
        task_id = queue.add_task("Complete this")
        
        checkpoint = Checkpoint(
            task_id=task_id,
            what_was_done="Completed the task",
            what_changed=["file1.py", "file2.py"],
            what_next="Nothing, task is done",
            blockers=[],
            citations=["chunk_abc123"],
            created_at="2024-01-01T00:00:00",
        )
        
        success = queue.mark_done(task_id, checkpoint)
        assert success is True
        
        task = queue.get_task(task_id)
        assert task.status == TaskStatus.DONE
        
        # Verify checkpoint was saved
        checkpoint_file = queue.checkpoints_dir / f"{task_id}.md"
        assert checkpoint_file.exists()
        content = checkpoint_file.read_text()
        assert "Completed the task" in content
        assert "chunk_abc123" in content
    
    def test_mark_failed(self, queue):
        """Test marking a task as failed."""
        task_id = queue.add_task("Fail this")
        
        checkpoint = Checkpoint(
            task_id=task_id,
            what_was_done="Attempted task but failed",
            what_changed=[],
            what_next="Retry with different approach",
            blockers=["Missing dependency", "API error"],
            citations=[],
            created_at="2024-01-01T00:00:00",
        )
        
        success = queue.mark_failed(task_id, "API returned 500", checkpoint)
        assert success is True
        
        task = queue.get_task(task_id)
        assert task.status == TaskStatus.FAILED
        assert task.metadata["error"] == "API returned 500"
        
        # Verify checkpoint was saved
        checkpoint_file = queue.checkpoints_dir / f"{task_id}.md"
        assert checkpoint_file.exists()
        content = checkpoint_file.read_text()
        assert "Missing dependency" in content
        assert "API error" in content
    
    def test_task_lifecycle(self, queue):
        """Test complete task lifecycle: add → next → done."""
        # Add task
        task_id = queue.add_task(
            objective="Full lifecycle test",
            acceptance="Task completes successfully",
        )
        
        # Verify queued
        task = queue.get_task(task_id)
        assert task.status == TaskStatus.QUEUED
        
        # Get next (should mark as running)
        next_task = queue.get_next()
        assert next_task.task_id == task_id
        assert next_task.status == TaskStatus.RUNNING
        
        # Mark done
        checkpoint = Checkpoint(
            task_id=task_id,
            what_was_done="Completed full lifecycle",
            what_changed=[],
            what_next="None",
            blockers=[],
            citations=[],
            created_at="2024-01-01T00:00:00",
        )
        queue.mark_done(task_id, checkpoint)
        
        # Verify done
        task = queue.get_task(task_id)
        assert task.status == TaskStatus.DONE
    
    def test_list_tasks(self, queue):
        """Test listing tasks with status filter."""
        # Add tasks with different states
        task_id1 = queue.add_task("Task 1")
        task_id2 = queue.add_task("Task 2")
        task_id3 = queue.add_task("Task 3")
        
        # Mark one as running
        queue.get_next()  # task_id1
        
        # Mark one as done
        queue.get_next()  # task_id2
        queue.mark_done(task_id2)
        
        # List all
        all_tasks = queue.list_tasks()
        assert len(all_tasks) == 3
        
        # List queued
        queued = queue.list_tasks(TaskStatus.QUEUED)
        assert len(queued) == 1
        assert queued[0].task_id == task_id3
        
        # List running
        running = queue.list_tasks(TaskStatus.RUNNING)
        assert len(running) == 1
        assert running[0].task_id == task_id1
        
        # List done
        done = queue.list_tasks(TaskStatus.DONE)
        assert len(done) == 1
        assert done[0].task_id == task_id2
    
    def test_task_persistence(self, queue):
        """Test that tasks persist across queue instances."""
        # Add task
        task_id = queue.add_task("Persistent task")
        
        # Create new queue instance (same workspace)
        workspace_path = queue.workspace_root
        new_queue = TaskQueue(workspace_path=str(workspace_path))
        
        # Verify task exists
        task = new_queue.get_task(task_id)
        assert task is not None
        assert task.objective == "Persistent task"
    
    def test_checkpoint_budget_exhaustion(self, queue):
        """Test checkpoint when budget is exhausted."""
        task_id = queue.add_task(
            objective="Budget test",
            max_tool_calls=5,
            max_steps=3,
        )
        
        # Simulate budget exhaustion
        checkpoint = Checkpoint(
            task_id=task_id,
            what_was_done="Executed 5 tool calls, budget exhausted",
            what_changed=["partial_result.txt"],
            what_next="Resume with more budget or break into subtasks",
            blockers=["Budget exhausted"],
            citations=["chunk_xyz"],
            created_at="2024-01-01T00:00:00",
        )
        
        queue.save_checkpoint(checkpoint)
        
        # Verify checkpoint
        checkpoint_file = queue.checkpoints_dir / f"{task_id}.md"
        assert checkpoint_file.exists()
        content = checkpoint_file.read_text()
        assert "Budget exhausted" in content
        assert "Resume with more budget" in content
    
    def test_subtasks(self, queue):
        """Test creating subtasks with parent_id."""
        # Add parent task
        parent_id = queue.add_task("Parent task")
        
        # Add subtasks
        subtask1_id = queue.add_task(
            objective="Subtask 1",
            parent_id=parent_id,
        )
        subtask2_id = queue.add_task(
            objective="Subtask 2",
            parent_id=parent_id,
        )
        
        # Verify parent relationship
        subtask1 = queue.get_task(subtask1_id)
        subtask2 = queue.get_task(subtask2_id)
        
        assert subtask1.parent_id == parent_id
        assert subtask2.parent_id == parent_id
    
    def test_get_stats(self, queue):
        """Test queue statistics."""
        # Add tasks
        queue.add_task("Task 1")
        queue.add_task("Task 2")
        queue.add_task("Task 3")
        
        # Process one
        queue.get_next()
        
        # Get stats
        stats = queue.get_stats()
        
        assert stats["total_tasks"] == 3
        assert stats["status_counts"]["queued"] == 2
        assert stats["status_counts"]["running"] == 1
        assert stats["status_counts"]["done"] == 0
        assert stats["status_counts"]["failed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
