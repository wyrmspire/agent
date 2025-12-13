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
    """List files in a directory."""
    
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
        return "List files and directories. Shows project structure (read-only) and workspace/ folder (writable). Use '.' for project root."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Use '.' for project root. The workspace/ folder is writable, rest is read-only.",
                },
            },
            required=["path"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """List files in directory."""
        path_str = arguments["path"]
        
        try:
            # For listing, try PROJECT first (so agent sees project structure)
            # This way '.' shows the project root with flow/, core/, etc.
            try:
                path = self.workspace.resolve_project_read(path_str)
                is_project = True
            except WorkspaceError:
                # Fall back to workspace-only paths
                path = self.workspace.resolve_read(path_str)
                is_project = False
            
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
                    # Mark workspace as writable in project listings
                    if is_project and entry["name"] == "workspace":
                        output_lines.append(f"  📁 {entry['name']}/ [WRITABLE]")
                    else:
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
    """Read contents of a file within workspace with optional line ranges."""
    
    def __init__(
        self, 
        workspace: Optional[Workspace] = None, 
        max_size: int = 1_000_000,
        default_max_lines: int = 200,  # Default chunk size
    ):
        """Initialize with workspace.
        
        Args:
            workspace: Workspace instance (uses default if None)
            max_size: Maximum file size in bytes to read
            default_max_lines: Default max lines to return if no range specified
        """
        self.workspace = workspace or get_default_workspace()
        self.max_size = max_size
        self.default_max_lines = default_max_lines
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return (
            f"Read file contents. For large files, use start_line/end_line to read in chunks. "
            f"Without line range, returns first {self.default_max_lines} lines with total line count. "
            f"Can read workspace files (writable) and project files (read-only)."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "File path to read (relative to workspace or project root)",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Start line (1-indexed, inclusive). Use with end_line to read chunks.",
                },
                "end_line": {
                    "type": "integer",
                    "description": "End line (1-indexed, inclusive). Use with start_line to read chunks.",
                },
            },
            required=["path"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Read file contents, optionally by line range."""
        path_str = arguments["path"]
        start_line = arguments.get("start_line")
        end_line = arguments.get("end_line")
        
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
                    error=f"File too large: {size} bytes (max {self.max_size}). Use data_view tool.",
                    success=False,
                )
            
            # Read file as lines
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()
            total_lines = len(lines)
            
            # Determine line range to return
            if start_line is not None and end_line is not None:
                # User specified range (1-indexed)
                start_idx = max(0, start_line - 1)
                end_idx = min(total_lines, end_line)
                selected_lines = lines[start_idx:end_idx]
                range_info = f"[Lines {start_line}-{end_line} of {total_lines}]"
            elif start_line is not None:
                # Start line only - read to end or max
                start_idx = max(0, start_line - 1)
                end_idx = min(total_lines, start_idx + self.default_max_lines)
                selected_lines = lines[start_idx:end_idx]
                range_info = f"[Lines {start_line}-{end_idx} of {total_lines}]"
            else:
                # No range - return first N lines
                if total_lines <= self.default_max_lines:
                    selected_lines = lines
                    range_info = f"[{total_lines} lines total]"
                else:
                    selected_lines = lines[:self.default_max_lines]
                    range_info = f"[Lines 1-{self.default_max_lines} of {total_lines}. Use start_line/end_line for more.]"
            
            # Rebuild content from selected lines
            output_content = "\n".join(selected_lines)
            
            # Build header
            if is_project:
                try:
                    rel_path = path.relative_to(self.workspace.project_root)
                except ValueError:
                    rel_path = path
                header = f"[PROJECT READ-ONLY: {rel_path}] {range_info}\n{'='*60}\n"
            else:
                header = f"[{path.name}] {range_info}\n{'='*60}\n"
            
            return ToolResult(
                tool_call_id="",
                output=header + output_content,
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
        return "Write content to a file. Files are saved in the workspace/ folder (writable sandbox). Project files outside workspace/ are read-only."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "File path to write. Path will be created inside workspace/. Use 'myfile.txt' not 'workspace/myfile.txt'.",
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
        
        # Strip workspace/ prefix if agent includes it (they see it in project root listing)
        if path_str.startswith("workspace/"):
            path_str = path_str[len("workspace/"):]
        elif path_str.startswith("workspace\\"):
            path_str = path_str[len("workspace\\"):]
        
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
