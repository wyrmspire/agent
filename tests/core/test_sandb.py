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
    (temp_workspace.root / "subdir").mkdir()
    
    contents = temp_workspace.list_contents()
    
    assert len(contents) == 3
    names = [p.name for p in contents]
    assert "file1.txt" in names
    assert "file2.txt" in names
    assert "subdir" in names


def test_get_relative_path(temp_workspace):
    """Test getting relative path from absolute."""
    abs_path = temp_workspace.root / "data" / "test.csv"
    rel_path = temp_workspace.get_relative_path(abs_path)
    
    assert str(rel_path) == "data/test.csv"


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


if __name__ == "__main__":
    # Run tests
    print("Running workspace tests...")
    pytest.main([__file__, "-v"])
