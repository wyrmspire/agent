"""
tool/patch.py - Patch Creation Tool

This module implements a tool for creating patches via the workspace-first protocol.
Agents use this to propose changes without directly editing project files.

Responsibilities:
- Create patch proposals with plan, diff, and tests
- Validate proposed changes
- Generate apply commands for human review
- Track patch status

Rules:
- Agent MUST use this tool for all project file changes
- Agent CANNOT claim "fixed" until tests pass after apply
- All patches stored in workspace/patches/
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from core.types import ToolCall, ToolResult
from core.patch import PatchManager, PatchStatus, BlockedBy, create_tool_error, format_tool_error
from .bases import BaseTool

logger = logging.getLogger(__name__)


class CreatePatchTool(BaseTool):
    """Tool for creating patch proposals.
    
    Allows agent to:
    - Propose changes to project files via patches
    - Include plan, diff, and test instructions
    - Get apply commands for human review
    """
    
    def __init__(
        self,
        patch_manager: Optional[PatchManager] = None,
    ):
        """Initialize patch creation tool.
        
        Args:
            patch_manager: Optional custom patch manager
        """
        self.patch_manager = patch_manager or PatchManager()
    
    @property
    def name(self) -> str:
        return "create_patch"
    
    @property
    def description(self) -> str:
        return (
            "Create a patch proposal for project file changes. REQUIRED for all changes to "
            "project files (anything outside workspace/). Creates plan.md (what/why/where), "
            "patch.diff (unified diff), and tests.md (test instructions). "
            "Returns apply command for human review."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the patch (e.g., 'Fix tool budget bug')"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the change and why it's needed"
                },
                "target_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of files that will be modified"
                },
                "plan": {
                    "type": "string",
                    "description": "Plan content in Markdown (what changes, why, where)"
                },
                "diff": {
                    "type": "string",
                    "description": "Unified diff content (git diff format)"
                },
                "tests": {
                    "type": "string",
                    "description": "Test instructions in Markdown (what to run, expected output)"
                }
            },
            "required": ["title", "description", "target_files", "plan", "diff", "tests"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute patch creation.
        
        Args:
            arguments: Tool arguments with patch details
            
        Returns:
            ToolResult with patch ID and apply command
        """
        try:
            title = arguments.get("title")
            description = arguments.get("description")
            target_files = arguments.get("target_files", [])
            plan = arguments.get("plan")
            diff = arguments.get("diff")
            tests = arguments.get("tests")
            
            # Validate required fields
            if not all([title, description, plan, diff, tests]):
                error = create_tool_error(
                    blocked_by=BlockedBy.RULES,
                    error_code="PATCH_MISSING_FIELDS",
                    message="Missing required fields. Need: title, description, plan, diff, tests",
                )
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=format_tool_error(error),
                    success=False,
                )
            
            # Validate target_files is a list of strings (LLMs may send weird shapes)
            if not isinstance(target_files, list) or not all(isinstance(f, str) for f in target_files):
                error = create_tool_error(
                    blocked_by=BlockedBy.RULES,
                    error_code="PATCH_INVALID_TARGETS",
                    message="target_files must be a list of strings",
                )
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=format_tool_error(error),
                    success=False,
                )
            
            if not target_files:
                error = create_tool_error(
                    blocked_by=BlockedBy.RULES,
                    error_code="PATCH_NO_TARGETS",
                    message="No target files specified. Must list files to be modified",
                )
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=format_tool_error(error),
                    success=False,
                )
            
            # Create patch
            patch = self.patch_manager.create_patch(
                title=title,
                description=description,
                target_files=target_files,
                plan_content=plan,
                diff_content=diff,
                tests_content=tests,
            )
            
            # Validate patch
            is_valid, error_msg = self.patch_manager.validate_patch(patch.patch_id)
            
            if not is_valid:
                error = create_tool_error(
                    blocked_by=BlockedBy.RULES,
                    error_code="PATCH_INVALID",
                    message=f"Patch validation failed: {error_msg}",
                )
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=format_tool_error(error),
                    success=False,
                )
            
            # Generate apply command
            apply_cmd = self.patch_manager.generate_apply_command(patch.patch_id)
            
            # Important message constant
            PATCH_APPLY_WARNING = (
                "IMPORTANT: You CANNOT claim this is 'fixed' until:\n"
                "1. Human applies the patch\n"
                "2. Tests run successfully\n"
                "3. You verify the results\n"
            )
            
            # Format output
            output = f"✓ Created patch: {patch.patch_id}\n\n"
            output += f"Title: {patch.title}\n"
            output += f"Status: {patch.status}\n"
            output += f"Target files: {', '.join(patch.target_files)}\n\n"
            output += f"Patch artifacts:\n"
            output += f"- Plan: {patch.plan_file}\n"
            output += f"- Diff: {patch.diff_file}\n"
            output += f"- Tests: {patch.tests_file}\n\n"
            output += f"TO APPLY (human action required):\n"
            output += f"  {apply_cmd}\n\n"
            output += PATCH_APPLY_WARNING
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Patch creation error: {e}", exc_info=True)
            error = create_tool_error(
                blocked_by=BlockedBy.RUNTIME,
                error_code="PATCH_CREATION_FAILED",
                message=f"Failed to create patch: {e}",
            )
            return ToolResult(
                tool_call_id="",
                output="",
                error=format_tool_error(error),
                success=False,
            )


class ListPatchesTool(BaseTool):
    """Tool for listing existing patches."""
    
    def __init__(
        self,
        patch_manager: Optional[PatchManager] = None,
    ):
        """Initialize patch list tool.
        
        Args:
            patch_manager: Optional custom patch manager
        """
        self.patch_manager = patch_manager or PatchManager()
    
    @property
    def name(self) -> str:
        return "list_patches"
    
    @property
    def description(self) -> str:
        return "List all patch proposals with their status. Filter by status: proposed, applied, tested, failed, rejected"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["proposed", "applied", "tested", "failed", "rejected"],
                    "description": "Optional status filter"
                }
            }
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute patch listing.
        
        Args:
            arguments: Tool arguments with optional status filter
            
        Returns:
            ToolResult with patch list
        """
        try:
            status_filter = arguments.get("status")
            
            # Convert to PatchStatus enum if provided
            # Support both value ("applied") and name ("APPLIED") formats
            status_enum = None
            if status_filter:
                try:
                    # Try value first (e.g., "applied")
                    status_enum = PatchStatus(status_filter.lower())
                except ValueError:
                    try:
                        # Try name (e.g., "APPLIED")
                        status_enum = PatchStatus[status_filter.upper()]
                    except KeyError:
                        return ToolResult(
                            tool_call_id="",
                            output="",
                            error=f"Invalid status: {status_filter}. Valid: proposed, applied, tested, failed, rejected",
                            success=False,
                        )
            
            # List patches
            patches = self.patch_manager.list_patches(status=status_enum)
            
            if not patches:
                output = "No patches found"
                if status_filter:
                    output += f" with status '{status_filter}'"
            else:
                output = f"Found {len(patches)} patches"
                if status_filter:
                    output += f" with status '{status_filter}'"
                output += ":\n\n"
                
                for i, patch in enumerate(patches, 1):
                    output += f"[{i}] {patch.patch_id}\n"
                    output += f"    Title: {patch.title}\n"
                    output += f"    Status: {patch.status}\n"
                    output += f"    Created: {patch.created_at}\n"
                    output += f"    Targets: {', '.join(patch.target_files)}\n"
                    if patch.error_message:
                        output += f"    Error: {patch.error_message}\n"
                    output += "\n"
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Patch listing error: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to list patches: {e}",
                success=False,
            )


class GetPatchTool(BaseTool):
    """Tool for getting patch details."""
    
    def __init__(
        self,
        patch_manager: Optional[PatchManager] = None,
    ):
        """Initialize patch get tool.
        
        Args:
            patch_manager: Optional custom patch manager
        """
        self.patch_manager = patch_manager or PatchManager()
    
    @property
    def name(self) -> str:
        return "get_patch"
    
    @property
    def description(self) -> str:
        return "Get details of a specific patch by ID. Returns plan, diff preview, and test instructions"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "patch_id": {
                    "type": "string",
                    "description": "Patch identifier"
                }
            },
            "required": ["patch_id"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute patch retrieval.
        
        Args:
            arguments: Tool arguments with patch_id
            
        Returns:
            ToolResult with patch details
        """
        try:
            patch_id = arguments.get("patch_id")
            
            if not patch_id:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error="Missing required parameter: patch_id",
                    success=False,
                )
            
            # Get patch
            patch = self.patch_manager.get_patch(patch_id)
            
            if not patch:
                error = create_tool_error(
                    blocked_by=BlockedBy.MISSING,
                    error_code="PATCH_NOT_FOUND",
                    message=f"Patch not found: {patch_id}",
                )
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=format_tool_error(error),
                    success=False,
                )
            
            # Read files - anchor to workspace if paths are relative
            def read_patch_file(file_path: str) -> str:
                path = Path(file_path)
                if not path.is_absolute():
                    path = Path(self.patch_manager.workspace_dir) / path
                return path.read_text() if path.exists() else "N/A"
            
            plan = read_patch_file(patch.plan_file)
            diff = read_patch_file(patch.diff_file)
            tests = read_patch_file(patch.tests_file)
            
            # Format output
            output = f"Patch: {patch.patch_id}\n"
            output += f"Title: {patch.title}\n"
            output += f"Status: {patch.status}\n"
            output += f"Created: {patch.created_at}\n"
            output += f"Targets: {', '.join(patch.target_files)}\n\n"
            
            output += "=== PLAN ===\n"
            output += plan + "\n\n"
            
            output += "=== DIFF ===\n"
            # Show first 50 lines of diff
            diff_lines = diff.split("\n")
            if len(diff_lines) > 50:
                output += "\n".join(diff_lines[:50]) + "\n... (truncated)\n\n"
            else:
                output += diff + "\n\n"
            
            output += "=== TESTS ===\n"
            output += tests + "\n"
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Patch retrieval error: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to get patch: {e}",
                success=False,
            )
