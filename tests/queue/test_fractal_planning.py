"""
Tests for Phase 1.8: Fractal planning protocol.

Tests epic → task → child task decomposition with proper checkpoints.
"""

import pytest
from datetime import datetime, timezone
from core.taskqueue import TaskQueue, Checkpoint, TaskStatus


class TestFractalPlanning:
    """Test epic → task → child task decomposition."""
    
    def test_epic_to_task_conversion(self, tmp_path):
        """Epics are converted to queue tasks with metadata."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        # Add epic-level tasks
        epic1 = queue.add_task(
            objective="Epic 1: Implement authentication",
            acceptance="Users can log in and out",
            metadata={"epic_id": 1, "type": "epic"},
        )
        epic2 = queue.add_task(
            objective="Epic 2: Implement dashboard",
            acceptance="Dashboard shows user stats",
            metadata={"epic_id": 2, "type": "epic"},
        )
        
        task1 = queue.get_task(epic1)
        task2 = queue.get_task(epic2)
        
        assert task1.metadata["type"] == "epic"
        assert task1.metadata["epic_id"] == 1
        assert task2.metadata["type"] == "epic"
        assert task2.metadata["epic_id"] == 2
    
    def test_child_task_spawning(self, tmp_path):
        """Tasks can spawn child tasks with parent_id."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        # Parent epic
        parent = queue.add_task(
            objective="Epic: Setup CI/CD",
            acceptance="CI runs on every PR",
        )
        
        # Start parent
        queue.get_next()
        
        # Spawn children
        child1 = queue.add_task(
            objective="Setup GitHub Actions workflow",
            parent_id=parent,
            acceptance="Workflow file exists",
        )
        child2 = queue.add_task(
            objective="Add test step to workflow",
            parent_id=parent,
            acceptance="Tests run in CI",
        )
        
        # Verify parent-child relationship
        assert queue.get_task(child1).parent_id == parent
        assert queue.get_task(child2).parent_id == parent
    
    def test_checkpoint_with_next_task_pointer(self, tmp_path):
        """Checkpoints can point to the next queued task."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        task1 = queue.add_task(objective="First task", acceptance="Done")
        task2 = queue.add_task(objective="Next task", acceptance="Done")
        
        queue.get_next()  # Start task1
        
        checkpoint = Checkpoint(
            task_id=task1,
            what_was_done="Completed first task",
            what_changed=["file.py"],
            what_next=f"Next: {task2}",  # Points to next task
            blockers=[],
            citations=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.save_checkpoint(checkpoint)
        
        content = (tmp_path / "queue" / "checkpoints" / f"{task1}.md").read_text()
        assert f"Next: {task2}" in content
    
    def test_checkpoint_with_spawned_child_pointer(self, tmp_path):
        """Checkpoints can point to spawned child tasks."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        parent = queue.add_task(objective="Parent task", acceptance="Done")
        queue.get_next()  # Start parent
        
        # Spawn child
        child = queue.add_task(
            objective="Child task",
            parent_id=parent,
            acceptance="Done",
        )
        
        checkpoint = Checkpoint(
            task_id=parent,
            what_was_done="Decomposed into subtasks",
            what_changed=[],
            what_next=f"Spawned: {child}",  # Points to spawned child
            blockers=[],
            citations=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.save_checkpoint(checkpoint)
        
        content = (tmp_path / "queue" / "checkpoints" / f"{parent}.md").read_text()
        assert f"Spawned: {child}" in content
    
    def test_checkpoint_done_is_valid(self, tmp_path):
        """'DONE - no further work needed' is a valid what_next."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        task = queue.add_task(objective="Final task", acceptance="Done")
        queue.get_next()
        
        checkpoint = Checkpoint(
            task_id=task,
            what_was_done="All work complete",
            what_changed=[],
            what_next="DONE - no further work needed",
            blockers=[],
            citations=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.mark_done(task, checkpoint)
        
        assert queue.get_task(task).status == TaskStatus.DONE
        
        content = (tmp_path / "queue" / "checkpoints" / f"{task}.md").read_text()
        assert "DONE - no further work needed" in content
    
    def test_full_epic_lifecycle(self, tmp_path):
        """Epic completes through child tasks with proper checkpoints."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        # Epic level
        epic = queue.add_task(
            objective="Epic: Create API",
            metadata={"type": "epic"},
        )
        
        # Start epic, realize it needs decomposition
        queue.get_next()
        
        # Spawn children
        child1 = queue.add_task(objective="Create routes", parent_id=epic)
        child2 = queue.add_task(objective="Add authentication", parent_id=epic)
        
        # Checkpoint epic pointing to children
        queue.mark_done(epic, Checkpoint(
            task_id=epic,
            what_was_done="Decomposed into subtasks",
            what_changed=[],
            what_next=f"Spawned: {child1}, {child2}",
            blockers=[],
            citations=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        
        # Complete child1
        queue.get_next()  # child1
        queue.mark_done(child1, Checkpoint(
            task_id=child1,
            what_was_done="Created routes",
            what_changed=["routes.py"],
            what_next=f"Next: {child2}",
            blockers=[],
            citations=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        
        # Complete child2
        queue.get_next()  # child2
        queue.mark_done(child2, Checkpoint(
            task_id=child2,
            what_was_done="Added authentication",
            what_changed=["auth.py"],
            what_next="DONE - no further work needed",
            blockers=[],
            citations=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        
        # All done
        assert queue.get_next() is None
        stats = queue.get_stats()
        assert stats["status_counts"]["done"] == 3
    
    def test_multi_level_hierarchy(self, tmp_path):
        """Support for epic → task → subtask hierarchy."""
        queue = TaskQueue(workspace_path=str(tmp_path))
        
        # Level 1: Epic
        epic = queue.add_task(
            objective="Epic: Build E-commerce",
            metadata={"level": "epic"},
        )
        
        # Level 2: Tasks
        task1 = queue.add_task(
            objective="Task: Product catalog",
            parent_id=epic,
            metadata={"level": "task"},
        )
        
        # Level 3: Subtasks
        subtask1 = queue.add_task(
            objective="Subtask: Product model",
            parent_id=task1,
            metadata={"level": "subtask"},
        )
        subtask2 = queue.add_task(
            objective="Subtask: Product API",
            parent_id=task1,
            metadata={"level": "subtask"},
        )
        
        # Verify hierarchy
        assert queue.get_task(epic).parent_id is None
        assert queue.get_task(task1).parent_id == epic
        assert queue.get_task(subtask1).parent_id == task1
        assert queue.get_task(subtask2).parent_id == task1
