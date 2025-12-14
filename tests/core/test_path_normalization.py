"""
Tests for path normalization edge cases (Windows compatibility).

These tests verify that the workspace resolver correctly handles:
- workspace/ prefix stripping
- Case insensitivity on Windows
- Forward/back slash normalization
- Directory traversal blocking
"""

import pytest
import tempfile
import os
from pathlib import Path

from core.sandb import Workspace, WorkspaceError


class TestPathNormalization:
    """Test Windows path edge cases and normalization."""
    
    def test_workspace_prefix_forward_slash(self, tmp_path):
        """workspace/file.txt should resolve to workspace_root/file.txt"""
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        ws = Workspace(ws_root)
        
        # Create a test file
        test_file = ws_root / "test.txt"
        test_file.write_text("hello")
        
        # workspace/test.txt should resolve to ws_root/test.txt (stripping prefix)
        resolved = ws.resolve("workspace/test.txt")
        assert resolved == test_file.resolve()
    
    def test_workspace_prefix_backslash(self, tmp_path):
        """workspace\\file.txt should resolve to workspace_root\\file.txt"""
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        ws = Workspace(ws_root)
        
        test_file = ws_root / "test.txt"
        test_file.write_text("hello")
        
        resolved = ws.resolve("workspace\\test.txt")
        assert resolved == test_file.resolve()
    
    def test_no_prefix_still_works(self, tmp_path):
        """Direct file paths should still work."""
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        ws = Workspace(ws_root)
        
        test_file = ws_root / "test.txt"
        test_file.write_text("hello")
        
        resolved = ws.resolve("test.txt")
        assert resolved == test_file.resolve()
    
    def test_nested_workspace_prefix(self, tmp_path):
        """workspace/subdir/file.txt should work."""
        ws_root = tmp_path / "workspace"
        (ws_root / "subdir").mkdir(parents=True)
        ws = Workspace(ws_root)
        
        test_file = ws_root / "subdir" / "test.txt"
        test_file.write_text("hello")
        
        resolved = ws.resolve("workspace/subdir/test.txt")
        assert resolved == test_file.resolve()
    
    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_case_insensitive_windows(self, tmp_path):
        """C:\\Agent and c:\\agent should be treated as same on Windows."""
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        ws = Workspace(ws_root)
        
        test_file = ws_root / "test.txt"
        test_file.write_text("hello")
        
        # Create upper case path string
        upper_path = str(test_file).upper()
        lower_path = str(test_file).lower()
        
        # Both should resolve without error if normalization works
        upper_resolved = ws.resolve(upper_path)
        lower_resolved = ws.resolve(lower_path)
        
        # They should resolve to the same canonical path (normalized)
        assert upper_resolved.resolve() == lower_resolved.resolve()
    
    def test_slash_normalization(self, tmp_path):
        """Forward and back slashes should be equivalent."""
        ws_root = tmp_path / "workspace"
        subdir = ws_root / "sub"
        subdir.mkdir(parents=True)
        ws = Workspace(ws_root)
        
        test_file = subdir / "test.txt"
        test_file.write_text("hello")
        
        fwd = ws.resolve("sub/test.txt")
        back = ws.resolve("sub\\test.txt")
        assert fwd == back
    
    def test_denied_parent_traversal(self, tmp_path):
        """Paths with .. that escape workspace should be denied."""
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        ws = Workspace(ws_root)
        
        with pytest.raises(WorkspaceError) as exc_info:
            ws.resolve("../secrets.txt")
        
        assert "workspace" in str(exc_info.value).lower()
    
    def test_denied_absolute_outside(self, tmp_path):
        """Absolute paths outside workspace should be denied."""
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        ws = Workspace(ws_root)
        
        with pytest.raises(WorkspaceError):
            # This should definitely be outside any workspace
            if os.name == 'nt':
                ws.resolve("C:\\Windows\\system32\\drivers\\etc\\hosts")
            else:
                ws.resolve("/etc/passwd")
    
    def test_error_message_contains_diagnostic_info(self, tmp_path):
        """Error should contain helpful diagnostic paths."""
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        ws = Workspace(ws_root)
        
        with pytest.raises(WorkspaceError) as exc_info:
            ws.resolve("../escape.txt")
        
        error_msg = str(exc_info.value)
        # Should contain diagnostic info per implementation plan
        assert "requested:" in error_msg or "resolved:" in error_msg
