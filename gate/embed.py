"""
gate/embed.py - Embedding Gateway Implementation

This module implements embedding generation for text.
Can use local models, OpenAI, or other embedding providers.

Responsibilities:
- Generate vector embeddings from text
- Support batch embedding
- Cache embeddings if needed

Rules:
- Only implements EmbeddingGateway interface
- No business logic about what to embed
"""

import httpx
from typing import List, Optional, Dict, Any

from .bases import EmbeddingGateway


class LMStudioEmbedding(EmbeddingGateway):
    """Embedding gateway using LM Studio.
    
    LM Studio can run embedding models locally.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "text-embedding-3-small",
        timeout: float = 30.0,
    ):
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        url = f"{self.base_url}/embeddings"
        
        request_data = {
            "model": self.model,
            "input": texts,
        }
        
        response = await self.client.post(url, json=request_data)
        response.raise_for_status()
        
        data = response.json()
        embeddings = [item["embedding"] for item in data["data"]]
        
        return embeddings
    
    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed([text])
        return embeddings[0]
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


class SimpleEmbedding(EmbeddingGateway):
    """Simple embedding for testing (no real model).
    
    Generates deterministic embeddings based on text hash.
    Only for testing - not for production use.
    """
    
    def __init__(self, dimension: int = 384):
        super().__init__("simple")
        self.dimension = dimension
    
    def _hash_to_embedding(self, text: str) -> List[float]:
        """Generate pseudo-embedding from text hash."""
        import hashlib
        
        # Generate hash
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        
        # Convert to floats
        embedding = []
        for i in range(self.dimension):
            byte_val = hash_bytes[i % len(hash_bytes)]
            embedding.append((byte_val / 255.0) * 2 - 1)  # Scale to [-1, 1]
        
        # Normalize
        magnitude = sum(x * x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [self._hash_to_embedding(text) for text in texts]
    
    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return self._hash_to_embedding(text)
