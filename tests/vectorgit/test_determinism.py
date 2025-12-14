"""
tests/vectorgit/test_determinism.py - VectorGit Determinism Tests

Verifies that ingesting the same content produces identical chunk IDs.
Crucial for reliable citations in Phase 0.8.
"""

import pytest
import tempfile
from pathlib import Path
from tool.vectorgit import VectorGit


class TestVectorGitDeterminism:
    """Tests for ingestion determinism."""
    
    def test_reingest_determinism(self, tmp_path):
        """Test that re-ingesting content produces same IDs."""
        
        content = "def sensitive_logic():\n    return 'safe_value'\n"
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "safe.py").write_text(content)
        
        # First ingest
        ws1 = tmp_path / "ws1"
        ws1.mkdir()
        vg1 = VectorGit(workspace_path=str(ws1))
        vg1.ingest(str(repo_dir))
        chunks1 = vg1.query("safe_value")
        ids1 = sorted([c["chunk_id"] for c in chunks1])
        
        # Second ingest (different workspace)
        ws2 = tmp_path / "ws2"
        ws2.mkdir()
        vg2 = VectorGit(workspace_path=str(ws2))
        vg2.ingest(str(repo_dir))
        chunks2 = vg2.query("safe_value")
        ids2 = sorted([c["chunk_id"] for c in chunks2])
        
        # Assertions
        assert len(ids1) > 0
        assert len(ids1) == len(ids2)
        assert ids1 == ids2, f"IDs differ: {set(ids1) ^ set(ids2)}"

    def test_chunk_consistency_over_timesteps(self, tmp_path):
        """Test that re-ingesting SAME file doesn't duplicate chunks."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "file.py").write_text("def foo():\n    pass\n")
        
        ws = tmp_path / "workspace"
        ws.mkdir()
        vg = VectorGit(workspace_path=str(ws))
        
        # Run 1
        vg.ingest(str(repo_dir))
        count1 = len(vg.chunk_manager.chunks)
        
        # Run 2 (same content)
        vg.ingest(str(repo_dir))
        count2 = len(vg.chunk_manager.chunks)
        
        assert count1 == count2, "Re-ingesting same content should not increase chunk count"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
