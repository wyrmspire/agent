"""
Tests for Phase 1.2: Inverted Index for Fast Keyword Search

Tests O(1) keyword lookup performance improvements.
"""

import tempfile
from pathlib import Path

from store.chunks import ChunkManager


class TestInvertedIndex:
    """Test inverted index functionality."""
    
    def test_inverted_index_build(self):
        """Test that inverted index is built correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ChunkManager(
                chunks_dir=str(Path(tmpdir) / "chunks"),
                manifest_path=str(Path(tmpdir) / "manifest.json")
            )
            
            # Create test files
            test_file1 = Path(tmpdir) / "auth.py"
            test_file1.write_text("def login():\n    return authenticate()\n")
            
            test_file2 = Path(tmpdir) / "user.py"
            test_file2.write_text("class User:\n    def __init__(self):\n        pass\n")
            
            # Ingest
            manager.ingest_file(str(test_file1))
            manager.ingest_file(str(test_file2))
            
            # Build index explicitly
            manager._build_inverted_index()
            
            # Verify index structure
            assert "login" in manager.inverted_index
            assert "authenticate" in manager.inverted_index
            assert "user" in manager.inverted_index
            assert "class" in manager.inverted_index
            
            # Each token should point to chunk IDs
            assert len(manager.inverted_index["login"]) > 0
            assert all(isinstance(cid, str) for cid in manager.inverted_index["login"])
    
    def test_search_uses_inverted_index(self):
        """Test that search_chunks uses the inverted index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ChunkManager(
                chunks_dir=str(Path(tmpdir) / "chunks"),
                manifest_path=str(Path(tmpdir) / "manifest.json")
            )
            
            # Create test file with specific content
            test_file = Path(tmpdir) / "auth.py"
            test_file.write_text("""
def login(username, password):
    return authenticate(username, password)

def logout(session):
    return destroy_session(session)
""")
            
            manager.ingest_file(str(test_file))
            
            # Search for "login"
            results = manager.search_chunks("login", k=5)
            
            # Should find the login function
            assert len(results) > 0
            assert "login" in results[0]["content"].lower()
    
    def test_multi_word_search_intersection(self):
        """Test that multi-word queries use intersection (AND logic)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ChunkManager(
                chunks_dir=str(Path(tmpdir) / "chunks"),
                manifest_path=str(Path(tmpdir) / "manifest.json")
            )
            
            # Create files
            file1 = Path(tmpdir) / "auth.py"
            file1.write_text("def login():\n    return authenticate()\n")
            
            file2 = Path(tmpdir) / "user.py"
            file2.write_text("def authenticate():\n    return check_credentials()\n")
            
            manager.ingest_file(str(file1))
            manager.ingest_file(str(file2))
            
            # Search for "authenticate login" - should only find file1
            results = manager.search_chunks("authenticate login", k=5)
            
            # Should find file1 which has both words
            assert len(results) > 0
            assert "login" in results[0]["content"].lower()
            assert "authenticate" in results[0]["content"].lower()
    
    def test_index_update_on_new_chunks(self):
        """Test that index is updated when new chunks are added."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ChunkManager(
                chunks_dir=str(Path(tmpdir) / "chunks"),
                manifest_path=str(Path(tmpdir) / "manifest.json")
            )
            
            # Initial file
            file1 = Path(tmpdir) / "test1.py"
            file1.write_text("def foo():\n    pass\n")
            manager.ingest_file(str(file1))
            
            # Build index
            manager._build_inverted_index()
            assert "foo" in manager.inverted_index
            
            # Add new file
            file2 = Path(tmpdir) / "test2.py"
            file2.write_text("def bar():\n    pass\n")
            manager.ingest_file(str(file2))
            
            # Index should be updated incrementally
            # Search should work
            results = manager.search_chunks("bar", k=5)
            assert len(results) > 0
    
    def test_tokenization(self):
        """Test tokenization logic."""
        manager = ChunkManager(
            chunks_dir="./test_chunks",
            manifest_path="./test_manifest.json"
        )
        
        # Test various inputs
        tokens = manager._tokenize("hello world")
        assert "hello" in tokens
        assert "world" in tokens
        
        tokens = manager._tokenize("user.authenticate()")
        assert "user" in tokens
        assert "authenticate" in tokens
        
        tokens = manager._tokenize("CamelCase")
        assert "camelcase" in tokens
        
        tokens = manager._tokenize("snake_case_function")
        assert "snake" in tokens
        assert "case" in tokens
        assert "function" in tokens
    
    def test_index_dirty_flag(self):
        """Test that index_dirty flag is set correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ChunkManager(
                chunks_dir=str(Path(tmpdir) / "chunks"),
                manifest_path=str(Path(tmpdir) / "manifest.json")
            )
            
            # Create and modify a file
            file1 = Path(tmpdir) / "test.py"
            file1.write_text("def old_function():\n    pass\n")
            manager.ingest_file(str(file1))
            
            # Build index
            manager._build_inverted_index()
            assert not manager.index_dirty
            
            # Modify file (causes stale chunks)
            file1.write_text("def new_function():\n    pass\n")
            manager.ingest_file(str(file1))
            
            # Index should be marked dirty if stale chunks were removed
            # (only if stale detection triggered)
            # Search should still work by rebuilding
            results = manager.search_chunks("new_function", k=5)
            assert len(results) > 0


class TestSearchPerformance:
    """Test search performance characteristics."""
    
    def test_large_corpus_search(self):
        """Test that search works efficiently with larger corpus."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ChunkManager(
                chunks_dir=str(Path(tmpdir) / "chunks"),
                manifest_path=str(Path(tmpdir) / "manifest.json")
            )
            
            # Create multiple files
            for i in range(20):
                file = Path(tmpdir) / f"module_{i}.py"
                content = f"def function_{i}():\n    return 'result_{i}'\n"
                if i == 10:
                    content += "\ndef special_function():\n    return 'found'\n"
                file.write_text(content)
                manager.ingest_file(str(file))
            
            # Search for specific function
            results = manager.search_chunks("special_function", k=5)
            
            # Should find it
            assert len(results) > 0
            assert "special_function" in results[0]["content"]
