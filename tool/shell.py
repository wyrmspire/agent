"""
tool/shell.py - Shell Command Tool

This module implements a tool for running shell commands.
This is powerful but dangerous - must be used with safety rules.

Responsibilities:
- Execute shell commands safely
- Capture stdout and stderr
- Timeout protection
- Working directory control

Rules:
- ALWAYS use with rule engine
- Never allow arbitrary commands without validation
- Timeout after reasonable duration
- Capture both stdout and stderr
"""

import asyncio
from typing import Any, Dict

from core.types import ToolResult
from .bases import BaseTool, create_json_schema


class ShellTool(BaseTool):
    """Execute shell commands safely."""
    
    def __init__(self, timeout: float = 30.0, cwd: str = "."):
        self.timeout = timeout
        self.cwd = cwd
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return f"Execute a shell command. CWD: {self.cwd}. Timeout: {self.timeout}s."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
            },
            required=["command"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute shell command."""
        command = arguments["command"]
        cwd = arguments.get("cwd", self.cwd)
        
        try:
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                # Note: tool_call_id will be set by BaseTool.call()
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Command timed out after {self.timeout}s",
                    success=False,
                )
            
            # Decode output
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            
            # Combine output
            output_parts = []
            if stdout_text:
                output_parts.append(f"STDOUT:\n{stdout_text}")
            if stderr_text:
                output_parts.append(f"STDERR:\n{stderr_text}")
            
            output = "\n".join(output_parts) if output_parts else "(no output)"
            
            # Check return code
            success = process.returncode == 0
            error_message = None
            
            if not success:
                output += f"\n\nExit code: {process.returncode}"
                # IMPORTANT: Populate error field because AgentLoop uses result.error when success=False
                error_message = f"Command failed with exit code {process.returncode}. Output:\n{output}"
            
            return ToolResult(
                tool_call_id="",
                output=output,
                error=error_message,
                success=success,
            )
        
        except Exception as e:
            # Note: tool_call_id will be set by BaseTool.call()
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error executing command: {e}",
                success=False,
            )
