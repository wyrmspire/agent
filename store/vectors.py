"""
store/vectors.py - Vector Store Implementation

This module handles the storage and retrieval of vector embeddings.
It uses numpy for efficient in-memory operations and persists to disk.

Responsibilities:
- Store embeddings for chunk IDs
- Persist to efficient binary format (.npz)
- Perform cosine similarity search
- Manage vector metadata (model version, dimensions)

Rules:
- Embeddings must match chunk IDs from ChunkManager
- Persistence is crash-safe (atomic write preferred, but simple save ok for now)
- Search is deterministic (stable tie-breaking)
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

class VectorStore:
    """Manages vector embeddings and similarity search."""
    
    def __init__(self, store_path: str = "./store/vectors"):
        self.store_path = Path(store_path)
        self.vectors_path = self.store_path / "embeddings.npz"
        self.manifest_path = self.store_path / "vectors_manifest.json"
        
        # In-memory state
        self.vectors: Optional[np.ndarray] = None
        self.chunk_ids: List[str] = []
        self.id_to_index: Dict[str, int] = {}
        self.metadata: Dict[str, Any] = {
            "embedding_model": "unknown",
            "dim": 0,
            "count": 0,
            "normalized": True,
            "updated_at": ""
        }
        
        # Ensure directory exists
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # Load if exists
        self.load()
    
    def load(self) -> bool:
        """Load vectors and manifest from disk."""
        if not self.vectors_path.exists() or not self.manifest_path.exists():
            return False
            
        try:
            # Load dimensions/manifest
            with open(self.manifest_path, "r") as f:
                self.metadata = json.load(f)
                self.chunk_ids = self.metadata.get("chunk_ids", [])
                
            # Rebuild index map
            self.id_to_index = {cid: i for i, cid in enumerate(self.chunk_ids)}
            
            # Load vectors
            data = np.load(self.vectors_path)
            self.vectors = data["vectors"]
            
            # Validation
            if self.vectors.shape[0] != len(self.chunk_ids):
                logger.error(f"VectorStore Corruption: {len(self.chunk_ids)} ids but {self.vectors.shape[0]} vectors")
                self.vectors = None
                self.chunk_ids = []
                self.id_to_index = {}
                return False
                
            logger.info(f"Loaded {len(self.chunk_ids)} vectors (dim={self.vectors.shape[1]}) model={self.metadata.get('embedding_model')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False
    
    def save(self) -> bool:
        """Save vectors and manifest to disk."""
        if self.vectors is None:
            return False
            
        try:
            # Save vectors
            np.savez_compressed(self.vectors_path, vectors=self.vectors)
            
            # Update metadata
            from datetime import datetime
            self.metadata["chunk_ids"] = self.chunk_ids
            self.metadata["count"] = len(self.chunk_ids)
            self.metadata["dim"] = self.vectors.shape[1] if self.vectors is not None else 0
            self.metadata["updated_at"] = datetime.utcnow().isoformat()
            
            # Save manifest
            with open(self.manifest_path, "w") as f:
                json.dump(self.metadata, f, indent=2)
                
            logger.info(f"Saved {len(self.chunk_ids)} vectors to disk")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
            return False
            
    def has(self, chunk_id: str) -> bool:
        """Check if chunk ID exists in store."""
        return chunk_id in self.id_to_index

    def missing(self, ids: List[str]) -> List[str]:
        """Return list of IDs that are missing from store."""
        return [cid for cid in ids if cid not in self.id_to_index]

    def prune(self, active_ids: List[str]) -> bool:
        """Remove chunks not present in the active_ids list. Returns True if changed."""
        if self.vectors is None:
            return False
            
        active_set = set(active_ids)
        if len(active_set) == len(self.chunk_ids):
            return False # No changes needed
            
        # Filter
        indices_to_keep = []
        new_ids = []
        
        for i, cid in enumerate(self.chunk_ids):
            if cid in active_set:
                indices_to_keep.append(i)
                new_ids.append(cid)
                
        if len(new_ids) == len(self.chunk_ids):
            return False
            
        # Update state
        self.chunk_ids = new_ids
        self.vectors = self.vectors[indices_to_keep]
        
        # Rebuild map
        self.id_to_index = {cid: i for i, cid in enumerate(self.chunk_ids)}
        self.metadata["count"] = len(self.chunk_ids)
        logger.info(f"Pruned active vectors to {len(self.chunk_ids)}")
        return True

    def add(self, chunk_ids: List[str], embeddings: List[List[float]], model_name: str = "unknown"):
        """Add new embeddings to the store. Updates existing IDs in-place.
        
        Args:
            chunk_ids: List of Chunk IDs
            embeddings: List of embedding vectors (floats)
            model_name: Name of the model used (for validation)
        """
        if not chunk_ids or not embeddings:
            return
            
        new_vecs = np.array(embeddings, dtype=np.float32)
        dim = new_vecs.shape[1]
        
        # Validation
        if self.vectors is not None:
             if dim != self.vectors.shape[1]:
                 raise ValueError(f"Dimension mismatch: new={dim}, existing={self.vectors.shape[1]}")
             
        # Update/Set model name
        if self.metadata["embedding_model"] == "unknown":
            self.metadata["embedding_model"] = model_name
        elif self.metadata["embedding_model"] != model_name:
             logger.warning(f"Model mismatch: existing={self.metadata['embedding_model']}, new={model_name}")
        
        if self.metadata["dim"] == 0:
            self.metadata["dim"] = dim
            
        # Normalize new vectors for cosine similarity (L2 norm)
        norms = np.linalg.norm(new_vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # Avoid division by zero
        new_vecs = new_vecs / norms
        
        # Initialize if empty
        if self.vectors is None:
            self.vectors = new_vecs
            self.chunk_ids = list(chunk_ids)
            self.id_to_index = {cid: i for i, cid in enumerate(self.chunk_ids)}
            return
            
        # Separate updates vs appends
        to_append_vecs = []
        to_append_ids = []
        
        for i, cid in enumerate(chunk_ids):
            if cid in self.id_to_index:
                # Update in-place
                idx = self.id_to_index[cid]
                self.vectors[idx] = new_vecs[i]
            else:
                # Queue for append
                to_append_ids.append(cid)
                to_append_vecs.append(new_vecs[i])
        
        # Process appends
        if to_append_ids:
             to_append_arr = np.stack(to_append_vecs, axis=0)
             self.vectors = np.concatenate([self.vectors, to_append_arr])
             
             start_idx = len(self.chunk_ids)
             self.chunk_ids.extend(to_append_ids)
             for i, cid in enumerate(to_append_ids):
                 self.id_to_index[cid] = start_idx + i
            
    def search(self, query_vec: List[float], k: int = 10) -> List[Tuple[str, float]]:
        """Search for similar vectors with deterministic tie-breaking.
        
        Args:
            query_vec: Query embedding vector
            k: Number of results
            
        Returns:
            List of (chunk_id, score) tuples
        """
        if self.vectors is None or len(self.chunk_ids) == 0:
            return []
            
        # Normalize query
        q = np.array(query_vec, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm
            
        # Compute scores (Dot product)
        scores = np.dot(self.vectors, q)
        
        # Prepare list of (chunk_id, score)
        # For full determinism, we sort ALL candidates then take top K.
        # Efficient enough for <100k chunks.
        
        # Create list of (chunk_id, score)
        candidates = []
        for i, score in enumerate(scores):
            candidates.append((self.chunk_ids[i], float(score)))
        
        # Stable sort:
        # Primary key: Score (Descending) -> -x[1]
        # Secondary key: Chunk ID (Ascending) -> x[0]
        candidates.sort(key=lambda x: (-x[1], x[0]))
        
        return candidates[:k]
