"""
tool/queue.py - Task Queue Tools

This module implements the queue tools for Phase 0.8B.
Provides agent access to task queue operations.

Responsibilities:
- queue_add: Add new tasks to queue
- queue_next: Get next task to execute
- queue_done: Mark task as complete
- queue_fail: Mark task as failed

Rules:
- Worker executes ONE task then stops
- All operations are logged for traceability
- Checkpoints saved on task completion/failure
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.types import ToolResult
from core.taskqueue import TaskQueue, TaskStatus, Checkpoint
from core.sandb import get_default_workspace
from .bases import BaseTool

logger = logging.getLogger(__name__)


class QueueAddTool(BaseTool):
    """Tool for adding tasks to the queue."""
    
    def __init__(self, workspace: Optional[Any] = None):
        """Initialize queue_add tool.
        
        Args:
            workspace: Workspace instance
        """
        self.workspace = workspace or get_default_workspace()
    
    @property
    def name(self) -> str:
        return "queue_add"
    
    @property
    def description(self) -> str:
        return "Add a new task to the execution queue. Use this to break down complex work into bounded, resumable units."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "objective": {
                    "type": "string",
                    "description": "Clear statement of what to accomplish"
                },
                "inputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of input references (chunk IDs, file paths, data sources)"
                },
                "acceptance": {
                    "type": "string",
                    "description": "Acceptance criteria for task completion"
                },
                "parent_id": {
                    "type": "string",
                    "description": "Optional parent task ID (for subtasks)"
                },
                "max_tool_calls": {
                    "type": "integer",
                    "description": "Maximum tool calls allowed (default: 20)",
                    "default": 20
                },
                "max_steps": {
                    "type": "integer",
                    "description": "Maximum steps allowed (default: 10)",
                    "default": 10
                }
            },
            "required": ["objective"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Add a task to the queue.
        
        Args:
            arguments: Task parameters
            
        Returns:
            ToolResult with task ID
        """
        try:
            # Create fresh TaskQueue to reload state
            queue = TaskQueue(workspace_path=str(self.workspace.base_path))
            
            objective = arguments.get("objective", "")
            if not objective:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error="Missing required parameter: objective",
                    success=False,
                )
            
            inputs = arguments.get("inputs", [])
            acceptance = arguments.get("acceptance")
            parent_id = arguments.get("parent_id")
            max_tool_calls = arguments.get("max_tool_calls", 20)
            max_steps = arguments.get("max_steps", 10)
            
            task_id = queue.add_task(
                objective=objective,
                inputs=inputs,
                acceptance=acceptance,
                parent_id=parent_id,
                max_tool_calls=max_tool_calls,
                max_steps=max_steps,
            )
            
            output = f"""Task added to queue successfully!

Task ID: {task_id}
Objective: {objective}
Budget: {max_tool_calls} tool calls, {max_steps} steps
Status: queued

Use queue_next to retrieve and execute this task.
"""
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Failed to add task: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to add task: {e}",
                success=False,
            )


class QueueNextTool(BaseTool):
    """Tool for getting the next task from queue."""
    
    def __init__(self, workspace: Optional[Any] = None):
        """Initialize queue_next tool.
        
        Args:
            workspace: Workspace instance
        """
        self.workspace = workspace or get_default_workspace()
    
    @property
    def name(self) -> str:
        return "queue_next"
    
    @property
    def description(self) -> str:
        return "Get the next queued task to execute. Returns task details including objective, inputs, and budget constraints."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Get the next task from queue.
        
        Args:
            arguments: No arguments required
            
        Returns:
            ToolResult with task details
        """
        try:
            # Create fresh TaskQueue to reload state
            queue = TaskQueue(workspace_path=str(self.workspace.base_path))
            task = queue.get_next()
            
            if task is None:
                return ToolResult(
                    tool_call_id="",
                    output="No queued tasks available. Queue is empty.",
                    success=True,
                )
            
            output = f"""Retrieved next task from queue:

Task ID: {task.task_id}
Parent ID: {task.parent_id or "None"}
Status: {task.status.value}

Objective:
{task.objective}

Inputs:
{chr(10).join(f"- {inp}" for inp in task.inputs) if task.inputs else "- None"}

Acceptance Criteria:
{task.acceptance}

Budget:
- Max tool calls: {task.budget.get('max_tool_calls', 20)}
- Max steps: {task.budget.get('max_steps', 10)}

Created: {task.created_at}

Execute this task and call queue_done when complete, or queue_fail if it cannot be completed.
"""
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Failed to get next task: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to get next task: {e}",
                success=False,
            )


class QueueDoneTool(BaseTool):
    """Tool for marking a task as done."""
    
    def __init__(self, workspace: Optional[Any] = None):
        """Initialize queue_done tool.
        
        Args:
            workspace: Workspace instance
        """
        self.workspace = workspace or get_default_workspace()
    
    @property
    def name(self) -> str:
        return "queue_done"
    
    @property
    def description(self) -> str:
        return "Mark a task as complete and save a checkpoint. This ends task execution and allows continuation from this point."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to mark as done"
                },
                "what_was_done": {
                    "type": "string",
                    "description": "Summary of completed work"
                },
                "what_changed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of changes made (file paths, patch IDs)"
                },
                "what_next": {
                    "type": "string",
                    "description": "Next steps to take (for continuation or subtasks)"
                },
                "citations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Chunk IDs or references used"
                }
            },
            "required": ["task_id", "what_was_done", "what_next"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Mark a task as done and save checkpoint.
        
        Args:
            arguments: Task completion details
            
        Returns:
            ToolResult with confirmation
        """
        try:
            # Create fresh TaskQueue to reload state
            queue = TaskQueue(workspace_path=str(self.workspace.base_path))
            
            task_id = arguments.get("task_id", "")
            if not task_id:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error="Missing required parameter: task_id",
                    success=False,
                )
            
            what_was_done = arguments.get("what_was_done", "")
            what_changed = arguments.get("what_changed", [])
            what_next = arguments.get("what_next", "")
            citations = arguments.get("citations", [])
            
            # Create checkpoint
            checkpoint = Checkpoint(
                task_id=task_id,
                what_was_done=what_was_done,
                what_changed=what_changed,
                what_next=what_next,
                blockers=[],
                citations=citations,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            
            # Mark task as done
            success = queue.mark_done(task_id, checkpoint)
            
            if not success:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Task not found: {task_id}",
                    success=False,
                )
            
            output = f"""Task marked as complete!

Task ID: {task_id}
Status: done

Checkpoint saved to: workspace/queue/checkpoints/{task_id}.md

Summary:
{what_was_done[:200]}{"..." if len(what_was_done) > 200 else ""}

Task execution complete. Worker should stop now.
"""
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Failed to mark task done: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to mark task done: {e}",
                success=False,
            )


class QueueFailTool(BaseTool):
    """Tool for marking a task as failed."""
    
    def __init__(self, workspace: Optional[Any] = None):
        """Initialize queue_fail tool.
        
        Args:
            workspace: Workspace instance
        """
        self.workspace = workspace or get_default_workspace()
    
    @property
    def name(self) -> str:
        return "queue_fail"
    
    @property
    def description(self) -> str:
        return "Mark a task as failed and save a checkpoint with error details. Use when task cannot be completed."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to mark as failed"
                },
                "error": {
                    "type": "string",
                    "description": "Error message or reason for failure"
                },
                "what_was_done": {
                    "type": "string",
                    "description": "Summary of work completed before failure"
                },
                "what_changed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of changes made before failure"
                },
                "blockers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific blockers or errors encountered"
                },
                "citations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Chunk IDs or references used"
                }
            },
            "required": ["task_id", "error"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Mark a task as failed and save checkpoint.
        
        Args:
            arguments: Task failure details
            
        Returns:
            ToolResult with confirmation
        """
        try:
            # Create fresh TaskQueue to reload state
            queue = TaskQueue(workspace_path=str(self.workspace.base_path))
            
            task_id = arguments.get("task_id", "")
            error = arguments.get("error", "")
            
            if not task_id or not error:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error="Missing required parameters: task_id and error",
                    success=False,
                )
            
            what_was_done = arguments.get("what_was_done", "No work completed")
            what_changed = arguments.get("what_changed", [])
            blockers = arguments.get("blockers", [error])
            citations = arguments.get("citations", [])
            
            # Create checkpoint
            checkpoint = Checkpoint(
                task_id=task_id,
                what_was_done=what_was_done,
                what_changed=what_changed,
                what_next="Review errors and retry or create subtasks",
                blockers=blockers,
                citations=citations,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            
            # Mark task as failed
            success = queue.mark_failed(task_id, error, checkpoint)
            
            if not success:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Task not found: {task_id}",
                    success=False,
                )
            
            output = f"""Task marked as failed.

Task ID: {task_id}
Status: failed
Error: {error}

Checkpoint saved to: workspace/queue/checkpoints/{task_id}.md

Blockers:
{chr(10).join(f"- {blocker}" for blocker in blockers)}

Task execution stopped. Worker should stop now.
"""
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Failed to mark task failed: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to mark task failed: {e}",
                success=False,
            )
