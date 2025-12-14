"""
tool/vectorgit.py - VectorGit Core Logic

This module implements the core logic for VectorGit, the durable memory layer.
It wraps ChunkManager to provide a simple API for ingestion, querying, and explanation.

Responsibilities:
- Repo ingestion (using ChunkManager)
- Keyword retrieval (using ChunkManager)
- Explanation generation (RAG-style)
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from store.chunks import ChunkManager
from store.vectors import VectorStore
from gate.bases import ModelGateway, EmbeddingGateway
from core.types import Message, MessageRole

logger = logging.getLogger(__name__)


class VectorGit:
    """VectorGit: Durable memory and retrieval system (v0 -> v0.9).
    
    Uses deterministic chunking + semantic vector search.
    """
    
    def __init__(
        self,
        workspace_path: str = "./workspace",
        index_name: str = "vectorgit",
    ):
        """Initialize VectorGit.
        
        Args:
            workspace_path: Root workspace path
            index_name: Name of the index (subdirectory in workspace)
        """
        self.workspace_root = Path(workspace_path)
        self.index_dir = self.workspace_root / index_name
        
        # Initialize ChunkManager
        self.chunks_dir = self.index_dir / "chunks"
        self.manifest_path = self.index_dir / "manifest.json"
        
        self.chunk_manager = ChunkManager(
            chunks_dir=str(self.chunks_dir),
            manifest_path=str(self.manifest_path),
        )
        
        # Initialize VectorStore (Phase 0.9A)
        self.vector_store_path = self.index_dir / "vectors"
        self.vector_store = VectorStore(store_path=str(self.vector_store_path))
    
    def ingest(self, repo_path: str) -> int:
        """Ingest a repository using keyword search only (legacy sync).
        
        Args:
            repo_path: Path to the repository to ingest
            
        Returns:
            Number of chunks ingested
        """
        # Call the async version without embeddings if synced call needed
        # Or just do keyword ingest
        return asyncio.run(self.ingest_async(repo_path, gateway=None))

    async def ingest_async(
        self, 
        repo_path: str,
        gateway: Optional[EmbeddingGateway] = None
    ) -> int:
        """Ingest a repository with optional embedding generation.
        
        Args:
            repo_path: Path to repo
            gateway: Embedding gateway (if None, only does keyword index)
            
        Returns:
            Number of chunks ingested
        """
        logger.info(f"Ingesting repo from {repo_path}...")
        
        path = Path(repo_path)
        if not path.exists():
            raise FileNotFoundError(f"Repo path not found: {repo_path}")
        
        # 1. Chunk Ingestion
        if path.is_file():
            count = self.chunk_manager.ingest_file(str(path))
        else:
            count = self.chunk_manager.ingest_directory(str(path), recursive=True)
            
        self.chunk_manager.save_manifest()
        
        # 2. Vector Embedding (Phase 0.9)
        if gateway and count > 0:
            logger.info("Computing embeddings for clean chunks...")
            # Ideally we only embed ONLY new chunks, but for now we'll check consistency
            # VectorStore.add handles updates/appends
            
            # Find chunks that are missing from vector store OR new
            # For simplicity in v0.9, we scan all chunks in manager
            chunks_to_embed = []
            ids_to_embed = []
            texts_to_embed = []
            
            # Identify what needs embedding
            # Optimization: check if ID in vector store
            existing_ids = set(self.vector_store.chunk_ids)
            
            for chunk_id, chunk_meta in self.chunk_manager.chunks.items():
                if chunk_id not in existing_ids:
                    content = self.chunk_manager.chunk_content.get(chunk_id)
                    # If content missing (reloaded from manifest), we might skip or re-read?
                    # ChunkManager currently doesn't persist content to disk except in memory
                    # We might need to handle 'content missing' if we just loaded manifest
                    # But ingest just ran, so content should be in memory
                    if content:
                        ids_to_embed.append(chunk_id)
                        # Format text for embedding: "Type: Name\nContent"
                        text = f"{chunk_meta.chunk_type}: {chunk_meta.name or ''}\n{content}"
                        texts_to_embed.append(text)
            
            if ids_to_embed:
                logger.info(f"Embedding {len(ids_to_embed)} chunks...")
                # Batch processing could go here
                try:
                    vectors = await gateway.embed(texts_to_embed)
                    self.vector_store.add(ids_to_embed, vectors)
                    self.vector_store.save()
                    logger.info(f"Embeddings saved for {len(vectors)} chunks")
                except Exception as e:
                    logger.error(f"Embedding generation failed: {e}")
        
        logger.info(f"Ingestion complete. Total chunks: {count}")
        return count
    
    def query(self, query_text: str, top_k: int = 8) -> List[Dict[str, Any]]:
        """Query using keyword search (legacy sync)."""
        return self.chunk_manager.search_chunks(query_text, k=top_k)

    async def query_async(
        self, 
        query_text: str, 
        gateway: Optional[EmbeddingGateway] = None,
        top_k: int = 8
    ) -> List[Dict[str, Any]]:
        """Query using semantic search if gateway provided, else keyword.
        
        Args:
            query_text: Search query
            gateway: Embedding gateway
            top_k: Results count
            
        Returns:
            List of matching chunks
        """
        # Phase 0.9: Semantic Search
        if gateway:
            try:
                # 1. Embed Query
                query_vec = await gateway.embed_single(query_text)
                if query_vec:
                    # 2. Vector Search
                    results = self.vector_store.search(query_vec, k=top_k)
                    
                    # 3. Hydrate Chunks
                    final_results = []
                    for chunk_id, score in results:
                        chunk = self.chunk_manager.get_chunk(chunk_id)
                        if chunk:
                            chunk["score"] = score  # Add similarity score
                            chunk["snippet"] = self.chunk_manager._get_snippet(chunk["content"], query_text)
                            final_results.append(chunk)
                    
                    if final_results:
                        return final_results
                    
            except Exception as e:
                logger.warning(f"Semantic search failed, falling back to keyword: {e}")
        
        # Fallback to keyword
        return self.chunk_manager.search_chunks(query_text, k=top_k)
    
    async def explain(
        self,
        query_text: str,
        gateway: ModelGateway,
        top_k: int = 8,
    ) -> str:
        """Generate an answer using retrieved chunks (RAG)."""
        # Support semantic query if gateway is also an EmbeddingGateway
        embedding_gateway = gateway if isinstance(gateway, EmbeddingGateway) else None
        
        # Retrieve
        chunks = await self.query_async(query_text, gateway=embedding_gateway, top_k=top_k)
        
        if not chunks:
            return "No relevant code found to answer your question."
        
        # Format context
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk["source_path"]
            start = chunk["start_line"]
            end = chunk["end_line"]
            content = chunk["content"]
            score = chunk.get("score", "N/A")
            
            context_parts.append(
                f"--- CHUNK {i} (Score: {score}) ---\n"
                f"File: {source} (lines {start}-{end})\n"
                f"Content:\n{content}\n"
            )
        
        context_str = "\n".join(context_parts)
        
        # Construct prompt
        system_prompt = (
            "You are an expert coding assistant. Answer the user's question based ONLY "
            "on the provided code chunks. Cite your sources by referring to the File and Line numbers.\n"
            "If the provided chunks do not contain enough information to answer, say so."
        )
        
        user_prompt = (
            f"Question: {query_text}\n\n"
            f"Context:\n{context_str}\n\n"
            f"Answer:"
        )
        
        # Call model
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_prompt),
        ]
        
        response = await gateway.complete(messages, tools=[])
        return response.content
