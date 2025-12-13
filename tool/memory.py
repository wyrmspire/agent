"""
tool/memory.py - Long-Term Memory Tool

This module implements a tool for accessing long-term memory.
Allows the agent to store and retrieve information across sessions.

Responsibilities:
- Store memories with semantic embedding
- Search memories by semantic similarity
- Provide context from past conversations

Rules:
- Memories are persisted to disk
- Search returns relevant context
- Tool handles embedding generation internally
"""

import logging
from typing import Dict, Any, Optional

from core.types import ToolCall, ToolResult
from .bases import BaseTool
from store.vects import SimpleVectorStore

logger = logging.getLogger(__name__)


class MemoryTool(BaseTool):
    """Tool for long-term memory access.
    
    Allows agent to:
    - Store important information for future reference
    - Search previous memories by semantic similarity
    - Build knowledge across sessions
    """
    
    def __init__(
        self,
        vector_store: Optional[SimpleVectorStore] = None,
        persist_path: str = "./workspace/memory.pkl",
    ):
        """Initialize memory tool.
        
        Args:
            vector_store: Optional custom vector store
            persist_path: Path to persist memories
        """
        self.vector_store = vector_store or SimpleVectorStore(persist_path=persist_path)
        self.persist_path = persist_path
        
        # For now, use simple keyword-based search
        # TODO: Integrate with embedding gateway for semantic search
        self._memory_counter = 0
    
    @property
    def name(self) -> str:
        return "memory"
    
    @property
    def description(self) -> str:
        return "Store and retrieve information from long-term memory. Operations: 'store' (save info), 'search' (find relevant memories)"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["store", "search"],
                    "description": "Operation to perform: 'store' or 'search'"
                },
                "content": {
                    "type": "string",
                    "description": "For 'store': content to remember. For 'search': query text"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata (tags, category, etc.)",
                    "additionalProperties": True
                }
            },
            "required": ["operation", "content"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute memory operation.
        
        Args:
            arguments: Tool arguments with operation and content
            
        Returns:
            ToolResult with operation outcome
        """
        try:
            operation = arguments.get("operation")
            content = arguments.get("content")
            metadata = arguments.get("metadata", {})
            
            if not operation or not content:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error="Missing required parameters: 'operation' and 'content'",
                    success=False,
                )
            
            if operation == "store":
                return await self._store_memory(content, metadata)
            elif operation == "search":
                return await self._search_memory(content, metadata)
            else:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Unknown operation: {operation}. Use 'store' or 'search'",
                    success=False,
                )
        
        except Exception as e:
            logger.error(f"Memory tool error: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Memory operation failed: {e}",
                success=False,
            )
    
    async def _store_memory(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> ToolResult:
        """Store content in long-term memory.
        
        Args:
            content: Content to store
            metadata: Optional metadata
            
        Returns:
            ToolResult with storage confirmation
        """
        try:
            # Generate unique ID
            self._memory_counter += 1
            memory_id = f"mem_{self._memory_counter}"
            
            # For now, use a simple dummy embedding
            # TODO: Use actual embedding gateway
            dummy_embedding = [0.0] * 768  # Standard embedding dimension
            
            # Store in vector store
            await self.vector_store.add(
                id=memory_id,
                text=content,
                embedding=dummy_embedding,
                metadata=metadata,
            )
            
            # Persist to disk
            self.vector_store.save()
            
            output = f"Stored memory with ID: {memory_id}\nContent: {content[:100]}..."
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Storage failed: {e}",
                success=False,
            )
    
    async def _search_memory(
        self,
        query: str,
        metadata: Dict[str, Any],
    ) -> ToolResult:
        """Search long-term memory.
        
        Args:
            query: Search query
            metadata: Optional search filters
            
        Returns:
            ToolResult with search results
        """
        try:
            # For now, use simple keyword matching
            # TODO: Use actual embedding-based semantic search
            
            results = []
            query_lower = query.lower()
            
            # Simple keyword search through stored documents
            for doc_id, doc in self.vector_store.documents.items():
                text = doc.get("text", "")
                if query_lower in text.lower():
                    results.append({
                        "id": doc_id,
                        "text": text,
                        "metadata": doc.get("metadata", {}),
                    })
            
            if not results:
                output = f"No memories found matching: {query}"
            else:
                output = f"Found {len(results)} relevant memories:\n\n"
                for i, result in enumerate(results[:5], 1):  # Limit to 5
                    text = result["text"]
                    preview = text[:200] + ("..." if len(text) > 200 else "")
                    output += f"{i}. {preview}\n\n"
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Search failed: {e}",
                success=False,
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics.
        
        Returns:
            Dictionary with memory counts and info
        """
        return {
            "total_memories": self.vector_store.count(),
            "persist_path": str(self.persist_path),
        }
