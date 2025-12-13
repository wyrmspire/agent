#!/usr/bin/env python3
"""
Phase 0.5 Demo - Tool Budget and Judge Guidance

This demonstrates the new Phase 0.5 features:
1. Tool budget enforcement
2. Judge workflow discipline checks
3. Actionable guidance

Note: This is a demonstration of the components. Full integration
with the agent loop requires the complete setup (gateway, tools, etc.)

Usage:
    python examples/phase05_demo.py
    # or with explicit PYTHONPATH:
    PYTHONPATH=. python examples/phase05_demo.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.state import ExecutionContext, generate_run_id
from core.types import Step, StepType, ToolCall, ToolResult
from flow.judge import AgentJudge


def demo_tool_budget():
    """Demonstrate tool budget enforcement."""
    print("=" * 60)
    print("DEMO 1: Tool Budget Enforcement")
    print("=" * 60)
    
    # Create execution context with small budget
    context = ExecutionContext(
        run_id=generate_run_id(),
        conversation_id="demo",
        max_tools_per_step=3,  # Only 3 tools per step
    )
    
    print(f"\nInitial state:")
    print(f"  max_tools_per_step: {context.max_tools_per_step}")
    print(f"  tools_used_this_step: {context.tools_used_this_step}")
    print(f"  can_use_tool(): {context.can_use_tool()}")
    
    # Use tools
    print(f"\nUsing tools...")
    for i in range(3):
        if context.can_use_tool():
            context.record_tool_use()
            print(f"  Tool {i+1} used. Remaining: {context.max_tools_per_step - context.tools_used_this_step}")
        else:
            print(f"  ❌ Cannot use tool {i+1} - budget exceeded!")
    
    # Try one more
    print(f"\nAttempting 4th tool:")
    if context.can_use_tool():
        print(f"  ✓ Can use tool")
    else:
        print(f"  ❌ Budget exceeded! tools_used={context.tools_used_this_step}, max={context.max_tools_per_step}")
    
    # Add a step - resets counter
    print(f"\nAdding new step (resets counter)...")
    context.add_step(Step(step_type=StepType.THINK, content="Next step"))
    print(f"  tools_used_this_step: {context.tools_used_this_step}")
    print(f"  can_use_tool(): {context.can_use_tool()}")
    

def demo_judge_code_without_tests():
    """Demonstrate judge detecting code without tests."""
    print("\n" + "=" * 60)
    print("DEMO 2: Judge Detects Code Without Tests")
    print("=" * 60)
    
    judge = AgentJudge()
    
    # Steps that write code but don't test
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="Reading file",
            tool_calls=[
                ToolCall(id="1", name="read_file", arguments={"path": "app.py"})
            ],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="File contents...",
            tool_results=[
                ToolResult(tool_call_id="1", output="def old_func(): pass", success=True)
            ],
        ),
        Step(
            step_type=StepType.CALL_TOOL,
            content="Writing updated code",
            tool_calls=[
                ToolCall(id="2", name="write_file", arguments={"path": "app.py", "content": "def new_func(): pass"})
            ],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="File written",
            tool_results=[
                ToolResult(tool_call_id="2", output="File written successfully", success=True)
            ],
        ),
    ]
    
    print(f"\nSteps taken:")
    for i, step in enumerate(steps):
        if step.tool_calls:
            print(f"  {i+1}. {step.tool_calls[0].name}")
    
    print(f"\nJudge evaluation:")
    judgment = judge.check_workflow_discipline(steps)
    print(f"  Passed: {judgment.passed}")
    print(f"  Reason: {judgment.reason}")
    print(f"  Severity: {judgment.severity}")
    print(f"  Suggestion: {judgment.suggestion}")


def demo_judge_repeated_errors():
    """Demonstrate judge detecting repeated shell errors."""
    print("\n" + "=" * 60)
    print("DEMO 3: Judge Detects Repeated Shell Errors")
    print("=" * 60)
    
    judge = AgentJudge()
    
    # Steps with repeated errors
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="Running command",
            tool_calls=[
                ToolCall(id="1", name="shell", arguments={"cmd": "npm test"})
            ],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="Error",
            tool_results=[
                ToolResult(
                    tool_call_id="1", 
                    output="", 
                    error="npm ERR! missing script: test",
                    success=False
                )
            ],
        ),
        Step(
            step_type=StepType.CALL_TOOL,
            content="Running command again",
            tool_calls=[
                ToolCall(id="2", name="shell", arguments={"cmd": "npm test"})
            ],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="Error again",
            tool_results=[
                ToolResult(
                    tool_call_id="2",
                    output="",
                    error="npm ERR! missing script: test",
                    success=False
                )
            ],
        ),
    ]
    
    print(f"\nSteps taken:")
    for i, step in enumerate(steps):
        if step.tool_results:
            result = step.tool_results[0]
            status = "✓" if result.success else "✗"
            print(f"  {i+1}. {status} {step.tool_results[0].error or 'Success'}")
    
    print(f"\nJudge evaluation:")
    judgment = judge.check_workflow_discipline(steps)
    print(f"  Passed: {judgment.passed}")
    print(f"  Reason: {judgment.reason}")
    print(f"  Severity: {judgment.severity}")
    print(f"  Suggestion: {judgment.suggestion[:100]}...")


def demo_judge_good_workflow():
    """Demonstrate judge accepting good workflow."""
    print("\n" + "=" * 60)
    print("DEMO 4: Judge Accepts Good Workflow")
    print("=" * 60)
    
    judge = AgentJudge()
    
    # Steps that follow good workflow
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="Reading code",
            tool_calls=[
                ToolCall(id="1", name="read_file", arguments={"path": "app.py"})
            ],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="File contents",
            tool_results=[
                ToolResult(tool_call_id="1", output="def func(): pass", success=True)
            ],
        ),
        Step(
            step_type=StepType.CALL_TOOL,
            content="Writing code",
            tool_calls=[
                ToolCall(id="2", name="write_file", arguments={"path": "app.py", "content": "def func(): return 42"})
            ],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="File written",
            tool_results=[
                ToolResult(tool_call_id="2", output="Success", success=True)
            ],
        ),
        Step(
            step_type=StepType.CALL_TOOL,
            content="Running tests",
            tool_calls=[
                ToolCall(id="3", name="shell", arguments={"cmd": "pytest tests/"})
            ],
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="Tests passed",
            tool_results=[
                ToolResult(tool_call_id="3", output="pytest: 10 tests passed", success=True)
            ],
        ),
    ]
    
    print(f"\nSteps taken:")
    workflow = ["Read", "Write", "Test"]
    for i, step_name in enumerate(workflow):
        print(f"  {i+1}. {step_name} ✓")
    
    print(f"\nJudge evaluation:")
    judgment = judge.check_workflow_discipline(steps)
    print(f"  Passed: {judgment.passed}")
    print(f"  Reason: {judgment.reason}")
    print(f"  This is the ideal workflow! 🎉")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "PHASE 0.5 DEMO" + " " * 29 + "║")
    print("║" + " " * 12 + "Tool Budget & Judge Guidance" + " " * 18 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    demo_tool_budget()
    demo_judge_code_without_tests()
    demo_judge_repeated_errors()
    demo_judge_good_workflow()
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("  1. Tool budget prevents infinite loops")
    print("  2. Judge detects anti-patterns (code without tests)")
    print("  3. Judge provides actionable 'DO THIS NEXT' guidance")
    print("  4. Agent is now more disciplined and measurable!")
    print()


if __name__ == "__main__":
    main()
