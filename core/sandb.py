"""
core/sandb.py - Workspace Path Manager (Sandbox)

This module implements a path manager that enforces workspace isolation.
All file operations must occur within a designated workspace directory.

Responsibilities:
- Resolve and validate paths within workspace
- Block access to sensitive directories (.env, servr/, boot/)
- Provide safe path operations
- Ensure data stays in ./workspace/
- Monitor resource usage (disk space, RAM)

Rules:
- All paths must be within ./workspace
- No access to source code directories
- No access to configuration files
- Paths are normalized and validated
- Enforce resource limits to prevent system crashes

This is the "jail" that keeps generated data separate from source code.
"""

import os
import psutil
from pathlib import Path
from typing import Union, Optional


class WorkspaceError(Exception):
    """Exception raised when workspace rules are violated."""
    pass


class ResourceLimitError(WorkspaceError):
    """Exception raised when resource limits are exceeded."""
    pass


class Workspace:
    """Workspace path manager that enforces directory isolation.
    
    This class ensures all file operations occur within a designated
    workspace directory, preventing access to source code and config files.
    It also monitors resource usage to prevent system crashes.
    
    Read-only project access:
        The agent can READ files from the project root but can only WRITE
        to the workspace directory. Sensitive files (.env, secrets) are blocked.
    
    Standard bins (Phase 1.5):
        workspace/repos/   - Cloned repositories
        workspace/runs/    - Run outputs by run_id
        workspace/notes/   - Human-readable summaries
        workspace/patches/ - Patch protocol files
        workspace/data/    - Data files for analysis
        workspace/queue/   - Task queue (auto-managed)
        workspace/chunks/  - Chunk index (auto-managed)
    
    Example:
        ws = Workspace("/home/user/agent/workspace")
        safe_path = ws.resolve("data/prices.csv")  # OK - workspace
        ws.resolve_project_read("flow/loops.py")   # OK - read-only project
        ws.resolve("../servr/api.py")  # Raises WorkspaceError
    """
    
    # Standard workspace bins (Phase 1.5)
    STANDARD_BINS = {
        "repos": "Cloned repositories",
        "runs": "Run outputs organized by run_id",
        "notes": "Human-readable summaries and analysis",
        "patches": "Patch protocol files",
        "data": "Data files for analysis",
        "queue": "Task queue files (auto-managed)",
        "chunks": "Chunk index files (auto-managed)",
    }
    
    def __init__(
        self,
        workspace_root: Union[str, Path],
        max_workspace_size_gb: float = 5.0,
        min_free_ram_percent: float = 10.0,
        allow_project_read: bool = True,
        create_standard_bins: bool = True,
    ):
        """Initialize workspace with root directory and resource limits.
        
        Args:
            workspace_root: Root directory for workspace operations
            max_workspace_size_gb: Maximum workspace size in GB (default: 5GB)
            min_free_ram_percent: Minimum free RAM percentage (default: 10%)
            allow_project_read: Allow read-only access to project files (default: True)
            create_standard_bins: Create standard bin directories (default: True)
        """
        self.root = Path(workspace_root).resolve()
        self.max_workspace_size_bytes = int(max_workspace_size_gb * 1024 * 1024 * 1024)
        self.min_free_ram_percent = min_free_ram_percent
        self.allow_project_read = allow_project_read
        
        # Create workspace if it doesn't exist
        self.root.mkdir(parents=True, exist_ok=True)
        
        # Create standard bins (Phase 1.5)
        if create_standard_bins:
            for bin_name in self.STANDARD_BINS:
                (self.root / bin_name).mkdir(exist_ok=True)
        
        # Project root is parent of workspace
        self._project_root = self.root.parent
        
        # Sensitive files that are NEVER readable (even with project read enabled)
        self.sensitive_patterns = [
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            "*secret*",
            "*credentials*",
            ".git/",
        ]
        
        # Directories blocked for WRITE operations (relative to project root)
        self.blocked_write_dirs = [
            self._project_root / "servr",
            self._project_root / "boot",
            self._project_root / "core",
            self._project_root / "gate",
            self._project_root / "flow",
            self._project_root / "model",
            self._project_root / "tool",
            # self._project_root / "tests", # Unblocked for agent test creation
        ]
        
        # Files blocked from any access
        self.blocked_files = [
            self._project_root / ".env",
            self._project_root / ".env.example",
            self._project_root / ".env.local",
        ]
    
    @property
    def project_root(self) -> Path:
        """Get the project root directory (parent of workspace)."""
        return self._project_root
    
    def get_run_dir(self, run_id: str) -> Path:
        """Get or create a run-specific output directory.
        
        Args:
            run_id: Unique run identifier
            
        Returns:
            Path to the run directory (created if needed)
        """
        run_dir = self.root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    
    def validate_path_in_bin(self, path: Path) -> Optional[str]:
        """Check if a path is in a standard bin.
        
        Args:
            path: Path to check
            
        Returns:
            Bin name if path is in a standard bin, None otherwise
        """
        try:
            # Make path absolute and resolve
            if not path.is_absolute():
                path = self.root / path
            resolved = path.resolve()
            
            # Get path relative to workspace
            rel = resolved.relative_to(self.root)
            first_part = rel.parts[0] if rel.parts else None
            
            if first_part in self.STANDARD_BINS:
                return first_part
            return None
        except ValueError:
            return None
    
    @property
    def base_path(self) -> Path:
        """Get the base path of the workspace (alias for root)."""
        return self.root
    
    def _normalize_path(self, p: Path) -> Path:
        """Normalize path for cross-platform comparison.
        
        Resolves symlinks, normalizes case on Windows, and converts to absolute.
        This ensures consistent comparison regardless of slash direction or case.
        """
        resolved = p.resolve()
        # On Windows, normalize case for comparison
        if os.name == 'nt':
            return Path(os.path.normcase(str(resolved)))
        return resolved
    
    def _strip_workspace_prefix(self, path_str: str) -> str:
        """Strip workspace/ prefix if agent included it.
        
        The agent sees 'workspace/' in project listings and may include it.
        """
        if path_str.startswith("workspace/"):
            return path_str[len("workspace/"):]
        elif path_str.startswith("workspace\\"):
            return path_str[len("workspace\\"):]
        return path_str
    
    def _is_sensitive_file(self, path: Path) -> bool:
        """Check if a file matches sensitive patterns."""
        name = path.name.lower()
        path_str = str(path).lower()
        
        for pattern in self.sensitive_patterns:
            if pattern.startswith("*") and pattern.endswith("*"):
                # Contains pattern
                if pattern[1:-1] in name:
                    return True
            elif pattern.startswith("*"):
                # Ends with pattern
                if name.endswith(pattern[1:]):
                    return True
            elif pattern.endswith("*"):
                # Starts with pattern
                if name.startswith(pattern[:-1]):
                    return True
            elif pattern.endswith("/"):
                # Directory pattern
                if f"/{pattern}" in path_str or path_str.endswith(pattern[:-1]):
                    return True
            else:
                # Exact match
                if name == pattern:
                    return True
        
        return False
    
    @property
    def base_path(self) -> Path:
        """Get the base path of the workspace (alias for root)."""
        return self.root
    
    def resolve(self, path: Union[str, Path]) -> Path:
        """Resolve a path within the workspace.
        
        This method takes a relative or absolute path and:
        1. Strips workspace/ prefix if present (agent may include it)
        2. Resolves it to an absolute path
        3. Validates it's within the workspace using path-aware comparison
        4. Checks it doesn't access blocked directories
        
        Args:
            path: Path to resolve (relative to workspace or absolute)
            
        Returns:
            Resolved absolute path within workspace
            
        Raises:
            WorkspaceError: If path is outside workspace or blocked
        """
        # Convert to Path object and strip workspace/ prefix
        if isinstance(path, str):
            path = Path(self._strip_workspace_prefix(path))
        
        # If path is relative, make it relative to workspace root
        if not path.is_absolute():
            path = self.root / path
        
        # Resolve to absolute path (handles .. and symlinks)
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as e:
            raise WorkspaceError(f"Cannot resolve path: {e}")
        
        # Check if path is within workspace using path-aware comparison
        # Use normalized paths for Windows case-insensitivity
        resolved_norm = self._normalize_path(resolved)
        workspace_norm = self._normalize_path(self.root)
        
        try:
            resolved_norm.relative_to(workspace_norm)
        except ValueError:
            raise WorkspaceError(
                f"[blocked_by: workspace] Path outside workspace\n"
                f"  requested: {path}\n"
                f"  resolved: {resolved}\n"
                f"  workspace_root: {self.root}"
            )
        
        # Workspace paths don't need blocked dir checks (they're already in workspace)
        # But check if path is a blocked file
        if resolved in self.blocked_files:
            raise WorkspaceError(
                f"[blocked_by: workspace] Access to '{resolved.name}' is blocked for safety"
            )
        
        return resolved
    
    def resolve_project_read(self, path: Union[str, Path]) -> Path:
        """Resolve a path for READ-ONLY access to project files.
        
        This allows the agent to read source code files but not modify them.
        Sensitive files (.env, secrets, keys) are still blocked.
        
        Args:
            path: Path to resolve (relative to project root or absolute)
            
        Returns:
            Resolved absolute path within project
            
        Raises:
            WorkspaceError: If path is outside project, blocked, or sensitive
        """
        if not self.allow_project_read:
            raise WorkspaceError("Project read access is disabled")
        
        # Convert to Path object
        if isinstance(path, str):
            path = Path(path)
        
        # If path is relative, make it relative to project root
        if not path.is_absolute():
            path = self._project_root / path
        
        # Resolve to absolute path
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as e:
            raise WorkspaceError(f"Cannot resolve path: {e}")
        
        # Check if path is within project using normalized comparison
        resolved_norm = self._normalize_path(resolved)
        project_norm = self._normalize_path(self._project_root)
        
        try:
            resolved_norm.relative_to(project_norm)
        except ValueError:
            raise WorkspaceError(
                f"[blocked_by: workspace] Path outside project\n"
                f"  requested: {path}\n"
                f"  resolved: {resolved}\n"
                f"  project_root: {self._project_root}"
            )
        
        # Check if path is a blocked file
        if resolved in self.blocked_files:
            raise WorkspaceError(
                f"[blocked_by: workspace] Access to '{resolved.name}' is blocked for safety"
            )
        
        # Check if path matches sensitive patterns
        if self._is_sensitive_file(resolved):
            raise WorkspaceError(
                f"[blocked_by: workspace] Access to '{resolved.name}' is blocked (sensitive file)"
            )
        
        # Verify file exists for read operations
        if not resolved.exists():
            raise WorkspaceError(f"Path does not exist: {resolved}")
        
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
    
    def get_workspace_size(self) -> int:
        """Get total size of workspace in bytes.
        
        Returns:
            Total size in bytes
        """
        total_size = 0
        for item in self.root.rglob('*'):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                except (OSError, PermissionError):
                    # Skip files we can't access
                    pass
        return total_size
    
    def check_workspace_size(self) -> None:
        """Check if workspace size is within limits.
        
        Raises:
            ResourceLimitError: If workspace exceeds size limit
        """
        current_size = self.get_workspace_size()
        if current_size > self.max_workspace_size_bytes:
            size_gb = current_size / (1024 * 1024 * 1024)
            limit_gb = self.max_workspace_size_bytes / (1024 * 1024 * 1024)
            raise ResourceLimitError(
                f"Workspace size ({size_gb:.2f}GB) exceeds limit ({limit_gb:.2f}GB). "
                f"Clean up files before continuing."
            )
    
    def check_ram_usage(self) -> None:
        """Check if system has sufficient free RAM.
        
        Raises:
            ResourceLimitError: If free RAM is below minimum threshold
        """
        memory = psutil.virtual_memory()
        free_percent = 100.0 - memory.percent
        
        if free_percent < self.min_free_ram_percent:
            raise ResourceLimitError(
                f"Low system memory: only {free_percent:.1f}% free "
                f"(minimum: {self.min_free_ram_percent}%). "
                f"Close other applications or increase memory."
            )
    
    def check_resources(self) -> None:
        """Check all resource limits before operations.
        
        This is a circuit breaker that prevents system crashes.
        Call this before expensive operations like file writes or code execution.
        
        Raises:
            ResourceLimitError: If any resource limit is exceeded
        """
        self.check_workspace_size()
        self.check_ram_usage()
    
    def get_resource_stats(self) -> dict:
        """Get current resource usage statistics.
        
        Returns:
            Dictionary with resource stats
        """
        workspace_size = self.get_workspace_size()
        memory = psutil.virtual_memory()
        
        return {
            "workspace_size_bytes": workspace_size,
            "workspace_size_gb": workspace_size / (1024 * 1024 * 1024),
            "workspace_limit_gb": self.max_workspace_size_bytes / (1024 * 1024 * 1024),
            "ram_used_percent": memory.percent,
            "ram_free_percent": 100.0 - memory.percent,
            "ram_available_gb": memory.available / (1024 * 1024 * 1024),
        }


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
