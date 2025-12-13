"""
core/rules.py - Safety and Authorization Rules

This module defines safety rules and authorization checks for agent execution.
Rules determine what the agent is allowed to do and what is forbidden.

Key classes:
- Rule: Base class for all rules
- SafetyRule: Rules for safe tool execution
- AuthRule: Authorization rules for tool access
- RuleEngine: Evaluates rules and enforces policies

Rules:
- Only depends on core/types.py
- Rules are immutable and composable
- Rule evaluation is fast and deterministic
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

from .types import Tool, ToolCall


class RuleResult(str, Enum):
    """Result of rule evaluation."""
    ALLOW = "allow"
    DENY = "deny"
    SKIP = "skip"


class RuleType(str, Enum):
    """Types of rules."""
    SAFETY = "safety"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"


@dataclass(frozen=True)
class RuleViolation:
    """Description of a rule violation.
    
    Attributes:
        rule_name: Name of the rule that was violated
        reason: Why the rule was violated
        severity: Severity level (info, warning, error, critical)
    """
    rule_name: str
    reason: str
    severity: str = "error"


class Rule(ABC):
    """Base class for all rules.
    
    Rules are immutable objects that can evaluate whether
    an action (like a tool call) is allowed.
    """
    
    def __init__(self, name: str, rule_type: RuleType):
        self.name = name
        self.rule_type = rule_type
    
    @abstractmethod
    def evaluate(self, tool_call: ToolCall, context: Dict[str, Any]) -> RuleResult:
        """Evaluate if this tool call is allowed.
        
        Args:
            tool_call: The tool call to evaluate
            context: Additional context for evaluation
            
        Returns:
            RuleResult indicating allow, deny, or skip
        """
        pass
    
    @abstractmethod
    def get_violation(self, tool_call: ToolCall) -> RuleViolation:
        """Get violation details if rule is violated."""
        pass


class SafetyRule(Rule):
    """Rules for safe tool execution.
    
    Safety rules prevent dangerous operations like:
    - Deleting critical files
    - Running untrusted code
    - Network access to forbidden domains
    """
    
    def __init__(self, name: str, forbidden_patterns: List[str]):
        super().__init__(name, RuleType.SAFETY)
        self.forbidden_patterns = forbidden_patterns
    
    def evaluate(self, tool_call: ToolCall, context: Dict[str, Any]) -> RuleResult:
        """Check if tool call matches any forbidden patterns."""
        # Check tool name
        for pattern in self.forbidden_patterns:
            if pattern in tool_call.name:
                return RuleResult.DENY
            
            # Check arguments
            for arg_value in tool_call.arguments.values():
                if isinstance(arg_value, str) and pattern in arg_value:
                    return RuleResult.DENY
        
        return RuleResult.ALLOW
    
    def get_violation(self, tool_call: ToolCall) -> RuleViolation:
        return RuleViolation(
            rule_name=self.name,
            reason=f"Tool call '{tool_call.name}' matches forbidden pattern",
            severity="critical"
        )


class AuthRule(Rule):
    """Authorization rules for tool access.
    
    Auth rules control which tools can be called based on:
    - User permissions
    - Tool capabilities
    - Execution context
    """
    
    def __init__(self, name: str, allowed_tools: List[str]):
        super().__init__(name, RuleType.AUTH)
        self.allowed_tools = allowed_tools
    
    def evaluate(self, tool_call: ToolCall, context: Dict[str, Any]) -> RuleResult:
        """Check if tool is in allowed list."""
        if "*" in self.allowed_tools:
            return RuleResult.ALLOW
        
        if tool_call.name in self.allowed_tools:
            return RuleResult.ALLOW
        
        return RuleResult.DENY
    
    def get_violation(self, tool_call: ToolCall) -> RuleViolation:
        return RuleViolation(
            rule_name=self.name,
            reason=f"Tool '{tool_call.name}' is not authorized",
            severity="error"
        )


class RuleEngine:
    """Evaluates rules and enforces policies.
    
    The rule engine takes a list of rules and evaluates them
    against tool calls to determine if they should be allowed.
    """
    
    def __init__(self, rules: Optional[List[Rule]] = None):
        self.rules = rules or []
    
    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self.rules.append(rule)
    
    def evaluate(self, tool_call: ToolCall, context: Optional[Dict[str, Any]] = None) -> tuple[bool, List[RuleViolation]]:
        """Evaluate all rules against a tool call.
        
        Args:
            tool_call: The tool call to evaluate
            context: Optional context for evaluation
            
        Returns:
            Tuple of (is_allowed, violations)
        """
        context = context or {}
        violations = []
        
        for rule in self.rules:
            result = rule.evaluate(tool_call, context)
            
            if result == RuleResult.DENY:
                violation = rule.get_violation(tool_call)
                violations.append(violation)
        
        is_allowed = len(violations) == 0
        return is_allowed, violations


# Default rule engine with basic safety rules
DEFAULT_RULES = [
    SafetyRule(
        name="no_dangerous_commands",
        forbidden_patterns=[
            "rm -rf /",
            "dd if=",
            "mkfs",
            "format",
            "> /dev/",
        ]
    ),
    SafetyRule(
        name="no_sensitive_files",
        forbidden_patterns=[
            "/etc/passwd",
            "/etc/shadow",
            "~/.ssh/id_rsa",
            ".env",
        ]
    ),
]


def get_default_engine() -> RuleEngine:
    """Get rule engine with default safety rules."""
    return RuleEngine(rules=DEFAULT_RULES)
