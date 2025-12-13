"""
Tests for core/state.py - Phase 0.5 enhancements
"""

import unittest

from core.state import ExecutionContext, generate_run_id


class TestExecutionContextPhase05(unittest.TestCase):
    """Test Phase 0.5 ExecutionContext enhancements."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.context = ExecutionContext(
            run_id=generate_run_id(),
            conversation_id="test_conv",
            max_tools_per_step=5,
        )
    
    def test_tool_budget_initialization(self):
        """Test that tool budget is initialized correctly."""
        self.assertEqual(self.context.max_tools_per_step, 5)
        self.assertEqual(self.context.tools_used_this_step, 0)
    
    def test_can_use_tool_initial(self):
        """Test can_use_tool when no tools used yet."""
        self.assertTrue(self.context.can_use_tool())
    
    def test_record_tool_use(self):
        """Test recording tool use increments counter."""
        self.context.record_tool_use()
        self.assertEqual(self.context.tools_used_this_step, 1)
        
        self.context.record_tool_use()
        self.assertEqual(self.context.tools_used_this_step, 2)
    
    def test_can_use_tool_at_limit(self):
        """Test can_use_tool when at limit."""
        # Use up all tools
        for _ in range(5):
            self.context.record_tool_use()
        
        # Should not be able to use more
        self.assertFalse(self.context.can_use_tool())
    
    def test_tool_counter_resets_on_new_step(self):
        """Test that tool counter resets when adding a new step."""
        from core.types import Step, StepType
        
        # Use some tools
        self.context.record_tool_use()
        self.context.record_tool_use()
        self.assertEqual(self.context.tools_used_this_step, 2)
        
        # Add a step - should reset counter
        self.context.add_step(Step(
            step_type=StepType.THINK,
            content="Thinking",
        ))
        
        self.assertEqual(self.context.tools_used_this_step, 0)
        self.assertTrue(self.context.can_use_tool())
    
    def test_default_tool_budget(self):
        """Test that default tool budget is set."""
        context = ExecutionContext(
            run_id=generate_run_id(),
            conversation_id="test",
        )
        
        # Default should be 10
        self.assertEqual(context.max_tools_per_step, 10)


if __name__ == "__main__":
    unittest.main()
