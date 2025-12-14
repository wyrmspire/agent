"""
tests/core/test_sandb.py - Workspace Tests

This module tests the workspace (sandbox) path manager:
- Path resolution and validation
- Directory isolation enforcement
- Resource monitoring
- Circuit breaker functionality
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from core.sandb import Workspace, WorkspaceError, ResourceLimitError


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    temp_dir = tempfile.mkdtemp()
    workspace = Workspace(temp_dir)
    yield workspace
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_workspace_creation(temp_workspace):
    """Test that workspace directory is created."""
    assert temp_workspace.root.exists()
    assert temp_workspace.root.is_dir()


def test_resolve_relative_path(temp_workspace):
    """Test resolving a relative path within workspace."""
    resolved = temp_workspace.resolve("data/test.csv")
    
    # Should be within workspace
    assert str(temp_workspace.root) in str(resolved)
    assert resolved.name == "test.csv"


def test_resolve_absolute_path_within_workspace(temp_workspace):
    """Test resolving an absolute path that's within workspace."""
    test_path = temp_workspace.root / "data" / "test.csv"
    resolved = temp_workspace.resolve(test_path)
    
    assert resolved == test_path


def test_resolve_path_outside_workspace_fails(temp_workspace):
    """Test that paths outside workspace are rejected."""
    with pytest.raises(WorkspaceError, match="outside workspace"):
        temp_workspace.resolve("../outside.txt")


def test_resolve_read_nonexistent_fails(temp_workspace):
    """Test that reading nonexistent file fails."""
    with pytest.raises(WorkspaceError, match="does not exist"):
        temp_workspace.resolve_read("nonexistent.txt")


def test_resolve_read_existing_succeeds(temp_workspace):
    """Test reading existing file."""
    # Create a test file
    test_file = temp_workspace.root / "test.txt"
    test_file.write_text("test content")
    
    resolved = temp_workspace.resolve_read("test.txt")
    assert resolved.exists()
    assert resolved.read_text() == "test content"


def test_resolve_write_creates_parents(temp_workspace):
    """Test that write resolution creates parent directories."""
    resolved = temp_workspace.resolve_write("data/subdir/file.txt")
    
    assert resolved.parent.exists()
    assert resolved.parent.is_dir()


def test_list_contents(temp_workspace):
    """Test listing workspace contents."""
    # Create some files and directories
    (temp_workspace.root / "file1.txt").write_text("content1")
    (temp_workspace.root / "file2.txt").write_text("content2")
    (temp_workspace.root / "subdir").mkdir(exist_ok=True)
    
    contents = temp_workspace.list_contents()
    names = [p.name for p in contents]
    
    # Should include standard bins (7) + our 3 new items
    # But subdir might already exist if it's in STANDARD_BINS, so check files
    assert "file1.txt" in names
    assert "file2.txt" in names
    assert "subdir" in names or "subdir" in Workspace.STANDARD_BINS
    
    # Should have at least the standard bins
    for bin_name in Workspace.STANDARD_BINS:
        assert bin_name in names


def test_get_relative_path(temp_workspace):
    """Test getting relative path from absolute."""
    abs_path = temp_workspace.root / "data" / "test.csv"
    rel_path = temp_workspace.get_relative_path(abs_path)
    
    # Use Path for cross-platform comparison
    assert rel_path == Path("data") / "test.csv"


def test_ensure_dir(temp_workspace):
    """Test ensuring directory exists."""
    dir_path = temp_workspace.ensure_dir("data/subdir")
    
    assert dir_path.exists()
    assert dir_path.is_dir()


def test_get_workspace_size(temp_workspace):
    """Test calculating workspace size."""
    # Create some files
    (temp_workspace.root / "file1.txt").write_text("a" * 100)
    (temp_workspace.root / "file2.txt").write_text("b" * 200)
    
    size = temp_workspace.get_workspace_size()
    assert size >= 300  # At least the size of our files


def test_check_workspace_size_under_limit(temp_workspace):
    """Test workspace size check passes when under limit."""
    # Create small file
    (temp_workspace.root / "small.txt").write_text("small")
    
    # Should not raise
    temp_workspace.check_workspace_size()


def test_check_workspace_size_over_limit(temp_workspace):
    """Test workspace size check fails when over limit."""
    # Set very small limit
    temp_workspace.max_workspace_size_bytes = 10
    
    # Create file that exceeds limit
    (temp_workspace.root / "large.txt").write_text("a" * 100)
    
    with pytest.raises(ResourceLimitError, match="exceeds limit"):
        temp_workspace.check_workspace_size()


def test_check_ram_usage(temp_workspace):
    """Test RAM usage check."""
    # This should normally pass unless system is critically low on memory
    # Just ensure it doesn't crash
    temp_workspace.check_ram_usage()


def test_get_resource_stats(temp_workspace):
    """Test getting resource statistics."""
    stats = temp_workspace.get_resource_stats()
    
    assert "workspace_size_bytes" in stats
    assert "workspace_size_gb" in stats
    assert "ram_used_percent" in stats
    assert "ram_free_percent" in stats
    assert stats["ram_free_percent"] >= 0


def test_resolve_nonexistent_path_within_workspace(temp_workspace):
    """Test resolving a non-existent path within workspace (Phase 1.6.1).
    
    This should work - we should be able to resolve paths that don't exist yet.
    The normalization should not throw errors for non-existent paths.
    """
    # Should not raise an error even though path doesn't exist
    resolved = temp_workspace.resolve("data/nonexistent/file.txt")
    
    # Should be within workspace
    assert str(temp_workspace.root) in str(resolved)
    assert resolved.name == "file.txt"
    # Verify it's properly normalized (this would fail with old buggy resolve())
    assert resolved.is_absolute()


def test_strip_workspace_prefix_simple(temp_workspace):
    """Test stripping workspace/ prefix from simple paths."""
    result = temp_workspace._strip_workspace_prefix("workspace/data/test.csv")
    assert result == "data/test.csv"
    
    result = temp_workspace._strip_workspace_prefix("data/test.csv")
    assert result == "data/test.csv"


def test_strip_workspace_prefix_nested_workspace_folder(temp_workspace):
    """Test that workspace/workspace/test.txt is handled correctly (Phase 1.6.1).
    
    If user has a subfolder literally named 'workspace' inside the workspace,
    the stripping logic should handle it correctly:
    - String "workspace/test.txt" gets stripped (agent mistake assumed)
    - Path object Path("workspace/test.txt") does NOT get stripped (intentional)
    
    This prevents false positives while still handling agent confusion.
    """
    # Create a subfolder literally named "workspace" inside workspace
    nested_ws_dir = temp_workspace.root / "workspace"
    nested_ws_dir.mkdir(exist_ok=True)
    test_file = nested_ws_dir / "test.txt"
    test_file.write_text("test")
    
    # Test the strip function directly
    # "workspace/workspace/test.txt" -> strip first segment -> "workspace/test.txt"
    result = temp_workspace._strip_workspace_prefix("workspace/workspace/test.txt")
    assert result == "workspace/test.txt"
    
    # When resolving a STRING "workspace/test.txt", it gets stripped
    resolved_string = temp_workspace.resolve("workspace/test.txt")
    # This resolves to root/test.txt (NOT the subfolder)
    assert resolved_string == temp_workspace.root / "test.txt"
    
    # To access the real workspace subfolder, pass a Path object (no stripping)
    resolved_path = temp_workspace.resolve(Path("workspace") / "test.txt")
    assert resolved_path == test_file
    
    # Or use a string that doesn't start with "workspace/"
    # (though in this case there's no such string for this path)


def test_normalize_path_does_not_double_resolve(temp_workspace):
    """Test that _normalize_path doesn't call resolve() again (Phase 1.6.1)."""
    # Create a path that's already resolved
    test_path = temp_workspace.root / "data" / "test.txt"
    
    # Normalize should work on already-resolved paths without issues
    normalized = temp_workspace._normalize_path(test_path)
    
    # Should be same path (or equivalent on Windows with case normalization)
    assert normalized == test_path or str(normalized).lower() == str(test_path).lower()


if __name__ == "__main__":
    # Run tests
    print("Running workspace tests...")
    pytest.main([__file__, "-v"])
