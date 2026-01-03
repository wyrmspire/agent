"""
gate/gemini.py - Google Gemini API Gateway

This module implements the ModelGateway interface for Google Gemini API.
Used for faster development iteration while the local model serves production.

Usage:
    Set GEMINI_API_KEY in .env and use rungem.sh to start with Gemini.
"""

import json
import re
import time
import logging
from typing import AsyncIterator, List, Optional, Dict, Any

import google.generativeai as genai

from core.types import Message, Tool, MessageRole, ToolCall
from core.proto import AgentResponse, StreamChunk, ResponseType
from .bases import ModelGateway, EmbeddingGateway

logger = logging.getLogger(__name__)


class GeminiGateway(ModelGateway, EmbeddingGateway):
    """ModelGateway implementation for Google Gemini API.
    
    Uses the google-generativeai SDK for direct API access.
    Parses <tool> tags from response text (same format as local model).
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
    ):
        super().__init__(model)
        self.api_key = api_key
        
        # Configure the SDK
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
        
        logger.info(f"Initialized Gemini gateway with model: {model}")
    
    def _message_to_gemini(self, message: Message) -> Dict[str, Any]:
        """Convert internal Message to Gemini format."""
        # Gemini uses 'user' and 'model' roles
        if message.role == MessageRole.SYSTEM:
            # System messages go into user context
            return {"role": "user", "parts": [f"[System]: {message.content}"]}
        elif message.role == MessageRole.USER:
            return {"role": "user", "parts": [message.content]}
        elif message.role == MessageRole.ASSISTANT:
            return {"role": "model", "parts": [message.content]}
        elif message.role == MessageRole.TOOL:
            # Tool results as user messages
            return {"role": "user", "parts": [f"[Tool Result]: {message.content}"]}
        else:
            return {"role": "user", "parts": [message.content]}
    
    def _parse_tool_calls(self, text: str) -> Optional[List[ToolCall]]:
        """Parse <tool> tags from response text.
        
        Same format as local model:
            <tool name="tool_name">{"arg": "value"}</tool>
        """
        tool_calls = []
        
        pattern = r'<tool\s+name="([^"]+)">(.*?)</tool>'
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for match in matches:
            tool_name = match.group(1)
            tool_args_str = match.group(2).strip()
            
            try:
                # Apply same sanitization as local model
                tool_args_str = tool_args_str.replace("\\'", "'")
                tool_args_str = re.sub(r'\bTrue\b', 'true', tool_args_str)
                tool_args_str = re.sub(r'\bFalse\b', 'false', tool_args_str)
                tool_args_str = re.sub(r'\bNone\b', 'null', tool_args_str)
                
                # Fix multiline strings: replace literal newlines with escaped newlines
                # This handles cases where model outputs code with actual newlines in JSON
                # We need to be careful to only escape newlines inside string values
                try:
                    tool_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    # Try escaping newlines inside string values
                    # Simple approach: replace all literal newlines with \n escape
                    sanitized = tool_args_str.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                    tool_args = json.loads(sanitized)
                
                tool_calls.append(ToolCall(
                    id=f"call_{tool_name}_{int(time.time() * 1000)}",
                    name=tool_name,
                    arguments=tool_args,
                ))
                logger.info(f"Parsed tool call: {tool_name}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool arguments for {tool_name}: {e}")
        
        return tool_calls if tool_calls else None
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentResponse:
        """Generate completion using Gemini API."""
        # Convert messages to Gemini format
        gemini_messages = [self._message_to_gemini(m) for m in messages]
        
        # Build generation config
        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        # Make request
        try:
            response = self.client.generate_content(
                gemini_messages,
                generation_config=generation_config,
            )
            
            content = response.text
            
            # Parse tool calls from text
            tool_calls = self._parse_tool_calls(content)
            
            # Determine response type
            if tool_calls:
                response_type = ResponseType.TOOL_CALL
                finish_reason = "tool_calls"
            else:
                response_type = ResponseType.COMPLETE
                finish_reason = "stop"
            
            return AgentResponse(
                response_type=response_type,
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
            )
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    async def stream_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming completion using Gemini API."""
        # Convert messages
        gemini_messages = [self._message_to_gemini(m) for m in messages]
        
        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        try:
            response = self.client.generate_content(
                gemini_messages,
                generation_config=generation_config,
                stream=True,
            )
            
            for chunk in response:
                if chunk.text:
                    yield StreamChunk(
                        delta=chunk.text,
                        chunk_type="text",
                    )
            
            yield StreamChunk(
                delta="",
                chunk_type="text",
                finish_reason="stop",
            )
            
        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            raise
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []
            
        try:
            # Gemini embedding model
            # Note: Older keys might need 'models/embedding-001' or 'models/text-embedding-004'
            # We'll default to text-embedding-004 if available, else embedding-001
            # For simplicity, let's try the modern standard first
            embedding_model = "models/text-embedding-004"
            
            result = genai.embed_content(
                model=embedding_model,
                content=texts,
                task_type="retrieval_document", 
            )
            
            # Result is dict with 'embedding' key which is list of lists
            return result['embedding']
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            raise

    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else []

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            # Simple test generation
            response = self.client.generate_content("Say 'ok'")
            return bool(response.text)
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Cleanup (no persistent connection to close)."""
        pass
