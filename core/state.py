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
import uuid
import time

from .types import Message, Tool, Step, ToolCall, ToolResult


def generate_run_id() -> str:
    """Generate a unique run ID for traceability.
    
    Format: run_{timestamp}_{uuid_short}
    This allows grep-ing logs by run_id to trace execution.
    
    Returns:
        Unique run identifier
    """
    timestamp = int(time.time())
    short_uuid = str(uuid.uuid4())[:8]
    return f"run_{timestamp}_{short_uuid}"


def generate_conversation_id() -> str:
    """Generate a unique conversation ID.
    
    Returns:
        Unique conversation identifier
    """
    return f"conv_{uuid.uuid4().hex}"


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
        run_id: Unique identifier for this execution (for traceability)
        conversation_id: ID of the conversation this belongs to
        available_tools: Tools available for this execution
        current_step: Current step number
        max_steps: Maximum steps allowed
        max_tools_per_step: Maximum tools allowed per step (Phase 0.5)
        tools_used_this_step: Count of tools used in current step (Phase 0.5)
        mode: Agent mode - 'planner' (no tools) or 'builder' (tools allowed)
        steps: History of steps taken
        started_at: When execution started
        metadata: Optional execution metadata
    """
    run_id: str
    conversation_id: str
    available_tools: List[Tool] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 50
    max_tools_per_step: int = 10  # Phase 0.5: Tool budget enforcement
    tools_used_this_step: int = 0
    mode: str = "builder"  # Phase C: 'planner' or 'builder'
    steps: List[Step] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Phase 3: Learning mode fields
    heavy_learning_mode: bool = False  # Triggered on empty search results
    last_failed_query: Optional[str] = None  # Track what query failed
    reflection_step_interval: int = 20  # Trigger reflection every N steps
    # Phase 2B: Learning enforcement
    learning_required_by_step: Optional[int] = None  # Must learn by this step
    pending_failures: List[Dict[str, Any]] = field(default_factory=list)  # Failures awaiting reflection
    
    def add_step(self, step: Step) -> None:
        """Add a step to execution history."""
        self.steps.append(step)
        self.current_step += 1
        # Reset tool counter for new step
        self.tools_used_this_step = 0
    
    def should_continue(self) -> bool:
        """Check if execution should continue."""
        return self.current_step < self.max_steps
    
    def can_use_tool(self) -> bool:
        """Check if more tools can be used in current step (Phase 0.5)."""
        return self.tools_used_this_step < self.max_tools_per_step
    
    def record_tool_use(self) -> None:
        """Record that a tool was used in current step (Phase 0.5)."""
        self.tools_used_this_step += 1
    
    def is_planner_mode(self) -> bool:
        """Check if agent is in planner mode (tools disabled)."""
        return self.mode == "planner"
    
    def set_mode(self, mode: str) -> None:
        """Set agent mode. 'planner' disables tools, 'builder' enables them."""
        if mode not in ("planner", "builder"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'planner' or 'builder'")
        self.mode = mode
    
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
