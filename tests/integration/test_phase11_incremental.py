"""
tests/integration/test_phase11_incremental.py - Phase 1.1 Integration Test

Phase 1.1 Goal: Git-aware incremental memory
- Edit a file → re-ingest → only affected chunks change
- Semantic search reflects new reality
- Old stale chunks are gone
- No duplicates

This test validates the complete Phase 1.1 definition of done.
"""

import unittest
import asyncio
import shutil
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tool.vectorgit import VectorGit
from gate.mock import MockGateway


class TestPhase11Incremental(unittest.TestCase):
    """Integration test for Phase 1.1 incremental memory."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path("workspace/test_phase11")
        self.repo_dir = self.test_dir / "repo"
        
        # Clean up
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Create initial files
        (self.repo_dir / "auth.py").write_text("""
def authenticate_user(username, password):
    '''Old authentication logic'''
    if username == 'admin' and password == 'secret':
        return True
    return False
""")
        
        (self.repo_dir / "utils.py").write_text("""
def format_name(name):
    '''Format a name to title case'''
    return name.title()

def validate_email(email):
    '''Simple email validation'''
    return '@' in email
""")
        
        # Initialize VectorGit
        self.vg = VectorGit(
            workspace_path=str(self.test_dir),
            index_name="phase11_test"
        )
    
    def tearDown(self):
        """Clean up test environment."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_phase11_definition_of_done(self):
        """Test Phase 1.1 Definition of Done:
        
        Edit a file → re-ingest → only affected chunks change → 
        semantic search reflects new reality → old stale chunks are gone → 
        no duplicates.
        """
        
        # ========== STEP 1: Initial Ingest ==========
        print("\n[STEP 1] Initial ingest...")
        count1 = self.vg.ingest(str(self.repo_dir))
        self.assertGreater(count1, 0, "Initial ingest should create chunks")
        
        # Get initial state
        initial_chunk_ids = set(self.vg.chunk_manager.chunks.keys())
        initial_count = len(initial_chunk_ids)
        print(f"  Initial chunks: {initial_count}")
        print(f"  Chunk IDs: {sorted(initial_chunk_ids)}")
        
        # Verify we can find the old auth logic
        results_old_auth = self.vg.query("authenticate", top_k=5)
        self.assertGreater(len(results_old_auth), 0, "Should find old auth logic")
        old_auth_chunk_id = results_old_auth[0]["chunk_id"]
        print(f"  Found old auth in: {old_auth_chunk_id}")
        
        # Verify content contains "Old authentication"
        found_old = False
        for result in results_old_auth:
            content = result.get("content", "")
            if "Old authentication" in content or "authenticate_user" in content:
                found_old = True
                print(f"    Content preview: {content[:100]}...")
                break
        self.assertTrue(found_old, "Should find authentication content in results")
        
        # ========== STEP 2: Edit One File ==========
        print("\n[STEP 2] Editing auth.py...")
        (self.repo_dir / "auth.py").write_text("""
def authenticate_user(username, password):
    '''New JWT-based authentication'''
    token = generate_jwt(username, password)
    return verify_jwt(token)

def generate_jwt(username, password):
    '''Generate JWT token'''
    return f"jwt_{username}_{password}"

def verify_jwt(token):
    '''Verify JWT token'''
    return token.startswith('jwt_')
""")
        
        # ========== STEP 3: Re-ingest ==========
        print("\n[STEP 3] Re-ingesting...")
        count2 = self.vg.ingest(str(self.repo_dir))
        print(f"  New chunks created: {count2}")
        
        # Get new state
        new_chunk_ids = set(self.vg.chunk_manager.chunks.keys())
        new_count = len(new_chunk_ids)
        print(f"  Total chunks after re-ingest: {new_count}")
        print(f"  Chunk IDs: {sorted(new_chunk_ids)}")
        
        # ========== VALIDATION 1: Only Affected Chunks Changed ==========
        print("\n[VALIDATION 1] Checking only affected chunks changed...")
        
        # Old auth chunk should be gone (different content = different hash = different ID)
        self.assertNotIn(old_auth_chunk_id, new_chunk_ids, 
                        "Old auth chunk ID should be replaced")
        
        # Utils.py chunks should still exist (unchanged)
        # Check by searching for utils functions
        results_utils = self.vg.query("format_name", top_k=5)
        self.assertGreater(len(results_utils), 0, "Utils functions should still be findable")
        print(f"  ✓ Unchanged file chunks preserved")
        
        # ========== VALIDATION 2: Semantic Search Reflects New Reality ==========
        print("\n[VALIDATION 2] Checking semantic search reflects new reality...")
        
        # Search for new JWT functionality (use simpler query)
        results_new_auth = self.vg.query("jwt", top_k=5)
        self.assertGreater(len(results_new_auth), 0, 
                          "Should find new JWT auth logic")
        
        # Verify new content is present
        found_jwt = False
        for result in results_new_auth:
            content = result.get("content", "")
            if "JWT" in content or "jwt" in content or "generate_jwt" in content:
                found_jwt = True
                print(f"  Found JWT in chunk: {result['chunk_id']}")
                print(f"    Content: {content[:150]}...")
                break
        self.assertTrue(found_jwt, "Should find JWT-related content")
        
        # Search for old authentication should find nothing or return new chunks
        results_old_search = self.vg.query("Old authentication", top_k=5)
        if results_old_search:
            # If results exist, they should be from the NEW file (not contain "Old authentication")
            for result in results_old_search:
                content = result.get("content", "")
                self.assertNotIn("Old authentication logic", content, 
                               "Should not find old authentication text")
        print(f"  ✓ Old content not found in search results")
        
        # ========== VALIDATION 3: Old Stale Chunks Are Gone ==========
        print("\n[VALIDATION 3] Checking old stale chunks are gone...")
        
        # The old auth chunk ID should not exist in the chunk manager
        self.assertNotIn(old_auth_chunk_id, self.vg.chunk_manager.chunks,
                        "Old chunk should be removed from chunk manager")
        
        # Should not be in the hash map either
        old_chunk_meta = None
        for chunk_id, meta in self.vg.chunk_manager.chunks.items():
            if "Old authentication" in str(meta):
                old_chunk_meta = meta
                break
        self.assertIsNone(old_chunk_meta, "Old chunk metadata should be gone")
        print(f"  ✓ Stale chunks removed from memory")
        
        # ========== VALIDATION 4: No Duplicates ==========
        print("\n[VALIDATION 4] Checking no duplicates...")
        
        # Count chunks per source file
        source_counts = {}
        for chunk_id, meta in self.vg.chunk_manager.chunks.items():
            source = meta.source_path
            source_counts[source] = source_counts.get(source, 0) + 1
        
        print(f"  Chunks per file: {source_counts}")
        
        # Verify no duplicate chunk IDs
        all_ids = list(self.vg.chunk_manager.chunks.keys())
        unique_ids = set(all_ids)
        self.assertEqual(len(all_ids), len(unique_ids), 
                        "Should have no duplicate chunk IDs")
        
        # Verify each function appears only once
        function_names = []
        for chunk_id, meta in self.vg.chunk_manager.chunks.items():
            if meta.name:
                function_names.append(meta.name)
        
        # Count occurrences
        from collections import Counter
        name_counts = Counter(function_names)
        duplicates = {name: count for name, count in name_counts.items() if count > 1}
        
        self.assertEqual(len(duplicates), 0, 
                        f"Should have no duplicate function names, found: {duplicates}")
        print(f"  ✓ No duplicate chunks")
        
        print("\n[SUCCESS] Phase 1.1 Definition of Done validated! ✓")
    
    @unittest.skip("Requires embedding gateway - tested in test_vectorgit_semantic.py")
    def test_phase11_with_embeddings(self):
        """Test Phase 1.1 with vector embeddings (semantic search).
        
        This test validates that re-embedding works correctly:
        - Old embeddings are removed
        - New embeddings are added
        - No duplicate vectors
        
        Note: This requires a real embedding gateway.
        The behavior is already tested in tests/integration/test_vectorgit_semantic.py
        which uses a proper embedding gateway.
        """
        pass


if __name__ == "__main__":
    unittest.main()
