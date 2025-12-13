"""
tests/tools/test_dview.py - Data View Tool Tests

This module tests the data view tool for inspecting large files:
- Reading CSV head/tail
- Getting shape and columns
- Working within workspace
"""

import pytest
import tempfile
import shutil
import csv
from pathlib import Path

from core.sandb import Workspace
from tool.dview import DataViewTool
from core.types import ToolCall


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with test data."""
    temp_dir = tempfile.mkdtemp()
    workspace = Workspace(temp_dir)
    
    # Create a test CSV file
    csv_path = workspace.root / "test_data.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        for i in range(100):
            writer.writerow([
                f'2024-01-{i+1:02d}',
                100 + i,
                105 + i,
                95 + i,
                102 + i,
                1000 + i * 10
            ])
    
    yield workspace
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_csv_columns(temp_workspace):
    """Test getting column names from CSV."""
    tool = DataViewTool(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-cols-1",
        name="data_view",
        arguments={
            "path": "test_data.csv",
            "operation": "columns"
        }
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "timestamp" in result.output
    assert "open" in result.output
    assert "close" in result.output
    assert "volume" in result.output


@pytest.mark.asyncio
async def test_csv_head(temp_workspace):
    """Test getting first N rows from CSV."""
    tool = DataViewTool(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-head-1",
        name="data_view",
        arguments={
            "path": "test_data.csv",
            "operation": "head",
            "n_rows": 3
        }
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "timestamp" in result.output  # Header
    assert "2024-01-01" in result.output  # First row
    assert "2024-01-03" in result.output  # Third row


@pytest.mark.asyncio
async def test_csv_tail(temp_workspace):
    """Test getting last N rows from CSV."""
    tool = DataViewTool(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-tail-1",
        name="data_view",
        arguments={
            "path": "test_data.csv",
            "operation": "tail",
            "n_rows": 3
        }
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    # Should show last 3 rows (98, 99, 100)
    assert "100" in result.output  # Row 100


@pytest.mark.asyncio
async def test_csv_shape(temp_workspace):
    """Test getting shape (rows × columns) from CSV."""
    tool = DataViewTool(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-shape-1",
        name="data_view",
        arguments={
            "path": "test_data.csv",
            "operation": "shape"
        }
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "100 rows" in result.output  # 100 data rows
    assert "6 columns" in result.output  # 6 columns


@pytest.mark.asyncio
async def test_unsupported_file_type(temp_workspace):
    """Test that unsupported file types are rejected."""
    # Create a text file
    (temp_workspace.root / "test.txt").write_text("not a data file")
    
    tool = DataViewTool(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-unsupported-1",
        name="data_view",
        arguments={
            "path": "test.txt",
            "operation": "head"
        }
    )
    
    result = await tool.call(tool_call)
    
    assert not result.success
    assert "Unsupported file type" in result.error


@pytest.mark.asyncio
async def test_nonexistent_file(temp_workspace):
    """Test that nonexistent files are handled gracefully."""
    tool = DataViewTool(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-nonexist-1",
        name="data_view",
        arguments={
            "path": "nonexistent.csv",
            "operation": "head"
        }
    )
    
    result = await tool.call(tool_call)
    
    assert not result.success
    assert "does not exist" in result.error


@pytest.mark.asyncio
async def test_file_outside_workspace(temp_workspace):
    """Test that files outside workspace are blocked."""
    tool = DataViewTool(workspace=temp_workspace)
    
    tool_call = ToolCall(
        id="test-outside-1",
        name="data_view",
        arguments={
            "path": "../outside.csv",
            "operation": "head"
        }
    )
    
    result = await tool.call(tool_call)
    
    assert not result.success
    assert "outside workspace" in result.error


if __name__ == "__main__":
    print("Running data view tool tests...")
    pytest.main([__file__, "-v"])
