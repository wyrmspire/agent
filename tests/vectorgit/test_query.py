"""
tests/vectorgit/test_query.py - VectorGit retrieval tests

Verifies that keyword retrieval returns relevant chunks.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from tool.vectorgit import VectorGit


class TestVectorGitQuery:
    """Tests for VectorGit retrieval accuracy."""
    
    @pytest.fixture
    def vg_with_data(self):
        """Create VectorGit instance with known data using tempfile directly."""
        tmp_dir = tempfile.mkdtemp()
        tmp_path = Path(tmp_dir)
        
        try:
            repo_dir = tmp_path / "repo"
            repo_dir.mkdir()
            
            # File 1: Database logic
            (repo_dir / "db.py").write_text("""
def connect_db():
    print('Connecting to postgres')
    return True

def query_users():
    return 'SELECT * FROM users'
""")
            
            # File 2: UI logic
            (repo_dir / "ui.py").write_text("""
def render_button():
    print('Rendering submit button')
    
def handle_click():
    print('Button clicked')
""")
            
            ws = tmp_path / "workspace"
            ws.mkdir()
            vg = VectorGit(workspace_path=str(ws))
            vg.ingest(str(repo_dir))
            
            yield vg
            
        finally:
            shutil.rmtree(tmp_dir)

    def test_query_keywords(self, vg_with_data):
        """Test retrieving by specific unique keywords."""
        
        # Search for DB concept
        results = vg_with_data.query("postgres")
        assert len(results) >= 1
        assert results[0]["name"] == "connect_db"
        assert "db.py" in results[0]["source_path"]
        
        # Search for UI concept
        results = vg_with_data.query("button")
        assert len(results) >= 1
        assert "ui.py" in results[0]["source_path"]

    def test_query_no_results(self, vg_with_data):
        """Test querying for nonexistent term."""
        results = vg_with_data.query("banana_split")
        assert len(results) == 0

    def test_query_context_snippet(self, vg_with_data):
        """Test that results include correct snippets."""
        results = vg_with_data.query("users")
        assert len(results) > 0
        snippet = results[0]["snippet"]
        assert "users" in snippet.lower()
        assert "..." in snippet or len(snippet) < 200

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
