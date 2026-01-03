"""
core/context.py - Workspace Context Builder

This module scans the workspace at startup to build a context dict
that is injected into the system prompt. This eliminates the need
for the agent to "discover" file locations via trial-and-error.

Responsibilities:
- Scan workspace/ directory for files and sizes
- Identify key data files (JSON, CSV, etc.)
- Build a summary dict for prompt injection
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional


class WorkspaceContextBuilder:
    """Scans workspace/ at startup and produces a context dict.
    
    This context is injected into the system prompt to give the agent
    immediate knowledge of available files and directories.
    """
    
    def __init__(self, workspace_root: Path, project_root: Optional[Path] = None):
        """Initialize the context builder.
        
        Args:
            workspace_root: Path to the workspace directory
            project_root: Path to the project root (defaults to workspace parent)
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.project_root = project_root or self.workspace_root.parent
    
    def build(self) -> Dict[str, Any]:
        """Build and return the workspace context dict.
        
        Returns:
            Dict with keys:
            - cwd: Current working directory (absolute path)
            - project_root: Project root directory
            - workspace_dir: Workspace directory (writable area)
            - data_files: List of files in workspace/data/ with sizes
            - recent_notes: Last 3 notes from workspace/notes/
            - standard_dirs: List of standard bin directories
            - last_session: Summary from previous session (Phase 5)
            - projects: Project descriptions (Phase 5)
            - skills: Available skills in workspace/skills/ (Phase 5)
        """
        context = {
            "name": self.project_root.name,
            "state": "active",
            "description": f"Project at {self.project_root}",
            "cwd": str(Path.cwd()),
            "project_root": str(self.project_root),
            "workspace_dir": str(self.workspace_root),
            "data_files": self._scan_data_files(),
            "recent_notes": self._get_recent_notes(),
            "standard_dirs": self._get_standard_dirs(),
            "tasks": [],  # Placeholder for future task integration
            # Phase 5: Session continuity
            "last_session": self._get_last_session(),
            "projects": self._get_project_descriptions(),
            "skills": self._get_available_skills(),
            # Phase 6: Structure awareness
            "project_folders": self._scan_project_folders(),
            "directory_tree": self._get_directory_tree(),
        }
        return context
    
    def _scan_data_files(self, max_files: int = 10) -> List[Dict[str, Any]]:
        """Scan workspace/data/ for data files.
        
        Args:
            max_files: Maximum number of files to return
            
        Returns:
            List of dicts with file info (path, size, type)
        """
        data_dir = self.workspace_root / "data"
        if not data_dir.exists():
            return []
        
        files = []
        try:
            for entry in data_dir.iterdir():
                if entry.is_file():
                    size_bytes = entry.stat().st_size
                    files.append({
                        "path": f"workspace/data/{entry.name}",
                        "absolute_path": str(entry),
                        "size_bytes": size_bytes,
                        "size_human": self._human_readable_size(size_bytes),
                        "type": entry.suffix.lower(),
                    })
                elif entry.is_dir():
                    # Count files in subdirectory
                    subdir_count = sum(1 for _ in entry.iterdir() if _.is_file())
                    files.append({
                        "path": f"workspace/data/{entry.name}/",
                        "absolute_path": str(entry),
                        "type": "directory",
                        "file_count": subdir_count,
                    })
        except PermissionError:
            pass
        
        # Sort by size (largest first) and limit
        files.sort(key=lambda x: x.get("size_bytes", 0), reverse=True)
        return files[:max_files]
    
    def _get_recent_notes(self, max_notes: int = 3) -> List[str]:
        """Get recent notes from workspace/notes/.
        
        Args:
            max_notes: Maximum number of notes to return
            
        Returns:
            List of note summaries (first line of each file)
        """
        notes_dir = self.workspace_root / "notes"
        if not notes_dir.exists():
            return []
        
        notes = []
        try:
            for entry in sorted(notes_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if entry.is_file() and entry.suffix == ".md":
                    try:
                        first_line = entry.read_text(encoding="utf-8").split("\n")[0]
                        notes.append(f"{entry.name}: {first_line[:80]}")
                    except Exception:
                        notes.append(f"{entry.name}: (unreadable)")
                if len(notes) >= max_notes:
                    break
        except PermissionError:
            pass
        
        return notes
    
    def _get_standard_dirs(self) -> List[str]:
        """Get list of standard workspace directories that exist.
        
        Returns:
            List of existing standard directory names
        """
        standard_bins = ["repos", "runs", "notes", "patches", "data", "queue", "chunks"]
        existing = []
        for bin_name in standard_bins:
            if (self.workspace_root / bin_name).exists():
                existing.append(f"workspace/{bin_name}/")
        return existing
    
    @staticmethod
    def _human_readable_size(size_bytes: int) -> str:
        """Convert bytes to human readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Human readable size string (e.g., "32MB")
        """
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes // 1024}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes // (1024 * 1024)}MB"
        else:
            return f"{size_bytes // (1024 * 1024 * 1024)}GB"
    
    def _get_last_session(self) -> Optional[str]:
        """Load last session summary (Phase 5).
        
        Returns:
            Last session summary text, or None if not available
        """
        session_file = self.workspace_root / "sessions" / "latest.md"
        if session_file.exists():
            try:
                content = session_file.read_text(encoding="utf-8")
                # Strip markdown header if present
                lines = content.strip().split("\n")
                if lines and lines[0].startswith("# "):
                    lines = lines[1:]
                return "\n".join(lines).strip()[:500]  # Limit to 500 chars
            except Exception:
                return None
        return None
    
    def _get_project_descriptions(self) -> List[Dict[str, str]]:
        """Load project descriptions from registry (Phase 5).
        
        Returns:
            List of project dicts with name and description
        """
        registry_file = self.workspace_root / "projects" / "registry.json"
        if registry_file.exists():
            try:
                import json
                return json.loads(registry_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []
    
    def _get_available_skills(self) -> List[str]:
        """List available skills in workspace/skills/ (Phase 5).
        
        Returns:
            List of skill module names (e.g., ["yfinance", "data_parser"])
        """
        skills_dir = self.workspace_root / "skills"
        if not skills_dir.exists():
            return []
        
        skills = []
        try:
            for entry in skills_dir.iterdir():
                if entry.is_file() and entry.suffix == ".py" and not entry.name.startswith("_"):
                    skills.append(entry.stem)  # filename without .py
        except PermissionError:
            pass
        return skills
    
    # Directories to exclude from project folder scanning
    EXCLUDED_DIRS = {"node_modules", "__pycache__", ".git", "chunks", "queue", "patches", "repos", "runs", "sessions"}
    
    def _scan_project_folders(self) -> List[Dict[str, Any]]:
        """Scan workspace for project folders (non-standard directories).
        
        Returns:
            List of project folder dicts with name, path, file_count
        """
        standard = {"data", "notes", "skills", "sessions", "queue", "patches", "repos", "runs", "chunks"}
        projects = []
        
        try:
            for entry in self.workspace_root.iterdir():
                if not entry.is_dir():
                    continue
                if entry.name in standard or entry.name in self.EXCLUDED_DIRS:
                    continue
                if entry.name.startswith((".", "_")):
                    continue
                
                # Count files, excluding node_modules subdirs
                file_count = 0
                try:
                    for f in entry.rglob("*"):
                        if f.is_file() and "node_modules" not in str(f):
                            file_count += 1
                except PermissionError:
                    pass
                
                projects.append({
                    "name": entry.name,
                    "path": f"workspace/{entry.name}/",
                    "file_count": file_count
                })
        except PermissionError:
            pass
        
        return projects
    
    def _get_directory_tree(self, max_entries: int = 20) -> str:
        """Get compact directory tree of workspace.
        
        Args:
            max_entries: Maximum entries to return
            
        Returns:
            Formatted tree string
        """
        lines = []
        try:
            for entry in sorted(self.workspace_root.iterdir()):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    lines.append(f"📁 {entry.name}/")
                else:
                    lines.append(f"📄 {entry.name}")
                if len(lines) >= max_entries:
                    lines.append("... (more files)")
                    break
        except PermissionError:
            pass
        
        return "\n".join(lines)


def get_workspace_context(workspace_path: str = "workspace") -> Dict[str, Any]:
    """Convenience function to get workspace context.
    
    Args:
        workspace_path: Path to workspace directory
        
    Returns:
        Context dict for prompt injection
    """
    builder = WorkspaceContextBuilder(Path(workspace_path))
    return builder.build()


# =============================================================================
# Path Resolution Utilities (Phase B)
# =============================================================================

def resolve_path_for(
    tool_name: str, 
    path: str,
    workspace_root: str = "workspace",
) -> Dict[str, Any]:
    """Resolve and normalize a path for a specific tool.
    
    This is the canonical path resolver for the agent. It returns both forms
    (absolute and relative) plus metadata about the path.
    
    Args:
        tool_name: Name of the tool that will use this path
        path: The path to resolve
        workspace_root: Root of the workspace directory
        
    Returns:
        Dict with keys:
        - absolute: Absolute path form
        - relative: Relative to cwd form
        - workspace_relative: Relative to workspace form (if applicable)
        - kind: "workspace", "project", "external"
        - recommended: Which form to use for this tool
        - needs_normalization: Whether path needed fixing
        - original: The original input path
    """
    workspace_path = Path(workspace_root).resolve()
    project_path = Path(".").resolve()
    
    try:
        # Handle empty path
        if not path:
            return {
                "absolute": "",
                "relative": "",
                "workspace_relative": "",
                "kind": "empty",
                "recommended": "",
                "needs_normalization": False,
                "original": path,
            }
        
        # Parse the path
        path_obj = Path(path)
        
        # If it's already absolute
        if path_obj.is_absolute():
            abs_path = path_obj.resolve()
        else:
            # Resolve relative to cwd
            abs_path = (Path.cwd() / path_obj).resolve()
        
        # Determine what kind of path this is
        try:
            rel_to_workspace = abs_path.relative_to(workspace_path)
            kind = "workspace"
            workspace_relative = f"workspace/{rel_to_workspace}".replace("\\", "/")
        except ValueError:
            workspace_relative = ""
            try:
                rel_to_project = abs_path.relative_to(project_path)
                kind = "project"
            except ValueError:
                kind = "external"
        
        # Get relative to cwd
        try:
            relative = str(abs_path.relative_to(Path.cwd()))
        except ValueError:
            relative = str(abs_path)
        
        # Tool-specific recommendations
        tool_path_forms = {
            "pyexe": "absolute",
            "shell": "relative",
            "write_file": "workspace_relative",
            "read_file": "relative",
            "list_files": "relative",
        }
        recommended_form = tool_path_forms.get(tool_name, "relative")
        
        if recommended_form == "absolute":
            recommended = str(abs_path)
        elif recommended_form == "workspace_relative" and workspace_relative:
            recommended = workspace_relative
        else:
            recommended = relative
        
        # Check if normalization changed anything
        needs_normalization = (
            path != recommended and
            path.replace("/", "\\") != recommended.replace("/", "\\")
        )
        
        return {
            "absolute": str(abs_path),
            "relative": relative,
            "workspace_relative": workspace_relative,
            "kind": kind,
            "recommended": recommended,
            "needs_normalization": needs_normalization,
            "original": path,
        }
        
    except (OSError, ValueError) as e:
        # Path is invalid or inaccessible
        return {
            "absolute": path,
            "relative": path,
            "workspace_relative": "",
            "kind": "invalid",
            "recommended": path,
            "needs_normalization": False,
            "original": path,
            "error": str(e),
        }


def is_workspace_path(path: str, workspace_root: str = "workspace") -> bool:
    """Check if a path is within the workspace.
    
    Args:
        path: Path to check
        workspace_root: Root of workspace directory
        
    Returns:
        True if path is inside workspace
    """
    result = resolve_path_for("any", path, workspace_root)
    return result["kind"] == "workspace"


def normalize_path(path: str, tool_name: str = "shell") -> str:
    """Normalize a path for consistent handling.
    
    Simple utility that returns the recommended form for the given tool.
    
    Args:
        path: Path to normalize
        tool_name: Tool that will use the path
        
    Returns:
        Normalized path string
    """
    result = resolve_path_for(tool_name, path)
    return result["recommended"]
