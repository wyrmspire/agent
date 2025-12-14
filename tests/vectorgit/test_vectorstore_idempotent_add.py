import unittest
import numpy as np
import shutil
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from store.vectors import VectorStore

class TestVectorStoreIdempotency(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("workspace/test_vectors_idempotent")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.store = VectorStore(store_path=str(self.test_dir))

    def test_idempotent_add(self):
        """Test that re-adding existing IDs updates vectors instead of duplicating."""
        # Initial add
        ids = ["a", "b"]
        vecs = [[1.0, 0.0], [0.0, 1.0]]
        self.store.add(ids, vecs)
        
        self.assertEqual(len(self.store.chunk_ids), 2)
        self.assertEqual(self.store.vectors.shape[0], 2)
        
        # Verify vector 'a' is [1, 0]
        idx_a = self.store.id_to_index["a"]
        np.testing.assert_array_almost_equal(self.store.vectors[idx_a], [1.0, 0.0])
        
        # Re-add 'a' with NEW vector
        ids_new = ["a"]
        vecs_new = [[0.0, 1.0]] # Changed vector
        self.store.add(ids_new, vecs_new)
        
        # Assertions
        # 1. Length should still be 2 (not 3)
        self.assertEqual(len(self.store.chunk_ids), 2, "Duplicate ID created on re-add")
        
        # 2. Vector for 'a' should be updated
        idx_a_new = self.store.id_to_index["a"]
        np.testing.assert_array_almost_equal(self.store.vectors[idx_a_new], [0.0, 1.0], err_msg="Vector failed to update in-place")
        
        # 3. 'b' should be untouched
        idx_b = self.store.id_to_index["b"]
        np.testing.assert_array_almost_equal(self.store.vectors[idx_b], [0.0, 1.0])

    def test_deterministic_sort(self):
        """Test strict deterministic sorting logic."""
        # Add vectors that are identical to query -> same score
        ids = ["z_last", "a_first"]
        vecs = [[1.0, 0.0], [1.0, 0.0]] # Both perfectly match [1,0]
        self.store.add(ids, vecs)
        
        query = [1.0, 0.0]
        results = self.store.search(query, k=2)
        
        # Scores should be identical (~1.0)
        self.assertAlmostEqual(results[0][1], results[1][1])
        
        # Sort rule: (-score, chunk_id)
        # Since score matches, chunk_id 'a_first' < 'z_last'
        # So 'a_first' should strictly be first
        self.assertEqual(results[0][0], "a_first")
        self.assertEqual(results[1][0], "z_last")

if __name__ == "__main__":
    unittest.main()
