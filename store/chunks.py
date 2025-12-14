"""
store/chunks.py - Code Chunk Management

This module implements intelligent code chunking for retrieval.
Creates function-level and section-level chunks with proper boundaries.

Responsibilities:
- Parse source files into semantic chunks
- Generate chunk manifest
- Deduplicate chunks (O(1) hash check)
- Persist content to disk
- Lazy load content for search/retrieval
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

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
    name: Optional[str] = None

class ChunkManager:
    """Manages code chunks for retrieval."""
    
    # Sensitive patterns to exclude
    SENSITIVE_PATTERNS = [
        r"\.env", r"\.ssh", r"\.git/", r"\.github/agents/", r"password", r"passwd", 
        r"secret", r"token", r"key", r"api[_-]?key", r"auth[_-]?token", r"credentials", 
        r"private[_-]?key", r"__pycache__", r"\.pyc$", r"node_modules/", r"dist/", 
        r"build/", r"\.venv/", r"venv/", r"target/", r"bin/", r"obj/",
    ]
    
    SUPPORTED_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml"}
    
    def __init__(
        self,
        chunks_dir: str = "./store/chunks",
        manifest_path: str = "./store/chunks_manifest.json",
    ):
        self.chunks_dir = Path(chunks_dir)
        self.manifest_path = Path(manifest_path)
        self.chunks: Dict[str, ChunkMetadata] = {}
        self.hashes: Dict[str, str] = {} # hash -> chunk_id map for O(1) dedupe
        self.chunk_content_cache: Dict[str, str] = {} # Optional memory cache
        self.source_to_chunks: Dict[str, List[str]] = {}  # source_path -> [chunk_ids] for stale detection
        self.stale_chunk_ids: List[str] = []  # IDs replaced on last ingest
        
        # Create directories
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing manifest
        self._load_manifest()
    
    def _is_sensitive(self, path: str) -> bool:
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        return False
    
    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _chunk_python_file(self, content: str, source_path: str) -> List[ChunkMetadata]:
        chunks = []
        lines = content.split("\n")
        
        current_chunk_start = None
        current_chunk_name = None
        current_chunk_type = None
        
        # Helper to finish a chunk
        def finish_chunk(start, end, ctype, name):
            if start is None: return
            # Adjust end to be inclusive if needed, or exclusive. Standard: end is last line index 1-based.
            # Here: lines are 1-based, slicing is 0-based.
            # content slice: lines[start-1:end]
            chunk_content = "\n".join(lines[start-1:end])
            if not chunk_content.strip(): return
            
            self._create_chunk_metadata(chunks, chunk_content, source_path, start, end, ctype, name)

        for i, line in enumerate(lines, start=1):
            match_func = re.match(r"^(\s*)def\s+(\w+)\s*\(", line)
            match_class = re.match(r"^(\s*)class\s+(\w+)(?:\(|:)", line)
            
            if match_func:
                finish_chunk(current_chunk_start, i-1, current_chunk_type, current_chunk_name)
                current_chunk_start = i
                current_chunk_name = match_func.group(2)
                current_chunk_type = "function"
            
            elif match_class:
                finish_chunk(current_chunk_start, i-1, current_chunk_type, current_chunk_name)
                current_chunk_start = i
                current_chunk_name = match_class.group(2)
                current_chunk_type = "class"
        
        # Finish last
        finish_chunk(current_chunk_start, len(lines), current_chunk_type, current_chunk_name)
        
        # Fallback if no chunks
        if not chunks:
            finish_chunk(1, len(lines), "file", None)
            
        return chunks

    def _create_chunk_metadata(self, chunks_list, content, source, start, end, ctype, name):
        chunk_hash = self._hash_content(content)
        chunk_id = f"chunk_{chunk_hash}"
        
        # Store content temporarily attached to object-like structure or just cache it
        # We'll use the cache to pass content back to ingest_file
        self.chunk_content_cache[chunk_id] = content
        
        chunks_list.append(ChunkMetadata(
            id=chunk_id,
            source_path=source,
            start_line=start,
            end_line=end,
            hash=chunk_hash,
            tags=["python", ctype or "code"],
            created_at=datetime.utcnow().isoformat(),
            chunk_type=ctype or "section",
            name=name,
        ))

    def _chunk_markdown_file(self, content: str, source_path: str) -> List[ChunkMetadata]:
        chunks = []
        lines = content.split("\n")
        current_start = None
        current_name = None
        
        def finish(start, end, name):
            if start is None: return
            c_content = "\n".join(lines[start-1:end])
            if not c_content.strip(): return
            
            chunk_hash = self._hash_content(c_content)
            chunk_id = f"chunk_{chunk_hash}"
            self.chunk_content_cache[chunk_id] = c_content
            
            chunks.append(ChunkMetadata(
                id=chunk_id,
                source_path=source_path,
                start_line=start,
                end_line=end,
                hash=chunk_hash,
                tags=["markdown", "section"],
                created_at=datetime.utcnow().isoformat(),
                chunk_type="section",
                name=name,
            ))

        for i, line in enumerate(lines, start=1):
            match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if match:
                finish(current_start, i-1, current_name)
                current_start = i
                current_name = match.group(2)
        
        finish(current_start, len(lines), current_name)
        if not chunks:
            finish(1, len(lines), None) # Whole file
            chunks[-1].chunk_type = "file" # Fixup type
            
        return chunks

    def _chunk_generic_file(self, content: str, source_path: str) -> List[ChunkMetadata]:
        chunk_hash = self._hash_content(content)
        chunk_id = f"chunk_{chunk_hash}"
        lines = content.split("\n")
        ext = Path(source_path).suffix
        
        self.chunk_content_cache[chunk_id] = content
        
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
        return [chunk]

    def ingest_file(self, file_path: str) -> int:
        try:
            path = Path(file_path)
            source_path = str(path.resolve())  # Normalize to absolute for consistency
            
            if not path.exists() or self._is_sensitive(source_path):
                return 0
            if path.suffix not in self.SUPPORTED_EXTENSIONS:
                return 0
            
            content = path.read_text(encoding="utf-8")
            
            if path.suffix == ".py":
                chunks = self._chunk_python_file(content, source_path)
            elif path.suffix == ".md":
                chunks = self._chunk_markdown_file(content, source_path)
            else:
                chunks = self._chunk_generic_file(content, source_path)
            
            # Get old chunk IDs for this source (for stale detection)
            old_chunk_ids = set(self.source_to_chunks.get(source_path, []))
            new_chunk_ids = []
            
            new_count = 0
            for chunk in chunks:
                # O(1) Check for duplicate content
                if chunk.hash in self.hashes:
                    # Duplicate content - use existing ID, update metadata
                    existing_id = self.hashes[chunk.hash]
                    new_chunk_ids.append(existing_id)
                    
                    # Update metadata to reflect latest location
                    if existing_id in self.chunks:
                        existing = self.chunks[existing_id]
                        existing.source_path = chunk.source_path
                        existing.start_line = chunk.start_line
                        existing.end_line = chunk.end_line
                        existing.chunk_type = chunk.chunk_type
                        existing.name = chunk.name
                    continue
                
                # New chunk
                new_chunk_ids.append(chunk.id)
                self.chunks[chunk.id] = chunk
                self.hashes[chunk.hash] = chunk.id
                
                # Persist content
                content_to_save = self.chunk_content_cache.get(chunk.id, "")
                self._persist_chunk_content(chunk.id, content_to_save)
                
                new_count += 1
            
            # Update source mapping
            self.source_to_chunks[source_path] = new_chunk_ids
            
            # Detect stale chunks (old IDs not in new set)
            stale_ids = old_chunk_ids - set(new_chunk_ids)
            if stale_ids:
                self.stale_chunk_ids.extend(stale_ids)
                # Remove stale chunks from memory
                for stale_id in stale_ids:
                    if stale_id in self.chunks:
                        stale_chunk = self.chunks.pop(stale_id)
                        if stale_chunk.hash in self.hashes:
                            del self.hashes[stale_chunk.hash]
                logger.info(f"Marked {len(stale_ids)} chunks as stale from {file_path}")
            
            logger.info(f"Ingested {new_count} new chunks from {file_path}")
            return new_count
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            return 0

    def ingest_directory(self, directory: str, recursive: bool = True) -> int:
        # Clear stale IDs at start of directory ingest
        self.stale_chunk_ids = []
        
        total_chunks = 0
        dir_path = Path(directory)
        if not dir_path.exists():
            return 0
        
        files = dir_path.rglob("*") if recursive else dir_path.glob("*")
        for file_path in files:
            if file_path.is_file():
                total_chunks += self.ingest_file(str(file_path))
        return total_chunks


    def search_chunks(self, query: str, k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        filters = filters or {}
        results = []
        query_lower = query.lower()
        
        # Iterate all chunks
        # Optimization: In real system, we'd use an index. Here we scan.
        for chunk_id, chunk_meta in self.chunks.items():
            # Filters
            if filters.get("path_prefix") and not chunk_meta.source_path.startswith(filters["path_prefix"]): continue
            if filters.get("file_type") and not chunk_meta.source_path.endswith(filters["file_type"]): continue
            if filters.get("chunk_type") and chunk_meta.chunk_type != filters["chunk_type"]: continue
            
            # Lazy load for content check
            # NOTE: iterating all files and reading disk is slow. 
            # ideally search_chunks is ONLY used for small workspaces or keyword search is optimized.
            # For 0.9A, we assume workspace fits in FS cache or is small.
            chunk_data = self.get_chunk(chunk_id)
            if not chunk_data: continue
            
            content = chunk_data["content"]
            if query_lower in content.lower():
                results.append({
                    "chunk_id": chunk_id,
                    "source_path": chunk_meta.source_path,
                    "start_line": chunk_meta.start_line,
                    "end_line": chunk_meta.end_line,
                    "chunk_type": chunk_meta.chunk_type,
                    "name": chunk_meta.name,
                    "content": content,
                    "snippet": self.get_snippet(content, query_lower),
                })
        
        # Deterministic sorting: Count desc, Path asc, Line asc
        results.sort(key=lambda x: (-x["content"].lower().count(query_lower), x["source_path"], x["start_line"]))
        return results[:k]

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        if chunk_id not in self.chunks:
            return None
        
        chunk_meta = self.chunks[chunk_id]
        content = self._load_content(chunk_id)
        
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

    def _load_content(self, chunk_id: str) -> str:
        """Load content from disk if not in cache."""
        # Check cache first (populated during ingest)
        if chunk_id in self.chunk_content_cache:
            return self.chunk_content_cache[chunk_id]
            
        # Check disk
        chunk_path = self.chunks_dir / f"{chunk_id}.txt"
        if chunk_path.exists():
            return chunk_path.read_text(encoding="utf-8")
        
        return ""

    def _persist_chunk_content(self, chunk_id: str, content: str) -> None:
        try:
            (self.chunks_dir / f"{chunk_id}.txt").write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to persist chunk content {chunk_id}: {e}")

    def get_snippet(self, content: str, query: str, context: int = 100) -> str:
        content_lower = content.lower()
        idx = content_lower.find(query)
        if idx == -1:
            return content[:200] + ("..." if len(content) > 200 else "")
        start = max(0, idx - context)
        end = min(len(content), idx + len(query) + context)
        snippet = content[start:end]
        if start > 0: snippet = "..." + snippet
        if end < len(content): snippet = snippet + "..."
        return snippet

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about chunks.
        
        Returns:
            Dict with statistics about the chunk manager
        """
        chunk_types = {}
        for chunk in self.chunks.values():
            chunk_types[chunk.chunk_type] = chunk_types.get(chunk.chunk_type, 0) + 1
        
        return {
            "total_chunks": len(self.chunks),
            "chunk_types": chunk_types,
            "total_sources": len(self.source_to_chunks),
            "manifest_path": str(self.manifest_path),
            "chunks_dir": str(self.chunks_dir),
        }
    
    def save_manifest(self) -> bool:
        try:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": "0.9A",
                "chunk_count": len(self.chunks),
                "last_updated": datetime.utcnow().isoformat(),
                "chunks": [asdict(chunk) for chunk in self.chunks.values()],
                "source_to_chunks": self.source_to_chunks,  # v1.1: persist for stale detection
            }
            with open(self.manifest_path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")
            return False

    def _load_manifest(self) -> bool:
        if not self.manifest_path.exists():
            return False
        try:
            with open(self.manifest_path, "r") as f:
                data = json.load(f)
            self.chunks = {}
            self.hashes = {}
            self.source_to_chunks = data.get("source_to_chunks", {})  # v1.1: load for stale detection
            for chunk_data in data.get("chunks", []):
                chunk = ChunkMetadata(**chunk_data)
                self.chunks[chunk.id] = chunk
                self.hashes[chunk.hash] = chunk.id
            logger.info(f"Loaded {len(self.chunks)} chunks from manifest")
            return True
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return False
