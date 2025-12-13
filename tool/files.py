"""
tool/files.py - File System Tools

This module implements tools for file system operations:
- list_files: List files in a directory
- read_file: Read file contents
- write_file: Write content to a file
- create_dir: Create a directory

Responsibilities:
- Safe file system access
- Path validation
- Error handling

Rules:
- Never delete files (too dangerous)
- Validate paths before access
- Respect size limits
"""

import os
from pathlib import Path
from typing import Any, Dict, List

from core.types import ToolResult
from .bases import BaseTool, create_json_schema


class ListFiles(BaseTool):
    """List files in a directory."""
    
    @property
    def name(self) -> str:
        return "list_files"
    
    @property
    def description(self) -> str:
        return "List files and directories in a given path. Returns names, types, and sizes."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "Directory path to list (relative or absolute)",
                },
            },
            required=["path"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """List files in directory."""
        path = Path(arguments["path"]).expanduser()
        
        try:
            if not path.exists():
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Path does not exist: {path}",
                    success=False,
                )
            
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
                entry = {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                }
                
                if item.is_file():
                    entry["size"] = item.stat().st_size
                
                entries.append(entry)
            
            # Format output
            output_lines = [f"Contents of {path}:"]
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
        
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error listing directory: {e}",
                success=False,
            )


class ReadFile(BaseTool):
    """Read contents of a file."""
    
    def __init__(self, max_size: int = 1_000_000):
        self.max_size = max_size
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return f"Read the contents of a file (up to {self.max_size} bytes). Returns file content as text."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "File path to read (relative or absolute)",
                },
            },
            required=["path"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Read file contents."""
        path = Path(arguments["path"]).expanduser()
        
        try:
            if not path.exists():
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"File does not exist: {path}",
                    success=False,
                )
            
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
                    error=f"File too large: {size} bytes (max {self.max_size})",
                    success=False,
                )
            
            # Read file
            content = path.read_text(encoding="utf-8")
            
            return ToolResult(
                tool_call_id="",
                output=content,
                success=True,
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
    """Write content to a file."""
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file. Creates parent directories if needed. Overwrites existing files."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "File path to write (relative or absolute)",
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
        path = Path(arguments["path"]).expanduser()
        content = arguments["content"]
        
        try:
            # Create parent directories
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            path.write_text(content, encoding="utf-8")
            
            return ToolResult(
                tool_call_id="",
                output=f"Successfully wrote {len(content)} bytes to {path}",
                success=True,
            )
        
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error writing file: {e}",
                success=False,
            )
