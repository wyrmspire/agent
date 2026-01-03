"""Tool module - Agent tools for interacting with the world."""

from .bases import BaseTool, create_json_schema
from .fetch import FetchTool

# Optional: Edgefire skill integration
try:
    from .edgefire_skills import (
        get_edgefire_tools,
        get_trading_tools,
        EdgefireSkillTool,
    )
    EDGEFIRE_AVAILABLE = True
except ImportError:
    EDGEFIRE_AVAILABLE = False
    get_edgefire_tools = lambda: []
    get_trading_tools = lambda group=None: []
    EdgefireSkillTool = None

__all__ = [
    "BaseTool",
    "create_json_schema",
    "FetchTool",
    "get_edgefire_tools",
    "get_trading_tools",
    "EdgefireSkillTool",
    "EDGEFIRE_AVAILABLE",
]
