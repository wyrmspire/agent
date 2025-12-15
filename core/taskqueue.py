"""
core/taskqueue.py - Task Queue and Checkpoint Management

This module implements the task queue system for Phase 0.8B.
Enables bounded task execution with resume capability.

Responsibilities:
- Task packet format (JSONL storage)
- Checkpoint format (Markdown storage)
- Task lifecycle management (queued/running/done/failed)
- Budget enforcement (max tool calls/steps)

Rules:
- Worker executes ONE task then stops
- Every task leaves artifacts for continuation
- Deterministic task IDs for traceability
- Checkpoints capture state for resume
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class TaskPacket:
    """A bounded unit of work for the agent.
    
    Attributes:
        task_id: Unique task identifier
        parent_id: Parent task ID (for subtasks)
        objective: Clear statement of what to accomplish
        inputs: References to chunks/files/data needed
        acceptance: Criteria for task completion
        budget: Limits (max_tool_calls, max_steps)
        status: Current status (queued/running/done/failed)
        created_at: Creation timestamp
        updated_at: Last update timestamp
        metadata: Additional task metadata
    """
    task_id: str
    parent_id: Optional[str]
    objective: str
    inputs: List[str]
    acceptance: str
    budget: Dict[str, int]
    status: TaskStatus
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


@dataclass
class Checkpoint:
    """Checkpoint for task continuation.
    
    Attributes:
        task_id: Associated task ID
        what_was_done: Summary of completed work
        what_changed: Patch IDs or file changes
        what_next: Next steps to take
        blockers: Errors or blockers encountered
        citations: Chunk IDs or references used
        created_at: Checkpoint timestamp
    """
    task_id: str
    what_was_done: str
    what_changed: List[str]
    what_next: str
    blockers: List[str]
    citations: List[str]
    created_at: str


class TaskQueue:
    """Manages task packets and checkpoints.
    
    Stores tasks in JSONL format and checkpoints in Markdown.
    Ensures deterministic task execution with resume capability.
    """
    
    def __init__(
        self,
        workspace_path: str = "./workspace",
        queue_name: str = "queue",
    ):
        """Initialize task queue.
        
        Args:
            workspace_path: Root workspace path
            queue_name: Name of the queue (subdirectory)
        """
        self.workspace_root = Path(workspace_path)
        self.queue_dir = self.workspace_root / queue_name
        self.tasks_file = self.queue_dir / "tasks.jsonl"
        self.tasks_file = self.queue_dir / "tasks.jsonl"
        self.checkpoints_dir = self.queue_dir / "checkpoints"
        self.active_task_file = self.queue_dir / "active_task.json"
        
        # Create directories
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory task index
        self._tasks: Dict[str, TaskPacket] = {}
        self._load_tasks()
    
    def _load_tasks(self) -> None:
        """Load tasks from JSONL file."""
        if not self.tasks_file.exists():
            logger.info("No existing tasks file found")
            return
        
        try:
            with open(self.tasks_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        # Convert status string to enum
                        data['status'] = TaskStatus(data['status'])
                        task = TaskPacket(**data)
                        self._tasks[task.task_id] = task
            
            logger.info(f"Loaded {len(self._tasks)} tasks from queue")
        
        except Exception as e:
            logger.error(f"Failed to load tasks: {e}")
    
    def _save_task(self, task: TaskPacket) -> None:
        """Append task to JSONL file.
        
        Args:
            task: Task packet to save
        """
        try:
            # Convert to dict and handle enum
            task_dict = asdict(task)
            task_dict['status'] = task.status.value
            
            # Append to JSONL
            with open(self.tasks_file, 'a') as f:
                f.write(json.dumps(task_dict) + '\n')
            
            logger.debug(f"Saved task {task.task_id}")
        
        except Exception as e:
            logger.error(f"Failed to save task: {e}")
            raise
    
    def add_task(
        self,
        objective: str,
        inputs: Optional[List[str]] = None,
        acceptance: Optional[str] = None,
        parent_id: Optional[str] = None,
        max_tool_calls: int = 30,  # Increased from 20
        max_steps: int = 50,  # Default step limit per task
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a new task to the queue.
        
        Args:
            objective: What to accomplish
            inputs: List of input references (chunk IDs, file paths)
            acceptance: Acceptance criteria
            parent_id: Parent task ID (for subtasks)
            max_tool_calls: Maximum tool calls allowed
            max_steps: Maximum steps allowed
            metadata: Additional metadata
            
        Returns:
            Task ID of the created task
        """
        # Generate deterministic task ID
        timestamp = datetime.now(timezone.utc).isoformat()
        task_id = f"task_{len(self._tasks) + 1:04d}"
        
        task = TaskPacket(
            task_id=task_id,
            parent_id=parent_id,
            objective=objective,
            inputs=inputs or [],
            acceptance=acceptance or "Task completed successfully",
            budget={
                "max_tool_calls": max_tool_calls,
                "max_steps": max_steps,
            },
            status=TaskStatus.QUEUED,
            created_at=timestamp,
            updated_at=timestamp,
            metadata=metadata or {},
        )
        
        # Save to memory and disk
        self._tasks[task_id] = task
        self._save_task(task)
        
        logger.info(f"Added task {task_id}: {objective[:50]}...")
        return task_id
    
    def get_next(self) -> Optional[TaskPacket]:
        """Get the next queued task.
        
        Returns:
            Next queued task, or None if queue is empty
        """
        for task in self._tasks.values():
            if task.status == TaskStatus.QUEUED:
                # Mark as running
                task.status = TaskStatus.RUNNING
                task.updated_at = datetime.now(timezone.utc).isoformat()
                self._update_task(task)
                
                # Persist active task for agent loop
                self.active_task_file.write_text(json.dumps(asdict(task), indent=2))
                
                logger.info(f"Starting task {task.task_id}")
                return task
        
        logger.info("No queued tasks available")
        return None
    
    def mark_done(
        self,
        task_id: str,
        checkpoint: Optional[Checkpoint] = None,
    ) -> bool:
        """Mark a task as done.
        
        Args:
            task_id: Task ID to mark as done
            checkpoint: Optional checkpoint to save
            
        Returns:
            True if successful
        """
        if task_id not in self._tasks:
            logger.error(f"Task not found: {task_id}")
            return False
        
        task = self._tasks[task_id]
        task.status = TaskStatus.DONE
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._update_task(task)
        
        # Save checkpoint if provided
        if checkpoint:
            self.save_checkpoint(checkpoint)
        
        # Cleanup active task file
        if self.active_task_file.exists():
            try:
                # Only delete if it matches the current task
                active = json.loads(self.active_task_file.read_text())
                if active.get("task_id") == task_id:
                    self.active_task_file.unlink()
            except Exception:
                pass # Best effort cleanup

        logger.info(f"Marked task {task_id} as done")
        return True
    
    def mark_failed(
        self,
        task_id: str,
        error: str,
        checkpoint: Optional[Checkpoint] = None,
    ) -> bool:
        """Mark a task as failed.
        
        Args:
            task_id: Task ID to mark as failed
            error: Error message
            checkpoint: Optional checkpoint to save
            
        Returns:
            True if successful
        """
        if task_id not in self._tasks:
            logger.error(f"Task not found: {task_id}")
            return False
        
        task = self._tasks[task_id]
        task.status = TaskStatus.FAILED
        task.updated_at = datetime.now(timezone.utc).isoformat()
        task.metadata['error'] = error
        self._update_task(task)
        
        # Save checkpoint if provided
        if checkpoint:
            self.save_checkpoint(checkpoint)
            
        # Cleanup active task file
        if self.active_task_file.exists():
            try:
                # Only delete if it matches the current task
                active = json.loads(self.active_task_file.read_text())
                if active.get("task_id") == task_id:
                    self.active_task_file.unlink()
            except Exception:
                pass # Best effort cleanup
        
        logger.info(f"Marked task {task_id} as failed: {error}")
        return True
    
    def _update_task(self, task: TaskPacket) -> None:
        """Update task in memory and rebuild JSONL file.
        
        Args:
            task: Task to update
        """
        self._tasks[task.task_id] = task
        
        # Rebuild JSONL file with all tasks
        try:
            with open(self.tasks_file, 'w') as f:
                for t in self._tasks.values():
                    task_dict = asdict(t)
                    task_dict['status'] = t.status.value
                    f.write(json.dumps(task_dict) + '\n')
        
        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            raise
    
    def save_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Save a checkpoint to disk.
        
        Args:
            checkpoint: Checkpoint to save
            
        Returns:
            True if successful
        """
        try:
            checkpoint_path = self.checkpoints_dir / f"{checkpoint.task_id}.md"
            
            # Format as markdown
            content = f"""# Checkpoint: {checkpoint.task_id}

**Created:** {checkpoint.created_at}

## What Was Done

{checkpoint.what_was_done}

## What Changed

{chr(10).join(f"- {change}" for change in checkpoint.what_changed) if checkpoint.what_changed else "- No changes"}

## What's Next

{checkpoint.what_next}

## Blockers/Errors

{chr(10).join(f"- {blocker}" for blocker in checkpoint.blockers) if checkpoint.blockers else "- None"}

## Citations Used

{chr(10).join(f"- {citation}" for citation in checkpoint.citations) if checkpoint.citations else "- None"}
"""
            
            checkpoint_path.write_text(content)
            logger.info(f"Saved checkpoint for task {checkpoint.task_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False
    
    def load_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint from disk.
        
        Args:
            task_id: Task ID to load checkpoint for
            
        Returns:
            Checkpoint if found, None otherwise
        """
        checkpoint_path = self.checkpoints_dir / f"{task_id}.md"
        
        if not checkpoint_path.exists():
            logger.info(f"No checkpoint found for task {task_id}")
            return None
        
        try:
            # For now, return a basic parsed checkpoint
            # Full markdown parsing could be added later
            content = checkpoint_path.read_text()
            
            # Simple parsing (could be enhanced)
            return Checkpoint(
                task_id=task_id,
                what_was_done="See checkpoint file",
                what_changed=[],
                what_next="See checkpoint file",
                blockers=[],
                citations=[],
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def get_task(self, task_id: str) -> Optional[TaskPacket]:
        """Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task packet if found
        """
        return self._tasks.get(task_id)
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
    ) -> List[TaskPacket]:
        """List all tasks, optionally filtered by status.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of tasks
        """
        if status is None:
            return list(self._tasks.values())
        
        return [t for t in self._tasks.values() if t.status == status]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics.
        
        Returns:
            Statistics about the queue
        """
        status_counts = {
            TaskStatus.QUEUED.value: 0,
            TaskStatus.RUNNING.value: 0,
            TaskStatus.DONE.value: 0,
            TaskStatus.FAILED.value: 0,
        }
        
        for task in self._tasks.values():
            status_counts[task.status.value] += 1
        
        return {
            "total_tasks": len(self._tasks),
            "status_counts": status_counts,
            "queue_dir": str(self.queue_dir),
            "tasks_file": str(self.tasks_file),
            "checkpoints_dir": str(self.checkpoints_dir),
        }
