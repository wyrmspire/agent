"""
tests/core/test_patch.py - Tests for patch protocol

Tests patch creation, validation, and lifecycle.
"""

import tempfile
import json
from pathlib import Path

from core.patch import PatchManager, PatchStatus, BlockedBy, create_tool_error, format_tool_error


def test_create_patch():
    """Test creating a basic patch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create patch
        patch = manager.create_patch(
            title="Fix tool budget bug",
            description="Fixes the tool budget per-batch bug",
            target_files=["core/state.py", "flow/loops.py"],
            plan_content="# Plan\n\nFix the budget calculation",
            diff_content="--- a/core/state.py\n+++ b/core/state.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests\n\nRun pytest tests/core/",
        )
        
        assert patch is not None
        assert patch.patch_id
        assert patch.title == "Fix tool budget bug"
        assert patch.status == PatchStatus.PROPOSED.value
        assert len(patch.target_files) == 2


def test_patch_validation():
    """Test patch validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create valid patch
        patch = manager.create_patch(
            title="Test patch",
            description="Test description",
            target_files=["test.py"],
            plan_content="# Plan\nTest plan",
            diff_content="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests\nTest instructions",
        )
        
        # Validate
        is_valid, error = manager.validate_patch(patch.patch_id)
        assert is_valid
        assert error is None


def test_patch_validation_empty_diff():
    """Test patch validation with empty diff."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create patch with empty diff
        patch = manager.create_patch(
            title="Test patch",
            description="Test description",
            target_files=["test.py"],
            plan_content="# Plan\nTest plan",
            diff_content="",
            tests_content="# Tests\nTest instructions",
        )
        
        # Validation should fail
        is_valid, error = manager.validate_patch(patch.patch_id)
        assert not is_valid
        assert "empty" in error.lower()


def test_patch_status_update():
    """Test updating patch status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create patch
        patch = manager.create_patch(
            title="Test patch",
            description="Test description",
            target_files=["test.py"],
            plan_content="# Plan\nTest plan",
            diff_content="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests\nTest instructions",
        )
        
        # Update status
        success = manager.update_status(
            patch.patch_id,
            PatchStatus.APPLIED,
        )
        
        assert success
        updated_patch = manager.get_patch(patch.patch_id)
        assert updated_patch.status == PatchStatus.APPLIED.value


def test_list_patches():
    """Test listing patches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create multiple patches
        patch1 = manager.create_patch(
            title="Patch 1",
            description="First patch",
            target_files=["file1.py"],
            plan_content="# Plan 1",
            diff_content="--- a/file1.py\n+++ b/file1.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests 1",
        )
        
        patch2 = manager.create_patch(
            title="Patch 2",
            description="Second patch",
            target_files=["file2.py"],
            plan_content="# Plan 2",
            diff_content="--- a/file2.py\n+++ b/file2.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests 2",
        )
        
        # Update one to applied
        manager.update_status(patch1.patch_id, PatchStatus.APPLIED)
        
        # List all
        all_patches = manager.list_patches()
        assert len(all_patches) == 2
        
        # List by status
        proposed = manager.list_patches(status=PatchStatus.PROPOSED)
        assert len(proposed) == 1
        assert proposed[0].patch_id == patch2.patch_id
        
        applied = manager.list_patches(status=PatchStatus.APPLIED)
        assert len(applied) == 1
        assert applied[0].patch_id == patch1.patch_id


def test_generate_apply_command():
    """Test generating apply command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create patch
        patch = manager.create_patch(
            title="Test patch",
            description="Test description",
            target_files=["test.py"],
            plan_content="# Plan\nTest plan",
            diff_content="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests\nTest instructions",
        )
        
        # Generate command
        cmd = manager.generate_apply_command(patch.patch_id)
        
        assert cmd is not None
        assert "git apply" in cmd
        assert patch.patch_id in cmd


def test_patch_persistence():
    """Test patch persistence across manager instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create patch with first manager
        manager1 = PatchManager(workspace_dir=tmpdir)
        patch = manager1.create_patch(
            title="Test patch",
            description="Test description",
            target_files=["test.py"],
            plan_content="# Plan\nTest plan",
            diff_content="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests\nTest instructions",
        )
        
        # Create new manager (should load existing patches)
        manager2 = PatchManager(workspace_dir=tmpdir)
        
        # Should find the patch
        loaded_patch = manager2.get_patch(patch.patch_id)
        assert loaded_patch is not None
        assert loaded_patch.title == patch.title


def test_tool_error_creation():
    """Test creating standardized tool errors."""
    error = create_tool_error(
        blocked_by=BlockedBy.RULES,
        error_code="TEST_ERROR",
        message="Test error message",
        context={"file": "test.py"},
    )
    
    assert error.blocked_by == BlockedBy.RULES.value
    assert error.error_code == "TEST_ERROR"
    assert error.message == "Test error message"
    assert error.context["file"] == "test.py"


def test_tool_error_formatting():
    """Test formatting tool errors."""
    error = create_tool_error(
        blocked_by=BlockedBy.WORKSPACE,
        error_code="OUTSIDE_WORKSPACE",
        message="Cannot access file outside workspace",
        context={"attempted_path": "/etc/passwd"},
    )
    
    formatted = format_tool_error(error)
    
    assert "ERROR [OUTSIDE_WORKSPACE]" in formatted
    assert "Blocked by: workspace" in formatted
    assert "Cannot access file outside workspace" in formatted
    assert "/etc/passwd" in formatted


def test_patch_stats():
    """Test getting patch statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create patches with different statuses
        patch1 = manager.create_patch(
            title="Patch 1",
            description="First patch",
            target_files=["file1.py"],
            plan_content="# Plan 1",
            diff_content="--- a/file1.py\n+++ b/file1.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests 1",
        )
        
        patch2 = manager.create_patch(
            title="Patch 2",
            description="Second patch",
            target_files=["file2.py"],
            plan_content="# Plan 2",
            diff_content="--- a/file2.py\n+++ b/file2.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests 2",
        )
        
        manager.update_status(patch1.patch_id, PatchStatus.APPLIED)
        
        # Get stats
        stats = manager.get_stats()
        
        assert stats["total_patches"] == 2
        assert stats["status_counts"][PatchStatus.PROPOSED.value] == 1
        assert stats["status_counts"][PatchStatus.APPLIED.value] == 1


if __name__ == "__main__":
    # Run tests
    test_create_patch()
    print("✓ test_create_patch")
    
    test_patch_validation()
    print("✓ test_patch_validation")
    
    test_patch_validation_empty_diff()
    print("✓ test_patch_validation_empty_diff")
    
    test_patch_status_update()
    print("✓ test_patch_status_update")
    
    test_list_patches()
    print("✓ test_list_patches")
    
    test_generate_apply_command()
    print("✓ test_generate_apply_command")
    
    test_patch_persistence()
    print("✓ test_patch_persistence")
    
    test_tool_error_creation()
    print("✓ test_tool_error_creation")
    
    test_tool_error_formatting()
    print("✓ test_tool_error_formatting")
    
    test_patch_stats()
    print("✓ test_patch_stats")
    
    print("\nAll patch tests passed!")
