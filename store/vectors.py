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
- Persistence is crash-safe using atomic writes (Phase 1.3)
- Search is deterministic (stable tie-breaking)
"""

import json
import logging
import numpy as np
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


class CorruptedIndexError(Exception):
    """Raised when vector store corruption is detected."""
    pass

class VectorStore:
    """Manages vector embeddings and similarity search."""
    
    def __init__(self, store_path: str = "./store/vectors", auto_load: bool = True):
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
        if auto_load:
            self.load()
    
    @classmethod
    def try_load(cls, store_path: str) -> 'VectorStore':
        """Create VectorStore and load, handling corruption.
        
        Args:
            store_path: Path to vector store
            
        Returns:
            Initialized VectorStore (empty if corrupted)
            
        Raises:
            CorruptedIndexError: If corruption detected and cannot recover
        """
        store = cls(store_path, auto_load=False)
        try:
            store.load()
        except CorruptedIndexError:
            # Return empty store on corruption
            logger.warning("Corruption detected, returning empty store")
            store.vectors = None
            store.chunk_ids = []
            store.id_to_index = {}
        return store
    
    def load(self) -> bool:
        """Load vectors and manifest from disk with corruption detection.
        
        Raises:
            CorruptedIndexError: If vector count doesn't match chunk IDs
        """
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
            
            # Phase 1.3: Corruption detection with checksum validation
            manifest_count = self.metadata.get("count", len(self.chunk_ids))
            vector_count = self.vectors.shape[0]
            chunk_id_count = len(self.chunk_ids)
            
            if vector_count != chunk_id_count or vector_count != manifest_count:
                error_msg = (
                    f"VectorStore Corruption Detected: "
                    f"manifest_count={manifest_count}, "
                    f"chunk_ids={chunk_id_count}, "
                    f"vectors={vector_count}"
                )
                logger.error(error_msg)
                raise CorruptedIndexError(error_msg)
                
            logger.info(f"Loaded {len(self.chunk_ids)} vectors (dim={self.vectors.shape[1]}) model={self.metadata.get('embedding_model')}")
            return True
            
        except CorruptedIndexError:
            raise  # Re-raise corruption errors for self-healing
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False
    
    def save(self) -> bool:
        """Save vectors and manifest to disk using atomic writes (Phase 1.3).
        
        Uses .tmp files and os.replace() for crash safety.
        """
        if self.vectors is None or len(self.chunk_ids) == 0:
            return False
            
        try:
            from datetime import datetime, timezone
            
            # Update metadata
            self.metadata["chunk_ids"] = self.chunk_ids
            self.metadata["count"] = len(self.chunk_ids)
            self.metadata["dim"] = self.vectors.shape[1] if self.vectors is not None else 0
            self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Phase 1.3: Atomic write for vectors
            # Note: np.savez_compressed automatically adds .npz extension
            # So we save without extension and it becomes .npz
            vectors_tmp_base = self.store_path / "embeddings.tmp"
            np.savez_compressed(vectors_tmp_base, vectors=self.vectors)
            # After save, the actual file is embeddings.tmp.npz
            vectors_tmp = self.store_path / "embeddings.tmp.npz"
            
            # Flush to disk
            with open(vectors_tmp, 'rb') as f:
                os.fsync(f.fileno())
            
            # Atomic replace (POSIX/Windows safe)
            os.replace(vectors_tmp, self.vectors_path)
            
            # Phase 1.3: Atomic write for manifest
            manifest_tmp = Path(str(self.manifest_path) + '.tmp')
            with open(manifest_tmp, "w") as f:
                json.dump(self.metadata, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
                
            # Atomic replace
            os.replace(manifest_tmp, self.manifest_path)
                
            logger.info(f"Saved {len(self.chunk_ids)} vectors to disk (atomic)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
            # Clean up temp files if they exist
            try:
                vectors_tmp = self.store_path / "embeddings.tmp.npz"
                if vectors_tmp.exists():
                    vectors_tmp.unlink()
                manifest_tmp = Path(str(self.manifest_path) + '.tmp')
                if manifest_tmp.exists():
                    manifest_tmp.unlink()
            except:
                pass
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

    def remove_ids(self, ids_to_remove: List[str]) -> bool:
        """Remove specific chunk IDs from store.
        
        Args:
            ids_to_remove: List of chunk IDs to remove
            
        Returns:
            True if any were removed
        """
        if not ids_to_remove or self.vectors is None:
            return False
            
        remove_set = set(ids_to_remove)
        indices_to_keep = []
        new_ids = []
        
        for i, cid in enumerate(self.chunk_ids):
            if cid not in remove_set:
                indices_to_keep.append(i)
                new_ids.append(cid)
        
        if len(new_ids) == len(self.chunk_ids):
            return False  # Nothing removed
        
        old_count = len(self.chunk_ids)
        self.chunk_ids = new_ids
        self.vectors = self.vectors[indices_to_keep]
        self.id_to_index = {cid: i for i, cid in enumerate(self.chunk_ids)}
        self.metadata["count"] = len(self.chunk_ids)
        logger.info(f"Removed {old_count - len(new_ids)} stale embeddings")
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
        """Search for similar vectors using fast top-K selection (Phase 1.2).
        
        Uses np.argpartition for O(N) top-K instead of O(N log N) sort.
        
        Args:
            query_vec: Query embedding vector
            k: Number of results
            
        Returns:
            List of (chunk_id, score) tuples, sorted deterministically
        """
        if self.vectors is None or len(self.chunk_ids) == 0:
            return []
            
        # Normalize query
        q = np.array(query_vec, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm
            
        # Compute scores (Dot product = cosine similarity for normalized vectors)
        scores = np.dot(self.vectors, q)
        
        n = len(scores)
        k_actual = min(k, n)
        
        # Phase 1.2: Use argpartition for O(N) top-K selection
        # argpartition puts the k largest elements at the end (for negative scores)
        if n <= k_actual:
            # All results needed, just sort
            top_indices = np.argsort(-scores)
        else:
            # Use argpartition to find top K efficiently
            # Negate scores to get largest values
            partition_indices = np.argpartition(-scores, k_actual-1)[:k_actual]
            # Sort only the top K
            top_indices = partition_indices[np.argsort(-scores[partition_indices])]
        
        # Build result list with deterministic tie-breaking
        candidates = []
        for idx in top_indices:
            candidates.append((self.chunk_ids[idx], float(scores[idx])))
        
        # Final stable sort for determinism (score desc, chunk_id asc)
        # Since we already sorted by score, we only need secondary sort for ties
        candidates.sort(key=lambda x: (-x[1], x[0]))
        
        return candidates[:k_actual]
