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
from typing import List, Optional
from dataclasses import dataclass

from core.types import Message, MessageRole, ToolCall, ToolResult, Step, StepType
from core.state import AgentState, ConversationState, ExecutionContext
from core.rules import RuleEngine
from core.trace import TraceLogger
from gate.bases import ModelGateway
from tool.index import ToolRegistry
from flow.judge import AgentJudge

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
        max_steps: int = 20,
        temperature: float = 0.7,
        enable_judge: bool = True,  # Phase 0.5: Judge guidance
    ):
        self.gateway = gateway
        self.tools = tools
        self.rule_engine = rule_engine
        self.max_steps = max_steps
        self.temperature = temperature
        self.judge = AgentJudge() if enable_judge else None
    
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
        """Internal reasoning loop.
        
        Continues until:
        - Model provides final answer (no more tool calls)
        - Max steps reached
        - Error occurs
        
        Args:
            state: Agent state
            tracer: TraceLogger instance for this run
        
        Returns:
            Final answer string
        """
        while state.execution.should_continue():
            step_num = state.execution.current_step + 1
            logger.info(f"Step {step_num}/{self.max_steps}")
            
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
                
                # Execute tools (with per-tool budget enforcement)
                tool_results, budget_hit = await self._execute_tools(state, response.tool_calls, tracer)
                
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
        
        # Max steps reached
        logger.warning(f"Max steps ({self.max_steps}) reached")
        return "I've reached the maximum number of reasoning steps. Please try a simpler request."
    
    async def _execute_tools(
        self,
        state: AgentState,
        tool_calls: List[ToolCall],
        tracer: TraceLogger,
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
            # Phase 0.5: Check budget BEFORE each tool (hard stop mid-batch)
            if not state.execution.can_use_tool():
                logger.warning(f"Budget exhausted mid-batch, skipping {tool_call.name} and remaining tools")
                budget_hit = True
                break  # Stop executing remaining tools
            
            logger.info(f"Executing tool: {tool_call.name}")
            
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
