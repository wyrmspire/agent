"""
tool/ledger.py - Mistake Ledger Tool

This module implements a tool for logging mistakes to the persistent ledger.
Allows the agent to record failures and learn from them across sessions.

Phase B: Learning via Persistent Artifacts

Responsibilities:
- Append entries to workspace/ledger.md
- Format entries consistently
- Provide searchable mistake history

Rules:
- Entries must include trigger, root cause, rule, and test
- Agent should consult ledger before retrying failed tools
"""

import logging
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

from core.types import ToolResult
from core.sandb import get_default_workspace
from .bases import BaseTool

logger = logging.getLogger(__name__)


class LogMistakeTool(BaseTool):
    """Tool for logging mistakes to the persistent ledger.
    
    Allows agent to:
    - Record failures with root cause analysis
    - Build institutional memory across sessions
    - Reference past mistakes before retrying
    """
    
    def __init__(self):
        """Initialize log_mistake tool."""
        self.workspace = get_default_workspace()
        self.ledger_path = Path(self.workspace.base_path) / "ledger.md"
    
    @property
    def name(self) -> str:
        return "log_mistake"
    
    @property
    def description(self) -> str:
        return (
            "Log an operational rule to the persistent ledger. "
            "USE LEDGER FOR: mistakes, rules (trigger→cause→rule→test), operational do/don't. "
            "USE MEMORY FOR: semantic facts, discoveries, how things work. "
            "Ledger entries persist as markdown and are checked before retrying failed operations."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "trigger": {
                    "type": "string",
                    "description": "What happened - the action that failed"
                },
                "root_cause": {
                    "type": "string",
                    "description": "Why it failed - the underlying reason"
                },
                "rule": {
                    "type": "string",
                    "description": "What to do differently next time"
                },
                "test": {
                    "type": "string",
                    "description": "How to verify the rule works"
                }
            },
            "required": ["trigger", "root_cause", "rule"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Log a mistake to the ledger.
        
        Args:
            arguments: trigger, root_cause, rule, and optional test
            
        Returns:
            ToolResult with confirmation
        """
        trigger = arguments.get("trigger", "")
        root_cause = arguments.get("root_cause", "")
        rule = arguments.get("rule", "")
        test = arguments.get("test", "N/A")
        
        if not trigger or not root_cause or not rule:
            return ToolResult(
                tool_call_id="",
                output="",
                error="Missing required parameters: trigger, root_cause, and rule",
                success=False,
            )
        
        try:
            # Read existing content
            if self.ledger_path.exists():
                content = self.ledger_path.read_text(encoding="utf-8")
            else:
                content = "# Mistake Ledger\n\n---\n\n## Entries\n"
            
            # Count existing entries for numbering
            entry_count = content.count("## Entry")
            new_entry_num = entry_count + 1
            
            # Create new entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_entry = f"""
## Entry {new_entry_num}: {trigger[:50]}
*Logged: {timestamp}*

- **Trigger**: {trigger}
- **Root Cause**: {root_cause}
- **Rule**: {rule}
- **Test**: {test}

---
"""
            # Append to ledger
            content += new_entry
            self.ledger_path.write_text(content, encoding="utf-8")
            
            return ToolResult(
                tool_call_id="",
                output=f"Logged mistake as Entry {new_entry_num}. Rule: {rule}",
                success=True,
            )
        
        except Exception as e:
            logger.error(f"Failed to log mistake: {e}", exc_info=True)
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Failed to log mistake: {e}",
                success=False,
            )
