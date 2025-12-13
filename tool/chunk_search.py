"""
tool/chunk_search.py - Chunk Search Tool

This module implements a tool for searching code chunks.
Provides semantic code search with proper citations.

Responsibilities:
- Search chunks by query with filters
- Return chunk IDs + snippets + metadata
- Support answering from chunks (cite-from-chunks rule)

Rules:
- Always cite chunk IDs in responses
- If no chunks found, say "not found" and propose next search
- Prefer chunk search before raw file reading
"""

import logging
from typing import Dict, Any, Optional

from core.types import ToolCall, ToolResult
from .bases import BaseTool
from store.chunks import ChunkManager

logger = logging.getLogger(__name__)


class ChunkSearchTool(BaseTool):
    """Tool for searching code chunks.
    
    Allows agent to:
    - Search for code by semantic meaning
    - Get exact citations (chunk IDs + line numbers)
    - Filter by path, file type, chunk type, tags
    """
    
    def __init__(
        self,
        chunk_manager: Optional[ChunkManager] = None,
    ):
        """Initialize chunk search tool.
        
        Args:
            chunk_manager: Optional custom chunk manager
        """
        self.chunk_manager = chunk_manager or ChunkManager()
    
    @property
    def name(self) -> str:
        return "search_chunks"
    
    @property
    def description(self) -> str:
        return (
            "Search code chunks with citations. Returns chunk IDs, source paths, "
            "line numbers, and snippets. Use this BEFORE read_file to find relevant code. "
            "Filters: path_prefix, file_type, chunk_type (function/class/section/file), tags"
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (keywords or concept to find)"
                },
                "k": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10)",
                    "default": 10
                },
                "filters": {
                    "type": "object",
                    "description": "Optional filters",
                    "properties": {
                        "path_prefix": {
                            "type": "string",
                            "description": "Filter by path prefix (e.g., 'tool/', 'flow/')"
                        },
                        "file_type": {
                            "type": "string",
                            "description": "Filter by file extension (e.g., '.py', '.md')"
                        },
                        "chunk_type": {
                            "type": "string",
                            "enum": ["function", "class", "section", "file"],
                            "description": "Filter by chunk type"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by tags (e.g., ['python', 'tool'])"
                        }
                    }
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute chunk search.
        
        Args:
            arguments: Tool arguments with query and optional filters
            
        Returns:
            ToolResult with search results and citations
        """
        try:
            query = arguments.get("query")
            k = arguments.get("k", 10)
            filters = arguments.get("filters", {})
            
            if not query:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error="Missing required parameter: 'query'",
                    success=False,
                )
            
            # Search chunks
            results = self.chunk_manager.search_chunks(
                query=query,
                k=k,
                filters=filters,
            )
            
            # Format output with citations
            if not results:
                output = (
                    f"No chunks found matching: '{query}'\n\n"
                    f"SUGGESTION: Try different keywords or remove filters.\n"
                    f"Current filters: {filters if filters else 'none'}"
                )
            else:
                output = f"Found {len(results)} chunks matching '{query}':\n\n"
                
                for i, result in enumerate(results, 1):
                    chunk_id = result["chunk_id"]
                    source_path = result["source_path"]
                    start_line = result["start_line"]
                    end_line = result["end_line"]
                    chunk_type = result["chunk_type"]
                    name = result.get("name", "")
                    snippet = result["snippet"]
                    
                    output += f"[{i}] CHUNK_ID: {chunk_id}\n"
                    output += f"    Source: {source_path} (lines {start_line}-{end_line})\n"
                    output += f"    Type: {chunk_type}"
                    if name:
                        output += f" ({name})"
                    output += "\n"
                    output += f"    Snippet: {snippet}\n\n"
                
                output += (
                    "CITATION RULE: Always reference chunks by ID in your answer.\n"
                    "Use read_file only if you need full context beyond these snippets."
                )
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Chunk search error: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Chunk search failed: {e}",
                success=False,
            )
    
    def rebuild_index(self, directory: str = ".") -> str:
        """Rebuild chunk index from directory.
        
        Args:
            directory: Root directory to index
            
        Returns:
            Status message
        """
        try:
            chunk_count = self.chunk_manager.ingest_directory(directory)
            self.chunk_manager.save_manifest()
            
            stats = self.chunk_manager.get_stats()
            
            return (
                f"Rebuilt chunk index:\n"
                f"- Total chunks: {stats['total_chunks']}\n"
                f"- Chunk types: {stats['chunk_types']}\n"
                f"- New chunks: {chunk_count}\n"
                f"- Manifest: {stats['manifest_path']}"
            )
        
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            return f"Index rebuild failed: {e}"
