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
        return (
            "Store and retrieve semantic knowledge from long-term memory. "
            "Operations: 'store' (save facts), 'search' (find relevant memories), "
            "'reflect' (capture work summary), 'learn' (store insight from failure). "
            "USE MEMORY FOR: facts, discoveries, how things work. "
            "USE LEDGER FOR: operational rules/mistakes (trigger→cause→rule→test format)."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["store", "search", "reflect", "learn"],
                    "description": "Operation: 'store' (save), 'search' (find), 'reflect' (store reflection), 'learn' (store learning from failed query)"
                },
                "content": {
                    "type": "string",
                    "description": "For 'store'/'reflect'/'learn': content to remember. For 'search': query text"
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
            elif operation == "reflect":
                return await self._reflect(content, metadata)
            elif operation == "learn":
                return await self._learn(content, metadata)
            else:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Unknown operation: {operation}. Use 'store', 'search', 'reflect', or 'learn'",
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
            
            # NOTE: Using placeholder embedding until embedding gateway is integrated
            # Current search uses keyword matching, not semantic similarity
            # TODO: Integrate with gate/embed.py for proper semantic search
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
    
    async def _reflect(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> ToolResult:
        """Store a reflection about completed work.
        
        Reflections are triggered periodically to capture patterns and learnings.
        
        Args:
            content: Reflection content (what was done, what worked)
            metadata: Optional metadata
            
        Returns:
            ToolResult with storage confirmation
        """
        from datetime import datetime
        
        # Add reflection-specific metadata
        metadata["category"] = "reflection"
        metadata["timestamp"] = datetime.now().isoformat()
        metadata["type"] = "periodic_reflection"
        
        result = await self._store_memory(content, metadata)
        
        if result.success:
            result.output = f"🪞 Reflection stored:\n{content[:200]}..."
        
        return result
    
    async def _learn(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> ToolResult:
        """Store a learning from a failed query or discovery.
        
        Learnings are triggered when the agent figures out something
        it didn't know before (e.g., after an empty search result).
        
        Auto-detects if content looks like an operational rule and
        suggests using log_mistake instead.
        
        Args:
            content: Learning content (what was discovered)
            metadata: Optional metadata (may include failed_query)
            
        Returns:
            ToolResult with storage confirmation
        """
        from datetime import datetime
        
        # Check if this looks like an operational rule (should use ledger)
        content_lower = content.lower()
        rule_indicators = [
            "rule:", "don't ", "do not ", "always ", "never ", 
            "trigger:", "root cause:", "next time",
        ]
        is_rule_like = any(indicator in content_lower for indicator in rule_indicators)
        
        # Add learning-specific metadata
        metadata["category"] = "learning"
        metadata["timestamp"] = datetime.now().isoformat()
        metadata["trigger"] = metadata.get("trigger", "discovery")
        
        # Try to extract structured playbook from content
        playbook = self._extract_playbook(content, metadata)
        if playbook:
            metadata["playbook"] = playbook
        
        result = await self._store_memory(content, metadata)
        
        if result.success:
            output = f"🧠 Learning stored:\n{content[:200]}...\n\nThis knowledge will be available for future queries."
            
            # If it looked like a rule, suggest ledger
            if is_rule_like:
                output += (
                    "\n\n💡 TIP: This looks like an operational rule. "
                    "Consider also using log_mistake(trigger='...', root_cause='...', rule='...') "
                    "to add it to the structured ledger for easier lookup."
                )
            
            result.output = output
        
        return result
    
    def _extract_playbook(self, content: str, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Extract structured playbook fields from learning content.
        
        Looks for patterns like:
        - TRIGGER: ...
        - SYMPTOM: ...
        - ROOT CAUSE: ...
        - SOLUTION: ...
        - TEST: ...
        
        Returns:
            Dict with extracted fields, or empty dict if no structure found
        """
        import re
        
        playbook = {
            "trigger": metadata.get("trigger", ""),
            "failed_query": metadata.get("failed_query", ""),
            "symptom": "",
            "root_cause": "",
            "solution": "",
            "test": "",
        }
        
        # Try to extract structured fields
        patterns = {
            "trigger": r"TRIGGER:\s*(.+?)(?:\n|$)",
            "symptom": r"SYMPTOM:\s*(.+?)(?:\n|$)",
            "root_cause": r"ROOT[\s_]?CAUSE:\s*(.+?)(?:\n|$)",
            "solution": r"SOLUTION:\s*(.+?)(?:\n|$)",
            "test": r"TEST:\s*(.+?)(?:\n|$)",
        }
        
        content_upper = content.upper()
        has_structure = any(pattern.split(":")[0] + ":" in content_upper for pattern in patterns)
        
        if has_structure:
            for field, pattern in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    playbook[field] = match.group(1).strip()
        else:
            # Freeform - store as symptom
            playbook["symptom"] = content[:500]
        
        # Only return if we found something
        return playbook if any(v for v in playbook.values()) else {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics.
        
        Returns:
            Dictionary with memory counts and info
        """
        return {
            "total_memories": self.vector_store.count(),
            "persist_path": str(self.persist_path),
        }
