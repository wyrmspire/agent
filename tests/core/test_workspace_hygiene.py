"""
Tests for Phase 1.5: Workspace hygiene enforcement.

Tests that:
1. Standard bins are created on workspace init
2. Run directories are created correctly
3. Path-in-bin validation works
"""

import pytest
from pathlib import Path
from core.sandb import Workspace


class TestWorkspaceHygiene:
    """Test standard workspace bins (Phase 1.5)."""
    
    def test_standard_bins_created_on_init(self, tmp_path):
        """Standard bins are created when workspace is initialized."""
        ws = Workspace(tmp_path / "workspace")
        
        # All standard bins should exist
        for bin_name in Workspace.STANDARD_BINS:
            bin_path = ws.root / bin_name
            assert bin_path.exists(), f"Bin {bin_name} should exist"
            assert bin_path.is_dir(), f"Bin {bin_name} should be a directory"
    
    def test_standard_bins_not_created_when_disabled(self, tmp_path):
        """Standard bins are not created when disabled."""
        ws = Workspace(tmp_path / "workspace", create_standard_bins=False)
        
        # Only workspace root should exist, not bins
        assert ws.root.exists()
        
        # Bins should NOT exist (unless they already did)
        for bin_name in Workspace.STANDARD_BINS:
            bin_path = ws.root / bin_name
            # They shouldn't exist since we disabled creation
            assert not bin_path.exists()
    
    def test_get_run_dir_creates_directory(self, tmp_path):
        """get_run_dir creates the run directory if it doesn't exist."""
        ws = Workspace(tmp_path / "workspace")
        
        run_id = "run_abc123_20241214"
        run_dir = ws.get_run_dir(run_id)
        
        assert run_dir.exists()
        assert run_dir.is_dir()
        assert run_dir == ws.root / "runs" / run_id
    
    def test_get_run_dir_idempotent(self, tmp_path):
        """get_run_dir is idempotent - calling twice returns same path."""
        ws = Workspace(tmp_path / "workspace")
        
        run_id = "run_test"
        run_dir1 = ws.get_run_dir(run_id)
        run_dir2 = ws.get_run_dir(run_id)
        
        assert run_dir1 == run_dir2
    
    def test_validate_path_in_bin_notes(self, tmp_path):
        """Paths in notes/ bin are identified correctly."""
        ws = Workspace(tmp_path / "workspace")
        
        notes_file = ws.root / "notes" / "summary.md"
        notes_file.parent.mkdir(exist_ok=True)
        notes_file.touch()
        
        assert ws.validate_path_in_bin(notes_file) == "notes"
    
    def test_validate_path_in_bin_runs(self, tmp_path):
        """Paths in runs/ bin are identified correctly."""
        ws = Workspace(tmp_path / "workspace")
        
        run_file = ws.root / "runs" / "run_001" / "output.log"
        run_file.parent.mkdir(parents=True, exist_ok=True)
        run_file.touch()
        
        assert ws.validate_path_in_bin(run_file) == "runs"
    
    def test_validate_path_in_bin_data(self, tmp_path):
        """Paths in data/ bin are identified correctly."""
        ws = Workspace(tmp_path / "workspace")
        
        data_file = ws.root / "data" / "prices.csv"
        data_file.touch()
        
        assert ws.validate_path_in_bin(data_file) == "data"
    
    def test_validate_path_not_in_bin(self, tmp_path):
        """Root-level files are identified as not in a bin."""
        ws = Workspace(tmp_path / "workspace")
        
        # File at workspace root, not in any bin
        root_file = ws.root / "random.txt"
        root_file.touch()
        
        assert ws.validate_path_in_bin(root_file) is None
    
    def test_validate_path_in_bin_relative(self, tmp_path):
        """Relative paths are resolved correctly."""
        ws = Workspace(tmp_path / "workspace")
        
        # Create a file in notes
        notes_file = ws.root / "notes" / "test.md"
        notes_file.touch()
        
        # Use relative path
        rel_path = Path("notes/test.md")
        assert ws.validate_path_in_bin(rel_path) == "notes"
    
    def test_validate_path_in_bin_unknown_folder(self, tmp_path):
        """Files in unknown folders (not standard bins) return None."""
        ws = Workspace(tmp_path / "workspace")
        
        # Create custom folder (not a standard bin)
        custom_dir = ws.root / "custom_outputs"
        custom_dir.mkdir()
        custom_file = custom_dir / "output.txt"
        custom_file.touch()
        
        assert ws.validate_path_in_bin(custom_file) is None
    
    def test_standard_bins_list(self):
        """Standard bins include expected directories."""
        expected_bins = {"repos", "runs", "notes", "patches", "data", "queue", "chunks"}
        actual_bins = set(Workspace.STANDARD_BINS.keys())
        
        assert expected_bins == actual_bins
