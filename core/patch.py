"""
core/patch.py - Patch Protocol for Workspace-First Engineering

This module implements the patch protocol where agents propose changes
via workspace artifacts (plan.md, patch.diff, tests.md) instead of
directly editing project files.

Responsibilities:
- Generate patch artifacts in workspace/patches/
- Create unified diffs for proposed changes
- Track patch lifecycle (proposed, applied, tested)
- Validate patches before apply

Rules:
- Agent never edits project files directly
- All changes go through workspace → patch → human review → apply
- Patches must include plan, diff, and test instructions
- Agent cannot claim "fixed" until tests pass after apply
"""

import logging
import subprocess
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class PatchStatus(Enum):
    """Status of a patch in its lifecycle."""
    PROPOSED = "proposed"  # Created but not applied
    APPLIED = "applied"    # Applied to codebase
    TESTED = "tested"      # Applied and tests passed
    FAILED = "failed"      # Tests failed after apply
    REJECTED = "rejected"  # Rejected by human review


class BlockedBy(Enum):
    """Categories for why an operation was blocked."""
    RULES = "rules"        # Safety rules prevent operation
    WORKSPACE = "workspace"  # Outside workspace boundary
    MISSING = "missing"    # File or resource doesn't exist
    RUNTIME = "runtime"    # Runtime error during execution
    PERMISSION = "permission"  # Permission denied


@dataclass
class PatchMetadata:
    """Metadata for a patch."""
    patch_id: str
    title: str
    created_at: str
    status: str
    plan_file: str
    diff_file: str
    tests_file: str
    target_files: List[str]
    description: str
    error_message: Optional[str] = None


@dataclass
class ToolError:
    """Standardized tool error with taxonomy."""
    blocked_by: str  # BlockedBy enum value
    error_code: str
    message: str
    context: Optional[Dict[str, Any]] = None


class PatchManager:
    """Manages patch protocol for workspace-first engineering.
    
    Enforces the rule that agents propose changes via patches in workspace,
    never editing project files directly.
    """
    
    def __init__(
        self,
        workspace_dir: str = "./workspace",
        patches_dir: Optional[str] = None,
    ):
        """Initialize patch manager.
        
        Args:
            workspace_dir: Root workspace directory
            patches_dir: Patch storage directory (defaults to workspace/patches)
        """
        self.workspace_dir = Path(workspace_dir)
        self.patches_dir = Path(patches_dir) if patches_dir else self.workspace_dir / "patches"
        
        # Create directories
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        
        # Track patches
        self.patches: Dict[str, PatchMetadata] = {}
        self._load_patches()
    
    def create_patch(
        self,
        title: str,
        description: str,
        target_files: List[str],
        plan_content: str,
        diff_content: str,
        tests_content: str,
    ) -> PatchMetadata:
        """Create a new patch with plan, diff, and tests.
        
        Args:
            title: Short title for the patch
            description: Detailed description
            target_files: List of files to be modified
            plan_content: Content for plan.md
            diff_content: Unified diff content
            tests_content: Test instructions
            
        Returns:
            PatchMetadata for the created patch
        """
        # Generate patch ID
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)
        patch_id = f"{timestamp}_{safe_title}"
        
        # Create patch directory
        patch_dir = self.patches_dir / patch_id
        patch_dir.mkdir(parents=True, exist_ok=True)
        
        # Write files
        plan_file = patch_dir / "plan.md"
        plan_file.write_text(plan_content)
        
        diff_file = patch_dir / "patch.diff"
        diff_file.write_text(diff_content)
        
        tests_file = patch_dir / "tests.md"
        tests_file.write_text(tests_content)
        
        # Create metadata
        metadata = PatchMetadata(
            patch_id=patch_id,
            title=title,
            created_at=datetime.utcnow().isoformat(),
            status=PatchStatus.PROPOSED.value,
            plan_file=str(plan_file),
            diff_file=str(diff_file),
            tests_file=str(tests_file),
            target_files=target_files,
            description=description,
        )
        
        # Save metadata
        metadata_file = patch_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(asdict(metadata), f, indent=2)
        
        # Track patch
        self.patches[patch_id] = metadata
        
        logger.info(f"Created patch: {patch_id}")
        return metadata
    
    def get_patch(self, patch_id: str) -> Optional[PatchMetadata]:
        """Get patch metadata by ID.
        
        Args:
            patch_id: Patch identifier
            
        Returns:
            PatchMetadata or None if not found
        """
        return self.patches.get(patch_id)
    
    def list_patches(
        self,
        status: Optional[PatchStatus] = None,
    ) -> List[PatchMetadata]:
        """List all patches, optionally filtered by status.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of PatchMetadata
        """
        patches = list(self.patches.values())
        
        if status:
            patches = [p for p in patches if p.status == status.value]
        
        # Sort by creation time (newest first)
        patches.sort(key=lambda p: p.created_at, reverse=True)
        
        return patches
    
    def update_status(
        self,
        patch_id: str,
        status: PatchStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update patch status.
        
        Args:
            patch_id: Patch identifier
            status: New status
            error_message: Optional error message for failed status
            
        Returns:
            True if updated successfully
        """
        if patch_id not in self.patches:
            logger.warning(f"Patch not found: {patch_id}")
            return False
        
        patch = self.patches[patch_id]
        patch.status = status.value
        patch.error_message = error_message
        
        # Save updated metadata
        patch_dir = self.patches_dir / patch_id
        metadata_file = patch_dir / "metadata.json"
        
        with open(metadata_file, "w") as f:
            json.dump(asdict(patch), f, indent=2)
        
        logger.info(f"Updated patch {patch_id} status to {status.value}")
        return True
    
    def validate_patch(self, patch_id: str) -> tuple[bool, Optional[str]]:
        """Validate patch before apply.
        
        Args:
            patch_id: Patch identifier
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if patch_id not in self.patches:
            return False, f"Patch not found: {patch_id}"
        
        patch = self.patches[patch_id]
        
        # Check all required files exist
        for file_path in [patch.plan_file, patch.diff_file, patch.tests_file]:
            if not Path(file_path).exists():
                return False, f"Missing required file: {file_path}"
        
        # Check diff is not empty
        diff_content = Path(patch.diff_file).read_text()
        if not diff_content.strip():
            return False, "Diff file is empty"
        
        # Check diff is valid unified diff format (allow various formats)
        # Valid diffs can start with: ---, diff, Index:, or have no header
        valid_starts = ["---", "diff", "index:", "@@"]
        has_valid_start = any(diff_content.lower().startswith(start) for start in valid_starts)
        has_diff_markers = "@@" in diff_content or "---" in diff_content
        
        if not has_valid_start and not has_diff_markers:
            return False, "Invalid diff format (must be unified diff with --- or @@ markers)"
        
        return True, None
    
    def generate_apply_command(self, patch_id: str) -> Optional[str]:
        """Generate command to apply patch.
        
        Args:
            patch_id: Patch identifier
            
        Returns:
            Shell command to apply patch, or None if invalid
        """
        if patch_id not in self.patches:
            return None
        
        patch = self.patches[patch_id]
        diff_file = Path(patch.diff_file)
        
        if not diff_file.exists():
            return None
        
        # Try to use relative path, fall back to absolute
        try:
            rel_path = diff_file.relative_to(Path.cwd())
            return f"git apply {rel_path}"
        except ValueError:
            # If not relative to cwd, use absolute path
            return f"git apply {diff_file.absolute()}"
    
    def _load_patches(self) -> None:
        """Load existing patches from disk."""
        if not self.patches_dir.exists():
            return
        
        for patch_dir in self.patches_dir.iterdir():
            if not patch_dir.is_dir():
                continue
            
            metadata_file = patch_dir / "metadata.json"
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, "r") as f:
                    data = json.load(f)
                
                patch = PatchMetadata(**data)
                self.patches[patch.patch_id] = patch
            
            except Exception as e:
                logger.error(f"Failed to load patch {patch_dir.name}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get patch statistics.
        
        Returns:
            Statistics about patches
        """
        status_counts = {}
        for patch in self.patches.values():
            status_counts[patch.status] = status_counts.get(patch.status, 0) + 1
        
        return {
            "total_patches": len(self.patches),
            "status_counts": status_counts,
            "patches_dir": str(self.patches_dir),
        }


def create_tool_error(
    blocked_by: BlockedBy,
    error_code: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> ToolError:
    """Create standardized tool error.
    
    Args:
        blocked_by: Category of blocking
        error_code: Specific error code
        message: Human-readable message
        context: Optional context information
        
    Returns:
        ToolError instance
    """
    return ToolError(
        blocked_by=blocked_by.value,
        error_code=error_code,
        message=message,
        context=context,
    )


def format_tool_error(error: ToolError) -> str:
    """Format tool error for display.
    
    Args:
        error: ToolError instance
        
    Returns:
        Formatted error string
    """
    output = f"ERROR [{error.error_code}]\n"
    output += f"Blocked by: {error.blocked_by}\n"
    output += f"Message: {error.message}\n"
    
    if error.context:
        output += f"Context: {json.dumps(error.context, indent=2)}\n"
    
    return output
