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
        
        # Test command keywords to detect in shell arguments
        test_cmd_keywords = [
            "pytest", "python -m pytest", "python -m unittest", 
            "unittest", "npm test", "pnpm test", "yarn test",
            "go test", "cargo test", "mvn test", "gradle test",
        ]
        
        has_write = False
        has_test_after_write = False
        write_step_idx = -1
        
        for i, step in enumerate(steps):
            if step.tool_calls:
                for tc in step.tool_calls:
                    if tc.name in write_tools:
                        has_write = True
                        write_step_idx = i
                    
                    # Phase 0.5 fix: Detect tests via shell command ARGUMENTS, not output
                    # This is reliable even when pytest -q outputs minimal text
                    if tc.name == "shell" and has_write and i > write_step_idx:
                        # Check if command argument contains test keywords
                        cmd_arg = str(tc.arguments.get("command", "") or 
                                      tc.arguments.get("cmd", "") or 
                                      tc.arguments.get("args", "")).lower()
                        if any(keyword in cmd_arg for keyword in test_cmd_keywords):
                            has_test_after_write = True
            
            # Fallback: Also check tool results text in OBSERVE steps (for backwards compat)
            if step.step_type == StepType.OBSERVE and has_write and i > write_step_idx:
                if step.tool_results:
                    for result in step.tool_results:
                        result_text = ((result.output or "") + (result.error or "")).lower()
                        if any(keyword in result_text 
                               for keyword in ["pytest", "unittest", "test passed", "tests passed"]):
                            has_test_after_write = True
        
        if has_write and not has_test_after_write:
            return Judgment(
                passed=False,
                reason="Code was written but tests were not run",
                severity="warning",
                suggestion="DO THIS NEXT: Run tests to verify your code changes work correctly.",
            )
        
        # Check: Repeated shell calls with errors?
        # Phase 0.5 fix: Only count shell tool errors, not all tool errors
        # Track shell tool call IDs from CALL_TOOL steps, then match to OBSERVE results
        recent_shell_errors = []
        last_tool_was_shell = False
        
        for step in steps[-10:]:  # Last 10 steps to cover CALL_TOOL + OBSERVE pairs
            # Track if this step's tool calls include shell
            if step.tool_calls:
                for tc in step.tool_calls:
                    if tc.name == "shell":
                        last_tool_was_shell = True
                        break
                else:
                    last_tool_was_shell = False
            
            # If this is an OBSERVE step and last tool was shell, count errors
            if step.step_type == StepType.OBSERVE and step.tool_results:
                for result in step.tool_results:
                    if not result.success and result.error and last_tool_was_shell:
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
    
    def check_patch_discipline(self, steps: List[Step]) -> Judgment:
        """Check if agent followed patch protocol for project changes (Phase 0.7).
        
        Detects patch protocol violations:
        - Proposing changes without creating a patch
        - Writing to project files directly (outside workspace)
        - Not explaining why tests weren't run when budget prevented them
        
        NOTE: Patch protocol is ONLY for project files (outside workspace/).
        For workspace files, write_file is the correct tool - no patch needed.
        
        Args:
            steps: Execution steps so far
            
        Returns:
            Judgment with actionable guidance
        """
        if len(steps) == 0:
            return Judgment(passed=True, reason="No steps yet")
        
        # Check: Did agent propose changes without creating a patch?
        proposes_change = False
        has_create_patch = False
        target_is_workspace = False
        
        # Keywords that indicate proposing changes
        propose_keywords = [
            "fix for", "change to", "modify", "update", "patch for",
            "i will fix", "i'll fix", "i can fix", "let me fix",
            "i've fixed", "i have fixed", "fixed the",
        ]
        
        for step in steps:
            # Check content for change proposals
            if step.content:
                content_lower = step.content.lower()
                if any(keyword in content_lower for keyword in propose_keywords):
                    proposes_change = True
                    # Check if the proposed change is for workspace files
                    if "workspace/" in content_lower or "workspace\\" in content_lower:
                        target_is_workspace = True
            
            # Check if patch was created OR if write_file was used for workspace
            if step.tool_calls:
                for tc in step.tool_calls:
                    if tc.name == "create_patch":
                        has_create_patch = True
                    # If write_file targets workspace, that's fine - no patch needed
                    if tc.name == "write_file":
                        path = str(tc.arguments.get("path", "") or tc.arguments.get("file_path", ""))
                        if "workspace" in path.lower():
                            target_is_workspace = True
        
        # Only enforce patch discipline for NON-workspace files
        if proposes_change and not has_create_patch and not target_is_workspace:
            return Judgment(
                passed=False,
                reason="Proposed changes to project files without creating a patch",
                severity="warning",
                suggestion="DO THIS NEXT: Use create_patch tool to propose changes via patch protocol.",
            )

        
        # Check: Did agent try to write to project files directly?
        write_tools = ["write_file"]
        project_file_writes = []
        
        for step in steps:
            if step.tool_calls:
                for tc in step.tool_calls:
                    if tc.name in write_tools:
                        # Check if target is outside workspace
                        path_str = tc.arguments.get("path", "") or tc.arguments.get("file_path", "")
                        if path_str:
                            from pathlib import Path
                            import os
                            
                            try:
                                # Resolve path to catch traversal attempts
                                path = Path(path_str).resolve()
                                workspace_path = Path("workspace").resolve()
                                tmp_path = Path("/tmp").resolve()
                                
                                # Check if path is under workspace or /tmp
                                try:
                                    path.relative_to(workspace_path)
                                    # Path is under workspace, allowed
                                except ValueError:
                                    # Not under workspace, check if under /tmp
                                    try:
                                        path.relative_to(tmp_path)
                                        # Path is under /tmp, allowed
                                    except ValueError:
                                        # Not under workspace or /tmp, block it
                                        project_file_writes.append(path_str)
                            except (OSError, ValueError):
                                # Path resolution failed, treat as suspicious
                                project_file_writes.append(path_str)
        
        if project_file_writes:
            return Judgment(
                passed=False,
                reason=f"Attempted to write project files directly: {project_file_writes[0]}",
                severity="error",
                suggestion="DO THIS NEXT: Use create_patch tool instead. Never edit project files directly.",
            )
        
        # Check: Tool budget prevented tests, did agent ask for tests next step?
        hit_tool_budget = False
        asked_for_tests = False
        
        for step in steps[-5:]:  # Check last 5 steps
            # Check for budget exhaustion content (must mention exhaustion/exceeded/prevented)
            if step.content:
                content_lower = step.content.lower()
                if "tool budget" in content_lower and any(word in content_lower for word in ["exhaust", "exceed", "prevent", "limit", "cannot"]):
                    hit_tool_budget = True
            
            # Check if agent mentioned running tests next
            if step.content:
                content_lower = step.content.lower()
                if any(phrase in content_lower for phrase in ["test next", "run tests next", "need to test", "should test"]):
                    asked_for_tests = True
        
        if hit_tool_budget and not asked_for_tests:
            return Judgment(
                passed=False,
                reason="Tool budget prevented tests, but agent didn't schedule tests for next step",
                severity="warning",
                suggestion="DO THIS NEXT: Explain that tests should be run in the next step after budget resets.",
            )
        
        return Judgment(
            passed=True,
            reason="Patch discipline looks good",
        )
