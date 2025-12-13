"""
gate/lmstd.py - LM Studio Adapter

This module implements the ModelGateway interface for LM Studio.
LM Studio provides an OpenAI-compatible API for local models.

Responsibilities:
- Connect to LM Studio server
- Translate requests to OpenAI format
- Parse responses from LM Studio
- Handle streaming

Rules:
- Only implements ModelGateway interface
- All LM Studio-specific logic goes here
- No leaking of implementation details
"""

import json
import httpx
from typing import AsyncIterator, List, Optional, Dict, Any

from core.types import Message, Tool, MessageRole, ToolCall
from core.proto import AgentResponse, StreamChunk, ResponseType
from .bases import ModelGateway


class LMStudioGateway(ModelGateway):
    """ModelGateway implementation for LM Studio.
    
    LM Studio runs local models and exposes an OpenAI-compatible API.
    Default endpoint: http://localhost:1234/v1
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "qwen2.5-coder",
        timeout: float = 60.0,
    ):
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    def _message_to_dict(self, message: Message) -> Dict[str, Any]:
        """Convert internal Message to OpenAI format."""
        msg_dict = {
            "role": message.role.value,
            "content": message.content,
        }
        
        if message.name:
            msg_dict["name"] = message.name
        
        if message.tool_calls:
            msg_dict["tool_calls"] = message.tool_calls
        
        return msg_dict
    
    def _tool_to_dict(self, tool: Tool) -> Dict[str, Any]:
        """Convert internal Tool to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
        }
    
    def _parse_tool_calls(self, response_data: Dict[str, Any]) -> Optional[List[ToolCall]]:
        """Parse tool calls from response."""
        choice = response_data.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls")
        
        if not tool_calls:
            return None
        
        parsed_calls = []
        for tc in tool_calls:
            function = tc.get("function", {})
            parsed_calls.append(ToolCall(
                id=tc.get("id", f"call_{len(parsed_calls)}"),
                name=function.get("name", ""),
                arguments=json.loads(function.get("arguments", "{}")),
            ))
        
        return parsed_calls
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentResponse:
        """Generate completion using LM Studio."""
        # Build request
        request_data = {
            "model": self.model,
            "messages": [self._message_to_dict(m) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Add tools if provided
        if tools:
            request_data["tools"] = [self._tool_to_dict(t) for t in tools]
        
        # Make request
        url = f"{self.base_url}/chat/completions"
        response = await self.client.post(url, json=request_data)
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]
        
        # Extract content
        content = message.get("content", "")
        
        # Parse tool calls if present
        tool_calls = self._parse_tool_calls(data)
        
        # Determine response type
        finish_reason = choice.get("finish_reason", "stop")
        if tool_calls:
            response_type = ResponseType.TOOL_CALL
        elif finish_reason == "stop":
            response_type = ResponseType.COMPLETE
        else:
            response_type = ResponseType.PARTIAL
        
        return AgentResponse(
            response_type=response_type,
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=data.get("usage"),
        )
    
    async def stream_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming completion using LM Studio."""
        # Build request
        request_data = {
            "model": self.model,
            "messages": [self._message_to_dict(m) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        if tools:
            request_data["tools"] = [self._tool_to_dict(t) for t in tools]
        
        # Make streaming request
        url = f"{self.base_url}/chat/completions"
        async with self.client.stream("POST", url, json=request_data) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                
                if line.startswith("data: "):
                    line = line[6:]
                
                if line == "[DONE]":
                    break
                
                try:
                    chunk_data = json.loads(line)
                    choice = chunk_data["choices"][0]
                    delta = choice.get("delta", {})
                    
                    # Extract content delta
                    content = delta.get("content", "")
                    
                    # Check for finish
                    finish_reason = choice.get("finish_reason")
                    
                    yield StreamChunk(
                        delta=content,
                        chunk_type="text",
                        finish_reason=finish_reason,
                    )
                
                except json.JSONDecodeError:
                    continue
    
    async def health_check(self) -> bool:
        """Check if LM Studio is reachable."""
        try:
            url = f"{self.base_url}/models"
            response = await self.client.get(url, timeout=5.0)
            return response.status_code == 200
        except:
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
