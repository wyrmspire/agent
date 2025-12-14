"""
Tests for Phase 1.4: Mandatory queue for complex tasks.

Tests that:
1. Large tasks complete over multiple queue cycles
2. Checkpoints include all required fields
3. Parent-child task relationships work correctly
"""

import pytest
from datetime import datetime, timezone
from core.taskqueue import TaskQueue, Checkpoint, TaskStatus


class TestMandatoryQueue:
    """Test queue requirements for complex tasks."""
    
    def test_large_task_multi_cycle_completion(self, tmp_path):
        """A large task completes over multiple queue cycles with checkpoints."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        # Add a large task that can't fit in one budget
        task_id = queue.add_task(
            objective="Implement 10 new API endpoints",
            inputs=["api_spec.json"],
            acceptance="All 10 endpoints implemented and tested",
            max_tool_calls=20,
            max_steps=10,
        )
        
        # Cycle 1: Get task, do partial work, checkpoint
        task = queue.get_next()
        assert task is not None
        assert task.task_id == task_id
        assert task.status == TaskStatus.RUNNING
        
        # Create checkpoint with ALL required fields
        checkpoint1 = Checkpoint(
            task_id=task_id,
            what_was_done="Implemented endpoints 1-3 with tests",
            what_changed=["api/endpoint1.py", "api/endpoint2.py", "api/endpoint3.py"],
            what_next="Implement endpoints 4-6",
            blockers=[],
            citations=["chunk_api_spec_001", "chunk_api_auth_002"],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.save_checkpoint(checkpoint1)
        
        # Verify checkpoint file exists and has content
        checkpoint_file = tmp_path / "queue" / "checkpoints" / f"{task_id}.md"
        assert checkpoint_file.exists()
        content = checkpoint_file.read_text()
        assert "Implemented endpoints 1-3" in content
        assert "chunk_api_spec_001" in content
        
        # Create continuation task (remaining work)
        remaining_task_id = queue.add_task(
            objective="Implement endpoints 4-10 (continuation of task_0001)",
            inputs=["api_spec.json"],
            acceptance="Endpoints 4-10 implemented",
            parent_id=task_id,
            max_tool_calls=20,
            max_steps=10,
        )
        
        # Mark first cycle done
        queue.mark_done(task_id, checkpoint1)
        assert queue.get_task(task_id).status == TaskStatus.DONE
        
        # Cycle 2: Continue with child task
        task2 = queue.get_next()
        assert task2 is not None
        assert task2.task_id == remaining_task_id
        assert task2.parent_id == task_id
        
        # Complete the continuation
        checkpoint2 = Checkpoint(
            task_id=remaining_task_id,
            what_was_done="Implemented endpoints 4-10 with tests",
            what_changed=["api/endpoint4.py", "api/endpoint5.py", "api/endpoint6.py"],
            what_next="None - task complete",
            blockers=[],
            citations=["chunk_api_spec_002"],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.mark_done(remaining_task_id, checkpoint2)
        
        # Verify both tasks completed
        assert queue.get_task(task_id).status == TaskStatus.DONE
        assert queue.get_task(remaining_task_id).status == TaskStatus.DONE
        
        # Verify no more tasks in queue
        assert queue.get_next() is None
    
    def test_checkpoint_persistence(self, tmp_path):
        """Checkpoints persist across queue restarts."""
        queue1 = TaskQueue(workspace_path=str(tmp_path))
        
        task_id = queue1.add_task(
            objective="Test persistence",
            acceptance="Done",
        )
        
        task = queue1.get_next()
        
        checkpoint = Checkpoint(
            task_id=task_id,
            what_was_done="Started work",
            what_changed=["file1.py"],
            what_next="Continue work",
            blockers=[],
            citations=["chunk_123"],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        queue1.save_checkpoint(checkpoint)
        
        # Simulate restart - create new queue instance
        queue2 = TaskQueue(workspace_path=str(tmp_path))
        
        # Checkpoint file should still exist
        checkpoint_file = tmp_path / "queue" / "checkpoints" / f"{task_id}.md"
        assert checkpoint_file.exists()
        
        # Can load checkpoint
        loaded = queue2.load_checkpoint(task_id)
        assert loaded is not None
    
    def test_failed_task_checkpoints_progress(self, tmp_path):
        """Failed tasks still checkpoint their partial progress."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        task_id = queue.add_task(
            objective="Task that will fail",
            acceptance="Done",
        )
        
        queue.get_next()
        
        # Task fails but we checkpoint what was done
        checkpoint = Checkpoint(
            task_id=task_id,
            what_was_done="Completed steps 1-3 before hitting blocker",
            what_changed=["partial/file.py"],
            what_next="Need to resolve dependency issue first",
            blockers=["Missing numpy version 2.0", "API key not configured"],
            citations=["chunk_error_005"],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        queue.mark_failed(task_id, error="Dependency conflict", checkpoint=checkpoint)
        
        # Task is failed but checkpoint exists
        assert queue.get_task(task_id).status == TaskStatus.FAILED
        assert "Dependency conflict" in queue.get_task(task_id).metadata.get("error", "")
        
        checkpoint_file = tmp_path / "queue" / "checkpoints" / f"{task_id}.md"
        assert checkpoint_file.exists()
        content = checkpoint_file.read_text()
        assert "Missing numpy" in content
        assert "Completed steps 1-3" in content
    
    def test_queue_stats(self, tmp_path):
        """Queue provides accurate statistics."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        # Add multiple tasks
        task1 = queue.add_task(objective="Task 1", acceptance="Done 1")
        task2 = queue.add_task(objective="Task 2", acceptance="Done 2")
        task3 = queue.add_task(objective="Task 3", acceptance="Done 3")
        
        stats = queue.get_stats()
        assert stats["total_tasks"] == 3
        assert stats["status_counts"]["queued"] == 3
        
        # Start and complete one task
        queue.get_next()  # task1 is now running
        queue.mark_done(task1)
        
        stats = queue.get_stats()
        assert stats["status_counts"]["queued"] == 2
        assert stats["status_counts"]["running"] == 0  # completed, not running
        assert stats["status_counts"]["done"] == 1
