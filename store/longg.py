"""
store/longg.py - Long-term Memory

This module implements long-term persistent storage.
Can use SQLite, Postgres, or other databases.

Responsibilities:
- Persistent conversation storage
- Cross-session memory
- Conversation search and retrieval
- Export/import capabilities

Rules:
- File-based or database-backed
- Survives restarts
- Efficient indexing for search
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from core.types import Message, MessageRole
from .bases import MemoryStore


class SQLiteMemory(MemoryStore):
    """Long-term memory using SQLite.
    
    Stores conversations in a SQLite database.
    Good for production single-user use.
    """
    
    def __init__(self, db_path: str = "./data/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                name TEXT,
                tool_calls TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_conversation (conversation_id)
            )
        """)
        
        # Create conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    async def save_message(
        self,
        conversation_id: str,
        message: Message,
    ) -> None:
        """Save a message to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Ensure conversation exists
        cursor.execute(
            "INSERT OR IGNORE INTO conversations (id) VALUES (?)",
            (conversation_id,)
        )
        
        # Update conversation timestamp
        cursor.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), conversation_id)
        )
        
        # Insert message
        cursor.execute("""
            INSERT INTO messages (conversation_id, role, content, name, tool_calls)
            VALUES (?, ?, ?, ?, ?)
        """, (
            conversation_id,
            message.role.value,
            message.content,
            message.name,
            json.dumps(message.tool_calls) if message.tool_calls else None,
        ))
        
        conn.commit()
        conn.close()
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """Get messages from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if limit:
            cursor.execute("""
                SELECT role, content, name, tool_calls
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (conversation_id, limit))
        else:
            cursor.execute("""
                SELECT role, content, name, tool_calls
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
            """, (conversation_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            role, content, name, tool_calls_json = row
            
            tool_calls = None
            if tool_calls_json:
                tool_calls = json.loads(tool_calls_json)
            
            messages.append(Message(
                role=MessageRole(role),
                content=content,
                name=name,
                tool_calls=tool_calls,
            ))
        
        # Reverse if we used DESC order with limit
        if limit:
            messages.reverse()
        
        return messages
    
    async def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (conversation_id,)
        )
        cursor.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        
        conn.commit()
        conn.close()
    
    def list_conversations(self) -> List[str]:
        """List all conversation IDs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM conversations ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
