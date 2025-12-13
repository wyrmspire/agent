"""
gate/bases.py - Model Gateway Interface

This module defines the abstract interface for model gateways.
All model adapters (LM Studio, local, OpenAI, etc.) implement this interface.

Responsibilities:
- Define standard interface for model communication
- Normalize request/response formats
- Handle streaming
- Abstract away model-specific quirks

Rules:
- Only depends on core/
- No implementation details (those go in lmstd.py, etc.)
- Interface should work for any LLM backend
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional

from core.types import Message, Tool
from core.proto import AgentResponse, StreamChunk


class ModelGateway(ABC):
    """Abstract base class for model gateways.
    
    A gateway handles communication with a language model backend.
    It translates between our internal format and the model's format.
    """
    
    def __init__(self, model: str):
        self.model = model
    
    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentResponse:
        """Generate a completion from the model.
        
        Args:
            messages: Conversation history
            tools: Available tools (if model supports function calling)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            AgentResponse with the model's output
        """
        pass
    
    @abstractmethod
    async def stream_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming completion from the model.
        
        Args:
            messages: Conversation history
            tools: Available tools (if model supports function calling)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Yields:
            StreamChunk objects with incremental content
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the model backend is healthy.
        
        Returns:
            True if backend is reachable and responding
        """
        pass


class EmbeddingGateway(ABC):
    """Abstract base class for embedding gateways.
    
    An embedding gateway generates vector embeddings from text.
    Used for semantic search and memory retrieval.
    """
    
    def __init__(self, model: str):
        self.model = model
    
    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (one per text)
        """
        pass
    
    @abstractmethod
    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            
        Returns:
            Embedding vector
        """
        pass
