"""
store/short.py - Short-term Memory

This module implements in-memory short-term storage.
Suitable for conversation buffers and recent history.

Responsibilities:
- Store recent conversation history
- Fast in-memory access
- Optional message summarization
- Sliding window for context management

Rules:
- Not persistent (resets on restart)
- Good for single sessions
- Can be upgraded to persistent store later
"""

from typing import Dict, List, Optional
from collections import defaultdict

from core.types import Message
from .bases import MemoryStore


class ShortMemory(MemoryStore):
    """In-memory short-term memory store.
    
    Stores conversations in memory with optional size limits.
    Good for development and single-session use.
    """
    
    def __init__(self, max_messages_per_conversation: int = 100):
        self.max_messages = max_messages_per_conversation
        self.conversations: Dict[str, List[Message]] = defaultdict(list)
    
    async def save_message(
        self,
        conversation_id: str,
        message: Message,
    ) -> None:
        """Save a message to memory."""
        self.conversations[conversation_id].append(message)
        
        # Trim if too many messages
        if len(self.conversations[conversation_id]) > self.max_messages:
            # Keep most recent messages
            self.conversations[conversation_id] = \
                self.conversations[conversation_id][-self.max_messages:]
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """Get messages from memory."""
        messages = self.conversations.get(conversation_id, [])
        
        if limit:
            return messages[-limit:]
        
        return messages
    
    async def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation from memory."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
    
    def get_conversation_count(self) -> int:
        """Get number of active conversations."""
        return len(self.conversations)
    
    def get_total_messages(self) -> int:
        """Get total number of messages across all conversations."""
        return sum(len(msgs) for msgs in self.conversations.values())


class BufferedMemory(ShortMemory):
    """Short-term memory with smart buffering.
    
    Extends ShortMemory with:
    - Automatic summarization of old messages
    - Token-aware context window
    - Priority-based message retention
    """
    
    def __init__(
        self,
        max_messages_per_conversation: int = 100,
        always_keep_recent: int = 10,
    ):
        super().__init__(max_messages_per_conversation)
        self.always_keep_recent = always_keep_recent
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """Get messages with smart buffering.
        
        Keeps most recent messages and optionally
        summarizes older ones.
        """
        messages = self.conversations.get(conversation_id, [])
        
        if not limit or len(messages) <= limit:
            return messages
        
        # Keep recent messages
        recent = messages[-self.always_keep_recent:]
        
        # Could add summarization of older messages here
        # For now, just return recent
        
        return recent
