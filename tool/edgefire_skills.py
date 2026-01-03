"""
tool/edgefire_skills.py - Edgefire Skills as Agent Tools

This module bridges the edgefire skill system with the agent tool system.
Each edgefire skill is wrapped as an agent BaseTool.

Usage:
    from tool.edgefire_skills import get_edgefire_tools

    tools = get_edgefire_tools()  # Returns list of Tool definitions
"""

import sys
from pathlib import Path
from typing import Any, Dict, List
import json

# Add edgefire backend to path
EDGEFIRE_BACKEND = Path(__file__).parent.parent.parent / "edgefire" / "backend"
if str(EDGEFIRE_BACKEND) not in sys.path:
    sys.path.insert(0, str(EDGEFIRE_BACKEND))

from core.types import Tool, ToolCall, ToolResult
from tool.bases import BaseTool


class EdgefireSkillTool(BaseTool):
    """Wraps an edgefire skill as an agent tool."""

    def __init__(self, skill_id: str, skill_info: dict, skill_class):
        self._skill_id = skill_id
        self._skill_info = skill_info
        self._skill_class = skill_class
        self._skill_instance = skill_class()

    @property
    def name(self) -> str:
        return f"edgefire_{self._skill_id}"

    @property
    def description(self) -> str:
        return f"[Edgefire Skill] {self._skill_info.get('description', self._skill_id)}"

    @property
    def parameters(self) -> Dict[str, Any]:
        # Convert edgefire skill input schema to JSON schema
        return self._skill_info.get("input_schema", {"type": "object", "properties": {}})

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the wrapped edgefire skill."""
        try:
            # Execute the skill
            result = await self._skill_instance.execute(**arguments)

            return ToolResult(
                tool_call_id="",  # Will be set by caller
                output=json.dumps(result, indent=2, default=str),
                success=True,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Skill execution failed: {str(e)}",
                success=False,
            )


def get_edgefire_tools() -> List[Tool]:
    """
    Get all edgefire skills as agent Tool definitions.

    Returns:
        List of Tool objects that can be passed to the model
    """
    tools = []

    try:
        # Import edgefire skill registry
        from skills.registry import SkillRegistry

        # Get all registered skills
        for skill_id, skill_info in SkillRegistry.list_skills().items():
            skill_class = SkillRegistry.get_skill_class(skill_id)
            if skill_class:
                wrapper = EdgefireSkillTool(skill_id, skill_info, skill_class)
                tools.append(wrapper.to_tool_definition())

    except ImportError as e:
        print(f"Warning: Could not import edgefire skills: {e}")
        # Return empty list if edgefire not available
        pass

    return tools


def get_edgefire_tool_wrappers() -> Dict[str, EdgefireSkillTool]:
    """
    Get all edgefire skills as EdgefireSkillTool wrappers.

    Returns:
        Dict mapping tool name to tool wrapper
    """
    tools = {}

    try:
        from skills.registry import SkillRegistry

        for skill_id, skill_info in SkillRegistry.list_skills().items():
            skill_class = SkillRegistry.get_skill_class(skill_id)
            if skill_class:
                wrapper = EdgefireSkillTool(skill_id, skill_info, skill_class)
                tools[wrapper.name] = wrapper

    except ImportError:
        pass

    return tools


# Convenience functions for specific skill categories
def get_window_tools() -> List[Tool]:
    """Get only WINDOW category skills as tools."""
    return _get_tools_by_category("window")


def get_indicator_tools() -> List[Tool]:
    """Get only INDICATOR category skills as tools."""
    return _get_tools_by_category("indicator")


def get_scan_tools() -> List[Tool]:
    """Get only SCAN category skills as tools."""
    return _get_tools_by_category("scan")


def get_oco_tools() -> List[Tool]:
    """Get only OCO category skills as tools."""
    return _get_tools_by_category("oco")


def _get_tools_by_category(category: str) -> List[Tool]:
    """Get skills of a specific category as tools."""
    tools = []

    try:
        from skills.registry import SkillRegistry, SkillCategory

        category_enum = SkillCategory(category)

        for skill_id, skill_info in SkillRegistry.list_skills().items():
            if skill_info.get("category") == category_enum:
                skill_class = SkillRegistry.get_skill_class(skill_id)
                if skill_class:
                    wrapper = EdgefireSkillTool(skill_id, skill_info, skill_class)
                    tools.append(wrapper.to_tool_definition())

    except (ImportError, ValueError):
        pass

    return tools


# Trading-specific tool groups
TRADING_TOOL_GROUPS = {
    "analysis": [
        "window_price",
        "window_multi_tf",
        "ind_ema",
        "ind_atr",
        "level_session",
        "level_swings",
        "level_proximity",
    ],
    "structure": [
        "struct_break",
    ],
    "execution": [
        "oco_market",
        "oco_limit",
        "oco_sizing",
        "oco_time_exit",
    ],
    "scanning": [
        "scan_compose",
        "scan_library",
        "scan_list",
    ],
}


def get_trading_tools(group: str = None) -> List[Tool]:
    """
    Get edgefire trading tools, optionally filtered by group.

    Args:
        group: Optional group name (analysis, structure, execution, scanning)

    Returns:
        List of Tool objects
    """
    tools = []

    try:
        from skills.registry import SkillRegistry

        if group:
            skill_ids = TRADING_TOOL_GROUPS.get(group, [])
        else:
            # All trading tools
            skill_ids = []
            for ids in TRADING_TOOL_GROUPS.values():
                skill_ids.extend(ids)

        for skill_id in skill_ids:
            skill_info = SkillRegistry.get_skill_info(skill_id)
            skill_class = SkillRegistry.get_skill_class(skill_id)
            if skill_class and skill_info:
                wrapper = EdgefireSkillTool(skill_id, skill_info, skill_class)
                tools.append(wrapper.to_tool_definition())

    except ImportError:
        pass

    return tools
