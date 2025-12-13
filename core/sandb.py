"""
core/sandb.py - Workspace Path Manager (Sandbox)

This module implements a path manager that enforces workspace isolation.
All file operations must occur within a designated workspace directory.

Responsibilities:
- Resolve and validate paths within workspace
- Block access to sensitive directories (.env, servr/, boot/)
- Provide safe path operations
- Ensure data stays in ./workspace/

Rules:
- All paths must be within ./workspace
- No access to source code directories
- No access to configuration files
- Paths are normalized and validated

This is the "jail" that keeps generated data separate from source code.
"""

import os
from pathlib import Path
from typing import Union, Optional


class WorkspaceError(Exception):
    """Exception raised when workspace rules are violated."""
    pass


class Workspace:
    """Workspace path manager that enforces directory isolation.
    
    This class ensures all file operations occur within a designated
    workspace directory, preventing access to source code and config files.
    
    Example:
        ws = Workspace("/home/user/agent/workspace")
        safe_path = ws.resolve("data/prices.csv")  # OK
        ws.resolve("../servr/api.py")  # Raises WorkspaceError
    """
    
    def __init__(self, workspace_root: Union[str, Path]):
        """Initialize workspace with root directory.
        
        Args:
            workspace_root: Root directory for workspace operations
        """
        self.root = Path(workspace_root).resolve()
        
        # Create workspace if it doesn't exist
        self.root.mkdir(parents=True, exist_ok=True)
        
        # Define blocked directories (relative to project root)
        project_root = self.root.parent
        self.blocked_dirs = [
            project_root / ".env",
            project_root / "servr",
            project_root / "boot",
            project_root / "core",
            project_root / "gate",
            project_root / "flow",
            project_root / "model",
        ]
        
        # Define blocked files
        self.blocked_files = [
            project_root / ".env",
            project_root / ".env.example",
            project_root / "requirements.txt",
        ]
    
    def resolve(self, path: Union[str, Path]) -> Path:
        """Resolve a path within the workspace.
        
        This method takes a relative or absolute path and:
        1. Resolves it to an absolute path
        2. Validates it's within the workspace
        3. Checks it doesn't access blocked directories
        
        Args:
            path: Path to resolve (relative to workspace or absolute)
            
        Returns:
            Resolved absolute path within workspace
            
        Raises:
            WorkspaceError: If path is outside workspace or blocked
        """
        # Convert to Path object
        if isinstance(path, str):
            path = Path(path)
        
        # If path is relative, make it relative to workspace root
        if not path.is_absolute():
            path = self.root / path
        
        # Resolve to absolute path (handles .. and symlinks)
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as e:
            raise WorkspaceError(f"Cannot resolve path: {e}")
        
        # Check if path is within workspace
        try:
            resolved.relative_to(self.root)
        except ValueError:
            raise WorkspaceError(
                f"Path '{path}' is outside workspace (must be within {self.root})"
            )
        
        # Check if path accesses blocked directories
        for blocked_dir in self.blocked_dirs:
            try:
                resolved.relative_to(blocked_dir)
                raise WorkspaceError(
                    f"Access to '{blocked_dir.name}/' is blocked for safety"
                )
            except ValueError:
                # Path is not under blocked_dir, which is good
                pass
        
        # Check if path is a blocked file
        if resolved in self.blocked_files:
            raise WorkspaceError(
                f"Access to '{resolved.name}' is blocked for safety"
            )
        
        return resolved
    
    def resolve_read(self, path: Union[str, Path]) -> Path:
        """Resolve a path for reading and verify it exists.
        
        Args:
            path: Path to resolve
            
        Returns:
            Resolved path
            
        Raises:
            WorkspaceError: If path is invalid or doesn't exist
        """
        resolved = self.resolve(path)
        
        if not resolved.exists():
            raise WorkspaceError(f"Path does not exist: {resolved}")
        
        return resolved
    
    def resolve_write(self, path: Union[str, Path], create_parents: bool = True) -> Path:
        """Resolve a path for writing and optionally create parent directories.
        
        Args:
            path: Path to resolve
            create_parents: Whether to create parent directories
            
        Returns:
            Resolved path
            
        Raises:
            WorkspaceError: If path is invalid
        """
        resolved = self.resolve(path)
        
        if create_parents:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        
        return resolved
    
    def list_contents(self, path: Optional[Union[str, Path]] = None) -> list[Path]:
        """List contents of a directory in the workspace.
        
        Args:
            path: Directory to list (relative to workspace), or None for root
            
        Returns:
            List of paths in directory
            
        Raises:
            WorkspaceError: If path is invalid or not a directory
        """
        if path is None:
            target = self.root
        else:
            target = self.resolve(path)
        
        if not target.is_dir():
            raise WorkspaceError(f"Path is not a directory: {target}")
        
        return sorted(target.iterdir())
    
    def get_relative_path(self, path: Union[str, Path]) -> Path:
        """Get path relative to workspace root.
        
        Args:
            path: Path to make relative
            
        Returns:
            Path relative to workspace root
            
        Raises:
            WorkspaceError: If path is invalid
        """
        resolved = self.resolve(path)
        return resolved.relative_to(self.root)
    
    def ensure_dir(self, path: Union[str, Path]) -> Path:
        """Ensure a directory exists within workspace.
        
        Args:
            path: Directory path to create
            
        Returns:
            Resolved directory path
            
        Raises:
            WorkspaceError: If path is invalid
        """
        resolved = self.resolve(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved


def get_default_workspace() -> Workspace:
    """Get the default workspace instance.
    
    This creates a workspace in ./workspace relative to the project root.
    
    Returns:
        Workspace instance
    """
    # Get project root (parent of core/)
    project_root = Path(__file__).parent.parent
    workspace_root = project_root / "workspace"
    
    return Workspace(workspace_root)
