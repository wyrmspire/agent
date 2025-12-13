"""
tests/store/test_chunks.py - Tests for chunk management

Tests chunk generation, deduplication, and search functionality.
"""

import tempfile
import shutil
from pathlib import Path

from store.chunks import ChunkManager, ChunkMetadata


def test_chunk_python_file():
    """Test chunking a Python file by functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test Python file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def function_one():
    '''First function'''
    return 1

def function_two():
    '''Second function'''
    return 2

class TestClass:
    def method_one(self):
        return "method"
""")
        
        # Create chunk manager
        manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        
        # Ingest file
        count = manager.ingest_file(str(test_file))
        
        # Should create multiple chunks (functions and class)
        assert count > 0
        assert len(manager.chunks) > 0
        
        # Check chunk types
        chunk_types = [c.chunk_type for c in manager.chunks.values()]
        assert "function" in chunk_types or "class" in chunk_types


def test_chunk_markdown_file():
    """Test chunking a Markdown file by sections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test Markdown file
        test_file = Path(tmpdir) / "test.md"
        test_file.write_text("""
# Header One

Content for section one.

## Header Two

Content for section two.

### Header Three

More content.
""")
        
        # Create chunk manager
        manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        
        # Ingest file
        count = manager.ingest_file(str(test_file))
        
        # Should create chunks for each header
        assert count > 0
        assert len(manager.chunks) > 0
        
        # Check that sections have names
        named_chunks = [c for c in manager.chunks.values() if c.name]
        assert len(named_chunks) > 0


def test_chunk_deduplication():
    """Test that duplicate chunks are not added."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        content = "def test(): return 1"
        test_file.write_text(content)
        
        # Create chunk manager
        manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        
        # Ingest file twice
        count1 = manager.ingest_file(str(test_file))
        count2 = manager.ingest_file(str(test_file))
        
        # Second ingest should not add duplicates
        assert count1 > 0
        assert count2 == 0


def test_sensitive_file_exclusion():
    """Test that sensitive files are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create sensitive files
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("SECRET=12345")
        
        password_file = Path(tmpdir) / "password.txt"
        password_file.write_text("password123")
        
        # Create chunk manager
        manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        
        # Ingest files
        count1 = manager.ingest_file(str(env_file))
        count2 = manager.ingest_file(str(password_file))
        
        # Should not ingest sensitive files
        assert count1 == 0
        assert count2 == 0


def test_search_chunks():
    """Test searching chunks by keyword."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file with specific content
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def calculate_rsi(prices):
    '''Calculate Relative Strength Index'''
    return rsi_value

def calculate_macd(prices):
    '''Calculate Moving Average Convergence Divergence'''
    return macd_value
""")
        
        # Create chunk manager and ingest
        manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        manager.ingest_file(str(test_file))
        
        # Search for "rsi"
        results = manager.search_chunks("rsi", k=10)
        
        # Should find relevant chunk
        assert len(results) > 0
        assert any("rsi" in r["content"].lower() for r in results)
        
        # Search for "macd"
        results = manager.search_chunks("macd", k=10)
        assert len(results) > 0
        assert any("macd" in r["content"].lower() for r in results)


def test_search_with_filters():
    """Test searching with filters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Python and Markdown files
        py_file = Path(tmpdir) / "code.py"
        py_file.write_text("def test(): pass")
        
        md_file = Path(tmpdir) / "docs.md"
        md_file.write_text("# Test\nThis is a test document.")
        
        # Create chunk manager and ingest
        manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        manager.ingest_file(str(py_file))
        manager.ingest_file(str(md_file))
        
        # Search with Python filter
        results = manager.search_chunks(
            "test",
            k=10,
            filters={"file_type": ".py"}
        )
        
        # Should only return Python chunks
        assert all(r["source_path"].endswith(".py") for r in results)
        
        # Search with Markdown filter
        results = manager.search_chunks(
            "test",
            k=10,
            filters={"file_type": ".md"}
        )
        
        # Should only return Markdown chunks
        assert all(r["source_path"].endswith(".md") for r in results)


def test_manifest_persistence():
    """Test saving and loading manifest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def test(): return 1")
        
        manifest_path = Path(tmpdir) / "manifest.json"
        
        # Create manager and ingest
        manager1 = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(manifest_path),
        )
        manager1.ingest_file(str(test_file))
        chunk_count1 = len(manager1.chunks)
        
        # Save manifest
        assert manager1.save_manifest()
        assert manifest_path.exists()
        
        # Create new manager and load
        manager2 = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(manifest_path),
        )
        
        # Should load chunks from manifest
        assert len(manager2.chunks) == chunk_count1


def test_get_chunk_by_id():
    """Test retrieving chunk by ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def example(): return 42")
        
        # Create manager and ingest
        manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        manager.ingest_file(str(test_file))
        
        # Get first chunk ID
        chunk_id = list(manager.chunks.keys())[0]
        
        # Retrieve chunk
        chunk_data = manager.get_chunk(chunk_id)
        
        assert chunk_data is not None
        assert chunk_data["chunk_id"] == chunk_id
        assert "content" in chunk_data
        assert "source_path" in chunk_data


def test_chunk_statistics():
    """Test getting chunk statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        py_file = Path(tmpdir) / "test.py"
        py_file.write_text("def test(): pass")
        
        md_file = Path(tmpdir) / "test.md"
        md_file.write_text("# Test\nContent")
        
        # Create manager and ingest
        manager = ChunkManager(
            chunks_dir=str(Path(tmpdir) / "chunks"),
            manifest_path=str(Path(tmpdir) / "manifest.json"),
        )
        manager.ingest_file(str(py_file))
        manager.ingest_file(str(md_file))
        
        # Get stats
        stats = manager.get_stats()
        
        assert stats["total_chunks"] > 0
        assert "chunk_types" in stats
        assert "manifest_path" in stats


if __name__ == "__main__":
    # Run tests
    test_chunk_python_file()
    print("✓ test_chunk_python_file")
    
    test_chunk_markdown_file()
    print("✓ test_chunk_markdown_file")
    
    test_chunk_deduplication()
    print("✓ test_chunk_deduplication")
    
    test_sensitive_file_exclusion()
    print("✓ test_sensitive_file_exclusion")
    
    test_search_chunks()
    print("✓ test_search_chunks")
    
    test_search_with_filters()
    print("✓ test_search_with_filters")
    
    test_manifest_persistence()
    print("✓ test_manifest_persistence")
    
    test_get_chunk_by_id()
    print("✓ test_get_chunk_by_id")
    
    test_chunk_statistics()
    print("✓ test_chunk_statistics")
    
    print("\nAll chunk tests passed!")
