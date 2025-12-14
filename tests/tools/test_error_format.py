"""
tests/tools/test_error_format.py - Error Taxonomy Tests

Verifies that file tool errors follow the BlockedBy taxonomy.
"""

import asyncio
import pytest

from core.sandb import Workspace
from tool.files import ListFiles, ReadFile, WriteFile


class TestFileToolErrorFormat:
    """Tests that file tools use BlockedBy error taxonomy."""
    
    @pytest.fixture
    def workspace(self, tmp_path):
        """Create a test workspace."""
        ws_path = tmp_path / "workspace"
        ws_path.mkdir()
        return Workspace(str(ws_path))
    
    def test_list_files_not_directory_error(self, workspace, tmp_path):
        """Test that list_files error includes BlockedBy taxonomy."""
        # Create a file (not directory)
        test_file = workspace.root / "test.txt"
        test_file.write_text("content")
        
        tool = ListFiles(workspace=workspace)
        result = asyncio.run(tool.execute({"path": "test.txt"}))
        
        assert not result.success
        assert "ERROR [NOT_A_DIRECTORY]" in result.error
        assert "Blocked by: missing" in result.error
    
    def test_read_file_not_found_error(self, workspace):
        """Test that read_file error includes BlockedBy taxonomy."""
        # Create a file to ensure workspace is valid, then try to read nonexistent sibling
        existing_file = workspace.root / "existing.txt"
        existing_file.write_text("exists")
        
        tool = ReadFile(workspace=workspace)
        # Read the existing file first to confirm setup, then try nonexistent
        result = asyncio.run(tool.execute({"path": "nonexistent.txt"}))
        
        assert not result.success
        # Could be NOT_A_FILE or PATH_OUTSIDE_WORKSPACE depending on resolve behavior
        assert "ERROR [" in result.error
        assert "Blocked by:" in result.error
    
    def test_read_file_outside_workspace_error(self, workspace):
        """Test that workspace violation errors are shaped."""
        tool = ReadFile(workspace=workspace)
        result = asyncio.run(tool.execute({"path": "../../../etc/passwd"}))
        
        assert not result.success
        assert "ERROR [PATH_OUTSIDE_WORKSPACE]" in result.error
        assert "Blocked by: workspace" in result.error
    
    def test_write_file_outside_workspace_error(self, workspace):
        """Test that write outside workspace is blocked with taxonomy."""
        tool = WriteFile(workspace=workspace)
        result = asyncio.run(tool.execute({
            "path": "../../../tmp/malicious.txt",
            "content": "bad content",
        }))
        
        assert not result.success
        assert "ERROR [PATH_OUTSIDE_WORKSPACE]" in result.error
        assert "Blocked by: workspace" in result.error
    
    def test_write_file_success(self, workspace):
        """Test that successful write doesn't have error."""
        tool = WriteFile(workspace=workspace)
        result = asyncio.run(tool.execute({
            "path": "test_output.txt",
            "content": "hello world",
        }))
        
        assert result.success
        assert result.error is None
        assert "Successfully wrote" in result.output
    
    def test_error_format_has_context(self, workspace):
        """Test that errors include context information."""
        tool = ReadFile(workspace=workspace)
        result = asyncio.run(tool.execute({"path": "missing_file.txt"}))
        
        assert not result.success
        # Context should be included in error
        assert "Context:" in result.error
        assert "missing_file.txt" in result.error


class TestErrorConsistency:
    """Tests that all file tools follow consistent error format."""
    
    @pytest.fixture
    def workspace(self, tmp_path):
        ws_path = tmp_path / "workspace"
        ws_path.mkdir()
        return Workspace(str(ws_path))
    
    def test_all_tools_have_error_code_format(self, workspace):
        """Test that failed tool calls have ERROR [CODE] format."""
        tools = [
            (ListFiles(workspace=workspace), {"path": "nonexistent_dir"}),
            (ReadFile(workspace=workspace), {"path": "nonexistent.txt"}),
            (WriteFile(workspace=workspace), {"path": "../forbidden.txt", "content": "x"}),
        ]
        
        for tool, args in tools:
            result = asyncio.run(tool.execute(args))
            if not result.success:
                assert "ERROR [" in result.error, \
                    f"{tool.name} error missing ERROR [CODE] format: {result.error}"
                assert "Blocked by:" in result.error, \
                    f"{tool.name} error missing Blocked by: {result.error}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
