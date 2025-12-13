"""
flow/planner.py - Project State Machine

This module implements a state machine for managing project.json.
The planner tracks project lifecycle: planning → executing → reviewing → complete.

Responsibilities:
- Manage project states and transitions
- Load/save project.json
- Track tasks and progress
- Provide project context to agent

Rules:
- State transitions must be valid
- Project file persists to disk
- Thread-safe operations
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


class ProjectState(Enum):
    """Project lifecycle states."""
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    COMPLETE = "complete"
    PAUSED = "paused"


@dataclass
class Task:
    """A single task in the project."""
    id: str
    description: str
    status: str = "pending"  # pending, in_progress, complete, blocked
    created_at: str = ""
    completed_at: Optional[str] = None
    notes: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ProjectPlan:
    """Project plan with tasks and state."""
    name: str
    description: str
    state: ProjectState
    tasks: List[Task]
    lab_notebook: List[str]  # Entries documenting progress
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
        
        # Convert state to ProjectState if string
        if isinstance(self.state, str):
            self.state = ProjectState(self.state)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "tasks": [task.to_dict() for task in self.tasks],
            "lab_notebook": self.lab_notebook,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectPlan":
        """Create from dictionary."""
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        return cls(
            name=data["name"],
            description=data["description"],
            state=ProjectState(data["state"]),
            tasks=tasks,
            lab_notebook=data.get("lab_notebook", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class ProjectStateMachine:
    """State machine for managing project lifecycle.
    
    Manages transitions between project states and maintains project.json.
    """
    
    # Valid state transitions
    TRANSITIONS = {
        ProjectState.PLANNING: [ProjectState.EXECUTING, ProjectState.PAUSED],
        ProjectState.EXECUTING: [ProjectState.REVIEWING, ProjectState.PAUSED],
        ProjectState.REVIEWING: [ProjectState.EXECUTING, ProjectState.COMPLETE, ProjectState.PAUSED],
        ProjectState.COMPLETE: [],  # Terminal state
        ProjectState.PAUSED: [ProjectState.PLANNING, ProjectState.EXECUTING, ProjectState.REVIEWING],
    }
    
    def __init__(self, project_file: str = "./workspace/project.json"):
        """Initialize state machine.
        
        Args:
            project_file: Path to project.json file
        """
        self.project_file = Path(project_file)
        self.project: Optional[ProjectPlan] = None
        
        # Ensure directory exists
        self.project_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing project if available
        if self.project_file.exists():
            self.load()
    
    def create(
        self,
        name: str,
        description: str,
        tasks: Optional[List[Dict[str, Any]]] = None,
    ) -> ProjectPlan:
        """Create a new project.
        
        Args:
            name: Project name
            description: Project description
            tasks: Optional list of initial tasks
            
        Returns:
            Created ProjectPlan
        """
        task_list = []
        if tasks:
            task_list = [Task.from_dict(t) for t in tasks]
        
        self.project = ProjectPlan(
            name=name,
            description=description,
            state=ProjectState.PLANNING,
            tasks=task_list,
            lab_notebook=[],
        )
        
        self.save()
        logger.info(f"Created project: {name}")
        return self.project
    
    def transition_to(self, new_state: ProjectState) -> bool:
        """Transition to a new state.
        
        Args:
            new_state: Target state
            
        Returns:
            True if transition was valid and completed
        """
        if not self.project:
            logger.error("No active project")
            return False
        
        current = self.project.state
        
        # Check if transition is valid
        if new_state not in self.TRANSITIONS[current]:
            logger.warning(
                f"Invalid transition: {current.value} -> {new_state.value}"
            )
            return False
        
        # Perform transition
        old_state = self.project.state
        self.project.state = new_state
        self.project.updated_at = datetime.now().isoformat()
        
        # Add to lab notebook
        self.add_lab_entry(f"State transition: {old_state.value} → {new_state.value}")
        
        self.save()
        logger.info(f"Transitioned: {old_state.value} -> {new_state.value}")
        return True
    
    def add_task(self, description: str, task_id: Optional[str] = None) -> Task:
        """Add a new task to the project.
        
        Args:
            description: Task description
            task_id: Optional custom task ID
            
        Returns:
            Created Task
        """
        if not self.project:
            raise ValueError("No active project")
        
        if not task_id:
            task_id = f"task_{len(self.project.tasks) + 1}"
        
        task = Task(id=task_id, description=description)
        self.project.tasks.append(task)
        self.project.updated_at = datetime.now().isoformat()
        
        self.save()
        logger.info(f"Added task: {task_id}")
        return task
    
    def update_task(self, task_id: str, status: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update a task's status or notes.
        
        Args:
            task_id: Task ID
            status: New status (pending, in_progress, complete, blocked)
            notes: Additional notes
            
        Returns:
            True if task was found and updated
        """
        if not self.project:
            return False
        
        for task in self.project.tasks:
            if task.id == task_id:
                if status:
                    task.status = status
                    if status == "complete" and not task.completed_at:
                        task.completed_at = datetime.now().isoformat()
                if notes:
                    task.notes = notes
                
                self.project.updated_at = datetime.now().isoformat()
                self.save()
                logger.info(f"Updated task: {task_id}")
                return True
        
        logger.warning(f"Task not found: {task_id}")
        return False
    
    def add_lab_entry(self, entry: str) -> None:
        """Add an entry to the lab notebook.
        
        The lab notebook tracks progress, observations, and decisions.
        
        Args:
            entry: Lab notebook entry
        """
        if not self.project:
            raise ValueError("No active project")
        
        timestamp = datetime.now().isoformat()
        self.project.lab_notebook.append(f"[{timestamp}] {entry}")
        self.project.updated_at = timestamp
        self.save()
    
    def get_summary(self) -> str:
        """Get a human-readable project summary.
        
        Returns:
            Formatted project summary
        """
        if not self.project:
            return "No active project"
        
        total_tasks = len(self.project.tasks)
        completed = sum(1 for t in self.project.tasks if t.status == "complete")
        in_progress = sum(1 for t in self.project.tasks if t.status == "in_progress")
        
        summary = f"""Project: {self.project.name}
State: {self.project.state.value}
Description: {self.project.description}

Tasks: {completed}/{total_tasks} complete, {in_progress} in progress

Recent Lab Notebook Entries:
"""
        
        # Show last 5 entries
        recent = self.project.lab_notebook[-5:] if self.project.lab_notebook else []
        for entry in recent:
            summary += f"  {entry}\n"
        
        return summary
    
    def save(self) -> None:
        """Save project to file."""
        if not self.project:
            return
        
        with open(self.project_file, 'w') as f:
            json.dump(self.project.to_dict(), f, indent=2)
        
        logger.debug(f"Saved project to {self.project_file}")
    
    def load(self) -> bool:
        """Load project from file.
        
        Returns:
            True if project was loaded successfully
        """
        if not self.project_file.exists():
            logger.warning(f"Project file not found: {self.project_file}")
            return False
        
        try:
            with open(self.project_file, 'r') as f:
                data = json.load(f)
            
            self.project = ProjectPlan.from_dict(data)
            logger.info(f"Loaded project: {self.project.name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            return False
    
    def get_context(self) -> Optional[Dict[str, Any]]:
        """Get project context for agent.
        
        Returns dictionary with current project state that can be
        included in the system prompt.
        
        Returns:
            Project context dictionary or None if no project
        """
        if not self.project:
            return None
        
        return {
            "name": self.project.name,
            "description": self.project.description,
            "state": self.project.state.value,
            "summary": self.get_summary(),
            "tasks": [t.to_dict() for t in self.project.tasks],
            "recent_notes": self.project.lab_notebook[-10:],
        }
