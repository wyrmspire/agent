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
from typing import List, Optional
from dataclasses import dataclass

from core.types import Message, MessageRole, ToolCall, ToolResult, Step, StepType
from core.state import AgentState, ConversationState, ExecutionContext
from core.rules import RuleEngine
from gate.bases import ModelGateway
from tool.index import ToolRegistry

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
    ):
        self.gateway = gateway
        self.tools = tools
        self.rule_engine = rule_engine
        self.max_steps = max_steps
        self.temperature = temperature
    
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
        
        # Add user message
        state.conversation.add_message(Message(
            role=MessageRole.USER,
            content=user_message,
        ))
        
        # Run loop
        try:
            final_answer = await self._reasoning_loop(state)
            
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
    
    async def _reasoning_loop(self, state: AgentState) -> str:
        """Internal reasoning loop.
        
        Continues until:
        - Model provides final answer (no more tool calls)
        - Max steps reached
        - Error occurs
        
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
                
                # Execute tools
                tool_results = await self._execute_tools(state, response.tool_calls)
                
                # Add tool results to conversation
                for result in tool_results:
                    state.conversation.add_message(Message(
                        role=MessageRole.TOOL,
                        content=result.output if result.success else f"Error: {result.error}",
                        name=result.tool_call_id,
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
    ) -> List[ToolResult]:
        """Execute a list of tool calls.
        
        For each tool call:
        1. Validate with rule engine
        2. Look up tool in registry
        3. Execute tool
        4. Capture result
        
        Args:
            state: Current agent state
            tool_calls: List of tool calls from model
            
        Returns:
            List of tool results
        """
        results = []
        
        for tool_call in tool_calls:
            logger.info(f"Executing tool: {tool_call.name}")
            
            # Validate with rule engine
            is_allowed, violations = self.rule_engine.evaluate(tool_call)
            
            if not is_allowed:
                logger.warning(f"Tool call blocked: {violations[0].reason}")
                results.append(ToolResult(
                    tool_call_id=tool_call.id,
                    output="",
                    error=f"Tool call blocked: {violations[0].reason}",
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
                logger.info(f"Tool {tool_call.name} completed: success={result.success}")
                
                # Add step
                state.execution.add_step(Step(
                    step_type=StepType.OBSERVE,
                    content=result.output if result.success else result.error,
                    tool_results=[result],
                ))
                
                results.append(result)
            
            except Exception as e:
                logger.error(f"Tool execution error: {e}", exc_info=True)
                results.append(ToolResult(
                    tool_call_id=tool_call.id,
                    output="",
                    error=f"Execution error: {e}",
                    success=False,
                ))
        
        return results
