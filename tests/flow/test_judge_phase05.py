"""
Tests for flow/judge.py - Phase 0.5 enhancements
"""

import unittest

from core.types import Step, StepType, ToolCall, ToolResult
from flow.judge import AgentJudge, Judgment


class TestJudgePhase05(unittest.TestCase):
    """Test Phase 0.5 judge enhancements."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.judge = AgentJudge()
    
    def test_workflow_discipline_no_steps(self):
        """Test workflow check with no steps."""
        judgment = self.judge.check_workflow_discipline([])
        self.assertTrue(judgment.passed)
    
    def test_workflow_discipline_code_without_tests(self):
        """Test detection of code written without running tests."""
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Writing code",
                tool_calls=[
                    ToolCall(id="1", name="write_file", arguments={"path": "test.py", "content": "def foo(): pass"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="File written",
                tool_results=[
                    ToolResult(tool_call_id="1", output="File written successfully", success=True)
                ],
            ),
        ]
        
        judgment = self.judge.check_workflow_discipline(steps)
        self.assertFalse(judgment.passed)
        self.assertIn("tests were not run", judgment.reason.lower())
        self.assertIn("DO THIS NEXT", judgment.suggestion)
    
    def test_workflow_discipline_code_with_tests(self):
        """Test that running tests after code is recognized."""
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Writing code",
                tool_calls=[
                    ToolCall(id="1", name="write_file", arguments={"path": "test.py", "content": "def foo(): pass"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="File written",
                tool_results=[
                    ToolResult(tool_call_id="1", output="File written successfully", success=True)
                ],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Running tests",
                tool_calls=[
                    ToolCall(id="2", name="shell", arguments={"cmd": "pytest tests/"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Tests passed",
                tool_results=[
                    ToolResult(tool_call_id="2", output="pytest: 5 tests passed", success=True)
                ],
            ),
        ]
        
        judgment = self.judge.check_workflow_discipline(steps)
        self.assertTrue(judgment.passed)
    
    def test_workflow_discipline_repeated_shell_errors(self):
        """Test detection of repeated shell errors."""
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Running command",
                tool_calls=[
                    ToolCall(id="1", name="shell", arguments={"cmd": "bad_command"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error",
                tool_results=[
                    ToolResult(tool_call_id="1", output="", error="Command not found: bad_command", success=False)
                ],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Running command again",
                tool_calls=[
                    ToolCall(id="2", name="shell", arguments={"cmd": "bad_command"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error again",
                tool_results=[
                    ToolResult(tool_call_id="2", output="", error="Command not found: bad_command", success=False)
                ],
            ),
        ]
        
        judgment = self.judge.check_workflow_discipline(steps)
        self.assertFalse(judgment.passed)
        self.assertIn("repeatedly", judgment.reason.lower())
        self.assertIn("DO THIS NEXT", judgment.suggestion)
        self.assertIn("error", judgment.suggestion.lower())
    
    def test_existing_check_progress(self):
        """Test that existing check_progress still works."""
        steps = [
            Step(
                step_type=StepType.OBSERVE,
                content="Error",
                tool_results=[
                    ToolResult(tool_call_id="1", output="", error="Failed", success=False)
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error",
                tool_results=[
                    ToolResult(tool_call_id="2", output="", error="Failed again", success=False)
                ],
            ),
        ]
        
        judgment = self.judge.check_progress(steps)
        self.assertFalse(judgment.passed)
        self.assertEqual(judgment.severity, "warning")
    
    def test_existing_check_tool_loop(self):
        """Test that existing check_tool_loop still works."""
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Call 1",
                tool_calls=[ToolCall(id="1", name="same_tool", arguments={})],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Call 2",
                tool_calls=[ToolCall(id="2", name="same_tool", arguments={})],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Call 3",
                tool_calls=[ToolCall(id="3", name="same_tool", arguments={})],
            ),
        ]
        
        judgment = self.judge.check_tool_loop(steps)
        self.assertFalse(judgment.passed)
        self.assertIn("same_tool", judgment.reason)
    
    def test_workflow_discipline_detects_test_via_shell_args(self):
        """Test that test detection works via shell command args, not just output (Phase 0.5 fix)."""
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Writing code",
                tool_calls=[
                    ToolCall(id="1", name="write_file", arguments={"path": "test.py", "content": "def foo(): pass"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="File written",
                tool_results=[
                    ToolResult(tool_call_id="1", output="File written successfully", success=True)
                ],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Running tests with quiet output",
                tool_calls=[
                    # Using pytest -q which may output minimal text
                    ToolCall(id="2", name="shell", arguments={"cmd": "pytest -q tests/"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Quiet output",
                tool_results=[
                    # Output doesn't contain "pytest" or "test" keywords
                    ToolResult(tool_call_id="2", output="..\n2 passed", success=True)
                ],
            ),
        ]
        
        judgment = self.judge.check_workflow_discipline(steps)
        # Should pass because we detect pytest in the command args, not output
        self.assertTrue(judgment.passed)
    
    def test_workflow_discipline_non_shell_errors_ignored(self):
        """Test that non-shell tool errors don't trigger shell warning (Phase 0.5 fix)."""
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Reading file",
                tool_calls=[
                    ToolCall(id="1", name="read_file", arguments={"path": "missing.txt"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error",
                tool_results=[
                    ToolResult(tool_call_id="1", output="", error="File not found: missing.txt", success=False)
                ],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Reading another file",
                tool_calls=[
                    ToolCall(id="2", name="read_file", arguments={"path": "also_missing.txt"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error again",
                tool_results=[
                    ToolResult(tool_call_id="2", output="", error="File not found: also_missing.txt", success=False)
                ],
            ),
        ]
        
        judgment = self.judge.check_workflow_discipline(steps)
        # Should pass (or not trigger shell warning) because these are read_file, not shell
        # The reason should NOT mention "shell repeatedly"
        if not judgment.passed:
            self.assertNotIn("shell", judgment.reason.lower())


if __name__ == "__main__":
    unittest.main()

