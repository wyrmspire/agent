"""
gate/escalating.py - Model Escalation Gateway

This module implements automatic model escalation:
- Start with fast/cheap model (gemini-2.5-flash)
- Escalate to powerful model (gemini-2.0-pro) on repeated failures
- Record learning before de-escalating
- Switch back to primary model

Usage:
    primary = GeminiGateway(api_key, model="gemini-2.5-flash")
    escalation = GeminiGateway(api_key, model="gemini-2.0-pro-exp-02-05")
    gateway = EscalatingGateway(primary, escalation)
"""

import logging
from typing import AsyncIterator, List, Optional

from core.types import Message, Tool
from core.proto import AgentResponse, StreamChunk
from .bases import ModelGateway
from .gemini import GeminiGateway

logger = logging.getLogger(__name__)


class EscalatingGateway(ModelGateway):
    """Gateway wrapper that escalates to a more powerful model on failures.
    
    Flow:
    1. Primary model (flash) handles requests
    2. On repeated failures, escalate to escalation model (pro)
    3. Pro solves problem, agent stores learning
    4. De-escalate back to primary
    5. Next time, primary can use stored learning
    """
    
    def __init__(
        self,
        primary_gateway: GeminiGateway,
        escalation_gateway: GeminiGateway,
        escalation_threshold: int = 3,
    ):
        """Initialize escalating gateway.
        
        Args:
            primary_gateway: Default fast/cheap model (e.g., gemini-2.5-flash)
            escalation_gateway: Powerful model for hard problems (e.g., gemini-2.0-pro)
            escalation_threshold: Number of failures before escalating
        """
        super().__init__(primary_gateway.model)
        self.primary = primary_gateway
        self.escalation = escalation_gateway
        self.escalation_threshold = escalation_threshold
        
        # State tracking
        self.is_escalated = False
        self.consecutive_failures = 0
        self.escalation_reason: Optional[str] = None
        self.learning_stored = False
        
        logger.info(f"EscalatingGateway: primary={primary_gateway.model}, escalation={escalation_gateway.model}")
    
    @property
    def current_gateway(self) -> GeminiGateway:
        """Get the currently active gateway."""
        return self.escalation if self.is_escalated else self.primary
    
    @property
    def current_model(self) -> str:
        """Get the currently active model name."""
        return self.current_gateway.model
    
    def escalate(self, reason: str) -> None:
        """Switch to escalation (powerful) model.
        
        Args:
            reason: Why we're escalating
        """
        if not self.is_escalated:
            self.is_escalated = True
            self.escalation_reason = reason
            self.learning_stored = False
            logger.info(f"🔺 ESCALATED to {self.escalation.model}: {reason}")
    
    def de_escalate(self) -> None:
        """Switch back to primary (fast) model."""
        if self.is_escalated:
            self.is_escalated = False
            self.consecutive_failures = 0
            self.escalation_reason = None
            logger.info(f"🔻 DE-ESCALATED back to {self.primary.model}")
    
    def record_failure(self) -> bool:
        """Record a failure and check if escalation is needed.
        
        Returns:
            True if escalation threshold was reached
        """
        self.consecutive_failures += 1
        logger.debug(f"Failure recorded: {self.consecutive_failures}/{self.escalation_threshold}")
        
        if not self.is_escalated and self.consecutive_failures >= self.escalation_threshold:
            self.escalate(f"Reached {self.consecutive_failures} consecutive failures")
            return True
        return False
    
    def record_success(self) -> None:
        """Record a success (resets failure counter)."""
        if self.consecutive_failures > 0:
            logger.debug(f"Success recorded, resetting failures from {self.consecutive_failures}")
        self.consecutive_failures = 0
    
    def mark_learning_stored(self) -> None:
        """Mark that learning was stored (ready for de-escalation)."""
        self.learning_stored = True
        logger.info("Learning stored, ready for de-escalation")
    
    def should_de_escalate(self) -> bool:
        """Check if we should de-escalate (success + learning stored)."""
        return self.is_escalated and self.learning_stored
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentResponse:
        """Generate completion using the appropriate gateway.
        
        Routes to primary or escalation gateway based on current state.
        """
        gateway = self.current_gateway
        logger.debug(f"Using {gateway.model} (escalated={self.is_escalated})")
        
        return await gateway.complete(messages, tools, temperature, max_tokens)
    
    async def stream_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming completion using the appropriate gateway."""
        gateway = self.current_gateway
        async for chunk in gateway.stream_complete(messages, tools, temperature, max_tokens):
            yield chunk
    
    async def health_check(self) -> bool:
        """Check if both gateways are accessible."""
        primary_ok = await self.primary.health_check()
        escalation_ok = await self.escalation.health_check()
        return primary_ok and escalation_ok
    
    async def close(self) -> None:
        """Cleanup both gateways."""
        await self.primary.close()
        await self.escalation.close()
    
    def get_status(self) -> dict:
        """Get current escalation status."""
        return {
            "is_escalated": self.is_escalated,
            "current_model": self.current_model,
            "consecutive_failures": self.consecutive_failures,
            "escalation_reason": self.escalation_reason,
            "learning_stored": self.learning_stored,
        }
