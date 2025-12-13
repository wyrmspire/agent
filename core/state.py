"""
core/state.py - Agent State Objects

This module defines state objects that track the agent's execution state.
State objects are mutable containers that flows use to manage execution.

Key classes:
- AgentState: Main state object for agent execution
- ConversationState: State of a conversation
- ExecutionContext: Context for a single execution run

Rules:
- Only depends on core/types.py and core/proto.py
- State objects are mutable (unlike types which are immutable)
- State provides methods for safe state transitions
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from .types import Message, Tool, Step, ToolCall, ToolResult


@dataclass
class ConversationState:
    """State of a conversation.
    
    Attributes:
        id: Unique conversation identifier
        messages: Full conversation history
        created_at: When conversation was created
        updated_at: When conversation was last updated
        metadata: Optional conversation metadata
    """
    id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, message: Message) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def get_recent_messages(self, n: int = 10) -> List[Message]:
        """Get the n most recent messages."""
        return self.messages[-n:]


@dataclass
class ExecutionContext:
    """Context for a single agent execution run.
    
    Attributes:
        run_id: Unique identifier for this execution
        conversation_id: ID of the conversation this belongs to
        available_tools: Tools available for this execution
        current_step: Current step number
        max_steps: Maximum steps allowed
        steps: History of steps taken
        metadata: Optional execution metadata
    """
    run_id: str
    conversation_id: str
    available_tools: List[Tool] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 20
    steps: List[Step] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_step(self, step: Step) -> None:
        """Add a step to execution history."""
        self.steps.append(step)
        self.current_step += 1
    
    def should_continue(self) -> bool:
        """Check if execution should continue."""
        return self.current_step < self.max_steps
    
    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        for tool in self.available_tools:
            if tool.name == name:
                return tool
        return None


@dataclass
class AgentState:
    """Main state object for agent execution.
    
    Attributes:
        conversation: Current conversation state
        execution: Current execution context
        model_name: Name of the model being used
        is_streaming: Whether response is streaming
        error: Optional error message
    """
    conversation: ConversationState
    execution: ExecutionContext
    model_name: str = "qwen2.5-coder"
    is_streaming: bool = False
    error: Optional[str] = None
    
    @property
    def messages(self) -> List[Message]:
        """Get conversation messages."""
        return self.conversation.messages
    
    @property
    def steps(self) -> List[Step]:
        """Get execution steps."""
        return self.execution.steps
    
    def is_complete(self) -> bool:
        """Check if execution is complete."""
        if self.error:
            return True
        return not self.execution.should_continue()
