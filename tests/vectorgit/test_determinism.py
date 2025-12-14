
import pytest
import shutil
from pathlib import Path
from store.chunks import ChunkManager

@pytest.fixture
def temp_chunk_env(tmp_path):
    """Create a temporary environment for chunk testing."""
    chunks_dir = tmp_path / "chunks"
    manifest_path = tmp_path / "manifest.json"
    manager = ChunkManager(
        chunks_dir=str(chunks_dir),
        manifest_path=str(manifest_path)
    )
    return manager, tmp_path

def test_reingest_produces_identical_ids(temp_chunk_env):
    """Test that re-ingesting the same content produces identical chunk IDs."""
    manager, root = temp_chunk_env
    
    # Create a source file
    source_file = root / "test_code.py"
    source_content = """
def hello():
    print("Hello world")

class Greeter:
    def greet(self):
        return "Hi"
"""
    source_file.write_text(source_content)
    
    # First ingestion
    manager.ingest_file(str(source_file))
    first_chunks = {c.id: c for c in manager.chunks.values()}
    
    assert len(first_chunks) > 0, "Should have created chunks"
    
    # Store IDs
    first_ids = set(first_chunks.keys())
    
    # Re-initialize manager (simulating restart)
    new_manager = ChunkManager(
        chunks_dir=str(manager.chunks_dir),
        manifest_path=str(manager.manifest_path)
    )
    
    # Re-ingest
    new_manager.ingest_file(str(source_file))
    second_chunks = {c.id: c for c in new_manager.chunks.values()}
    second_ids = set(second_chunks.keys())
    
    # Assert identity
    assert first_ids == second_ids, "Chunk IDs must be deterministic across runs"
    
    # Verify content match
    for chunk_id in first_ids:
        chunk1 = first_chunks[chunk_id]
        chunk2 = second_chunks[chunk_id]
        
        assert chunk1.hash == chunk2.hash
        assert chunk1.start_line == chunk2.start_line

def test_search_ranking_determinism(temp_chunk_env):
    """Test that search results are deterministically ranked."""
    manager, root = temp_chunk_env
    
    # Create two files with similar content but different paths
    # Create two files with DIFFERENT content but SAME keyword count
    file1 = root / "a_file.py"
    file1.write_text("def func_a():\n    # unique keyword\n    pass")
    
    file2 = root / "b_file.py" 
    file2.write_text("def func_b():\n    # unique keyword\n    pass")
    
    manager.ingest_file(str(file1))
    manager.ingest_file(str(file2))
    
    # Query for keyword
    results = manager.search_chunks("unique keyword", k=10)
    
    assert len(results) >= 2
    
    # Expected order: by count (same), then by path (asc)
    # a_file.py should come before b_file.py
    assert "a_file.py" in str(results[0]["source_path"])
    assert "b_file.py" in str(results[1]["source_path"])
