"""
Tests for flow/planner.py - Project State Machine
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from flow.planner import (
    ProjectStateMachine,
    ProjectState,
    ProjectPlan,
    Task,
)


class TestProjectStateMachine(unittest.TestCase):
    """Test project state machine."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.project_file = f"{self.temp_dir}/project.json"
        self.planner = ProjectStateMachine(project_file=self.project_file)
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_project(self):
        """Test creating a new project."""
        project = self.planner.create(
            name="Test Project",
            description="A test project",
            tasks=[
                {"id": "task1", "description": "First task"},
                {"id": "task2", "description": "Second task"},
            ]
        )
        
        self.assertIsNotNone(project)
        self.assertEqual(project.name, "Test Project")
        self.assertEqual(project.state, ProjectState.PLANNING)
        self.assertEqual(len(project.tasks), 2)
        
        # Check that file was created
        self.assertTrue(Path(self.project_file).exists())
    
    def test_state_transitions(self):
        """Test valid state transitions."""
        self.planner.create(
            name="Test Project",
            description="Test transitions"
        )
        
        # Valid: PLANNING -> EXECUTING
        self.assertTrue(self.planner.transition_to(ProjectState.EXECUTING))
        self.assertEqual(self.planner.project.state, ProjectState.EXECUTING)
        
        # Valid: EXECUTING -> REVIEWING
        self.assertTrue(self.planner.transition_to(ProjectState.REVIEWING))
        self.assertEqual(self.planner.project.state, ProjectState.REVIEWING)
        
        # Valid: REVIEWING -> COMPLETE
        self.assertTrue(self.planner.transition_to(ProjectState.COMPLETE))
        self.assertEqual(self.planner.project.state, ProjectState.COMPLETE)
    
    def test_invalid_transitions(self):
        """Test invalid state transitions are blocked."""
        self.planner.create(
            name="Test Project",
            description="Test invalid transitions"
        )
        
        # Invalid: PLANNING -> COMPLETE (must go through EXECUTING and REVIEWING)
        result = self.planner.transition_to(ProjectState.COMPLETE)
        self.assertFalse(result)
        self.assertEqual(self.planner.project.state, ProjectState.PLANNING)
        
        # Invalid: COMPLETE -> anywhere (terminal state)
        self.planner.transition_to(ProjectState.EXECUTING)
        self.planner.transition_to(ProjectState.REVIEWING)
        self.planner.transition_to(ProjectState.COMPLETE)
        
        result = self.planner.transition_to(ProjectState.PLANNING)
        self.assertFalse(result)
        self.assertEqual(self.planner.project.state, ProjectState.COMPLETE)
    
    def test_add_task(self):
        """Test adding tasks to project."""
        self.planner.create(
            name="Test Project",
            description="Test tasks"
        )
        
        task = self.planner.add_task("New task")
        
        self.assertIsNotNone(task)
        self.assertEqual(task.description, "New task")
        self.assertEqual(task.status, "pending")
        self.assertEqual(len(self.planner.project.tasks), 1)
    
    def test_update_task(self):
        """Test updating task status."""
        self.planner.create(
            name="Test Project",
            description="Test task updates"
        )
        
        task = self.planner.add_task("Test task")
        
        # Update to in_progress
        result = self.planner.update_task(task.id, status="in_progress")
        self.assertTrue(result)
        self.assertEqual(self.planner.project.tasks[0].status, "in_progress")
        
        # Update to complete
        result = self.planner.update_task(task.id, status="complete")
        self.assertTrue(result)
        self.assertEqual(self.planner.project.tasks[0].status, "complete")
        self.assertIsNotNone(self.planner.project.tasks[0].completed_at)
    
    def test_lab_notebook(self):
        """Test lab notebook entries."""
        self.planner.create(
            name="Test Project",
            description="Test lab notebook"
        )
        
        self.planner.add_lab_entry("First observation")
        self.planner.add_lab_entry("Second observation")
        
        self.assertEqual(len(self.planner.project.lab_notebook), 2)
        self.assertIn("First observation", self.planner.project.lab_notebook[0])
        self.assertIn("Second observation", self.planner.project.lab_notebook[1])
    
    def test_persistence(self):
        """Test saving and loading project."""
        # Create project
        self.planner.create(
            name="Persistent Project",
            description="Test persistence"
        )
        self.planner.add_task("Task 1")
        self.planner.add_lab_entry("Test entry")
        
        # Create new planner instance to load from disk
        planner2 = ProjectStateMachine(project_file=self.project_file)
        
        self.assertIsNotNone(planner2.project)
        self.assertEqual(planner2.project.name, "Persistent Project")
        self.assertEqual(len(planner2.project.tasks), 1)
        self.assertEqual(len(planner2.project.lab_notebook), 1)
    
    def test_get_summary(self):
        """Test project summary generation."""
        self.planner.create(
            name="Summary Test",
            description="Test summary"
        )
        self.planner.add_task("Task 1")
        self.planner.add_task("Task 2")
        self.planner.update_task("task_1", status="complete")
        
        summary = self.planner.get_summary()
        
        self.assertIn("Summary Test", summary)
        self.assertIn("1/2 complete", summary)
    
    def test_get_context(self):
        """Test getting project context for agent."""
        self.planner.create(
            name="Context Test",
            description="Test context"
        )
        self.planner.add_task("Test task")
        self.planner.add_lab_entry("Test note")
        
        context = self.planner.get_context()
        
        self.assertIsNotNone(context)
        self.assertEqual(context["name"], "Context Test")
        self.assertEqual(context["state"], "planning")
        self.assertEqual(len(context["tasks"]), 1)
        self.assertEqual(len(context["recent_notes"]), 1)


if __name__ == "__main__":
    unittest.main()
