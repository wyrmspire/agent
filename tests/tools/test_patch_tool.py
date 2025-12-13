"""
tests/tools/test_patch_tool.py - Tests for patch tools

Tests the patch creation and management tools.
"""

import tempfile
from pathlib import Path

from tool.patch import CreatePatchTool, ListPatchesTool, GetPatchTool
from core.patch import PatchManager, PatchStatus


async def test_create_patch_tool():
    """Test creating a patch via tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        tool = CreatePatchTool(patch_manager=manager)
        
        # Create patch
        result = await tool.execute({
            "title": "Fix tool budget bug",
            "description": "Fixes the tool budget per-batch bug",
            "target_files": ["core/state.py", "flow/loops.py"],
            "plan": "# Plan\n\nFix the budget calculation",
            "diff": "--- a/core/state.py\n+++ b/core/state.py\n@@ -1 +1 @@\n-old\n+new",
            "tests": "# Tests\n\nRun pytest tests/core/",
        })
        
        assert result.success
        assert "Created patch:" in result.output
        assert "git apply" in result.output
        assert "CANNOT claim this is 'fixed'" in result.output


async def test_create_patch_tool_missing_fields():
    """Test creating patch with missing required fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        tool = CreatePatchTool(patch_manager=manager)
        
        # Missing diff
        result = await tool.execute({
            "title": "Test",
            "description": "Test",
            "target_files": ["test.py"],
            "plan": "# Plan",
            "tests": "# Tests",
        })
        
        assert not result.success
        assert "PATCH_MISSING_FIELDS" in result.error


async def test_create_patch_tool_no_targets():
    """Test creating patch without target files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        tool = CreatePatchTool(patch_manager=manager)
        
        result = await tool.execute({
            "title": "Test",
            "description": "Test",
            "target_files": [],
            "plan": "# Plan",
            "diff": "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            "tests": "# Tests",
        })
        
        assert not result.success
        assert "PATCH_NO_TARGETS" in result.error


async def test_list_patches_tool():
    """Test listing patches via tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create some patches
        manager.create_patch(
            title="Patch 1",
            description="First",
            target_files=["file1.py"],
            plan_content="# Plan",
            diff_content="--- a/file1.py\n+++ b/file1.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests",
        )
        
        manager.create_patch(
            title="Patch 2",
            description="Second",
            target_files=["file2.py"],
            plan_content="# Plan",
            diff_content="--- a/file2.py\n+++ b/file2.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests",
        )
        
        tool = ListPatchesTool(patch_manager=manager)
        
        # List all patches
        result = await tool.execute({})
        
        assert result.success
        assert "Found 2 patches" in result.output
        assert "Patch 1" in result.output
        assert "Patch 2" in result.output


async def test_list_patches_tool_with_filter():
    """Test listing patches with status filter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create patches
        patch1 = manager.create_patch(
            title="Patch 1",
            description="First",
            target_files=["file1.py"],
            plan_content="# Plan",
            diff_content="--- a/file1.py\n+++ b/file1.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests",
        )
        
        patch2 = manager.create_patch(
            title="Patch 2",
            description="Second",
            target_files=["file2.py"],
            plan_content="# Plan",
            diff_content="--- a/file2.py\n+++ b/file2.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests",
        )
        
        # Update one to applied
        manager.update_status(patch1.patch_id, PatchStatus.APPLIED)
        
        tool = ListPatchesTool(patch_manager=manager)
        
        # List only proposed
        result = await tool.execute({"status": "proposed"})
        
        assert result.success
        assert "Found 1 patch" in result.output
        assert "Patch 2" in result.output
        assert "Patch 1" not in result.output


async def test_get_patch_tool():
    """Test getting patch details via tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        
        # Create patch
        patch = manager.create_patch(
            title="Test Patch",
            description="Test description",
            target_files=["test.py"],
            plan_content="# Plan\n\nThis is the plan",
            diff_content="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new",
            tests_content="# Tests\n\nRun pytest",
        )
        
        tool = GetPatchTool(patch_manager=manager)
        
        # Get patch
        result = await tool.execute({"patch_id": patch.patch_id})
        
        assert result.success
        assert "Test Patch" in result.output
        assert "=== PLAN ===" in result.output
        assert "=== DIFF ===" in result.output
        assert "=== TESTS ===" in result.output
        assert "This is the plan" in result.output


async def test_get_patch_tool_not_found():
    """Test getting non-existent patch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PatchManager(workspace_dir=tmpdir)
        tool = GetPatchTool(patch_manager=manager)
        
        # Get non-existent patch
        result = await tool.execute({"patch_id": "nonexistent"})
        
        assert not result.success
        assert "PATCH_NOT_FOUND" in result.error


async def test_get_patch_tool_missing_id():
    """Test getting patch without ID."""
    tool = GetPatchTool()
    
    result = await tool.execute({})
    
    assert not result.success
    assert "Missing required parameter" in result.error


if __name__ == "__main__":
    import asyncio
    
    # Run tests
    asyncio.run(test_create_patch_tool())
    print("✓ test_create_patch_tool")
    
    asyncio.run(test_create_patch_tool_missing_fields())
    print("✓ test_create_patch_tool_missing_fields")
    
    asyncio.run(test_create_patch_tool_no_targets())
    print("✓ test_create_patch_tool_no_targets")
    
    asyncio.run(test_list_patches_tool())
    print("✓ test_list_patches_tool")
    
    asyncio.run(test_list_patches_tool_with_filter())
    print("✓ test_list_patches_tool_with_filter")
    
    asyncio.run(test_get_patch_tool())
    print("✓ test_get_patch_tool")
    
    asyncio.run(test_get_patch_tool_not_found())
    print("✓ test_get_patch_tool_not_found")
    
    asyncio.run(test_get_patch_tool_missing_id())
    print("✓ test_get_patch_tool_missing_id")
    
    print("\nAll patch tool tests passed!")
