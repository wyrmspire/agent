"""
store/vectors.py - Vector Storage and Retrieval

This module handles dense vector storage, persistence, and similarity search.
It complements ChunkManager by adding semantic search capabilities.

Responsibilities:
- Store embeddings efficiently (numpy .npz)
- Maintain mapping between vectors and chunk IDs
- Perform fast cosine similarity search
- Persist index to disk

Rules:
- Embeddings are stored in normalized form (for dot product similarity)
- Chunk IDs map 1:1 to rows in the embedding matrix
- Operations should be vectorized where possible
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)

class VectorStore:
    """Manages vector embeddings and similarity search."""
    
    def __init__(self, store_path: str = "./store/vectors"):
        """Initialize vector store.
        
        Args:
            store_path: Directory to store vector data
        """
        self.store_path = Path(store_path)
        self.vectors_path = self.store_path / "embeddings.npz"
        self.manifest_path = self.store_path / "vectors_manifest.json"
        
        # State
        self.embeddings: Optional[np.ndarray] = None  # Shape (N, D)
        self.chunk_ids: List[str] = []                # Shape (N,)
        self.id_to_index: Dict[str, int] = {}         # ID -> Row Index
        
        # Ensure directory exists
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing data
        self.load()
    
    def _normalize(self, v: np.ndarray) -> np.ndarray:
        """Normalize vectors to unit length."""
        norm = np.linalg.norm(v, axis=1, keepdims=True)
        # Avoid division by zero
        norm[norm == 0] = 1e-10
        return v / norm
        
    def add(self, chunk_ids: List[str], vectors: List[List[float]]) -> None:
        """Add or update vectors in the store.
        
        Args:
            chunk_ids: List of chunk IDs correpsonding to vectors
            vectors: List of embedding vectors
        """
        if not chunk_ids or not vectors:
            return
            
        new_vecs = np.array(vectors, dtype=np.float32)
        
        # Normalize new vectors
        new_vecs = self._normalize(new_vecs)
        
        # If empty, just set
        if self.embeddings is None:
            self.embeddings = new_vecs
            self.chunk_ids = chunk_ids
            self._rebuild_index()
            return
            
        # Update existing or append new
        # For simplicity in this version, we will just rebuild/append naive approach
        # A full production version would update in place.
        # Here we filter out existing IDs from current state, then append all new
        
        # Create map of new data
        new_data = dict(zip(chunk_ids, new_vecs))
        
        # Keep existing data that is NOT in new data
        final_ids = []
        final_vecs = []
        
        for i, cid in enumerate(self.chunk_ids):
            if cid not in new_data:
                final_ids.append(cid)
                final_vecs.append(self.embeddings[i])
        
        # Add all new data
        for cid, vec in new_data.items():
            final_ids.append(cid)
            final_vecs.append(vec)
            
        # Update state
        self.chunk_ids = final_ids
        self.embeddings = np.array(final_vecs)
        self._rebuild_index()
        
    def _rebuild_index(self) -> None:
        """Rebuild ID to index mapping."""
        self.id_to_index = {cid: i for i, cid in enumerate(self.chunk_ids)}
        
    def search(self, query_vector: List[float], k: int = 10) -> List[Tuple[str, float]]:
        """Search for similar chunks using cosine similarity.
        
        Args:
            query_vector: Query embedding
            k: Number of results to return
            
        Returns:
            List of (chunk_id, score) tuples
        """
        if self.embeddings is None or len(self.embeddings) == 0:
            return []
            
        # Prepare query (1, D)
        q = np.array([query_vector], dtype=np.float32)
        q = self._normalize(q)
        
        # Cosine similarity = dot product of normalized vectors
        # scores shape: (1, N) -> (N,)
        scores = np.dot(self.embeddings, q.T).flatten()
        
        # Get top k indices
        # argsort sorts ascending, so take last k and reverse
        if k >= len(scores):
            top_k_indices = np.argsort(scores)[::-1]
        else:
            # partitioning is faster than full sort for large N
            top_k_indices = np.argpartition(scores, -k)[-k:]
            # Then sort the top k
            top_k_indices = top_k_indices[np.argsort(scores[top_k_indices])][::-1]
            
        results = []
        for idx in top_k_indices:
            results.append((self.chunk_ids[idx], float(scores[idx])))
            
        return results
        
    def save(self) -> bool:
        """Save store to disk."""
        try:
            if self.embeddings is not None:
                np.savez_compressed(self.vectors_path, embeddings=self.embeddings)
                
            manifest = {
                "chunk_ids": self.chunk_ids,
                "count": len(self.chunk_ids),
                "dim": self.embeddings.shape[1] if self.embeddings is not None else 0
            }
            
            with open(self.manifest_path, "w") as f:
                json.dump(manifest, f)
                
            logger.info(f"Saved vector store with {len(self.chunk_ids)} vectors")
            return True
        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
            return False
            
    def load(self) -> bool:
        """Load store from disk."""
        try:
            if not self.manifest_path.exists():
                return False
                
            with open(self.manifest_path, "r") as f:
                manifest = json.load(f)
                self.chunk_ids = manifest.get("chunk_ids", [])
            
            if self.vectors_path.exists():
                data = np.load(self.vectors_path)
                self.embeddings = data["embeddings"]
            
            self._rebuild_index()
            logger.info(f"Loaded vector store with {len(self.chunk_ids)} vectors")
            return True
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            self.chunk_ids = []
            self.embeddings = None
            return False
