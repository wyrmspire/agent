"""
Tests for Phase 1.3: Atomic Writes and Corruption Detection

Tests crash safety and self-healing capabilities.
"""

import tempfile
import shutil
import json
import numpy as np
from pathlib import Path

from store.vectors import VectorStore, CorruptedIndexError
from store.chunks import ChunkManager


class TestAtomicWrites:
    """Test atomic write operations for crash safety."""
    
    def test_vector_store_atomic_write(self):
        """Test that VectorStore uses atomic writes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(store_path=tmpdir)
            
            # Add some vectors
            chunk_ids = ["chunk_1", "chunk_2", "chunk_3"]
            embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
            store.add(chunk_ids, embeddings, model_name="test_model")
            
            # Save
            assert store.save()
            
            # Verify files exist
            vectors_path = Path(tmpdir) / "embeddings.npz"
            manifest_path = Path(tmpdir) / "vectors_manifest.json"
            assert vectors_path.exists()
            assert manifest_path.exists()
            
            # Verify no .tmp files remain
            tmp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(tmp_files) == 0, f"Temp files not cleaned up: {tmp_files}"
    
    def test_chunk_manager_atomic_write(self):
        """Test that ChunkManager uses atomic writes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks_dir = Path(tmpdir) / "chunks"
            manifest_path = Path(tmpdir) / "manifest.json"
            
            manager = ChunkManager(
                chunks_dir=str(chunks_dir),
                manifest_path=str(manifest_path)
            )
            
            # Create a test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello():\n    return 'world'\n")
            
            # Ingest
            manager.ingest_file(str(test_file))
            
            # Save
            assert manager.save_manifest()
            
            # Verify no .tmp files remain
            tmp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(tmp_files) == 0, f"Temp files not cleaned up: {tmp_files}"
    
    def test_corruption_detection(self):
        """Test that corruption is detected on load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(store_path=tmpdir)
            
            # Add vectors
            chunk_ids = ["chunk_1", "chunk_2", "chunk_3"]
            embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
            store.add(chunk_ids, embeddings, model_name="test_model")
            store.save()
            
            # Corrupt the manifest (remove a chunk ID)
            manifest_path = Path(tmpdir) / "vectors_manifest.json"
            with open(manifest_path, "r") as f:
                data = json.load(f)
            data["chunk_ids"] = ["chunk_1", "chunk_2"]  # Missing chunk_3
            data["count"] = 2  # Wrong count
            with open(manifest_path, "w") as f:
                json.dump(data, f)
            
            # Try to load - should raise CorruptedIndexError
            try:
                store2 = VectorStore(store_path=tmpdir)
                assert False, "Should have raised CorruptedIndexError"
            except CorruptedIndexError as e:
                assert "Corruption Detected" in str(e)
                assert "vectors=3" in str(e)
                assert "chunk_ids=2" in str(e)
    
    def test_vector_count_mismatch_detection(self):
        """Test detection of count mismatch between metadata and actual vectors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(store_path=tmpdir)
            
            # Add vectors
            chunk_ids = ["chunk_1", "chunk_2"]
            embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            store.add(chunk_ids, embeddings, model_name="test_model")
            store.save()
            
            # Corrupt manifest count
            manifest_path = Path(tmpdir) / "vectors_manifest.json"
            with open(manifest_path, "r") as f:
                data = json.load(f)
            data["count"] = 5  # Wrong count
            with open(manifest_path, "w") as f:
                json.dump(data, f)
            
            # Should detect corruption
            try:
                store2 = VectorStore(store_path=tmpdir)
                assert False, "Should have raised CorruptedIndexError"
            except CorruptedIndexError as e:
                assert "Corruption Detected" in str(e)


class TestSelfHealing:
    """Test self-healing capabilities."""
    
    def test_auto_heal_on_init(self):
        """Test that VectorGit can initialize with auto_heal=True on corruption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from tool.vectorgit import VectorGit
            
            # Create and corrupt a vector store
            vg = VectorGit(workspace_path=tmpdir, index_name="test_index")
            
            # Add some test data manually
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello():\n    return 'world'\n")
            vg.chunk_manager.ingest_file(str(test_file))
            vg.chunk_manager.save_manifest()
            
            # Manually corrupt vectors
            vectors_path = Path(tmpdir) / "test_index" / "vectors"
            vectors_path.mkdir(parents=True, exist_ok=True)
            
            # Create mismatched vector store
            manifest = vectors_path / "vectors_manifest.json"
            manifest.write_text(json.dumps({
                "chunk_ids": ["chunk_1", "chunk_2"],
                "count": 2,
                "dim": 3,
                "embedding_model": "test",
                "normalized": True,
                "updated_at": "2024-01-01T00:00:00Z"
            }))
            
            # Create vectors with wrong count
            vectors = np.array([[0.1, 0.2, 0.3]])  # Only 1 vector, not 2
            np.savez_compressed(vectors_path / "embeddings.npz", vectors=vectors)
            
            # Initialize with auto_heal - should not crash
            vg2 = VectorGit(workspace_path=tmpdir, index_name="test_index", auto_heal=True)
            assert vg2.corruption_detected == True
            assert vg2.vector_store is not None
    
    def test_auto_heal_disabled(self):
        """Test that auto_heal=False raises error on corruption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from tool.vectorgit import VectorGit
            
            # Create corrupted store
            vectors_path = Path(tmpdir) / "test_index" / "vectors"
            vectors_path.mkdir(parents=True, exist_ok=True)
            
            manifest = vectors_path / "vectors_manifest.json"
            manifest.write_text(json.dumps({
                "chunk_ids": ["chunk_1", "chunk_2"],
                "count": 2,
                "dim": 3,
                "embedding_model": "test",
                "normalized": True,
                "updated_at": "2024-01-01T00:00:00Z"
            }))
            
            vectors = np.array([[0.1, 0.2, 0.3]])
            np.savez_compressed(vectors_path / "embeddings.npz", vectors=vectors)
            
            # Should raise
            try:
                vg = VectorGit(workspace_path=tmpdir, index_name="test_index", auto_heal=False)
                assert False, "Should have raised CorruptedIndexError"
            except CorruptedIndexError:
                pass  # Expected
