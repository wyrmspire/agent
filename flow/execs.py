"""
flow/execs.py - Tool Execution Utilities

This module provides utilities for safe tool execution.
It handles the runtime aspects of calling tools.

Responsibilities:
- Execute tools with timeouts
- Validate arguments before execution
- Convert exceptions to structured results
- Log execution details

Critical: Never throw raw exceptions up to the model call path.
Always convert to the standard result envelope.

Standard result envelope:
- ok: bool
- data: object | null  
- err: {code, message, detail} | null
"""

import logging
import asyncio
from typing import Any, Dict, Optional
from dataclasses import dataclass

from core.types import ToolCall, ToolResult
from tool.bases import BaseTool

logger = logging.getLogger(__name__)


@dataclass
class ExecutionConfig:
    """Configuration for tool execution.
    
    Attributes:
        timeout: Maximum execution time (seconds)
        log_args: Whether to log arguments
        log_results: Whether to log results
    """
    timeout: float = 30.0
    log_args: bool = True
    log_results: bool = True


class ToolExecutor:
    """Safe tool executor with timeouts and error handling.
    
    This wraps tool execution to ensure:
    - Timeouts are enforced
    - Errors are caught and converted to results
    - Execution is logged
    """
    
    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.config = config or ExecutionConfig()
    
    async def execute(
        self,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> ToolResult:
        """Execute a tool with safety guarantees.
        
        Args:
            tool: Tool to execute
            tool_call: Tool call parameters
            
        Returns:
            ToolResult (never raises exceptions)
        """
        # Log execution start
        if self.config.log_args:
            logger.info(f"Executing {tool.name} with args: {tool_call.arguments}")
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                tool.call(tool_call),
                timeout=self.config.timeout,
            )
            
            # Log result
            if self.config.log_results:
                if result.success:
                    logger.info(f"Tool {tool.name} succeeded")
                else:
                    logger.warning(f"Tool {tool.name} failed: {result.error}")
            
            return result
        
        except asyncio.TimeoutError:
            logger.error(f"Tool {tool.name} timed out after {self.config.timeout}s")
            return ToolResult(
                tool_call_id=tool_call.id,
                output="",
                error=f"Tool execution timed out after {self.config.timeout} seconds",
                success=False,
            )
        
        except Exception as e:
            logger.error(f"Tool {tool.name} raised exception: {e}", exc_info=True)
            return ToolResult(
                tool_call_id=tool_call.id,
                output="",
                error=f"Unexpected error: {str(e)}",
                success=False,
            )


def validate_tool_arguments(
    tool_call: ToolCall,
    expected_params: Dict[str, Any],
) -> tuple[bool, Optional[str]]:
    """Validate tool call arguments against schema.
    
    Args:
        tool_call: Tool call to validate
        expected_params: Expected parameter schema
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic validation: check required fields
    properties = expected_params.get("properties", {})
    required = expected_params.get("required", [])
    
    for field in required:
        if field not in tool_call.arguments:
            return False, f"Missing required parameter: {field}"
    
    # Type validation could go here
    # For now, just check presence of required fields
    
    return True, None


def create_error_result(
    tool_call_id: str,
    error_code: str,
    message: str,
    detail: Optional[str] = None,
) -> ToolResult:
    """Create a standardized error result.
    
    Args:
        tool_call_id: ID of the tool call
        error_code: Error code (e.g., "timeout", "validation_error")
        message: Human-readable error message
        detail: Optional detailed error info
        
    Returns:
        ToolResult with error
    """
    error_text = f"[{error_code}] {message}"
    if detail:
        error_text += f"\n\nDetails: {detail}"
    
    return ToolResult(
        tool_call_id=tool_call_id,
        output="",
        error=error_text,
        success=False,
    )
