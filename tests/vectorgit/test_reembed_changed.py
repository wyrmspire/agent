import unittest
import shutil
import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tool.vectorgit import VectorGit


class TestReEmbedChanged(unittest.TestCase):
    """Test that modified files get fresh embeddings."""
    
    def setUp(self):
        self.test_dir = Path("workspace/test_reembed")
        self.repo_dir = self.test_dir / "repo"
        
        # Clean up
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Create initial file
        (self.repo_dir / "data.py").write_text("def get_foo():\n    return 'foo'")
        
        # Initialize VectorGit (no embedding gateway for unit test)
        self.vg = VectorGit(
            workspace_path=str(self.test_dir),
            index_name="reembed_test"
        )
    
    def test_stale_detection_on_file_change(self):
        """Test that changing a file marks old chunks as stale."""
        # 1. Ingest original
        count1 = self.vg.ingest(str(self.repo_dir))
        self.assertGreater(count1, 0)
        
        # Get original chunk IDs
        original_ids = set(self.vg.chunk_manager.chunks.keys())
        self.assertEqual(len(original_ids), 1)
        
        # 2. Modify file
        (self.repo_dir / "data.py").write_text("def get_bar():\n    return 'bar'")
        
        # 3. Re-ingest
        count2 = self.vg.ingest(str(self.repo_dir))
        self.assertGreater(count2, 0)
        
        # 4. Verify stale detection worked
        new_ids = set(self.vg.chunk_manager.chunks.keys())
        
        # Original IDs should NOT be in new set (content changed = new hash = new ID)
        self.assertEqual(len(original_ids & new_ids), 0, "Old chunk IDs should be replaced")
        
        # New chunks should exist
        self.assertEqual(len(new_ids), 1)
        
    def test_keyword_search_finds_new_content(self):
        """Test that keyword search returns new content, not old."""
        # 1. Ingest original
        self.vg.ingest(str(self.repo_dir))
        
        # Search for "foo"
        results_foo = self.vg.query("foo")
        self.assertEqual(len(results_foo), 1)
        
        # 2. Modify file to "bar"
        (self.repo_dir / "data.py").write_text("def get_bar():\n    return 'bar'")
        self.vg.ingest(str(self.repo_dir))
        
        # 3. Search for "foo" should find nothing
        results_foo_after = self.vg.query("foo")
        self.assertEqual(len(results_foo_after), 0, "Old content should not be found")
        
        # 4. Search for "bar" should find the new content
        results_bar = self.vg.query("bar")
        self.assertEqual(len(results_bar), 1, "New content should be found")

    def test_stale_detection_survives_restart(self):
        """Test that stale detection works after simulated restart (reload from manifest)."""
        # 1. Ingest original
        self.vg.ingest(str(self.repo_dir))
        self.vg.chunk_manager.save_manifest()
        
        original_ids = set(self.vg.chunk_manager.chunks.keys())
        
        # 2. Simulate restart by creating new VectorGit instance
        vg2 = VectorGit(
            workspace_path=str(self.test_dir),
            index_name="reembed_test"
        )
        
        # Verify manifest was loaded with source_to_chunks
        self.assertGreater(len(vg2.chunk_manager.source_to_chunks), 0, "source_to_chunks should be loaded")
        
        # 3. Modify file
        (self.repo_dir / "data.py").write_text("def get_baz():\n    return 'baz'")
        
        # 4. Re-ingest with new instance
        vg2.ingest(str(self.repo_dir))
        vg2.chunk_manager.save_manifest()
        
        # 5. Verify stale detection worked
        new_ids = set(vg2.chunk_manager.chunks.keys())
        self.assertEqual(len(original_ids & new_ids), 0, "Old chunk IDs should be replaced after restart")
        
        # 6. Stale IDs should have been detected
        # Note: stale_chunk_ids is cleared after directory ingest, but the removal should have happened
        self.assertEqual(len(new_ids), 1, "Should have exactly 1 new chunk")


if __name__ == "__main__":
    unittest.main()
