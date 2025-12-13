"""
store/bases.py - Memory Store Interface

This module defines the abstract interface for memory stores.
Memory stores handle conversation history and long-term recall.

Responsibilities:
- Define standard interface for memory
- Support both short-term and long-term memory
- Enable retrieval and search

Rules:
- Stores are pluggable (memory → SQLite → Postgres)
- Interface is vendor-neutral
- Retrieval returns citations + snippets
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.types import Message


class MemoryStore(ABC):
    """Abstract base class for memory stores.
    
    A memory store handles persistence of conversations
    and other agent memory.
    """
    
    @abstractmethod
    async def save_message(
        self,
        conversation_id: str,
        message: Message,
    ) -> None:
        """Save a message to the store.
        
        Args:
            conversation_id: ID of the conversation
            message: Message to save
        """
        pass
    
    @abstractmethod
    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """Get messages from a conversation.
        
        Args:
            conversation_id: ID of the conversation
            limit: Optional limit on number of messages
            
        Returns:
            List of messages (newest first)
        """
        pass
    
    @abstractmethod
    async def clear_conversation(self, conversation_id: str) -> None:
        """Clear all messages in a conversation.
        
        Args:
            conversation_id: ID of the conversation
        """
        pass


class VectorStore(ABC):
    """Abstract base class for vector stores.
    
    A vector store handles embeddings for semantic search.
    Used for long-term memory and document retrieval.
    """
    
    @abstractmethod
    async def add(
        self,
        id: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a document with its embedding.
        
        Args:
            id: Unique document ID
            text: Document text
            embedding: Vector embedding
            metadata: Optional metadata
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents.
        
        Args:
            query_embedding: Query vector
            limit: Maximum results to return
            min_score: Minimum similarity score
            
        Returns:
            List of results with text, score, and metadata.
            Each result includes:
            - id: Document ID
            - text: Document text
            - score: Similarity score
            - metadata: Document metadata
        """
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> None:
        """Delete a document.
        
        Args:
            id: Document ID to delete
        """
        pass


class DocumentStore(ABC):
    """Abstract base class for document stores.
    
    A document store handles ingestion and chunking of
    documents for retrieval.
    """
    
    @abstractmethod
    async def ingest(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Ingest a document.
        
        Args:
            doc_id: Unique document ID
            content: Document content
            metadata: Optional metadata
            
        Returns:
            Number of chunks created
        """
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks.
        
        Returns citations + snippets.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of chunks with:
            - doc_id: Source document ID
            - chunk_text: Text snippet
            - score: Relevance score
            - citation: Source reference
        """
        pass
