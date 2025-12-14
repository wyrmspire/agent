"""
tests/vectorgit/test_ingest.py - VectorGit Ingestion Tests

Verifies that VectorGit correctly ingests chunks from files and directories.
"""

import pytest
from pathlib import Path
from tool.vectorgit import VectorGit


class TestVectorGitIngest:
    """Tests for VectorGit ingestion."""

    @pytest.fixture
    def test_repo(self, tmp_path):
        """Create a dummy repo for testing."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        
        # Create a python file
        py_file = repo_dir / "example.py"
        py_file.write_text("def hello():\n    print('Hello World')\n")
        
        # Create a markdown file
        md_file = repo_dir / "README.md"
        md_file.write_text("# Title\n\nSection 1\nContent 1\n")
        
        # Create a subdir
        subdir = repo_dir / "utils"
        subdir.mkdir()
        sub_file = subdir / "helper.py"
        sub_file.write_text("class Helper:\n    pass\n")
        
        return repo_dir

    @pytest.fixture
    def vg(self, tmp_path):
        """Create a VectorGit instance."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return VectorGit(workspace_path=str(workspace))

    def test_ingest_directory(self, vg, test_repo):
        """Test recursive directory ingestion."""
        print(f"Ingesting from: {test_repo}")
        count = vg.ingest(str(test_repo))
        print(f"Ingested count: {count}")
        
        # Check chunk count (1 function + 1 md section + 1 class)
        # Note: exact count depends on chunker logic, but should be > 0
        assert count >= 3
        
        # Check manifest exists
        assert vg.manifest_path.exists()
        
        # Query to verify content is indexed
        results = vg.query("hello")
        assert len(results) >= 1
        assert "example.py" in results[0]["source_path"]

    def test_ingest_single_file(self, vg, test_repo):
        """Test single file ingestion."""
        file_path = test_repo / "example.py"
        count = vg.ingest(str(file_path))
        
        assert count == 1  # 1 function chunk
        results = vg.query("hello")
        assert len(results) == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
