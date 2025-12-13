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
    from .dview import DataViewTool
    from .pyexe import PythonReplTool
    from .memory import MemoryTool
    
    # Default to all enabled if no config provided
    if config is None:
        config = {
            "enable_files": True,
            "enable_shell": True,
            "enable_fetch": True,
            "enable_data_view": True,
            "enable_pyexe": True,
            "enable_memory": True,
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
    
    # Data science tools (Phase 0.2)
    if config.get("enable_data_view", True):
        registry.register(DataViewTool())
    
    if config.get("enable_pyexe", True):
        registry.register(PythonReplTool())
    
    # Memory tool (Phase 0.3)
    if config.get("enable_memory", True):
        registry.register(MemoryTool())
    
    # Skill management tool (Phase 0.4)
    if config.get("enable_promote_skill", True):
        from .manager import PromoteSkillTool
        registry.register(PromoteSkillTool(registry=registry))
    
    # Load dynamic skills (Phase 0.4)
    if config.get("load_dynamic_skills", True):
        from .manager import load_dynamic_skills
        loaded = load_dynamic_skills(registry)
        if loaded > 0:
            import logging
            logging.getLogger(__name__).info(f"Loaded {loaded} dynamic skills")
    
    return registry
