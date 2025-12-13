"""
tests/flow/test_judge_phase07.py - Tests for Phase 0.7 judge enhancements

Tests the patch discipline checks in the judge.
"""

from flow.judge import AgentJudge
from core.types import Step, StepType, ToolCall, ToolResult


def test_patch_discipline_proposes_without_patch():
    """Test detecting change proposals without patch creation."""
    judge = AgentJudge()
    
    # Agent proposes a fix but doesn't create patch
    steps = [
        Step(
            step_type=StepType.THINK,
            content="I will fix the tool budget bug in core/state.py",
            tool_calls=None,
            tool_results=None,
        ),
    ]
    
    judgment = judge.check_patch_discipline(steps)
    
    assert not judgment.passed
    assert "without creating a patch" in judgment.reason
    assert "create_patch" in judgment.suggestion


def test_patch_discipline_creates_patch():
    """Test that creating patch satisfies discipline."""
    judge = AgentJudge()
    
    # Agent proposes fix and creates patch
    steps = [
        Step(
            step_type=StepType.THINK,
            content="I will fix the tool budget bug",
            tool_calls=None,
            tool_results=None,
        ),
        Step(
            step_type=StepType.CALL_TOOL,
            content="",
            tool_calls=[
                ToolCall(
                    id="1",
                    name="create_patch",
                    arguments={
                        "title": "Fix bug",
                        "description": "Fix",
                        "target_files": ["core/state.py"],
                        "plan": "# Plan",
                        "diff": "diff",
                        "tests": "tests",
                    },
                ),
            ],
            tool_results=None,
        ),
    ]
    
    judgment = judge.check_patch_discipline(steps)
    
    assert judgment.passed


def test_patch_discipline_project_file_write():
    """Test detecting direct project file writes."""
    judge = AgentJudge()
    
    # Agent tries to write project file directly
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="",
            tool_calls=[
                ToolCall(
                    id="1",
                    name="write_file",
                    arguments={
                        "path": "core/state.py",
                        "content": "new code",
                    },
                ),
            ],
            tool_results=None,
        ),
    ]
    
    judgment = judge.check_patch_discipline(steps)
    
    assert not judgment.passed
    assert "project files directly" in judgment.reason
    assert "create_patch" in judgment.suggestion


def test_patch_discipline_workspace_write_allowed():
    """Test that workspace writes are allowed."""
    judge = AgentJudge()
    
    # Agent writes to workspace (allowed)
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="",
            tool_calls=[
                ToolCall(
                    id="1",
                    name="write_file",
                    arguments={
                        "path": "workspace/test.py",
                        "content": "test code",
                    },
                ),
            ],
            tool_results=None,
        ),
    ]
    
    judgment = judge.check_patch_discipline(steps)
    
    assert judgment.passed


def test_patch_discipline_tmp_write_allowed():
    """Test that /tmp writes are allowed."""
    judge = AgentJudge()
    
    # Agent writes to tmp (allowed)
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="",
            tool_calls=[
                ToolCall(
                    id="1",
                    name="write_file",
                    arguments={
                        "path": "/tmp/test.py",
                        "content": "test code",
                    },
                ),
            ],
            tool_results=None,
        ),
    ]
    
    judgment = judge.check_patch_discipline(steps)
    
    assert judgment.passed


def test_patch_discipline_budget_without_test_request():
    """Test detecting tool budget exhaustion without test scheduling."""
    judge = AgentJudge()
    
    # Agent hits tool budget but doesn't mention tests
    steps = [
        Step(
            step_type=StepType.THINK,
            content="Tool budget exhausted, cannot run more tools",
            tool_calls=None,
            tool_results=None,
        ),
    ]
    
    judgment = judge.check_patch_discipline(steps)
    
    assert not judgment.passed
    assert "budget prevented tests" in judgment.reason
    assert "test" in judgment.suggestion.lower()


def test_patch_discipline_budget_with_test_request():
    """Test that mentioning tests satisfies discipline."""
    judge = AgentJudge()
    
    # Agent hits tool budget and mentions tests
    steps = [
        Step(
            step_type=StepType.THINK,
            content="Tool budget exhausted. I will run tests next step.",
            tool_calls=None,
            tool_results=None,
        ),
    ]
    
    judgment = judge.check_patch_discipline(steps)
    
    assert judgment.passed


def test_patch_discipline_no_issues():
    """Test that normal workflow passes all checks."""
    judge = AgentJudge()
    
    # Normal workflow: search, read, create patch
    steps = [
        Step(
            step_type=StepType.CALL_TOOL,
            content="",
            tool_calls=[
                ToolCall(
                    id="1",
                    name="search_chunks",
                    arguments={"query": "ToolRegistry"},
                ),
            ],
            tool_results=None,
        ),
        Step(
            step_type=StepType.OBSERVE,
            content="",
            tool_calls=None,
            tool_results=[
                ToolResult(
                    tool_call_id="1",
                    output="Found chunks...",
                    success=True,
                ),
            ],
        ),
        Step(
            step_type=StepType.CALL_TOOL,
            content="",
            tool_calls=[
                ToolCall(
                    id="2",
                    name="create_patch",
                    arguments={
                        "title": "Fix",
                        "description": "Fix",
                        "target_files": ["test.py"],
                        "plan": "plan",
                        "diff": "diff",
                        "tests": "tests",
                    },
                ),
            ],
            tool_results=None,
        ),
    ]
    
    judgment = judge.check_patch_discipline(steps)
    
    assert judgment.passed


if __name__ == "__main__":
    # Run tests
    test_patch_discipline_proposes_without_patch()
    print("✓ test_patch_discipline_proposes_without_patch")
    
    test_patch_discipline_creates_patch()
    print("✓ test_patch_discipline_creates_patch")
    
    test_patch_discipline_project_file_write()
    print("✓ test_patch_discipline_project_file_write")
    
    test_patch_discipline_workspace_write_allowed()
    print("✓ test_patch_discipline_workspace_write_allowed")
    
    test_patch_discipline_tmp_write_allowed()
    print("✓ test_patch_discipline_tmp_write_allowed")
    
    test_patch_discipline_budget_without_test_request()
    print("✓ test_patch_discipline_budget_without_test_request")
    
    test_patch_discipline_budget_with_test_request()
    print("✓ test_patch_discipline_budget_with_test_request")
    
    test_patch_discipline_no_issues()
    print("✓ test_patch_discipline_no_issues")
    
    print("\nAll Phase 0.7 judge tests passed!")
