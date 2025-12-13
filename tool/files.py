"""
tool/files.py - File System Tools

This module implements tools for file system operations:
- list_files: List files in a directory
- read_file: Read file contents
- write_file: Write content to a file
- create_dir: Create a directory

Responsibilities:
- Safe file system access
- Path validation within workspace
- Error handling
- Resource limit enforcement

Rules:
- Never delete files (too dangerous)
- All operations within workspace only
- Validate paths before access
- Respect size limits
- Check resource limits before writes
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.types import ToolResult
from core.sandb import Workspace, WorkspaceError, ResourceLimitError, get_default_workspace
from .bases import BaseTool, create_json_schema


class ListFiles(BaseTool):
    """List files in a directory within workspace."""
    
    def __init__(self, workspace: Optional[Workspace] = None):
        """Initialize with workspace.
        
        Args:
            workspace: Workspace instance (uses default if None)
        """
        self.workspace = workspace or get_default_workspace()
    
    @property
    def name(self) -> str:
        return "list_files"
    
    @property
    def description(self) -> str:
        return "List files and directories in a given path within workspace. Returns names, types, and sizes."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "Directory path to list (relative to workspace)",
                },
            },
            required=["path"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """List files in directory."""
        path_str = arguments["path"]
        
        try:
            # Try workspace first
            try:
                path = self.workspace.resolve_read(path_str)
                is_project = False
            except WorkspaceError:
                # Fall back to project read (read-only)
                path = self.workspace.resolve_project_read(path_str)
                is_project = True
            
            if not path.is_dir():
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Path is not a directory: {path}",
                    success=False,
                )
            
            # List entries
            entries = []
            for item in sorted(path.iterdir()):
                # Skip hidden files in project (like .git)
                if is_project and item.name.startswith('.'):
                    continue
                    
                entry = {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                }
                
                if item.is_file():
                    entry["size"] = item.stat().st_size
                
                entries.append(entry)
            
            # Format output
            if is_project:
                # For project paths, show relative to project root
                try:
                    rel_path = path.relative_to(self.workspace.project_root)
                except ValueError:
                    rel_path = path
                prefix = "[PROJECT READ-ONLY] "
            else:
                rel_path = self.workspace.get_relative_path(path)
                prefix = ""
            
            output_lines = [f"{prefix}Contents of {rel_path}:"]
            for entry in entries:
                if entry["type"] == "dir":
                    output_lines.append(f"  📁 {entry['name']}/")
                else:
                    size = entry.get("size", 0)
                    output_lines.append(f"  📄 {entry['name']} ({size} bytes)")
            
            return ToolResult(
                tool_call_id="",
                output="\n".join(output_lines),
                success=True,
            )
        
        except WorkspaceError as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=str(e),
                success=False,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error listing directory: {e}",
                success=False,
            )


class ReadFile(BaseTool):
    """Read contents of a file within workspace."""
    
    def __init__(self, workspace: Optional[Workspace] = None, max_size: int = 1_000_000):
        """Initialize with workspace.
        
        Args:
            workspace: Workspace instance (uses default if None)
            max_size: Maximum file size to read
        """
        self.workspace = workspace or get_default_workspace()
        self.max_size = max_size
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return f"Read the contents of a file (up to {self.max_size} bytes). Can read workspace files and project files (read-only)."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "File path to read (relative to workspace or project root)",
                },
            },
            required=["path"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Read file contents."""
        path_str = arguments["path"]
        
        try:
            # Try workspace first
            try:
                path = self.workspace.resolve_read(path_str)
                is_project = False
            except WorkspaceError:
                # Fall back to project read (read-only)
                path = self.workspace.resolve_project_read(path_str)
                is_project = True
            
            if not path.is_file():
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Path is not a file: {path}",
                    success=False,
                )
            
            # Check size
            size = path.stat().st_size
            if size > self.max_size:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"File too large: {size} bytes (max {self.max_size}). Use data view tool for large files.",
                    success=False,
                )
            
            # Read file
            content = path.read_text(encoding="utf-8")
            
            # Add header for project files
            if is_project:
                try:
                    rel_path = path.relative_to(self.workspace.project_root)
                except ValueError:
                    rel_path = path
                header = f"[PROJECT READ-ONLY: {rel_path}]\n{'='*60}\n"
                content = header + content
            
            return ToolResult(
                tool_call_id="",
                output=content,
                success=True,
            )
        
        except WorkspaceError as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=str(e),
                success=False,
            )
        except UnicodeDecodeError:
            return ToolResult(
                tool_call_id="",
                output="",
                error="File is not valid UTF-8 text",
                success=False,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error reading file: {e}",
                success=False,
            )


class WriteFile(BaseTool):
    """Write content to a file within workspace."""
    
    def __init__(self, workspace: Optional[Workspace] = None):
        """Initialize with workspace.
        
        Args:
            workspace: Workspace instance (uses default if None)
        """
        self.workspace = workspace or get_default_workspace()
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file within workspace. Creates parent directories if needed. Overwrites existing files. Checks resource limits before writing."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "File path to write (relative to workspace)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            required=["path", "content"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Write content to file."""
        path_str = arguments["path"]
        content = arguments["content"]
        
        try:
            # Check resource limits before writing (circuit breaker)
            try:
                self.workspace.check_resources()
            except ResourceLimitError as e:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Resource limit exceeded: {e}",
                    success=False,
                )
            
            # Resolve path within workspace (creates parent dirs)
            path = self.workspace.resolve_write(path_str, create_parents=True)
            
            # Write file
            path.write_text(content, encoding="utf-8")
            
            rel_path = self.workspace.get_relative_path(path)
            return ToolResult(
                tool_call_id="",
                output=f"Successfully wrote {len(content)} bytes to {rel_path}",
                success=True,
            )
        
        except WorkspaceError as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=str(e),
                success=False,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error writing file: {e}",
                success=False,
            )
