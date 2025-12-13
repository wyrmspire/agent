"""
tool/fetch.py - HTTP Fetch Tool

This module implements a tool for fetching content from URLs.
Useful for retrieving documentation, API data, etc.

Responsibilities:
- HTTP GET requests
- Content type handling
- Size limits
- Timeout protection

Rules:
- Only GET requests (no POST/PUT/DELETE)
- Respect size limits
- Handle common content types
- Timeout after reasonable duration
"""

import httpx
from typing import Any, Dict

from core.types import ToolResult
from .bases import BaseTool, create_json_schema


class FetchTool(BaseTool):
    """Fetch content from a URL."""
    
    def __init__(
        self,
        timeout: float = 30.0,
        max_size: int = 5_000_000,
    ):
        self.timeout = timeout
        self.max_size = max_size
        self.client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        )
    
    @property
    def name(self) -> str:
        return "fetch"
    
    @property
    def description(self) -> str:
        return f"Fetch content from a URL via HTTP GET. Max size: {self.max_size} bytes."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "url": {
                    "type": "string",
                    "description": "URL to fetch (must be HTTP or HTTPS)",
                },
            },
            required=["url"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Fetch content from URL."""
        url = arguments["url"]
        
        # Validate URL
        if not url.startswith(("http://", "https://")):
            return ToolResult(
                tool_call_id="",
                output="",
                error="URL must start with http:// or https://",
                success=False,
            )
        
        try:
            # Make request
            response = await self.client.get(url)
            
            # Check status
            if response.status_code != 200:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"HTTP {response.status_code}: {response.reason_phrase}",
                    success=False,
                )
            
            # Check size
            content_length = len(response.content)
            if content_length > self.max_size:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Content too large: {content_length} bytes (max {self.max_size})",
                    success=False,
                )
            
            # Get content type
            content_type = response.headers.get("content-type", "").lower()
            
            # Return appropriate content
            if "text" in content_type or "json" in content_type or "xml" in content_type:
                output = response.text
            else:
                output = f"Binary content ({content_length} bytes, type: {content_type})"
            
            return ToolResult(
                tool_call_id="",
                output=output,
                success=True,
            )
        
        except httpx.TimeoutException:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Request timed out after {self.timeout}s",
                success=False,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error fetching URL: {e}",
                success=False,
            )
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
