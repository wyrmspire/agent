"""
flow/loops.py - Agent Loop Orchestration

This is the main agent loop that orchestrates reasoning:
1. Call model with conversation history
2. Detect if model wants to use a tool
3. Execute tool safely
4. Feed results back to model
5. Repeat until final answer or max turns

Two modes supported:
1. **Native tool-calls** - Use backend's function calling (best)
2. **Structured JSON** - Parse JSON tool calls as fallback

Docstrings emphasize: This is the smallest runnable path:
prompt → model → optional tool → final answer.

Rules:
- Max turns prevents infinite loops
- Always return a final answer
- Handle errors gracefully
- Never throw exceptions to caller
"""


import logging
import time
import json
from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from core.types import Message, MessageRole, ToolCall, ToolResult, Step, StepType
from core.state import AgentState, ConversationState, ExecutionContext
from core.rules import RuleEngine
from core.trace import TraceLogger
from core.taskqueue import TaskQueue, Checkpoint
from core.sandb import get_default_workspace
from gate.bases import ModelGateway
from tool.index import ToolRegistry
from flow.judge import AgentJudge
from flow.preflight import PreflightChecker, create_preflight_checker

logger = logging.getLogger(__name__)


@dataclass
class LoopResult:
    """Result of an agent loop execution.
    
    Attributes:
        success: Whether loop completed successfully
        final_answer: Final response to user
        steps_taken: Number of steps executed
        error: Optional error message
    """
    success: bool
    final_answer: str
    steps_taken: int
    error: Optional[str] = None


class AgentLoop:
    """Main agent loop orchestrator.
    
    This orchestrates the full agent reasoning cycle:
    - Receive user input
    - Call model (possibly multiple times)
    - Execute tools as needed
    - Return final answer
    
    The loop enforces:
    - Maximum turns (prevents infinite tool loops)
    - Safety rules (via RuleEngine)
    - Structured error handling
    """
    
    def __init__(
        self,
        gateway: ModelGateway,
        tools: ToolRegistry,
        rule_engine: RuleEngine,
        max_steps: int = 50,
        temperature: float = 0.7,
        enable_judge: bool = True,  # Phase 0.5: Judge guidance
    ):
        self.gateway = gateway
        self.tools = tools
        self.rule_engine = rule_engine
        self.max_steps = max_steps
        self.temperature = temperature
        self.judge = AgentJudge() if enable_judge else None
        
        # Phase A: Preflight and Circuit Breaker
        self.preflight = create_preflight_checker()
        
        # Phase 0.8B: Active Task Tracking
        self.workspace_root = Path(get_default_workspace().base_path)
        self.active_task_file = self.workspace_root / "queue" / "active_task.json"
        
    def _load_active_task(self) -> Optional[Dict[str, Any]]:
        """Load active task definition if present."""
        if self.active_task_file.exists():
            try:
                task_data = json.loads(self.active_task_file.read_text())
                logger.info(f"Loaded active task: {task_data.get('task_id')}")
                return task_data
            except Exception as e:
                logger.error(f"Failed to load active task: {e}")
        return None

    def _fail_active_task(self, task_data: Dict[str, Any], reason: str, state: AgentState) -> None:
        """Mark active task as failed directly via TaskQueue."""
        try:
            queue = TaskQueue(workspace_path=str(self.workspace_root))
            checkpoint = Checkpoint(
                task_id=task_data["task_id"],
                what_was_done=f"Task terminated by agent loop. {reason}",
                what_changed=[], # Could be enriched from state if tracked
                what_next="Handle failure or increase budget",
                blockers=[reason],
                citations=[],
                created_at=datetime.now(timezone.utc).isoformat()
            )
            # Mark failed and cleanup active_task.json (handled by queue.mark_failed in our updated logic)
            # Actually our updated queue.mark_failed does cleanup, but we should ensure it
            queue.mark_failed(task_data["task_id"], reason, checkpoint)
            
            # Explicitly ensure cleanup just in case
            if self.active_task_file.exists():
                active = json.loads(self.active_task_file.read_text())
                if active.get("task_id") == task_data["task_id"]:
                    self.active_task_file.unlink()
                    
        except Exception as e:
            logger.error(f"Failed to mark task failed: {e}")
    
    async def run(
        self,
        state: AgentState,
        user_message: str,
    ) -> LoopResult:
        """Run the agent loop for a user message.
        
        This is the main entry point. It:
        1. Adds user message to state
        2. Runs the reasoning loop
        3. Returns final answer
        
        Args:
            state: Current agent state
            user_message: User's input
            
        Returns:
            LoopResult with final answer and execution info
        """
        logger.info(f"Starting agent loop for message: {user_message[:50]}...")
        
        # Create tracer for this run (local to avoid concurrency issues)
        tracer = TraceLogger(state.execution.run_id)
        
        # Add user message
        state.conversation.add_message(Message(
            role=MessageRole.USER,
            content=user_message,
        ))
        
        # Run loop
        try:
            final_answer = await self._reasoning_loop(state, tracer)
            
            return LoopResult(
                success=True,
                final_answer=final_answer,
                steps_taken=state.execution.current_step,
            )
        
        except Exception as e:
            logger.error(f"Agent loop error: {e}", exc_info=True)
            return LoopResult(
                success=False,
                final_answer="I encountered an error and cannot complete the request.",
                steps_taken=state.execution.current_step,
                error=str(e),
            )
    
    async def _reasoning_loop(self, state: AgentState, tracer: TraceLogger) -> str:
        """Internal reasoning loop."""
        
        # Load active task to enforce budget
        active_task = self._load_active_task()
        task_budget = active_task.get("budget", {}) if active_task else {}
        
        # Counters
        # steps_used is tracked in state.execution.current_step (which persists across turns if state does)
        # tool_calls_used needs to be tracked. Since we restart the loop per run, 
        # we assume tool_calls_used for THIS run starting at 0, OR we would need to persist it.
        # For Phase 0.8B, we'll track for this session. Ideally this should be in state.
        tool_calls_used = 0
        
        max_tool_calls_limit = task_budget.get("max_tool_calls", 100) # Default high if no task
        max_steps_limit = task_budget.get("max_steps", self.max_steps)
        
        while state.execution.should_continue():
            # BUDGET ENFORCEMENT CHECK
            if active_task:
                # Check Steps
                if state.execution.current_step >= max_steps_limit:
                    reason = f"Step budget exhausted ({state.execution.current_step} >= {max_steps_limit})"
                    logger.warning(reason)
                    self._fail_active_task(active_task, "BUDGET_EXHAUSTED: " + reason, state)
                    return f"Task stopped: {reason}"
                
                # Check Tool Calls
                if tool_calls_used >= max_tool_calls_limit:
                     reason = f"Tool call budget exhausted ({tool_calls_used} >= {max_tool_calls_limit})"
                     logger.warning(reason)
                     self._fail_active_task(active_task, "BUDGET_EXHAUSTED: " + reason, state)
                     return f"Task stopped: {reason}"

            step_num = state.execution.current_step + 1
            logger.info(f"Step {step_num}/{max_steps_limit}")
            
            # Phase 2B: Learning enforcement - check if deadline passed
            if state.execution.learning_required_by_step is not None:
                if step_num >= state.execution.learning_required_by_step:
                    from flow.learning_nudge import format_pending_failures, create_playbook_template
                    failures_summary = format_pending_failures(state.execution.pending_failures)
                    template = ""
                    if state.execution.pending_failures:
                        template = create_playbook_template(state.execution.pending_failures[0])
                    
                    state.conversation.add_message(Message(
                        role=MessageRole.SYSTEM,
                        content=(
                            f"⚠️ LEARNING REQUIRED: You have pending failures that need reflection.\n\n"
                            f"{failures_summary}\n\n"
                            f"{template}\n"
                            f"Use log_mistake or memory(operation='learn') NOW before continuing."
                        ),
                    ))
                    logger.warning(f"Learning deadline passed at step {step_num}")
            
            # Phase 3: Periodic reflection trigger
            reflection_interval = state.execution.reflection_step_interval
            if step_num > 0 and step_num % reflection_interval == 0:
                logger.info(f"Reflection point at step {step_num}")
                state.conversation.add_message(Message(
                    role=MessageRole.SYSTEM,
                    content="🪞 REFLECTION POINT: You've completed several steps. Briefly summarize what you've accomplished and store it using memory(operation='reflect', content='...').",
                ))
            
            # Get tool definitions
            tool_defs = self.tools.get_tool_definitions() if self.tools.count > 0 else None
            
            # Call model
            response = await self.gateway.complete(
                messages=state.messages,
                tools=tool_defs,
                temperature=self.temperature,
            )
            
            # Add step
            state.execution.add_step(Step(
                step_type=StepType.THINK,
                content=response.content,
            ))
            
            # Check if model wants to use tools
            if response.tool_calls:
                logger.info(f"Model requested {len(response.tool_calls)} tool calls")
                
                # Phase 0.5: Check tool budget BEFORE executing batch
                if not state.execution.can_use_tool():
                    logger.warning(f"Tool budget exhausted before batch, step {step_num}")
                    # Add THINK step to prevent soft loop (forces step boundary)
                    state.execution.add_step(Step(
                        step_type=StepType.THINK,
                        content="Budget exhausted; summarizing progress and replanning.",
                    ))
                    state.conversation.add_message(Message(
                        role=MessageRole.SYSTEM,
                        content="⚠️ Tool budget exhausted. Summarize what you've learned and replan your next step.",
                    ))
                    continue
                
                # Phase B: Enhanced preflight check with intent tracking and alternatives
                mode = getattr(state.execution, 'mode', 'builder')
                model_output = response.content or ""  # For OVERRIDE detection
                preflight_result = self.preflight.check(
                    response.tool_calls, 
                    mode=mode,
                    model_output=model_output,
                )
                
                if not preflight_result.passed:
                    logger.warning(f"Preflight failed: {preflight_result.failures}")
                    # Inject failures as system message with alternatives
                    failure_msg = "\n\n".join(preflight_result.failures)
                    
                    # Check if forced plan mode (intent exhausted)
                    if preflight_result.forced_plan_mode:
                        state.conversation.add_message(Message(
                            role=MessageRole.SYSTEM,
                            content=(
                                f"🛑 FORCED PLAN MODE:\n{failure_msg}\n\n"
                                f"You MUST now output a text plan with:\n"
                                f"1. What failed and why\n"
                                f"2. What we know for certain\n"
                                f"3. Next minimal experiment to try\n"
                                f"4. Success criteria"
                            ),
                        ))
                    else:
                        state.conversation.add_message(Message(
                            role=MessageRole.SYSTEM,
                            content=f"🛑 PREFLIGHT BLOCKED:\n{failure_msg}",
                        ))
                    
                    # Add THINK step to force replanning
                    state.execution.add_step(Step(
                        step_type=StepType.THINK,
                        content=f"Preflight blocked: {failure_msg}",
                    ))
                    continue
                
                # Apply safe path rewrites before execution
                from flow.preflight import RewriteSafety
                for rewrite in preflight_result.rewrites:
                    if rewrite.safety == RewriteSafety.SAFE:
                        # Find the tool call and apply rewrite
                        for tc in response.tool_calls:
                            if tc.id == rewrite.tool_call_id:
                                old_val = tc.arguments.get(rewrite.argument_name, "")
                                tc.arguments[rewrite.argument_name] = rewrite.normalized
                                logger.info(
                                    f"AUTO-REWRITE {rewrite.argument_name}: "
                                    f"{rewrite.original} → {rewrite.normalized} "
                                    f"({rewrite.reason})"
                                )
                                break
                
                # Inject preflight warnings with alternatives
                if preflight_result.warnings:
                    warning_msg = "\n".join(f"⚠️ {w}" for w in preflight_result.warnings)
                    state.conversation.add_message(Message(
                        role=MessageRole.SYSTEM,
                        content=warning_msg,
                    ))
                    for warning in preflight_result.warnings:
                        logger.info(f"Preflight warning: {warning}")
                
                # Execute tools (with per-tool budget enforcement)
                # Pass incremented tool_calls_used to _execute_tools or update it after?
                # We need to update our local counter.
                tool_results, budget_hit = await self._execute_tools(state, response.tool_calls, tracer, active_task, tool_calls_used, max_tool_calls_limit)
                
                # Phase A: Record successes/failures in circuit breaker
                for i, result in enumerate(tool_results):
                    if i < len(response.tool_calls):
                        tc = response.tool_calls[i]
                        if result.success:
                            self.preflight.circuit_breaker.record_success(tc)
                        else:
                            self.preflight.circuit_breaker.record_failure(tc, result.error or "Unknown error")
                
                # Update usage
                tool_calls_used += len(tool_results)
                
                # If budget hit inside execution (the method handles hard stop), 
                # we might need to break immediately if it failed the task.
                if budget_hit and active_task:
                     # Re-check if we need provided hard stop
                     if tool_calls_used >= max_tool_calls_limit:
                         return "Task stopped: Tool call budget exhausted."
                
                # Print tool results to terminal for user visibility
                for i, result in enumerate(tool_results):
                    tool_name = response.tool_calls[i].name if i < len(response.tool_calls) else "unknown"
                    print(f"\n📦 [{tool_name}]")
                    if result.success:
                        # Truncate very long outputs for terminal display
                        output = result.output
                        if len(output) > 2000:
                            output = output[:2000] + f"\n... [truncated, {len(result.output)} chars total]"
                        print(output)
                    else:
                        print(f"❌ Error: {result.error}")
                
                # Add tool results to conversation
                for result in tool_results:
                    state.conversation.add_message(Message(
                        role=MessageRole.TOOL,
                        content=result.output if result.success else f"Error: {result.error}",
                        tool_call_id=result.tool_call_id,
                    ))
                
                # Phase 6: Error pattern detection and nudges
                for i, result in enumerate(tool_results):
                    if not result.success and result.error:
                        error_msg = result.error.lower()
                        nudge = None
                        
                        # Common pyexe errors
                        if "name 'true' is not defined" in error_msg:
                            nudge = "💡 HINT: Use Python's True/False, not JSON's true/false."
                        elif "name 'false' is not defined" in error_msg:
                            nudge = "💡 HINT: Use Python's True/False, not JSON's true/false."
                        elif "name 'null' is not defined" in error_msg or "name 'none' is not defined" in error_msg:
                            nudge = "💡 HINT: Use Python's None, not JSON's null."
                        elif "is not defined" in error_msg and "pyexe" in (response.tool_calls[i].name if i < len(response.tool_calls) else ""):
                            nudge = "💡 HINT: Each pyexe call is independent. Variables don't persist between calls. Re-import and re-load data."
                        elif "patch" in error_msg and "required" in error_msg:
                            nudge = "💡 HINT: create_patch needs 'file', 'plan', and 'diff' arguments. For workspace files, use write_file instead."
                        
                        if nudge:
                            logger.info(f"Error nudge: {nudge}")
                            state.conversation.add_message(Message(
                                role=MessageRole.SYSTEM,
                                content=nudge,
                            ))
                        
                        # Phase 2B: Track failure for learning enforcement
                        tc = response.tool_calls[i] if i < len(response.tool_calls) else None
                        if tc:
                            state.execution.pending_failures.append({
                                "tool": tc.name,
                                "error": result.error[:200] if result.error else "unknown",
                                "args": {k: str(v)[:50] for k, v in list(tc.arguments.items())[:3]},
                                "step": state.execution.current_step,
                            })
                            
                            # Set deadline: must reflect within 3 steps
                            if state.execution.learning_required_by_step is None:
                                deadline = state.execution.current_step + 3
                                state.execution.learning_required_by_step = deadline
                                logger.info(f"Learning deadline set: must learn by step {deadline}")
                                
                                # Get contextual learning prompt
                                from flow.learning_nudge import get_learning_prompt
                                from flow.preflight import CircuitBreakerState
                                error_class = CircuitBreakerState()._classify_error(result.error or "")
                                learning_prompt = get_learning_prompt(error_class, tc.name, result.error or "")
                                
                                state.conversation.add_message(Message(
                                    role=MessageRole.SYSTEM,
                                    content=f"{learning_prompt}\n\nYou have {3} steps to reflect on this.",
                                ))
                
                # Phase 3: Learning mode trigger
                # Check if memory search returned empty results
                for i, result in enumerate(tool_results):
                    if i < len(response.tool_calls):
                        tc = response.tool_calls[i]
                        if tc.name == "memory" and result.success:
                            if "No memories found" in result.output:
                                state.execution.heavy_learning_mode = True
                                state.execution.last_failed_query = tc.arguments.get("content", "")
                                logger.info(f"Learning mode triggered: no memories for '{state.execution.last_failed_query}'")
                                state.conversation.add_message(Message(
                                    role=MessageRole.SYSTEM,
                                    content=f"🧠 LEARNING MODE: No prior knowledge found for '{state.execution.last_failed_query[:50]}...'. After completing this task, use memory(operation='learn', content='...') to save what you figured out.",
                                ))
                            # Phase 4: Track learning for de-escalation
                            if tc.arguments.get("operation") == "learn" and "Learning stored" in result.output:
                                # Clear learning requirement - agent learned something!
                                state.execution.pending_failures.clear()
                                state.execution.learning_required_by_step = None
                                logger.info("Learning completed, cleared pending failures")
                                
                                # Mark learning as stored for de-escalation check
                                from gate.escalating import EscalatingGateway
                                if isinstance(self.gateway, EscalatingGateway):
                                    self.gateway.mark_learning_stored()
                        
                        # Also clear on log_mistake
                        if tc.name == "log_mistake" and result.success:
                            state.execution.pending_failures.clear()
                            state.execution.learning_required_by_step = None
                            logger.info("Mistake logged, cleared pending failures")
                
                # Phase 4: Escalation tracking
                from gate.escalating import EscalatingGateway
                if isinstance(self.gateway, EscalatingGateway):
                    # Count failures vs successes
                    for result in tool_results:
                        if result.success:
                            self.gateway.record_success()
                        else:
                            escalated = self.gateway.record_failure()
                            if escalated:
                                state.conversation.add_message(Message(
                                    role=MessageRole.SYSTEM,
                                    content=f"🔺 ESCALATED: Switching to {self.gateway.escalation.model}. You are now using a more powerful model. Solve this problem, then use memory(operation='learn', content='...') to save what you figured out for next time.",
                                ))
                    
                    # Check if we should de-escalate
                    if self.gateway.should_de_escalate():
                        self.gateway.de_escalate()
                        state.conversation.add_message(Message(
                            role=MessageRole.SYSTEM,
                            content=f"🔻 DE-ESCALATED: Learning captured. Switching back to {self.gateway.primary.model}.",
                        ))
                
                # If budget was hit mid-batch, inject guidance
                if budget_hit:
                    skipped_calls = response.tool_calls[len(tool_results):]
                    skipped = len(skipped_calls)
                    
                    # Phase 0.5 enhancement: Check if tests were skipped due to budget
                    # This gives a more actionable nudge than generic "budget hit"
                    test_keywords = ["pytest", "unittest", "npm test", "pnpm test", "yarn test", "go test"]
                    wrote_code = any(
                        tc.name in ["write_file", "edit_file", "create_file"]
                        for tc in response.tool_calls[:len(tool_results)]
                    )
                    tests_skipped = any(
                        tc.name == "shell" and 
                        any(kw in str(tc.arguments.get("cmd", "") or tc.arguments.get("command", "")).lower()
                            for kw in test_keywords)
                        for tc in skipped_calls
                    )
                    
                    if wrote_code and tests_skipped:
                        nudge = f"⚠️ Tests were skipped due to tool budget ({skipped} tool(s)). Run tests in the next step."
                    else:
                        nudge = f"⚠️ Tool budget hit mid-batch. {skipped} tool(s) skipped. Replan next step with remaining work."
                    
                    state.conversation.add_message(Message(
                        role=MessageRole.SYSTEM,
                        content=nudge,
                    ))
                
                # Phase 0.5: Check workflow discipline with judge
                if self.judge:
                    judgment = self.judge.check_workflow_discipline(state.execution.steps)
                    if not judgment.passed and judgment.suggestion:
                        logger.info(f"Judge guidance: {judgment.suggestion}")
                        # Add judge guidance to conversation to guide next step
                        state.conversation.add_message(Message(
                            role=MessageRole.SYSTEM,
                            content=f"⚠️ Workflow guidance: {judgment.suggestion}",
                        ))
                    
                    # Phase 0.7: Check patch discipline for project file changes
                    patch_judgment = self.judge.check_patch_discipline(state.execution.steps)
                    if not patch_judgment.passed and patch_judgment.suggestion:
                        logger.info(f"Patch discipline: {patch_judgment.suggestion}")
                        state.conversation.add_message(Message(
                            role=MessageRole.SYSTEM,
                            content=f"⚠️ Patch protocol: {patch_judgment.suggestion}",
                        ))
                
                # Continue loop to get final answer
                continue
            
            # No tool calls - this is the final answer
            state.conversation.add_message(Message(
                role=MessageRole.ASSISTANT,
                content=response.content,
            ))
            
            return response.content
        
        # Max steps reached - prompt to continue or cancel
        logger.warning(f"Max steps ({self.max_steps}) reached")
        print(f"\n{'='*60}")
        print(f"⏸️  PAUSED: Reached {self.max_steps} steps.")
        print(f"   Press ENTER to continue for another {self.max_steps} steps")
        print(f"   Press ESC or type 'quit' to stop")
        print(f"{'='*60}")
        
        try:
            import sys
            user_input = input("\n>>> ").strip().lower()
            if user_input in ('quit', 'q', 'exit', 'stop', 'cancel'):
                return "Task stopped by user at step limit."
            
            # User wants to continue - reset step counter and loop again
            logger.info(f"User continued past step limit")
            state.execution.current_step = 0
            return await self._reasoning_loop(state, tracer)
            
        except (KeyboardInterrupt, EOFError):
            return "Task cancelled by user."
    
    async def _execute_tools(
        self,
        state: AgentState,
        tool_calls: List[ToolCall],
        tracer: TraceLogger,
        active_task: Optional[Dict[str, Any]],
        current_tool_usage: int,
        max_tool_usage: int,
    ) -> tuple[List[ToolResult], bool]:
        """Execute a list of tool calls with per-tool budget enforcement.
        
        For each tool call:
        1. Check budget (hard stop if exhausted)
        2. Validate with rule engine
        3. Look up tool in registry
        4. Execute tool
        5. Capture result
        
        Args:
            state: Current agent state
            tool_calls: List of tool calls from model
            tracer: TraceLogger instance for this run
            
        Returns:
            Tuple of (list of tool results, whether budget was hit mid-batch)
        """
        results = []
        budget_hit = False
        
        for tool_call in tool_calls:
            # Global Budget Check for Active Task
            if active_task:
                 if current_tool_usage >= max_tool_usage:
                     reason = f"Tool call budget exhausted ({current_tool_usage} >= {max_tool_usage})"
                     logger.warning(reason)
                     self._fail_active_task(active_task, "BUDGET_EXHAUSTED: " + reason, state)
                     budget_hit = True
                     break
                
            # Phase 0.5: Check state-based budget (legacy)
            if not state.execution.can_use_tool():
                logger.warning(f"Budget exhausted mid-batch, skipping {tool_call.name} and remaining tools")
                budget_hit = True
                break  # Stop executing remaining tools
            
            logger.info(f"Executing tool: {tool_call.name}")
            
            # Increment usage for next check in loop
            current_tool_usage += 1
            
            # Trace: Log tool call initiation
            tracer.log_tool_call(tool_call)
            
            # Phase 0.5: Record tool use AFTER confirming budget allows it
            state.execution.record_tool_use()
            
            # Start timing
            start_time = time.perf_counter()
            
            # Validate with rule engine
            is_allowed, violations = self.rule_engine.evaluate(tool_call)
            
            if not is_allowed:
                logger.warning(f"Tool call blocked: {violations[0].reason}")
                results.append(ToolResult(
                    tool_call_id=tool_call.id,
                    output="",
                    error=f"Tool call blocked: {violations[0].reason} [blocked_by: {violations[0].blocked_by}]",
                    success=False,
                ))
                continue
            
            # Look up tool
            tool = self.tools.get(tool_call.name)
            
            if not tool:
                logger.error(f"Tool not found: {tool_call.name}")
                results.append(ToolResult(
                    tool_call_id=tool_call.id,
                    output="",
                    error=f"Tool '{tool_call.name}' not found",
                    success=False,
                ))
                continue
            
            # Execute tool
            try:
                result = await tool.call(tool_call)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"Tool {tool_call.name} completed: success={result.success}")
                
                # Trace: Log tool result
                tracer.log_tool_result(result, elapsed_ms, tool_call.name)
                
                # Add step
                state.execution.add_step(Step(
                    step_type=StepType.OBSERVE,
                    content=result.output if result.success else result.error,
                    tool_results=[result],
                ))
                
                # Phase 0.5: Judge tool result quality
                if self.judge:
                    judgment = self.judge.check_tool_result(result)
                    if not judgment.passed:
                        logger.warning(f"Tool result issue: {judgment.reason}")
                
                results.append(result)
            
            except Exception as e:
                logger.error(f"Tool execution error: {e}", exc_info=True)
                results.append(ToolResult(
                    tool_call_id=tool_call.id,
                    output="",
                    error=f"Execution error: {e}",
                    success=False,
                ))
        
        return results, budget_hit
