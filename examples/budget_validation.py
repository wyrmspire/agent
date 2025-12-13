"""
Phase 0.5 Budget + Judge Validation Script

This script programmatically tests the patched behaviors:
1. Hard stop mid-batch (budget enforcement per tool)
2. Step boundary on budget exhaustion (no soft loops)
3. Judge test detection via shell command args
4. Judge shell-only error filtering

Run: python examples/budget_validation.py
"""

import asyncio
import sys
sys.path.insert(0, '.')

from core.types import Step, StepType, ToolCall, ToolResult
from core.state import ExecutionContext, ConversationState, AgentState, generate_run_id, generate_conversation_id
from flow.judge import AgentJudge


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"TEST: {title}")
    print('='*60)


def print_result(passed: bool, description: str):
    icon = "✅" if passed else "❌"
    print(f"  {icon} {description}")


def test_budget_mid_batch_stop():
    """Test 1: Budget is enforced per-tool, not per-batch."""
    print_header("Budget Mid-Batch Stop (Hard Stop)")
    
    # Create execution context with budget of 2
    execution = ExecutionContext(
        run_id=generate_run_id(),
        conversation_id=generate_conversation_id(),
        max_tools_per_step=2,
    )
    
    # Simulate 5 tool calls in one batch
    tool_calls = [
        ToolCall(id=f"tc_{i}", name=f"tool_{i}", arguments={})
        for i in range(5)
    ]
    
    executed = []
    for tc in tool_calls:
        # Check budget BEFORE each tool (this is what we patched)
        if not execution.can_use_tool():
            break
        execution.record_tool_use()
        executed.append(tc.name)
    
    # Assertions
    passed_count = len(executed) == 2
    passed_budget = not execution.can_use_tool()
    passed_remaining = execution.tools_used_this_step == 2
    
    print_result(passed_count, f"Only 2 tools executed (got {len(executed)})")
    print_result(passed_budget, f"can_use_tool() returns False after budget hit")
    print_result(passed_remaining, f"tools_used_this_step == 2")
    
    return passed_count and passed_budget and passed_remaining


def test_step_boundary_resets_budget():
    """Test 2: Adding a step resets the budget (prevents soft loops)."""
    print_header("Step Boundary Resets Budget (No Soft Loops)")
    
    execution = ExecutionContext(
        run_id=generate_run_id(),
        conversation_id=generate_conversation_id(),
        max_tools_per_step=2,
    )
    
    # Use up budget
    execution.record_tool_use()
    execution.record_tool_use()
    
    budget_exhausted = not execution.can_use_tool()
    print_result(budget_exhausted, "Budget exhausted after 2 tools")
    
    # Add a step (simulates what we do when budget is hit)
    execution.add_step(Step(
        step_type=StepType.THINK,
        content="Budget exhausted; replanning.",
    ))
    
    budget_reset = execution.can_use_tool()
    counter_reset = execution.tools_used_this_step == 0
    step_advanced = execution.current_step == 1
    
    print_result(budget_reset, "can_use_tool() returns True after step added")
    print_result(counter_reset, "tools_used_this_step reset to 0")
    print_result(step_advanced, f"current_step advanced to {execution.current_step}")
    
    return budget_exhausted and budget_reset and counter_reset and step_advanced


def test_judge_detects_test_via_command_args():
    """Test 3: Judge detects tests via shell command args, not just output."""
    print_header("Judge Detects Tests via Shell Command Args")
    
    judge = AgentJudge()
    
    # Scenario: Write file, then run pytest -q (minimal output)
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="Writing code",
            tool_calls=[
                ToolCall(id="1", name="write_file", arguments={"path": "foo.py"})
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
            content="Running quiet tests",
            tool_calls=[
                # pytest -q outputs minimal text, might not contain "pytest" in output
                ToolCall(id="2", name="shell", arguments={"cmd": "pytest -q"})
            ],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="Quiet output",
            tool_results=[
                # Output doesn't contain test keywords
                ToolResult(tool_call_id="2", output="..\n2 passed", success=True)
            ],
        ),
    ]
    
    judgment = judge.check_workflow_discipline(steps)
    
    passed = judgment.passed
    print_result(passed, f"Judge passed (recognized pytest via command args)")
    if not passed:
        print(f"      Reason: {judgment.reason}")
    
    return passed


def test_judge_ignores_non_shell_errors():
    """Test 4: Judge shell warning only triggers for shell tool errors."""
    print_header("Judge Ignores Non-Shell Tool Errors")
    
    judge = AgentJudge()
    
    # Scenario: Multiple read_file errors (not shell)
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="Reading",
            tool_calls=[ToolCall(id="1", name="read_file", arguments={})],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="Error",
            tool_results=[
                ToolResult(tool_call_id="1", output="", error="Not found", success=False)
            ],
        ),
        Step(
            step_type=StepType.CALL_TOOL,
            content="Reading again",
            tool_calls=[ToolCall(id="2", name="read_file", arguments={})],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="Error again",
            tool_results=[
                ToolResult(tool_call_id="2", output="", error="Not found", success=False)
            ],
        ),
    ]
    
    judgment = judge.check_workflow_discipline(steps)
    
    # Should NOT trigger "calling shell repeatedly" warning
    no_shell_warning = "shell" not in judgment.reason.lower() if not judgment.passed else True
    
    print_result(no_shell_warning, "No false 'shell repeatedly' warning for read_file errors")
    if not no_shell_warning:
        print(f"      Reason: {judgment.reason}")
    
    return no_shell_warning


def test_judge_catches_actual_shell_errors():
    """Test 5: Judge correctly catches repeated shell errors."""
    print_header("Judge Catches Actual Repeated Shell Errors")
    
    judge = AgentJudge()
    
    # Scenario: Multiple shell command errors
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="Running shell",
            tool_calls=[ToolCall(id="1", name="shell", arguments={"cmd": "bad"})],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="Error",
            tool_results=[
                ToolResult(tool_call_id="1", output="", error="Command not found", success=False)
            ],
        ),
        Step(
            step_type=StepType.CALL_TOOL,
            content="Running shell again",
            tool_calls=[ToolCall(id="2", name="shell", arguments={"cmd": "bad"})],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="Error again",
            tool_results=[
                ToolResult(tool_call_id="2", output="", error="Command not found", success=False)
            ],
        ),
    ]
    
    judgment = judge.check_workflow_discipline(steps)
    
    caught = not judgment.passed and "repeatedly" in judgment.reason.lower()
    has_suggestion = judgment.suggestion and "DO THIS NEXT" in judgment.suggestion
    
    print_result(caught, "Judge caught repeated shell errors")
    print_result(has_suggestion, "Judge provided 'DO THIS NEXT' suggestion")
    
    return caught and has_suggestion


def main():
    print("\n" + "="*60)
    print("   PHASE 0.5 BUDGET + JUDGE VALIDATION")
    print("="*60)
    
    tests = [
        ("Budget Mid-Batch Stop", test_budget_mid_batch_stop),
        ("Step Boundary Resets Budget", test_step_boundary_resets_budget),
        ("Test Detection via Command Args", test_judge_detects_test_via_command_args),
        ("Non-Shell Errors Ignored", test_judge_ignores_non_shell_errors),
        ("Shell Errors Caught", test_judge_catches_actual_shell_errors),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"  ❌ Exception: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    
    for name, passed, error in results:
        icon = "✅" if passed else "❌"
        suffix = f" (Error: {error})" if error else ""
        print(f"  {icon} {name}{suffix}")
    
    print(f"\n  Result: {passed_count}/{total} tests passed")
    
    if passed_count == total:
        print("\n  🎉 All Phase 0.5 patches validated!")
    else:
        print("\n  ⚠️ Some tests failed. Review output above.")
    
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
