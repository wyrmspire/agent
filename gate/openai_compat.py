"""
gate/openai_compat.py - Generic OpenAI-Compatible Adapter

This module implements the ModelGateway interface for any server 
that speaks the standard OpenAI API format (e.g. vLLM, Ollama, LocalAI, generic Qwen server).

Responsibilities:
- Connect to any OpenAI-compatible server
- Support standard /v1/chat/completions
- Support standard /v1/embeddings
- Handle tool calls in standard format

Rules:
- Protocol-agnostic (works with any standard server)
- Feature parity with Gemini adapter (Embeddings + Chat)
"""

import json
import httpx
import logging
from typing import AsyncIterator, List, Optional, Dict, Any

from core.types import Message, Tool, MessageRole, ToolCall
from core.proto import AgentResponse, StreamChunk, ResponseType
from .bases import ModelGateway, EmbeddingGateway

logger = logging.getLogger(__name__)

class OpenAICompatGateway(ModelGateway, EmbeddingGateway):
    """Generic adapter for OpenAI-compatible APIs (Qwen, Llama, etc.)."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "local-model",
        timeout: float = 120.0,
        api_key: str = "not-needed",
    ):
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Some servers require a dummy API key
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
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
        if message.tool_call_id:
            msg_dict["tool_call_id"] = message.tool_call_id
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
            try:
                args = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
                
            parsed_calls.append(ToolCall(
                id=tc.get("id", f"call_{len(parsed_calls)}"),
                name=function.get("name", ""),
                arguments=args,
            ))
        return parsed_calls
    
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentResponse:
        """Generate completion."""
        request_data = {
            "model": self.model,
            "messages": [self._message_to_dict(m) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if tools:
            request_data["tools"] = [self._tool_to_dict(t) for t in tools]
        
        try:
            url = f"{self.base_url}/chat/completions"
            response = await self.client.post(url, json=request_data)
            response.raise_for_status()
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            content = message.get("content", "")
            tool_calls = self._parse_tool_calls(data)
            
            finish_reason = choice.get("finish_reason", "stop")
            response_type = ResponseType.TOOL_CALL if tool_calls else ResponseType.COMPLETE
            
            return AgentResponse(
                response_type=response_type,
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=data.get("usage"),
            )
        except Exception as e:
            logger.error(f"OpenAI Compat API error: {e}")
            raise

    async def stream_complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming completion."""
        request_data = {
            "model": self.model,
            "messages": [self._message_to_dict(m) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            request_data["tools"] = [self._tool_to_dict(t) for t in tools]
            
        url = f"{self.base_url}/chat/completions"
        try:
            async with self.client.stream("POST", url, json=request_data) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip() or line.strip() == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    
                    try:
                        chunk_data = json.loads(line)
                        choice = chunk_data["choices"][0]
                        delta = choice.get("delta", {})
                        content = delta.get("content", "")
                        finish_reason = choice.get("finish_reason")
                        
                        yield StreamChunk(
                            delta=content,
                            chunk_type="text",
                            finish_reason=finish_reason
                        )
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using standard /v1/embeddings endpoint."""
        if not texts:
            return []
            
        url = f"{self.base_url}/embeddings"
        try:
            request_data = {
                "input": texts,
                "model": self.model, 
            }
            
            response = await self.client.post(url, json=request_data)
            response.raise_for_status()
            
            data = response.json()
            # Standard format: { "data": [ { "embedding": [...] } ] }
            return [item["embedding"] for item in data["data"]]
            
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            # Ensure we don't crash silently
            raise

    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else []

    async def health_check(self) -> bool:
        """Check availability."""
        try:
            # Try models endpoint
            response = await self.client.get(f"{self.base_url}/models", timeout=5.0)
            return response.status_code == 200
        except:
            return False

    async def close(self) -> None:
        await self.client.aclose()
