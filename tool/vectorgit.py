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
from gate.bases import ModelGateway
from core.types import Message, MessageRole

logger = logging.getLogger(__name__)


class VectorGit:
    """VectorGit: Durable memory and retrieval system (v0).
    
    Currently uses keyword search (no vectors yet) and deterministic chunking.
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
        # We store chunks in workspace/vectorgit/chunks
        # and manifest in workspace/vectorgit/manifest.json
        self.chunks_dir = self.index_dir / "chunks"
        self.manifest_path = self.index_dir / "manifest.json"
        
        self.chunk_manager = ChunkManager(
            chunks_dir=str(self.chunks_dir),
            manifest_path=str(self.manifest_path),
        )
    
    def ingest(self, repo_path: str) -> int:
        """Ingest a repository into VectorGit.
        
        Args:
            repo_path: Path to the repository to ingest
            
        Returns:
            Number of chunks ingested
        """
        logger.info(f"Ingesting repo from {repo_path}...")
        
        path = Path(repo_path)
        if not path.exists():
            raise FileNotFoundError(f"Repo path not found: {repo_path}")
        
        if path.is_file():
            count = self.chunk_manager.ingest_file(str(path))
        else:
            count = self.chunk_manager.ingest_directory(str(path), recursive=True)
            
        # Save manifest to persist the index
        self.chunk_manager.save_manifest()
        
        logger.info(f"Ingestion complete. Total chunks: {count}")
        return count
    
    def query(self, query_text: str, top_k: int = 8) -> List[Dict[str, Any]]:
        """Query the memory using keyword search.
        
        Args:
            query_text: Search query
            top_k: Number of results to return
            
        Returns:
            List of matching chunks
        """
        return self.chunk_manager.search_chunks(query_text, k=top_k)
    
    async def explain(
        self,
        query_text: str,
        gateway: ModelGateway,
        top_k: int = 8,
    ) -> str:
        """Generate an answer using retrieved chunks (RAG).
        
        Args:
            query_text: User question
            gateway: Model gateway to use for generation
            top_k: Number of chunks to retrieve
            
        Returns:
            The model's answer
        """
        # 1. Retrieve chunks
        chunks = self.query(query_text, top_k=top_k)
        
        if not chunks:
            return "No relevant code found to answer your question."
        
        # 2. Format context
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk["source_path"]
            start = chunk["start_line"]
            end = chunk["end_line"]
            content = chunk["content"]
            
            context_parts.append(
                f"--- CHUNK {i} ---\n"
                f"File: {source} (lines {start}-{end})\n"
                f"Content:\n{content}\n"
            )
        
        context_str = "\n".join(context_parts)
        
        # 3. Construct prompt
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
        
        # 4. Call model
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_prompt),
        ]
        
        response = await gateway.complete(messages, tools=[])
        return response.content
