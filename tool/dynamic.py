"""
tool/dynamic.py - Dynamic Tool Wrapper

This module implements a wrapper for dynamically loaded skills.
Dynamic tools execute in a safe pyexe subprocess to prevent crashes.

Responsibilities:
- Wrap skill functions as tools
- Execute via pyexe for safety
- Handle serialization of arguments and results
- Provide clean error messages

Rules:
- Never execute skill code in main process
- Always use pyexe subprocess
- Serialize arguments as JSON
- Parse results from stdout
"""

import json
import logging
from typing import Dict, Any, Optional

from core.types import ToolResult
from core.skills import FunctionInfo
from .bases import BaseTool
from .pyexe import PythonReplTool

logger = logging.getLogger(__name__)


class DynamicTool(BaseTool):
    """A tool that wraps a dynamically loaded Python function.
    
    Executes the function in a safe pyexe subprocess.
    """
    
    def __init__(
        self,
        func_info: FunctionInfo,
        skill_file: str,
        pyexe: Optional[PythonReplTool] = None,
    ):
        """Initialize dynamic tool.
        
        Args:
            func_info: Function information from compiler
            skill_file: Path to skill file
            pyexe: Optional PythonReplTool instance (creates new if None)
        """
        self._func_info = func_info
        self._skill_file = skill_file
        self._pyexe = pyexe or PythonReplTool()
    
    @property
    def name(self) -> str:
        return self._func_info.name
    
    @property
    def description(self) -> str:
        return self._func_info.description
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return self._func_info.parameters
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the skill function via pyexe.
        
        Args:
            arguments: Function arguments
            
        Returns:
            ToolResult with function output
        """
        try:
            # Build Python code to execute the function
            code = self._build_execution_code(arguments)
            
            # Execute via pyexe
            from core.types import ToolCall
            pyexe_call = ToolCall(
                id="dynamic_exec",
                name="pyexe",
                arguments={
                    "code": code,
                    "reset": False,  # Keep session for efficiency
                }
            )
            
            result = await self._pyexe.call(pyexe_call)
            
            if not result.success:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Skill execution failed: {result.error}",
                    success=False,
                )
            
            # Parse result from output
            output = result.output
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Dynamic tool execution error: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Execution error: {e}",
                success=False,
            )
    
    def _build_execution_code(self, arguments: Dict[str, Any]) -> str:
        """Build Python code to execute the skill function.
        
        Args:
            arguments: Function arguments
            
        Returns:
            Python code as string
        """
        # Read the skill file
        with open(self._skill_file, 'r') as f:
            skill_code = f.read()
        
        # Build argument string
        arg_parts = []
        for key, value in arguments.items():
            # Serialize value as JSON for safety
            if isinstance(value, str):
                arg_parts.append(f"{key}={json.dumps(value)}")
            elif isinstance(value, (int, float, bool)):
                arg_parts.append(f"{key}={value}")
            elif isinstance(value, (list, dict)):
                arg_parts.append(f"{key}={json.dumps(value)}")
            else:
                arg_parts.append(f"{key}={json.dumps(str(value))}")
        
        args_str = ", ".join(arg_parts)
        
        # Build complete code
        code = f"""
# Load skill function
{skill_code}

# Execute function
try:
    result = {self._func_info.name}({args_str})
    print(f"Result: {{result}}")
except Exception as e:
    print(f"Error executing skill: {{e}}")
    import traceback
    traceback.print_exc()
"""
        
        return code
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about this dynamic tool.
        
        Returns:
            Dict with tool metadata
        """
        return {
            "name": self.name,
            "description": self.description,
            "skill_file": self._skill_file,
            "is_dynamic": True,
        }
