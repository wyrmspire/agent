"""
tool/index.py - Tool Registry

This module implements the tool registry for managing available tools.
The registry is the central place where all tools are registered and discovered.

Responsibilities:
- Register tools
- Look up tools by name
- Get all available tools
- Tool validation

Rules:
- Tools must have unique names
- Registry is the single source of truth
- Thread-safe operations
"""

from typing import Dict, List, Optional, Any

from core.types import Tool
from .bases import BaseTool


class ToolRegistry:
    """Registry for managing tools.
    
    The registry maintains a collection of all available tools
    and provides methods for registration and lookup.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool.
        
        Args:
            tool: Tool instance to register
            
        Raises:
            ValueError: If tool with same name already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool.
        
        Args:
            name: Name of tool to unregister
        """
        if name in self._tools:
            del self._tools[name]
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool is registered
        """
        return name in self._tools
    
    def list(self) -> List[str]:
        """List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_tools(self) -> List[BaseTool]:
        """Get all registered tools.
        
        Returns:
            List of tool instances
        """
        return list(self._tools.values())
    
    def get_tool_definitions(self) -> List[Tool]:
        """Get tool definitions for all registered tools.
        
        Returns:
            List of Tool objects suitable for sending to model
        """
        return [tool.to_tool_definition() for tool in self._tools.values()]
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
    
    @property
    def count(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)


def create_default_registry(config: Optional[Dict[str, Any]] = None) -> ToolRegistry:
    """Create a registry with default tools.
    
    Args:
        config: Configuration dictionary to toggle tools
        
    Returns:
        ToolRegistry with common tools registered
    """
    from .files import ListFiles, ReadFile, WriteFile
    from .shell import ShellTool
    from .fetch import FetchTool
    
    # Default to all enabled if no config provided
    if config is None:
        config = {
            "enable_files": True,
            "enable_shell": True,
            "enable_fetch": True,
        }
    
    registry = ToolRegistry()
    
    # File tools
    if config.get("enable_files", True):
        registry.register(ListFiles())
        registry.register(ReadFile())
        registry.register(WriteFile())
    
    # Shell tool
    if config.get("enable_shell", True):
        registry.register(ShellTool())
    
    # HTTP tool
    if config.get("enable_fetch", True):
        registry.register(FetchTool())
    
    return registry
