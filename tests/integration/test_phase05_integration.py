"""
Phase 0.5 Integration Tests

Simulates the 5 validation scenarios to test budget enforcement and judge behavior
in realistic multi-step agent execution contexts.

These tests don't need a real LLM - they directly manipulate AgentLoop internals
to verify the patched behaviors work correctly in integrated scenarios.

Run: python -m pytest tests/integration/test_phase05_integration.py -v
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
sys.path.insert(0, '.')

from core.types import Message, MessageRole, Step, StepType, ToolCall, ToolResult, Tool
from core.state import AgentState, ConversationState, ExecutionContext, generate_run_id, generate_conversation_id
from core.rules import RuleEngine
from flow.loops import AgentLoop
from flow.judge import AgentJudge
from tool.index import ToolRegistry


class MockTool:
    """Simple mock tool for testing."""
    
    def __init__(self, name: str, output: str = "OK", success: bool = True):
        self.name = name
        self._output = output
        self._success = success
    
    async def call(self, tool_call: ToolCall) -> ToolResult:
        return ToolResult(
            tool_call_id=tool_call.id,
            output=self._output,
            success=self._success,
            error="" if self._success else self._output,
        )


def create_test_state(max_tools_per_step: int = 2) -> AgentState:
    """Create a fresh AgentState for testing."""
    conv = ConversationState(id=generate_conversation_id())
    exec_ctx = ExecutionContext(
        run_id=generate_run_id(),
        conversation_id=conv.id,
        max_tools_per_step=max_tools_per_step,
        max_steps=10,
    )
    return AgentState(conversation=conv, execution=exec_ctx)


class TestPhase05IntegrationA(unittest.TestCase):
    """Test A: Mid-batch hard stop."""
    
    def test_mid_batch_hard_stop(self):
        """
        Scenario: Model requests 4 tools, budget is 2.
        Expected: Only 2 execute, rest skipped, budget_hit=True.
        """
        state = create_test_state(max_tools_per_step=2)
        
        # Simulate 4 tool calls in one batch
        tool_calls = [
            ToolCall(id="1", name="list_files", arguments={}),
            ToolCall(id="2", name="read_file", arguments={"path": "a.py"}),
            ToolCall(id="3", name="read_file", arguments={"path": "b.py"}),
            ToolCall(id="4", name="summarize", arguments={}),
        ]
        
        # Manually execute budget enforcement logic (simulates _execute_tools)
        executed = []
        budget_hit = False
        
        for tc in tool_calls:
            if not state.execution.can_use_tool():
                budget_hit = True
                break
            state.execution.record_tool_use()
            executed.append(tc.name)
        
        # Assertions
        self.assertEqual(len(executed), 2, "Only 2 tools should execute")
        self.assertEqual(executed, ["list_files", "read_file"])
        self.assertTrue(budget_hit, "budget_hit should be True")
        self.assertEqual(state.execution.tools_used_this_step, 2)
        
        # Verify skipped count
        skipped = len(tool_calls) - len(executed)
        self.assertEqual(skipped, 2, "2 tools should be skipped")


class TestPhase05IntegrationB(unittest.TestCase):
    """Test B: No soft loop."""
    
    def test_step_boundary_prevents_soft_loop(self):
        """
        Scenario: Budget exhausted, THINK step added.
        Expected: Budget resets, step advances, no infinite loop.
        """
        state = create_test_state(max_tools_per_step=2)
        
        # Exhaust budget
        state.execution.record_tool_use()
        state.execution.record_tool_use()
        
        self.assertFalse(state.execution.can_use_tool())
        initial_step = state.execution.current_step
        
        # Simulate what the patched code does: add THINK step
        state.execution.add_step(Step(
            step_type=StepType.THINK,
            content="Budget exhausted; summarizing progress and replanning.",
        ))
        
        # After step, budget should reset
        self.assertTrue(state.execution.can_use_tool(), "Budget should reset after step")
        self.assertEqual(state.execution.tools_used_this_step, 0)
        self.assertEqual(state.execution.current_step, initial_step + 1)
        
        # Verify we can now use tools again
        state.execution.record_tool_use()
        self.assertEqual(state.execution.tools_used_this_step, 1)


class TestPhase05IntegrationC(unittest.TestCase):
    """Test C: Judge catches missing tests."""
    
    def test_judge_catches_write_without_tests(self):
        """
        Scenario: Agent writes code but doesn't run tests.
        Expected: Judge warns with actionable suggestion.
        """
        judge = AgentJudge()
        
        # Simulate: write_file, then stop (no tests)
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Editing function",
                tool_calls=[
                    ToolCall(id="1", name="write_file", arguments={"path": "foo.py", "content": "def bar(): pass"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Done",
                tool_results=[
                    ToolResult(tool_call_id="1", output="File written", success=True)
                ],
            ),
        ]
        
        judgment = judge.check_workflow_discipline(steps)
        
        self.assertFalse(judgment.passed, "Should fail - no tests run")
        self.assertIn("tests were not run", judgment.reason.lower())
        self.assertIn("DO THIS NEXT", judgment.suggestion)
        self.assertIn("Run tests", judgment.suggestion)


class TestPhase05IntegrationD(unittest.TestCase):
    """Test D: Quiet tests recognized."""
    
    def test_quiet_pytest_recognized(self):
        """
        Scenario: Agent writes code, then runs pytest -q (minimal output).
        Expected: Judge recognizes tests via command args, no warning.
        """
        judge = AgentJudge()
        
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Writing",
                tool_calls=[
                    ToolCall(id="1", name="write_file", arguments={"path": "x.py"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Done",
                tool_results=[
                    ToolResult(tool_call_id="1", output="OK", success=True)
                ],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Testing",
                tool_calls=[
                    # pytest -q has very quiet output
                    ToolCall(id="2", name="shell", arguments={"cmd": "pytest -q tests/"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Quiet",
                tool_results=[
                    # Output doesn't contain "pytest" or "test" - just dots and "passed"
                    ToolResult(tool_call_id="2", output="...\n3 passed", success=True)
                ],
            ),
        ]
        
        judgment = judge.check_workflow_discipline(steps)
        
        self.assertTrue(judgment.passed, "Should pass - pytest detected via command args")


class TestPhase05IntegrationE(unittest.TestCase):
    """Test E: Shell error spam detection."""
    
    def test_repeated_shell_errors_caught(self):
        """
        Scenario: Agent runs broken shell command twice.
        Expected: Judge warns specifically about shell errors.
        """
        judge = AgentJudge()
        
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Running",
                tool_calls=[
                    ToolCall(id="1", name="shell", arguments={"cmd": "npm run missing"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error",
                tool_results=[
                    ToolResult(tool_call_id="1", output="", error="npm ERR! missing script", success=False)
                ],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Trying again",
                tool_calls=[
                    ToolCall(id="2", name="shell", arguments={"cmd": "npm run missing"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error again",
                tool_results=[
                    ToolResult(tool_call_id="2", output="", error="npm ERR! missing script", success=False)
                ],
            ),
        ]
        
        judgment = judge.check_workflow_discipline(steps)
        
        self.assertFalse(judgment.passed, "Should fail - repeated shell errors")
        self.assertIn("repeatedly", judgment.reason.lower())
        self.assertIn("shell", judgment.reason.lower())
        self.assertIn("DO THIS NEXT", judgment.suggestion)
        self.assertIn("error", judgment.suggestion.lower())
    
    def test_non_shell_errors_not_flagged(self):
        """
        Scenario: Agent has repeated read_file errors (not shell).
        Expected: No shell warning triggered.
        """
        judge = AgentJudge()
        
        steps = [
            Step(
                step_type=StepType.CALL_TOOL,
                content="Reading",
                tool_calls=[
                    ToolCall(id="1", name="read_file", arguments={"path": "missing.txt"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error",
                tool_results=[
                    ToolResult(tool_call_id="1", output="", error="File not found", success=False)
                ],
            ),
            Step(
                step_type=StepType.CALL_TOOL,
                content="Reading again",
                tool_calls=[
                    ToolCall(id="2", name="read_file", arguments={"path": "also_missing.txt"})
                ],
            ),
            Step(
                step_type=StepType.OBSERVE,
                content="Error again",
                tool_results=[
                    ToolResult(tool_call_id="2", output="", error="File not found", success=False)
                ],
            ),
        ]
        
        judgment = judge.check_workflow_discipline(steps)
        
        # Should NOT mention "shell repeatedly"
        if not judgment.passed:
            self.assertNotIn("shell", judgment.reason.lower(),
                           "Non-shell errors should not trigger shell warning")


class TestPhase05EdgeCase(unittest.TestCase):
    """Edge case: mixed tool batch with early write and skipped tests."""
    
    def test_write_then_test_skipped_due_to_budget(self):
        """
        Scenario: Model requests [write_file, read_file, shell(pytest)], budget=2.
        Expected: write and read run, shell(pytest) skipped.
        Judge correctly warns about missing tests.
        """
        state = create_test_state(max_tools_per_step=2)
        judge = AgentJudge()
        
        tool_calls = [
            ToolCall(id="1", name="write_file", arguments={"path": "x.py"}),
            ToolCall(id="2", name="read_file", arguments={"path": "y.py"}),
            ToolCall(id="3", name="shell", arguments={"cmd": "pytest"}),  # Will be skipped
        ]
        
        # Simulate budget enforcement
        steps = []
        for tc in tool_calls:
            if not state.execution.can_use_tool():
                break  # Skip remaining
            
            state.execution.record_tool_use()
            
            # Add CALL_TOOL step
            steps.append(Step(
                step_type=StepType.CALL_TOOL,
                content=f"Calling {tc.name}",
                tool_calls=[tc],
            ))
            
            # Add OBSERVE step
            steps.append(Step(
                step_type=StepType.OBSERVE,
                content="Done",
                tool_results=[
                    ToolResult(tool_call_id=tc.id, output="OK", success=True)
                ],
            ))
        
        # Only 2 tools should have run
        self.assertEqual(state.execution.tools_used_this_step, 2)
        self.assertEqual(len(steps), 4)  # 2 tools × 2 steps each
        
        # Judge should warn about missing tests
        judgment = judge.check_workflow_discipline(steps)
        self.assertFalse(judgment.passed, "Should warn - tests were skipped")
        self.assertIn("tests were not run", judgment.reason.lower())


if __name__ == "__main__":
    unittest.main()
