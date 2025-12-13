"""
store/chunks.py - Code Chunk Management

This module implements intelligent code chunking for retrieval.
Creates function-level and section-level chunks with proper boundaries.

Responsibilities:
- Parse source files into semantic chunks (functions, classes, sections)
- Generate chunk manifest with IDs, metadata, and hashes
- Support chunk deduplication via hash comparison
- Exclude sensitive files at ingestion time

Rules:
- Chunk boundaries respect code structure (not arbitrary size limits)
- Each chunk has unique ID for citation
- Manifest persists to disk (chunks_manifest.json)
- Chunks stored in store/chunks/ directory
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    """Metadata for a code chunk."""
    id: str
    source_path: str
    start_line: int
    end_line: int
    hash: str
    tags: List[str]
    created_at: str
    chunk_type: str  # "function", "class", "section", "file"
    name: Optional[str] = None  # function/class name if applicable


class ChunkManager:
    """Manages code chunks for retrieval.
    
    Creates semantic chunks from source files and maintains a manifest
    for efficient lookup and citation.
    """
    
    # Sensitive patterns to exclude
    SENSITIVE_PATTERNS = [
        r"\.env",
        r"\.ssh",
        r"\.git/",
        r"\.github/agents/",
        r"password",
        r"secret",
        r"token",
        r"key",
        r"credentials",
        r"__pycache__",
        r"\.pyc$",
    ]
    
    # File extensions to process
    SUPPORTED_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml"}
    
    def __init__(
        self,
        chunks_dir: str = "./store/chunks",
        manifest_path: str = "./store/chunks_manifest.json",
    ):
        """Initialize chunk manager.
        
        Args:
            chunks_dir: Directory to store chunks
            manifest_path: Path to manifest file
        """
        self.chunks_dir = Path(chunks_dir)
        self.manifest_path = Path(manifest_path)
        self.chunks: Dict[str, ChunkMetadata] = {}
        self.chunk_content: Dict[str, str] = {}
        
        # Create directories
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing manifest
        self._load_manifest()
    
    def _is_sensitive(self, path: str) -> bool:
        """Check if file should be excluded as sensitive.
        
        Args:
            path: File path to check
            
        Returns:
            True if file is sensitive and should be excluded
        """
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        return False
    
    def _hash_content(self, content: str) -> str:
        """Generate hash for content deduplication.
        
        Args:
            content: Content to hash
            
        Returns:
            SHA256 hash of content
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _chunk_python_file(
        self,
        content: str,
        source_path: str,
    ) -> List[ChunkMetadata]:
        """Chunk Python file by functions and classes.
        
        Args:
            content: File content
            source_path: Source file path
            
        Returns:
            List of chunk metadata
        """
        chunks = []
        lines = content.split("\n")
        
        # Simple regex-based chunking (could be enhanced with AST)
        current_chunk_start = None
        current_chunk_name = None
        current_chunk_type = None
        indent_level = 0
        
        for i, line in enumerate(lines, start=1):
            # Detect function or class definition
            match_func = re.match(r"^(\s*)def\s+(\w+)\s*\(", line)
            match_class = re.match(r"^(\s*)class\s+(\w+)", line)
            
            if match_func:
                # Save previous chunk if exists
                if current_chunk_start is not None:
                    chunk_content = "\n".join(lines[current_chunk_start-1:i-1])
                    chunk_hash = self._hash_content(chunk_content)
                    chunk_id = f"chunk_{chunk_hash}"
                    
                    chunks.append(ChunkMetadata(
                        id=chunk_id,
                        source_path=source_path,
                        start_line=current_chunk_start,
                        end_line=i-1,
                        hash=chunk_hash,
                        tags=["python", current_chunk_type or "code"],
                        created_at=datetime.utcnow().isoformat(),
                        chunk_type=current_chunk_type or "section",
                        name=current_chunk_name,
                    ))
                    self.chunk_content[chunk_id] = chunk_content
                
                # Start new function chunk
                current_chunk_start = i
                current_chunk_name = match_func.group(2)
                current_chunk_type = "function"
                indent_level = len(match_func.group(1))
            
            elif match_class:
                # Save previous chunk if exists
                if current_chunk_start is not None:
                    chunk_content = "\n".join(lines[current_chunk_start-1:i-1])
                    chunk_hash = self._hash_content(chunk_content)
                    chunk_id = f"chunk_{chunk_hash}"
                    
                    chunks.append(ChunkMetadata(
                        id=chunk_id,
                        source_path=source_path,
                        start_line=current_chunk_start,
                        end_line=i-1,
                        hash=chunk_hash,
                        tags=["python", current_chunk_type or "code"],
                        created_at=datetime.utcnow().isoformat(),
                        chunk_type=current_chunk_type or "section",
                        name=current_chunk_name,
                    ))
                    self.chunk_content[chunk_id] = chunk_content
                
                # Start new class chunk
                current_chunk_start = i
                current_chunk_name = match_class.group(2)
                current_chunk_type = "class"
                indent_level = len(match_class.group(1))
        
        # Save last chunk
        if current_chunk_start is not None:
            chunk_content = "\n".join(lines[current_chunk_start-1:])
            chunk_hash = self._hash_content(chunk_content)
            chunk_id = f"chunk_{chunk_hash}"
            
            chunks.append(ChunkMetadata(
                id=chunk_id,
                source_path=source_path,
                start_line=current_chunk_start,
                end_line=len(lines),
                hash=chunk_hash,
                tags=["python", current_chunk_type or "code"],
                created_at=datetime.utcnow().isoformat(),
                chunk_type=current_chunk_type or "section",
                name=current_chunk_name,
            ))
            self.chunk_content[chunk_id] = chunk_content
        
        # If no chunks created (e.g., module-level code only), create one chunk for entire file
        if not chunks:
            chunk_hash = self._hash_content(content)
            chunk_id = f"chunk_{chunk_hash}"
            chunks.append(ChunkMetadata(
                id=chunk_id,
                source_path=source_path,
                start_line=1,
                end_line=len(lines),
                hash=chunk_hash,
                tags=["python", "file"],
                created_at=datetime.utcnow().isoformat(),
                chunk_type="file",
                name=None,
            ))
            self.chunk_content[chunk_id] = content
        
        return chunks
    
    def _chunk_markdown_file(
        self,
        content: str,
        source_path: str,
    ) -> List[ChunkMetadata]:
        """Chunk Markdown file by headers.
        
        Args:
            content: File content
            source_path: Source file path
            
        Returns:
            List of chunk metadata
        """
        chunks = []
        lines = content.split("\n")
        
        current_chunk_start = None
        current_chunk_name = None
        
        for i, line in enumerate(lines, start=1):
            # Detect markdown header
            match = re.match(r"^(#{1,6})\s+(.+)$", line)
            
            if match:
                # Save previous chunk if exists
                if current_chunk_start is not None:
                    chunk_content = "\n".join(lines[current_chunk_start-1:i-1])
                    chunk_hash = self._hash_content(chunk_content)
                    chunk_id = f"chunk_{chunk_hash}"
                    
                    chunks.append(ChunkMetadata(
                        id=chunk_id,
                        source_path=source_path,
                        start_line=current_chunk_start,
                        end_line=i-1,
                        hash=chunk_hash,
                        tags=["markdown", "section"],
                        created_at=datetime.utcnow().isoformat(),
                        chunk_type="section",
                        name=current_chunk_name,
                    ))
                    self.chunk_content[chunk_id] = chunk_content
                
                # Start new section
                current_chunk_start = i
                current_chunk_name = match.group(2)
        
        # Save last chunk
        if current_chunk_start is not None:
            chunk_content = "\n".join(lines[current_chunk_start-1:])
            chunk_hash = self._hash_content(chunk_content)
            chunk_id = f"chunk_{chunk_hash}"
            
            chunks.append(ChunkMetadata(
                id=chunk_id,
                source_path=source_path,
                start_line=current_chunk_start,
                end_line=len(lines),
                hash=chunk_hash,
                tags=["markdown", "section"],
                created_at=datetime.utcnow().isoformat(),
                chunk_type="section",
                name=current_chunk_name,
            ))
            self.chunk_content[chunk_id] = chunk_content
        
        # If no chunks, create one for entire file
        if not chunks:
            chunk_hash = self._hash_content(content)
            chunk_id = f"chunk_{chunk_hash}"
            chunks.append(ChunkMetadata(
                id=chunk_id,
                source_path=source_path,
                start_line=1,
                end_line=len(lines),
                hash=chunk_hash,
                tags=["markdown", "file"],
                created_at=datetime.utcnow().isoformat(),
                chunk_type="file",
                name=None,
            ))
            self.chunk_content[chunk_id] = content
        
        return chunks
    
    def _chunk_generic_file(
        self,
        content: str,
        source_path: str,
    ) -> List[ChunkMetadata]:
        """Chunk generic text file (whole file as one chunk).
        
        Args:
            content: File content
            source_path: Source file path
            
        Returns:
            List with single chunk metadata
        """
        chunk_hash = self._hash_content(content)
        chunk_id = f"chunk_{chunk_hash}"
        
        lines = content.split("\n")
        ext = Path(source_path).suffix
        
        chunk = ChunkMetadata(
            id=chunk_id,
            source_path=source_path,
            start_line=1,
            end_line=len(lines),
            hash=chunk_hash,
            tags=[ext.lstrip("."), "file"],
            created_at=datetime.utcnow().isoformat(),
            chunk_type="file",
            name=None,
        )
        
        self.chunk_content[chunk_id] = content
        return [chunk]
    
    def ingest_file(self, file_path: str) -> int:
        """Ingest a file and create chunks.
        
        Args:
            file_path: Path to file to ingest
            
        Returns:
            Number of chunks created
        """
        try:
            path = Path(file_path)
            
            # Check if file exists
            if not path.exists():
                logger.warning(f"File not found: {file_path}")
                return 0
            
            # Check if sensitive
            if self._is_sensitive(str(path)):
                logger.info(f"Skipping sensitive file: {file_path}")
                return 0
            
            # Check extension
            if path.suffix not in self.SUPPORTED_EXTENSIONS:
                logger.debug(f"Skipping unsupported file type: {file_path}")
                return 0
            
            # Read content
            content = path.read_text(encoding="utf-8")
            
            # Chunk based on file type
            if path.suffix == ".py":
                chunks = self._chunk_python_file(content, str(path))
            elif path.suffix == ".md":
                chunks = self._chunk_markdown_file(content, str(path))
            else:
                chunks = self._chunk_generic_file(content, str(path))
            
            # Check for duplicates and add new chunks
            new_count = 0
            for chunk in chunks:
                if chunk.hash not in [c.hash for c in self.chunks.values()]:
                    self.chunks[chunk.id] = chunk
                    new_count += 1
                else:
                    logger.debug(f"Duplicate chunk found: {chunk.id}")
            
            logger.info(f"Ingested {new_count} new chunks from {file_path}")
            return new_count
        
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            return 0
    
    def ingest_directory(
        self,
        directory: str,
        recursive: bool = True,
    ) -> int:
        """Ingest all files in a directory.
        
        Args:
            directory: Directory to ingest
            recursive: Whether to process subdirectories
            
        Returns:
            Total number of chunks created
        """
        total_chunks = 0
        dir_path = Path(directory)
        
        if not dir_path.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0
        
        # Get files
        if recursive:
            files = dir_path.rglob("*")
        else:
            files = dir_path.glob("*")
        
        # Ingest each file
        for file_path in files:
            if file_path.is_file():
                total_chunks += self.ingest_file(str(file_path))
        
        logger.info(f"Ingested {total_chunks} total chunks from {directory}")
        return total_chunks
    
    def search_chunks(
        self,
        query: str,
        k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks.
        
        Args:
            query: Search query (keyword-based for now)
            k: Maximum number of results
            filters: Optional filters (path_prefix, file_type, tags, etc.)
            
        Returns:
            List of matching chunks with content
        """
        filters = filters or {}
        results = []
        
        # Simple keyword search
        query_lower = query.lower()
        
        for chunk_id, chunk_meta in self.chunks.items():
            # Apply filters
            if filters.get("path_prefix"):
                if not chunk_meta.source_path.startswith(filters["path_prefix"]):
                    continue
            
            if filters.get("file_type"):
                if not chunk_meta.source_path.endswith(filters["file_type"]):
                    continue
            
            if filters.get("chunk_type"):
                if chunk_meta.chunk_type != filters["chunk_type"]:
                    continue
            
            if filters.get("tags"):
                filter_tags = set(filters["tags"])
                chunk_tags = set(chunk_meta.tags)
                if not filter_tags.intersection(chunk_tags):
                    continue
            
            # Check if query matches content
            content = self.chunk_content.get(chunk_id, "")
            if query_lower in content.lower():
                results.append({
                    "chunk_id": chunk_id,
                    "source_path": chunk_meta.source_path,
                    "start_line": chunk_meta.start_line,
                    "end_line": chunk_meta.end_line,
                    "chunk_type": chunk_meta.chunk_type,
                    "name": chunk_meta.name,
                    "content": content,
                    "snippet": self._get_snippet(content, query_lower),
                })
        
        # Sort by relevance (simple: count occurrences)
        results.sort(
            key=lambda x: x["content"].lower().count(query_lower),
            reverse=True,
        )
        
        return results[:k]
    
    def _get_snippet(self, content: str, query: str, context: int = 100) -> str:
        """Get a snippet of content around the query match.
        
        Args:
            content: Full content
            query: Query string (lowercase)
            context: Characters of context on each side
            
        Returns:
            Snippet with query highlighted
        """
        content_lower = content.lower()
        idx = content_lower.find(query)
        
        if idx == -1:
            # Return first N characters
            return content[:200] + ("..." if len(content) > 200 else "")
        
        start = max(0, idx - context)
        end = min(len(content), idx + len(query) + context)
        
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get full chunk by ID.
        
        Args:
            chunk_id: Chunk ID
            
        Returns:
            Chunk data with content, or None if not found
        """
        if chunk_id not in self.chunks:
            return None
        
        chunk_meta = self.chunks[chunk_id]
        content = self.chunk_content.get(chunk_id, "")
        
        return {
            "chunk_id": chunk_id,
            "source_path": chunk_meta.source_path,
            "start_line": chunk_meta.start_line,
            "end_line": chunk_meta.end_line,
            "chunk_type": chunk_meta.chunk_type,
            "name": chunk_meta.name,
            "tags": chunk_meta.tags,
            "content": content,
        }
    
    def _load_manifest(self) -> bool:
        """Load manifest from disk.
        
        Returns:
            True if loaded successfully
        """
        if not self.manifest_path.exists():
            logger.info("No existing manifest found")
            return False
        
        try:
            with open(self.manifest_path, "r") as f:
                data = json.load(f)
            
            self.chunks = {}
            for chunk_data in data.get("chunks", []):
                chunk = ChunkMetadata(**chunk_data)
                self.chunks[chunk.id] = chunk
            
            # Note: chunk_content not persisted, will be regenerated on ingest
            logger.info(f"Loaded {len(self.chunks)} chunks from manifest")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return False
    
    def save_manifest(self) -> bool:
        """Save manifest to disk.
        
        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data
            data = {
                "version": "1.0",
                "chunk_count": len(self.chunks),
                "last_updated": datetime.utcnow().isoformat(),
                "chunks": [asdict(chunk) for chunk in self.chunks.values()],
            }
            
            # Save to disk
            with open(self.manifest_path, "w") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.chunks)} chunks to manifest")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get chunk statistics.
        
        Returns:
            Statistics about chunks
        """
        chunk_types = {}
        for chunk in self.chunks.values():
            chunk_types[chunk.chunk_type] = chunk_types.get(chunk.chunk_type, 0) + 1
        
        return {
            "total_chunks": len(self.chunks),
            "chunk_types": chunk_types,
            "manifest_path": str(self.manifest_path),
            "chunks_dir": str(self.chunks_dir),
        }
