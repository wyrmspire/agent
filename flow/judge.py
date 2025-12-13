"""
flow/judge.py - Verifier and Critic

This module implements verification and quality checking.
It can validate tool results and agent responses.

Responsibilities:
- Verify tool results are sensible
- Check if agent is making progress
- Detect loops or stuck states
- Quality check final answers

Rules:
- Judge doesn't execute, only evaluates
- Judgments are advisory, not blocking
- Keep judgments simple and fast
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

from core.types import Step, StepType, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class Judgment:
    """Result of a verification check.
    
    Attributes:
        passed: Whether the check passed
        reason: Explanation of the judgment
        severity: How serious (info, warning, error)
        suggestion: Optional suggestion for improvement
    """
    passed: bool
    reason: str
    severity: str = "info"
    suggestion: Optional[str] = None


class AgentJudge:
    """Verifier for agent execution quality.
    
    This watches the agent's execution and provides feedback:
    - Are tools being used effectively?
    - Is the agent making progress?
    - Are there issues to address?
    
    Phase 0.5: Enhanced with actionable "do this next" guidance.
    """
    
    def __init__(self):
        self.seen_tool_calls = set()
    
    def check_progress(self, steps: List[Step]) -> Judgment:
        """Check if agent is making progress.
        
        Args:
            steps: Execution steps so far
            
        Returns:
            Judgment on progress
        """
        if len(steps) == 0:
            return Judgment(
                passed=True,
                reason="Just started",
            )
        
        # Check for repeated failed tools
        recent_errors = [
            s for s in steps[-3:]
            if s.step_type == StepType.OBSERVE and s.tool_results
            and not s.tool_results[0].success
        ]
        
        if len(recent_errors) >= 2:
            return Judgment(
                passed=False,
                reason="Multiple tool failures in a row",
                severity="warning",
                suggestion="Consider trying a different approach",
            )
        
        return Judgment(
            passed=True,
            reason="Making progress",
        )
    
    def check_tool_loop(self, steps: List[Step]) -> Judgment:
        """Check for tool usage loops.
        
        Args:
            steps: Execution steps so far
            
        Returns:
            Judgment on whether agent is looping
        """
        # Look for same tool call repeated
        tool_names = []
        for step in steps:
            if step.tool_calls:
                for tc in step.tool_calls:
                    tool_names.append(tc.name)
        
        # Check last 3 tool calls
        if len(tool_names) >= 3:
            recent = tool_names[-3:]
            if len(set(recent)) == 1:
                return Judgment(
                    passed=False,
                    reason=f"Repeating same tool: {recent[0]}",
                    severity="warning",
                    suggestion="Try a different tool or approach",
                )
        
        return Judgment(
            passed=True,
            reason="No loops detected",
        )
    
    def check_tool_result(self, result: ToolResult) -> Judgment:
        """Check if a tool result is sensible.
        
        Args:
            result: Tool result to check
            
        Returns:
            Judgment on the result
        """
        if not result.success:
            return Judgment(
                passed=False,
                reason=f"Tool failed: {result.error}",
                severity="warning",
            )
        
        # Check for empty results
        if not result.output or result.output.strip() == "":
            return Judgment(
                passed=True,  # Not necessarily bad
                reason="Tool returned empty output",
                severity="info",
                suggestion="Verify this was expected",
            )
        
        return Judgment(
            passed=True,
            reason="Tool result looks good",
        )
    
    def check_final_answer(self, answer: str, steps: List[Step]) -> Judgment:
        """Check quality of final answer.
        
        Args:
            answer: Final answer to user
            steps: Steps taken to reach answer
            
        Returns:
            Judgment on answer quality
        """
        # Check if answer is too short
        if len(answer.strip()) < 10:
            return Judgment(
                passed=False,
                reason="Answer is very short",
                severity="warning",
                suggestion="Consider providing more detail",
            )
        
        # Check if tools were used but not mentioned
        tool_steps = [s for s in steps if s.step_type == StepType.OBSERVE]
        if tool_steps and "tool" not in answer.lower():
            return Judgment(
                passed=True,
                reason="Answer doesn't mention tool usage",
                severity="info",
                suggestion="Consider explaining how you used tools",
            )
        
        return Judgment(
            passed=True,
            reason="Answer quality looks good",
        )
    
    def check_workflow_discipline(self, steps: List[Step]) -> Judgment:
        """Check if agent followed tool-first workflow (Phase 0.5).
        
        Detects common anti-patterns:
        - Writing code without running tests
        - Calling shell repeatedly without reading errors
        - Not following list/read → write → test → summarize pattern
        
        Args:
            steps: Execution steps so far
            
        Returns:
            Judgment with actionable guidance
        """
        if len(steps) == 0:
            return Judgment(passed=True, reason="No steps yet")
        
        # Check: Did agent write code without running tests?
        write_tools = ["write_file", "edit_file", "create_file"]
        test_tools = ["shell"]  # Assumes tests run via shell
        
        has_write = False
        has_test_after_write = False
        write_step_idx = -1
        
        for i, step in enumerate(steps):
            if step.tool_calls:
                for tc in step.tool_calls:
                    if tc.name in write_tools:
                        has_write = True
                        write_step_idx = i
            
            # Check tool results in OBSERVE steps
            if step.step_type == StepType.OBSERVE and has_write and i > write_step_idx:
                if step.tool_results:
                    for result in step.tool_results:
                        result_text = (result.output or "") + (result.error or "")
                        if any(keyword in result_text.lower() 
                               for keyword in ["test", "pytest", "unittest"]):
                            has_test_after_write = True
        
        if has_write and not has_test_after_write:
            return Judgment(
                passed=False,
                reason="Code was written but tests were not run",
                severity="warning",
                suggestion="DO THIS NEXT: Run tests to verify your code changes work correctly.",
            )
        
        # Check: Repeated shell calls with errors?
        recent_shell_errors = []
        for step in steps[-5:]:  # Last 5 steps
            if step.step_type == StepType.OBSERVE and step.tool_results:
                for result in step.tool_results:
                    if not result.success and result.error:
                        recent_shell_errors.append(result.error)
        
        if len(recent_shell_errors) >= 2:
            return Judgment(
                passed=False,
                reason="Calling shell repeatedly without reading errors",
                severity="warning",
                suggestion=f"DO THIS NEXT: Read and analyze the error: {recent_shell_errors[-1][:100]}...",
            )
        
        return Judgment(
            passed=True,
            reason="Workflow discipline looks good",
        )
