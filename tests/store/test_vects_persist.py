"""
Tests for store/vects.py - Vector Store Persistence
"""

import unittest
import tempfile
import shutil
import asyncio
from pathlib import Path

from store.vects import SimpleVectorStore


class TestVectorStorePersistence(unittest.TestCase):
    """Test vector store persistence functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.persist_path = f"{self.temp_dir}/embeddings.pkl"
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def _run_async_test(self, coro):
        """Helper to run async tests."""
        return await coro
    
    def test_save_and_load(self):
        """Test saving and loading embeddings."""
        # Create store and add some documents
        store = SimpleVectorStore(persist_path=self.persist_path)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Add documents
            loop.run_until_complete(store.add(
                id="doc1",
                text="Machine learning is awesome",
                embedding=[0.1, 0.2, 0.3],
                metadata={"category": "AI"}
            ))
            
            loop.run_until_complete(store.add(
                id="doc2",
                text="Python is great for data science",
                embedding=[0.4, 0.5, 0.6],
                metadata={"category": "Programming"}
            ))
            
            self.assertEqual(store.count(), 2)
            
            # Save to disk
            result = store.save()
            self.assertTrue(result)
            self.assertTrue(Path(self.persist_path).exists())
            
            # Create new store and load
            store2 = SimpleVectorStore(persist_path=self.persist_path)
            self.assertEqual(store2.count(), 2)
            
            # Verify documents were loaded correctly
            self.assertIn("doc1", store2.documents)
            self.assertIn("doc2", store2.documents)
            self.assertEqual(store2.documents["doc1"]["text"], "Machine learning is awesome")
            self.assertEqual(store2.documents["doc2"]["metadata"]["category"], "Programming")
        
        finally:
            loop.close()
    
    def test_save_without_persist_path(self):
        """Test that save returns False without persist_path."""
        store = SimpleVectorStore()  # No persist_path
        
        result = store.save()
        self.assertFalse(result)
    
    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file."""
        store = SimpleVectorStore()
        
        result = store.load("/nonexistent/path.pkl")
        self.assertFalse(result)
    
    def test_auto_load_on_init(self):
        """Test automatic loading when persist_path exists."""
        # Create and save a store
        store1 = SimpleVectorStore(persist_path=self.persist_path)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(store1.add(
                id="doc1",
                text="Test document",
                embedding=[0.1, 0.2, 0.3]
            ))
            store1.save()
            
            # Create new store with same path - should auto-load
            store2 = SimpleVectorStore(persist_path=self.persist_path)
            self.assertEqual(store2.count(), 1)
            self.assertIn("doc1", store2.documents)
        
        finally:
            loop.close()
    
    def test_save_custom_path(self):
        """Test saving to custom path."""
        store = SimpleVectorStore()
        custom_path = f"{self.temp_dir}/custom.pkl"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(store.add(
                id="doc1",
                text="Test",
                embedding=[0.1, 0.2]
            ))
            
            # Save to custom path
            result = store.save(custom_path)
            self.assertTrue(result)
            self.assertTrue(Path(custom_path).exists())
            
            # Load from custom path
            store2 = SimpleVectorStore()
            result = store2.load(custom_path)
            self.assertTrue(result)
            self.assertEqual(store2.count(), 1)
        
        finally:
            loop.close()
    
    def test_persistence_with_search(self):
        """Test that search works after save/load."""
        store1 = SimpleVectorStore(persist_path=self.persist_path)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Add documents
            loop.run_until_complete(store1.add(
                id="doc1",
                text="Python programming",
                embedding=[1.0, 0.0, 0.0]
            ))
            
            loop.run_until_complete(store1.add(
                id="doc2",
                text="Java development",
                embedding=[0.0, 1.0, 0.0]
            ))
            
            store1.save()
            
            # Load in new store
            store2 = SimpleVectorStore(persist_path=self.persist_path)
            
            # Search should work
            results = loop.run_until_complete(store2.search(
                query_embedding=[0.9, 0.1, 0.0],
                limit=1
            ))
            
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["id"], "doc1")
        
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
