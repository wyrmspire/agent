"""
core/trace.py - Tool-Call Traceability

This module provides structured, grep-able logging for tool calls.
Every tool execution can be traced via run_id and tool_call_id.

Responsibilities:
- Centralized trace logging format
- Consistent log structure for grep/search
- Timing information for performance analysis

Usage:
    tracer = TraceLogger(run_id="run_abc123")
    tracer.log_tool_call(tool_call)
    # ... execute tool ...
    tracer.log_tool_result(result, elapsed_ms=123.4)

Log Format:
    [run_id=X] [tool_call_id=Y] CALL Tool={name} Args={...}
    [run_id=X] [tool_call_id=Y] RESULT success={bool} elapsed={ms}ms
"""

import logging
import json
from typing import Dict, Any, Optional

from core.types import ToolCall, ToolResult

logger = logging.getLogger("agent.trace")


class TraceLogger:
    """Centralized tool-call tracing for debuggability.
    
    All tool calls go through this logger for consistent, grep-able output.
    """
    
    def __init__(self, run_id: str):
        """Initialize tracer with run ID.
        
        Args:
            run_id: Unique identifier for this agent run
        """
        self.run_id = run_id
    
    def log_tool_call(self, tool_call: ToolCall) -> None:
        """Log when a tool call is initiated.
        
        Format: [run_id=X] [tool_call_id=Y] CALL Tool={name} Args={...}
        
        Args:
            tool_call: The tool call being made
        """
        # Truncate large arguments for log readability
        args_str = self._format_args(tool_call.arguments)
        
        logger.info(
            f"[run_id={self.run_id}] [tool_call_id={tool_call.id}] "
            f"CALL Tool={tool_call.name} Args={args_str}"
        )
    
    def log_tool_result(
        self,
        result: ToolResult,
        elapsed_ms: float,
        tool_name: Optional[str] = None,
    ) -> None:
        """Log when a tool call completes.
        
        Format: [run_id=X] [tool_call_id=Y] RESULT success={bool} elapsed={ms}ms
        
        Args:
            result: The tool result
            elapsed_ms: Time taken in milliseconds
            tool_name: Optional tool name for context
        """
        status = "success" if result.success else "error"
        
        # Include error snippet if failed
        error_info = ""
        if not result.success and result.error:
            error_snippet = result.error[:100].replace('\n', ' ')
            error_info = f" error=\"{error_snippet}\""
        
        # Include output size if successful
        output_info = ""
        if result.success and result.output:
            output_info = f" output_len={len(result.output)}"
        
        tool_info = f" Tool={tool_name}" if tool_name else ""
        
        logger.info(
            f"[run_id={self.run_id}] [tool_call_id={result.tool_call_id}] "
            f"RESULT {status}{tool_info} elapsed={elapsed_ms:.1f}ms{output_info}{error_info}"
        )
    
    def log_budget_exhausted(self, skipped_tools: int) -> None:
        """Log when tool budget is exhausted.
        
        Args:
            skipped_tools: Number of tools that were skipped
        """
        logger.warning(
            f"[run_id={self.run_id}] BUDGET_EXHAUSTED skipped={skipped_tools} tools"
        )
    
    def log_step(self, step_num: int, max_steps: int, step_type: str) -> None:
        """Log agent step progression.
        
        Args:
            step_num: Current step number
            max_steps: Maximum steps allowed
            step_type: Type of step (THINK, OBSERVE, etc.)
        """
        logger.debug(
            f"[run_id={self.run_id}] STEP {step_num}/{max_steps} type={step_type}"
        )
    
    def _format_args(self, args: Dict[str, Any], max_len: int = 200) -> str:
        """Format arguments for logging, truncating if needed.
        
        Args:
            args: Tool arguments dict
            max_len: Maximum string length
            
        Returns:
            Formatted arguments string
        """
        try:
            args_json = json.dumps(args)
            if len(args_json) > max_len:
                return args_json[:max_len] + "..."
            return args_json
        except (TypeError, ValueError):
            return str(args)[:max_len]
