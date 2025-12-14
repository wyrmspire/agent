"""
tool/textr.py - Text Replacement Tool

This tool executes text replacements in files.
Originally prototyped in workspace/textr.py.

Responsibilities:
- Replace specific lines in files
- Validate file existence and line ranges
"""

from typing import Dict, Any
from pathlib import Path
from .bases import BaseTool
from core.types import ToolResult

class TextReplacementTool(BaseTool):
    @property
    def name(self) -> str:
        return "text_replace"

    @property
    def description(self) -> str:
        return "Replace a specific line in a file with new text."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to file"
                },
                "line_number": {
                    "type": "integer",
                    "description": "1-based line number"
                },
                "new_text": {
                    "type": "string",
                    "description": "New content for the line"
                }
            },
            "required": ["file_path", "line_number", "new_text"]
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        file_path = arguments["file_path"]
        line_num = arguments["line_number"]
        new_text = arguments["new_text"]
        
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(tool_call_id="", output="", error=f"File not found: {file_path}", success=False)
                
            lines = path.read_text().splitlines(keepends=True)
            if not (1 <= line_num <= len(lines)):
                 return ToolResult(tool_call_id="", output="", error=f"Line {line_num} out of range", success=False)
                 
            # Replace
            lines[line_num - 1] = new_text + ("\n" if not new_text.endswith("\n") else "")
            
            # Write back
            path.write_text("".join(lines))
            
            return ToolResult(
                tool_call_id="",
                output=f"Successfully replaced line {line_num} in {file_path}",
                success=True
            )
        except Exception as e:
            return ToolResult(tool_call_id="", output="", error=str(e), success=False)
