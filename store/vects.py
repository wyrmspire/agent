"""
store/vects.py - Vector Store Implementation

This module implements vector storage for semantic search.
Uses simple in-memory storage with cosine similarity.

Responsibilities:
- Store text embeddings
- Semantic search via cosine similarity
- Document retrieval with citations
- Persistence to disk

Rules:
- Returns citations + snippets
- Pluggable (can upgrade to Qdrant/Pinecone later)
- Simple but functional
"""

import numpy as np
import pickle
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from .bases import VectorStore, DocumentStore

logger = logging.getLogger(__name__)


class SimpleVectorStore(VectorStore):
    """Simple in-memory vector store with disk persistence.
    
    Uses cosine similarity for search.
    Good for development and small datasets.
    Supports saving/loading embeddings to/from disk.
    """
    
    def __init__(self, persist_path: Optional[str] = None):
        """Initialize vector store.
        
        Args:
            persist_path: Optional path to persist embeddings
        """
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.persist_path = Path(persist_path) if persist_path else None
        
        # Load from disk if file exists
        if self.persist_path and self.persist_path.exists():
            self.load()
    
    async def add(
        self,
        id: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a document with embedding."""
        self.documents[id] = {
            "id": id,
            "text": text,
            "embedding": np.array(embedding),
            "metadata": metadata or {},
        }
    
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents."""
        if not self.documents:
            return []
        
        query_vec = np.array(query_embedding)
        
        # Calculate cosine similarity for all documents
        results = []
        for doc_id, doc in self.documents.items():
            doc_vec = doc["embedding"]
            
            # Cosine similarity
            similarity = np.dot(query_vec, doc_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(doc_vec)
            )
            
            if similarity >= min_score:
                results.append({
                    "id": doc["id"],
                    "text": doc["text"],
                    "score": float(similarity),
                    "metadata": doc["metadata"],
                })
        
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:limit]
    
    async def delete(self, id: str) -> None:
        """Delete a document."""
        if id in self.documents:
            del self.documents[id]
    
    def clear(self) -> None:
        """Clear all documents."""
        self.documents.clear()
    
    def count(self) -> int:
        """Get document count."""
        return len(self.documents)
    
    def save(self, path: Optional[str] = None) -> bool:
        """Save embeddings to disk.
        
        Args:
            path: Optional custom path (overrides persist_path)
            
        Returns:
            True if saved successfully
        """
        save_path = Path(path) if path else self.persist_path
        
        if not save_path:
            logger.warning("No persist_path configured, cannot save")
            return False
        
        try:
            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data for serialization
            data = {}
            for doc_id, doc in self.documents.items():
                data[doc_id] = {
                    "id": doc["id"],
                    "text": doc["text"],
                    "embedding": doc["embedding"].tolist(),  # Convert numpy to list
                    "metadata": doc["metadata"],
                }
            
            # Save as pickle for efficiency
            with open(save_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"Saved {len(self.documents)} embeddings to {save_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save embeddings: {e}")
            return False
    
    def load(self, path: Optional[str] = None) -> bool:
        """Load embeddings from disk.
        
        Args:
            path: Optional custom path (overrides persist_path)
            
        Returns:
            True if loaded successfully
        """
        load_path = Path(path) if path else self.persist_path
        
        if not load_path or not load_path.exists():
            logger.warning(f"File not found: {load_path}")
            return False
        
        try:
            with open(load_path, 'rb') as f:
                data = pickle.load(f)
            
            # Restore documents with numpy arrays
            self.documents.clear()
            for doc_id, doc_data in data.items():
                self.documents[doc_id] = {
                    "id": doc_data["id"],
                    "text": doc_data["text"],
                    "embedding": np.array(doc_data["embedding"]),  # Convert list to numpy
                    "metadata": doc_data["metadata"],
                }
            
            logger.info(f"Loaded {len(self.documents)} embeddings from {load_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")
            return False


class SimpleDocumentStore(DocumentStore):
    """Simple document store with chunking.
    
    Chunks documents and stores them in a vector store.
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.vector_store = vector_store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.documents: Dict[str, Dict[str, Any]] = {}
    
    def _chunk_text(self, text: str) -> List[str]:
        """Chunk text into overlapping segments."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            
            if chunk:
                chunks.append(chunk)
            
            start += self.chunk_size - self.chunk_overlap
        
        return chunks
    
    async def ingest(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Ingest a document (without embeddings for now).
        
        This is a placeholder. Real implementation needs:
        - Embedding generation
        - Chunk embedding and storage
        """
        metadata = metadata or {}
        
        # Store document metadata
        self.documents[doc_id] = {
            "id": doc_id,
            "content": content,
            "metadata": metadata,
        }
        
        # Chunk the document
        chunks = self._chunk_text(content)
        
        # NOTE: Real implementation would:
        # 1. Generate embeddings for each chunk
        # 2. Store chunks in vector store
        # For now, just return chunk count
        
        return len(chunks)
    
    async def retrieve(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks.
        
        This is a placeholder. Real implementation needs:
        - Query embedding generation
        - Vector search
        - Citation formatting
        """
        # NOTE: Real implementation would:
        # 1. Embed the query
        # 2. Search vector store
        # 3. Format results with citations
        
        # For now, return empty
        return []
