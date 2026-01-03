"""
store/session_chunks.py - Session Log Chunking

Parses session logs into searchable chunks so the agent can
query past sessions for errors, tool calls, and learnings.

Usage:
    from store.session_chunks import index_recent_sessions
    index_recent_sessions("logs/", chunk_manager, max_sessions=5)
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


def extract_timestamp(line: str) -> Optional[str]:
    """Extract timestamp from log line.
    
    Expected format: 2025-12-15 16:31:34.435 [INFO] ...
    
    Returns:
        ISO timestamp string or None
    """
    match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    if match:
        return match.group(1)
    return None


def chunk_session_log(log_path: Path) -> List[Dict[str, Any]]:
    """Parse a session log into searchable chunks.
    
    Extracts:
    - Tool calls (successful and failed)
    - Errors and warnings
    - Learning events
    
    Args:
        log_path: Path to session log file
        
    Returns:
        List of chunk dicts with type, content, timestamp, source
    """
    chunks = []
    
    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return chunks
    
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        
        timestamp = extract_timestamp(line)
        
        # Tool calls
        if "[INFO]" in line and "Tool" in line:
            chunks.append({
                "type": "tool_call",
                "content": line[:500],  # Limit length
                "timestamp": timestamp,
                "source": str(log_path.name),
                "tags": ["session", "tool"],
            })
        
        # Errors
        elif "[ERROR]" in line:
            chunks.append({
                "type": "error",
                "content": line[:500],
                "timestamp": timestamp,
                "source": str(log_path.name),
                "tags": ["session", "error"],
            })
        
        # Warnings
        elif "[WARNING]" in line:
            chunks.append({
                "type": "warning", 
                "content": line[:500],
                "timestamp": timestamp,
                "source": str(log_path.name),
                "tags": ["session", "warning"],
            })
        
        # Learning events
        elif "learn" in line.lower() or "memory" in line.lower():
            chunks.append({
                "type": "learning",
                "content": line[:500],
                "timestamp": timestamp,
                "source": str(log_path.name),
                "tags": ["session", "learning"],
            })
    
    return chunks


def index_recent_sessions(
    logs_dir: str,
    chunk_manager: Any,
    max_sessions: int = 5,
) -> int:
    """Index recent session logs for search.
    
    Args:
        logs_dir: Path to logs directory
        chunk_manager: ChunkManager instance to add chunks to
        max_sessions: Maximum number of recent sessions to index
        
    Returns:
        Number of chunks added
    """
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        return 0
    
    # Get recent session logs
    session_files = sorted(
        logs_path.glob("session_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:max_sessions]
    
    total_chunks = 0
    
    for log_file in session_files:
        chunks = chunk_session_log(log_file)
        
        for chunk in chunks:
            # Add to chunk manager with session metadata
            chunk_manager.add_chunk(
                chunk_id=f"session_{log_file.stem}_{total_chunks}",
                content=chunk["content"],
                source_path=f"logs/{log_file.name}",
                chunk_type="session_event",
                metadata={
                    "event_type": chunk["type"],
                    "timestamp": chunk.get("timestamp"),
                    "tags": chunk.get("tags", []),
                }
            )
            total_chunks += 1
    
    return total_chunks
