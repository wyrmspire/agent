"""
tests/tools/test_files_workspace.py - File Tools with Workspace Tests

This module tests file tools integrated with workspace isolation:
- Writing files within workspace
- Reading files within workspace
- Listing workspace contents
- Workspace boundary enforcement
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from core.sandb import Workspace
from tool.files import ListFiles, ReadFile, WriteFile
from core.types import ToolCall


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    temp_dir = tempfile.mkdtemp()
    workspace = Workspace(temp_dir)
    yield workspace
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_write_file_in_workspace(temp_workspace):
    """Test writing a file within workspace."""
    tool = WriteFile(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-write-1",
        name="write_file",
        arguments={
            "path": "test.txt",
            "content": "Hello, workspace!"
        }
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "test.txt" in result.output
    
    # Verify file was created
    file_path = temp_workspace.root / "test.txt"
    assert file_path.exists()
    assert file_path.read_text() == "Hello, workspace!"


@pytest.mark.asyncio
async def test_write_file_creates_subdirs(temp_workspace):
    """Test that writing file creates parent directories."""
    tool = WriteFile(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-write-2",
        name="write_file",
        arguments={
            "path": "data/subdir/test.txt",
            "content": "Nested file"
        }
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    
    # Verify directory structure
    file_path = temp_workspace.root / "data" / "subdir" / "test.txt"
    assert file_path.exists()
    assert file_path.read_text() == "Nested file"


@pytest.mark.asyncio
async def test_write_file_outside_workspace_fails(temp_workspace):
    """Test that writing outside workspace is blocked."""
    tool = WriteFile(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-write-3",
        name="write_file",
        arguments={
            "path": "../outside.txt",
            "content": "Attempt to escape"
        }
    )
    
    result = await tool.call(tool_call)
    
    assert not result.success
    assert "outside workspace" in result.error


@pytest.mark.asyncio
async def test_read_file_in_workspace(temp_workspace):
    """Test reading a file within workspace."""
    # Create a test file
    test_file = temp_workspace.root / "test.txt"
    test_file.write_text("Test content")
    
    tool = ReadFile(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-read-1",
        name="read_file",
        arguments={"path": "test.txt"}
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "Test content" in result.output  # May include header with new format


@pytest.mark.asyncio
async def test_read_nonexistent_file_fails(temp_workspace):
    """Test reading nonexistent file fails gracefully."""
    tool = ReadFile(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-read-2",
        name="read_file",
        arguments={"path": "nonexistent.txt"}
    )
    
    result = await tool.call(tool_call)
    
    assert not result.success
    assert "does not exist" in result.error


@pytest.mark.asyncio
async def test_list_files_in_workspace(temp_workspace):
    """Test listing files in workspace."""
    # Create some test files
    (temp_workspace.root / "file1.txt").write_text("content1")
    (temp_workspace.root / "file2.txt").write_text("content2")
    (temp_workspace.root / "subdir").mkdir()
    
    tool = ListFiles(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-list-1",
        name="list_files",
        # Use absolute path to workspace root since '.' maps to project_root
        arguments={"path": str(temp_workspace.root)}
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "file1.txt" in result.output
    assert "file2.txt" in result.output
    assert "subdir" in result.output


@pytest.mark.asyncio
async def test_list_files_outside_workspace_fails(temp_workspace):
    """Test that listing outside workspace is blocked."""
    tool = ListFiles(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-list-2",
        name="list_files",
        arguments={"path": ".."}
    )
    
    result = await tool.call(tool_call)
    
    assert not result.success
    assert "outside workspace" in result.error


if __name__ == "__main__":
    print("Running file tools workspace tests...")
    pytest.main([__file__, "-v"])
