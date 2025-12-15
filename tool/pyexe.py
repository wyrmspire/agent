"""
tool/pyexe.py - Persistent Python REPL Tool

This module implements a persistent Python execution environment.
Unlike shell commands, this maintains state between executions (like a Jupyter notebook).

Responsibilities:
- Manage persistent Python subprocess
- Send code and receive output
- Keep variables alive between calls
- Handle timeouts and errors
- Ensure process isolation from model server

Rules:
- One subprocess per session
- Timeout protection for long-running code
- Capture stdout and stderr separately
- Clean error messages
- Process isolation (separate from server/api.py)

This tool transforms the agent from "run script" to "interactive data scientist."
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
import logging

from core.types import ToolResult
from core.sandb import Workspace, WorkspaceError, ResourceLimitError, get_default_workspace
from .bases import BaseTool, create_json_schema

logger = logging.getLogger(__name__)


class PythonReplTool(BaseTool):
    """Persistent Python REPL for stateful execution.
    
    This tool maintains a Python subprocess that keeps variables in memory.
    Critical for data science workflows where loading data takes time.
    
    Example workflow:
        1. pyexe: df = pd.read_csv('prices.csv')  # Load once
        2. pyexe: print(df.head())                 # Use loaded data
        3. pyexe: print(df.describe())             # Still has df in memory
    """
    
    def __init__(
        self,
        workspace: Optional[Workspace] = None,
        timeout: float = 180.0,  # Increased from 60s for large data loading
        session_id: Optional[str] = None,
    ):
        """Initialize Python REPL tool.
        
        Args:
            workspace: Workspace instance (uses default if None)
            timeout: Maximum execution time in seconds
            session_id: Unique session identifier for this REPL instance
        """
        self.workspace = workspace or get_default_workspace()
        self.timeout = timeout
        self.session_id = session_id or f"pyrepl_{int(time.time())}"
        self.process: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()  # Ensure only one execution at a time
    
    @property
    def name(self) -> str:
        return "pyexe"
    
    @property
    def description(self) -> str:
        return (
            "Execute Python code in a persistent session. Variables are kept in memory "
            "between calls. Use for data analysis, loading datasets, training models, etc. "
            f"Timeout: {self.timeout}s. Runs in isolated process (won't crash model server)."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
                "reset": {
                    "type": "boolean",
                    "description": "Reset session (clear all variables). Default: false",
                    "default": False,
                },
            },
            required=["code"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute Python code in persistent session."""
        code = arguments["code"]
        reset = arguments.get("reset", False)
        
        # Check resource limits before execution (circuit breaker)
        try:
            self.workspace.check_resources()
        except ResourceLimitError as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Resource limit exceeded: {e}",
                success=False,
            )
        
        async with self._lock:
            try:
                # Reset if requested
                if reset:
                    await self._stop_process()
                    logger.info(f"[{self.session_id}] Session reset")
                
                # Start process if not running
                if self.process is None or self.process.returncode is not None:
                    await self._start_process()
                
                # Execute code
                result = await self._execute_code(code)
                return result
            
            except asyncio.TimeoutError:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Execution timed out after {self.timeout}s. Consider breaking into smaller steps.",
                    success=False,
                )
            except Exception as e:
                logger.error(f"[{self.session_id}] Error executing code: {e}")
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Execution error: {e}",
                    success=False,
                )
    
    async def _start_process(self) -> None:
        """Start persistent Python subprocess."""
        logger.info(f"[{self.session_id}] Starting Python subprocess")
        
        # Prepare Python environment
        # Change to workspace directory so relative paths work
        cwd = str(self.workspace.root)
        
        # Create subprocess with Python interpreter
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",  # Unbuffered output
            "-c",
            self._get_repl_wrapper(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        
        logger.info(f"[{self.session_id}] Python subprocess started (PID: {self.process.pid})")
    
    async def _stop_process(self) -> None:
        """Stop Python subprocess."""
        if self.process and self.process.returncode is None:
            logger.info(f"[{self.session_id}] Stopping Python subprocess")
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"[{self.session_id}] Process didn't terminate, killing")
                self.process.kill()
                await self.process.wait()
            logger.info(f"[{self.session_id}] Python subprocess stopped")
    
    def _get_repl_wrapper(self) -> str:
        """Get Python wrapper code for REPL.
        
        This wrapper:
        1. Reads code from stdin
        2. Executes in persistent namespace
        3. Captures stdout/stderr
        4. Returns result with delimiter
        
        Returns:
            Python wrapper code as string
        """
        return """
import sys
import io
import traceback
import json

# Persistent namespace for variables
namespace = {}

# Main REPL loop
while True:
    try:
        # Read input (length-prefixed)
        line = sys.stdin.readline()
        if not line:
            break
        
        # Parse length and code
        try:
            length = int(line.strip())
            code = sys.stdin.read(length)
        except Exception as e:
            print(f"PYEXE_ERROR: Failed to read code: {e}", file=sys.stderr)
            continue
        
        # Capture output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        
        success = True
        error_msg = ""
        
        try:
            # Execute code in persistent namespace
            exec(code, namespace)
        except Exception:
            success = False
            error_msg = traceback.format_exc()
        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        # Get captured output
        stdout_text = stdout_capture.getvalue()
        stderr_text = stderr_capture.getvalue()
        
        # Send result as JSON (with delimiter)
        result = {
            "success": success,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "error": error_msg,
        }
        
        print("PYEXE_START", file=old_stdout, flush=True)
        print(json.dumps(result), file=old_stdout, flush=True)
        print("PYEXE_END", file=old_stdout, flush=True)
        
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"PYEXE_FATAL: {e}", file=sys.stderr, flush=True)
        break
"""
    
    async def _execute_code(self, code: str) -> ToolResult:
        """Execute code in subprocess.
        
        Args:
            code: Python code to execute
            
        Returns:
            ToolResult with output
        """
        if not self.process or self.process.stdin is None:
            raise RuntimeError("Process not started")
        
        logger.debug(f"[{self.session_id}] Executing code:\n{code}")
        
        # Send code with length prefix
        code_bytes = code.encode('utf-8')
        length_line = f"{len(code_bytes)}\n"
        
        self.process.stdin.write(length_line.encode('utf-8'))
        self.process.stdin.write(code_bytes)
        await self.process.stdin.drain()
        
        # Read output with timeout
        try:
            output = await asyncio.wait_for(
                self._read_result(),
                timeout=self.timeout,
            )
            return output
        except asyncio.TimeoutError:
            # Kill process if timeout
            logger.warning(f"[{self.session_id}] Execution timeout, killing process")
            await self._stop_process()
            raise
    
    async def _read_result(self) -> ToolResult:
        """Read execution result from subprocess.
        
        Returns:
            ToolResult with output
        """
        if not self.process or self.process.stdout is None:
            raise RuntimeError("Process not started")
        
        # Read until we find delimiters
        output_lines = []
        in_result = False
        
        while True:
            line = await self.process.stdout.readline()
            if not line:
                # Process died
                raise RuntimeError("Python subprocess terminated unexpectedly")
            
            line_text = line.decode('utf-8').rstrip()
            
            if line_text == "PYEXE_START":
                in_result = True
            elif line_text == "PYEXE_END":
                break
            elif in_result:
                output_lines.append(line_text)
        
        # Parse result JSON
        result_json = "\n".join(output_lines)
        try:
            import json
            result = json.loads(result_json)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.session_id}] Failed to parse result JSON: {e}")
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to parse execution result: {e}",
                success=False,
            )
        
        # Format output
        output_parts = []
        if result["stdout"]:
            output_parts.append(result["stdout"])
        if result["stderr"]:
            output_parts.append(f"STDERR:\n{result['stderr']}")
        
        output_text = "\n".join(output_parts) if output_parts else "(no output)"
        
        if result["success"]:
            return ToolResult(
                tool_call_id="",
                output=output_text,
                success=True,
            )
        else:
            return ToolResult(
                tool_call_id="",
                output=output_text,
                error=result["error"],
                success=False,
            )
    
    async def cleanup(self) -> None:
        """Clean up subprocess on tool destruction."""
        await self._stop_process()
    
    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        await self.cleanup()
        return False
