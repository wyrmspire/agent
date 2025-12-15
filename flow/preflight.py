"""
flow/preflight.py - Preflight Checks and Circuit Breaker

This module implements preflight validation and circuit breaker pattern
to prevent tool misuse and infinite retry loops.

Phase B: Agent Resilience Improvements
- Tool capability matrix with suggested alternatives
- Intent-based circuit breaker (catches "same thing 10 ways" loops)
- Strict recovery ladder with OVERRIDE escape hatch
- Safe path rewrite pattern (metadata + executor application)

Responsibilities:
- Validate preconditions before tool execution
- Track failed tool calls by INTENT, not just args
- Enforce mode-based restrictions (planner vs builder)
- Suggest alternatives when blocking
- Compute safe path rewrites for executor

Rules:
- Preflight checks run BEFORE every tool batch
- Intent breaker triggers after 3 failures (2 for deterministic errors)
- Rewrites are computed here but APPLIED at executor
- All checks are fast and non-blocking
"""

import logging
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.types import ToolCall

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

class RewriteSafety(Enum):
    """Safety level for path rewrites."""
    SAFE = "safe"      # Apply automatically (slash normalization, redundant prefix)
    RISKY = "risky"    # Log warning, apply only if would definitely fail otherwise


@dataclass
class PathRewrite:
    """A proposed path rewrite for a tool call."""
    tool_call_id: str
    argument_name: str    # "path" or "file_path"
    original: str
    normalized: str
    reason: str
    safety: RewriteSafety = RewriteSafety.SAFE


@dataclass
class PathAnalysis:
    """Analysis of a path for a tool call."""
    original_path: str
    normalized_path: str
    path_kind: str        # "relative", "workspace", "absolute", "project"
    recommended_form: str # What form this tool prefers
    needs_rewrite: bool
    rewrite: Optional[PathRewrite] = None


@dataclass
class IntentState:
    """Tracks failures for a specific intent."""
    failure_count: int = 0
    step_numbers: List[int] = field(default_factory=list)
    last_error: str = ""
    override_used: bool = False


@dataclass
class PreflightResult:
    """Result of preflight checks.
    
    Attributes:
        passed: Whether all checks passed
        failures: List of failed check descriptions with alternatives
        warnings: List of warning messages
        rewrites: List of safe path rewrites for executor to apply
        forced_plan_mode: If True, block tools and force planning
        intent_blocked: Intent that triggered block (for OVERRIDE checks)
    """
    passed: bool
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rewrites: List[PathRewrite] = field(default_factory=list)
    forced_plan_mode: bool = False
    intent_blocked: Optional[str] = None


# =============================================================================
# Tool Capability Matrix
# =============================================================================

TOOL_CAPABILITIES = {
    "data_view": {
        "max_file_size_mb": 10,
        "supported_types": [".csv", ".parquet", ".xlsx"],
        "unsupported_alternatives": {
            ".json": "Use read_file + json.loads() in pyexe, OR shell: jq for filtering",
            ".xml": "Use shell: xmllint, OR pyexe with xml.etree.ElementTree",
            ".txt": "Use read_file for text content",
            ".log": "Use read_file OR shell: tail/head for large files",
        },
        "description": "Structured data viewer for tabular formats",
    },
    "read_file": {
        "max_file_size_mb": 5,
        "blocked_types": [".exe", ".dll", ".bin", ".zip", ".tar", ".gz", ".7z"],
        "blocked_alternatives": {
            ".zip": "Use shell: unzip -l to list contents, unzip to extract",
            ".gz": "Use shell: zcat or gunzip to decompress first",
            ".tar": "Use shell: tar -tf to list, tar -xf to extract",
            ".7z": "Use shell: 7z l to list, 7z x to extract",
        },
        "description": "Read text file contents",
    },
    "write_file": {
        "requires_workspace": True,
        "path_form": "workspace-relative",
        "description": "Write content to file in workspace",
    },
    "pyexe": {
        "max_file_size_mb": 50,
        "timeout_seconds": 120,
        "path_form": "absolute",
        "description": "Execute Python code",
    },
    "shell": {
        "path_form": "workspace-relative",
        "description": "Execute shell commands",
    },
    "list_files": {
        "path_form": "workspace-relative",
        "description": "List directory contents",
    },
}


# =============================================================================
# Intent Classification
# =============================================================================

def _classify_intent(tool_call: ToolCall) -> Optional[str]:
    """Classify a tool call into an intent category.
    
    Intent categories help detect when agent is trying "the same thing 10 ways."
    
    Returns:
        Intent string like "inspect_file", "find_data", "create_structure", etc.
    """
    name = tool_call.name
    args = tool_call.arguments
    path = str(args.get("path", "") or args.get("file_path", "") or "").lower()
    cmd = str(args.get("command", "") or args.get("cmd", "") or "").lower()
    
    # File inspection intents
    if name in ("read_file", "data_view"):
        return "inspect_file"
    
    # Directory exploration intents
    if name == "list_files":
        if "data" in path:
            return "find_data"
        return "explore_directory"
    
    # Shell-based intents - check more specific patterns first
    if name == "shell":
        # Structural changes first (most specific)
        if any(kw in cmd for kw in ["mkdir", "md ", "new-item"]):
            return "create_structure"
        if any(kw in cmd for kw in ["cp", "copy", "mv", "move", "rename"]):
            return "move_files"
        # Then inspection/search
        if any(kw in cmd for kw in ["find ", "dir ", "ls ", "tree"]):
            return "find_data"
        if any(kw in cmd for kw in ["cat", "type", "head", "tail", "more"]):
            return "inspect_file"
    
    # Write intents
    if name == "write_file":
        if path.endswith((".md", ".txt")):
            return "write_document"
        if path.endswith((".py", ".js", ".ts")):
            return "write_code"
        return "write_file"
    
    # Python execution
    if name == "pyexe":
        content = str(args.get("code", "") or "").lower()
        if "import json" in content or "json.load" in content:
            return "parse_json"
        if "import pandas" in content or "pd.read" in content:
            return "analyze_data"
        return "execute_code"
    
    return f"use_{name}"


# =============================================================================
# Circuit Breaker State
# =============================================================================

@dataclass 
class CircuitBreakerState:
    """Tracks tool call failures for circuit breaker pattern.
    
    Enhanced with intent-based tracking to catch "same thing many ways" loops.
    
    Attributes:
        failure_counts: Map of (tool_name, args_hash) -> failure count
        last_failures: Map of (tool_name, args_hash) -> last error message
        error_classes: Map of (tool_name, error_class) -> failure count
        bad_paths: Set of paths that have failed existence checks
        intent_states: Map of intent -> IntentState (failure tracking per intent)
        current_step: Current step number for tracking
    """
    failure_counts: Dict[str, int] = field(default_factory=dict)
    last_failures: Dict[str, str] = field(default_factory=dict)
    error_classes: Dict[str, int] = field(default_factory=dict)
    bad_paths: set = field(default_factory=set)
    intent_states: Dict[str, IntentState] = field(default_factory=dict)
    current_step: int = 0
    
    def get_call_key(self, tool_call: ToolCall) -> str:
        """Generate unique key for a tool call based on name + args."""
        args_str = json.dumps(tool_call.arguments, sort_keys=True, default=str)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
        return f"{tool_call.name}:{args_hash}"
    
    def _classify_error(self, error: str) -> str:
        """Classify an error into a category for pattern detection."""
        error_lower = error.lower()
        if "not found" in error_lower or "does not exist" in error_lower or "no such file" in error_lower:
            return "PATH_NOT_FOUND"
        if "permission" in error_lower or "access denied" in error_lower:
            return "PERMISSION_DENIED"
        if "syntax" in error_lower or "invalid" in error_lower:
            return "SYNTAX_ERROR"
        if "timeout" in error_lower:
            return "TIMEOUT"
        if "already exists" in error_lower:
            return "ALREADY_EXISTS"
        if "too large" in error_lower or "size" in error_lower:
            return "SIZE_LIMIT"
        if "outside" in error_lower and "workspace" in error_lower:
            return "PATH_OUTSIDE_WORKSPACE"
        return "UNKNOWN"
    
    def _is_deterministic_error(self, error_class: str) -> bool:
        """Check if error class is deterministic (unlikely to change on retry)."""
        return error_class in ("PATH_NOT_FOUND", "PATH_OUTSIDE_WORKSPACE", "PERMISSION_DENIED")
    
    def record_failure(self, tool_call: ToolCall, error: str) -> int:
        """Record a tool call failure.
        
        Returns:
            New failure count for this call signature
        """
        key = self.get_call_key(tool_call)
        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
        self.last_failures[key] = error
        
        # Track error class too
        error_class = self._classify_error(error)
        class_key = f"{tool_call.name}:{error_class}"
        self.error_classes[class_key] = self.error_classes.get(class_key, 0) + 1
        
        # Track bad paths for path gate
        if error_class == "PATH_NOT_FOUND":
            path = tool_call.arguments.get("path") or tool_call.arguments.get("file_path") or ""
            if path:
                self.bad_paths.add(path)
        
        # Track intent-based failures
        intent = _classify_intent(tool_call)
        if intent:
            if intent not in self.intent_states:
                self.intent_states[intent] = IntentState()
            state = self.intent_states[intent]
            state.failure_count += 1
            state.step_numbers.append(self.current_step)
            state.last_error = error
            
            # For deterministic errors, count double
            if self._is_deterministic_error(error_class):
                state.failure_count += 1
        
        logger.debug(f"Circuit breaker: {key} failed {self.failure_counts[key]} times ({error_class})")
        return self.failure_counts[key]
    
    def record_success(self, tool_call: ToolCall) -> None:
        """Clear failure count on success."""
        key = self.get_call_key(tool_call)
        if key in self.failure_counts:
            del self.failure_counts[key]
        if key in self.last_failures:
            del self.last_failures[key]
    
    def is_tripped(self, tool_call: ToolCall, threshold: int = 2) -> Tuple[bool, Optional[str]]:
        """Check if circuit breaker is tripped for this call.
        
        Triggers on:
        1. Same tool + same args failed 2+ times
        2. Same tool + same error CLASS failed 3+ times (catches minor variations)
        
        Args:
            tool_call: The tool call to check
            threshold: Number of failures before tripping (default: 2)
            
        Returns:
            Tuple of (is_tripped, reason)
        """
        key = self.get_call_key(tool_call)
        count = self.failure_counts.get(key, 0)
        
        # Check 1: Exact same call
        if count >= threshold:
            last_error = self.last_failures.get(key, "unknown")
            return True, f"Same call failed {count} times. Last error: {last_error[:100]}"
        
        # Check 2: Same error class across similar calls (threshold + 1)
        for error_class in ["PATH_NOT_FOUND", "PERMISSION_DENIED", "SYNTAX_ERROR", "PATH_OUTSIDE_WORKSPACE"]:
            class_key = f"{tool_call.name}:{error_class}"
            class_count = self.error_classes.get(class_key, 0)
            if class_count >= threshold + 1:
                return True, f"'{tool_call.name}' has failed with {error_class} {class_count} times"
        
        return False, None
    
    def is_intent_exhausted(
        self, 
        tool_call: ToolCall, 
        threshold: int = 3,
        step_window: int = 10,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if intent has failed too many times within step window.
        
        Args:
            tool_call: The tool call to check
            threshold: Number of failures before blocking (default: 3, 2 for deterministic)
            step_window: Only count failures within last N steps
            
        Returns:
            Tuple of (is_exhausted, reason, intent_name)
        """
        intent = _classify_intent(tool_call)
        if not intent or intent not in self.intent_states:
            return False, None, intent
        
        state = self.intent_states[intent]
        
        # Filter to recent steps
        recent_failures = [s for s in state.step_numbers if s >= self.current_step - step_window]
        recent_count = len(recent_failures)
        
        # Already used override?
        if state.override_used:
            # After override, require even more failures to block again
            threshold += 2
        
        if recent_count >= threshold:
            return True, (
                f"Intent '{intent}' has failed {recent_count} times in last {step_window} steps. "
                f"Last error: {state.last_error[:80]}..."
            ), intent
        
        return False, None, intent
    
    def use_override(self, intent: str) -> bool:
        """Mark that OVERRIDE was used for this intent.
        
        Returns:
            True if override was allowed, False if already used
        """
        if intent not in self.intent_states:
            self.intent_states[intent] = IntentState()
        
        state = self.intent_states[intent]
        if state.override_used:
            return False
        
        state.override_used = True
        # Reset failure count to give fresh attempts
        state.failure_count = 0
        state.step_numbers = []
        return True
    
    def is_bad_path(self, path: str) -> bool:
        """Check if a path has previously failed existence checks."""
        return path in self.bad_paths
    
    def advance_step(self) -> None:
        """Advance the step counter."""
        self.current_step += 1
    
    def clear(self) -> None:
        """Reset all circuit breaker state."""
        self.failure_counts.clear()
        self.last_failures.clear()
        self.error_classes.clear()
        self.bad_paths.clear()
        self.intent_states.clear()
        self.current_step = 0


# =============================================================================
# Path Resolver
# =============================================================================

class PathResolver:
    """Resolves and normalizes paths for tool calls."""
    
    def __init__(self, workspace_root: Optional[Path] = None, project_root: Optional[Path] = None):
        """Initialize path resolver.
        
        Args:
            workspace_root: Path to workspace directory
            project_root: Path to project root
        """
        self.workspace_root = (workspace_root or Path("workspace")).resolve()
        self.project_root = (project_root or Path(".")).resolve()
    
    def analyze_path(self, path: str, tool_name: str) -> PathAnalysis:
        """Analyze a path and compute normalization.
        
        Returns PathAnalysis with original, normalized, and rewrite info.
        """
        if not path:
            return PathAnalysis(
                original_path="",
                normalized_path="",
                path_kind="empty",
                recommended_form="any",
                needs_rewrite=False,
            )
        
        # Determine path kind
        path_obj = Path(path)
        path_kind = self._classify_path(path)
        
        # Get tool's preferred form
        tool_caps = TOOL_CAPABILITIES.get(tool_name, {})
        recommended_form = tool_caps.get("path_form", "any")
        
        # Compute normalized path
        normalized = self._normalize_path(path, tool_name, path_kind)
        needs_rewrite = normalized != path
        
        # Create rewrite if needed
        rewrite = None
        if needs_rewrite:
            safety = self._determine_rewrite_safety(path, normalized, path_kind)
            reason = self._get_rewrite_reason(path, normalized, path_kind)
            rewrite = PathRewrite(
                tool_call_id="",  # Filled in by caller
                argument_name="path",
                original=path,
                normalized=normalized,
                reason=reason,
                safety=safety,
            )
        
        return PathAnalysis(
            original_path=path,
            normalized_path=normalized,
            path_kind=path_kind,
            recommended_form=recommended_form,
            needs_rewrite=needs_rewrite,
            rewrite=rewrite,
        )
    
    def _classify_path(self, path: str) -> str:
        """Classify a path type."""
        path_obj = Path(path)
        
        if path_obj.is_absolute():
            try:
                path_obj.resolve().relative_to(self.workspace_root)
                return "workspace"
            except ValueError:
                try:
                    path_obj.resolve().relative_to(self.project_root)
                    return "project"
                except ValueError:
                    return "absolute"
        
        # Relative path
        if path.startswith("workspace/") or path.startswith("workspace\\"):
            return "workspace"
        
        return "relative"
    
    def _normalize_path(self, path: str, tool_name: str, path_kind: str) -> str:
        """Normalize path for the given tool."""
        # Normalize slashes for Windows
        if os.name == 'nt':
            # But keep forward slashes for shell commands (git bash)
            if tool_name != "shell":
                path = path.replace("/", "\\")
        
        # Remove redundant workspace prefix
        if path.startswith("workspace/workspace/") or path.startswith("workspace\\workspace\\"):
            path = path.replace("workspace/workspace/", "workspace/").replace("workspace\\workspace\\", "workspace\\")
        
        # Collapse .. and . 
        try:
            path_obj = Path(path)
            if not path_obj.is_absolute():
                # Don't resolve relative paths (changes semantics)
                # Just normalize the string
                pass
            else:
                path = str(path_obj.resolve())
        except (OSError, ValueError):
            pass
        
        return path
    
    def _determine_rewrite_safety(self, original: str, normalized: str, path_kind: str) -> RewriteSafety:
        """Determine if a rewrite is safe to auto-apply."""
        # Slash normalization is always safe
        if original.replace("/", "\\") == normalized or original.replace("\\", "/") == normalized:
            return RewriteSafety.SAFE
        
        # Redundant prefix removal is safe
        if "workspace/workspace" in original or "workspace\\workspace" in original:
            return RewriteSafety.SAFE
        
        # Everything else is risky
        return RewriteSafety.RISKY
    
    def _get_rewrite_reason(self, original: str, normalized: str, path_kind: str) -> str:
        """Get human-readable reason for rewrite."""
        if original.replace("/", "\\") == normalized or original.replace("\\", "/") == normalized:
            return "slash normalization"
        if "workspace/workspace" in original or "workspace\\workspace" in original:
            return "redundant workspace prefix"
        return "path normalization"


# =============================================================================
# Recovery Ladder
# =============================================================================

RECOVERY_LADDER = [
    ("retry_once", "Retry with same tool if error was transient (network, timeout)"),
    ("switch_tool", "Try alternative tool from capability matrix"),
    ("switch_approach", "Inspect smaller sample / convert format / create scratch copy"),
    ("stop_and_plan", "STOP. Write a plan: what failed, what we know, next minimal experiment, success criteria"),
]


def get_recovery_action(intent: str, failure_count: int, last_error: str) -> Tuple[str, str]:
    """Get the next recovery action based on failure count.
    
    Returns:
        Tuple of (action_name, action_description)
    """
    if failure_count <= 1:
        return RECOVERY_LADDER[0]
    elif failure_count == 2:
        return RECOVERY_LADDER[1]
    elif failure_count == 3:
        return RECOVERY_LADDER[2]
    else:
        return RECOVERY_LADDER[3]


# =============================================================================
# Preflight Checker
# =============================================================================

class PreflightChecker:
    """Validates preconditions before tool execution.
    
    Checks performed:
    1. Mode check: Is acting allowed? (planner mode blocks tools)
    2. Circuit breaker: Has this exact call failed too many times?
    3. Intent exhaustion: Has this INTENT failed too many times?
    4. Path gate: Block calls to known-bad paths
    5. Tool capability: File type/size limits with alternatives
    6. Path normalization: Compute safe rewrites for executor
    """
    
    def __init__(
        self, 
        circuit_breaker: Optional[CircuitBreakerState] = None,
        path_resolver: Optional[PathResolver] = None,
    ):
        """Initialize preflight checker.
        
        Args:
            circuit_breaker: Optional shared circuit breaker state
            path_resolver: Optional path resolver
        """
        self.circuit_breaker = circuit_breaker or CircuitBreakerState()
        self.path_resolver = path_resolver or PathResolver()
    
    def check(
        self,
        tool_calls: List[ToolCall],
        mode: str = "builder",
        environment: Optional[Dict[str, Any]] = None,
        model_output: str = "",
    ) -> PreflightResult:
        """Run all preflight checks on a batch of tool calls.
        
        Args:
            tool_calls: List of tool calls to validate
            mode: Current agent mode ("planner" or "builder")
            environment: Optional environment info (platform, constraints)
            model_output: Model's text output (for OVERRIDE detection)
            
        Returns:
            PreflightResult with pass/fail, alternatives, and rewrites
        """
        failures = []
        warnings = []
        rewrites = []
        forced_plan_mode = False
        intent_blocked = None
        
        # Check 0: Mode restriction
        if mode == "planner":
            failures.append(
                "BLOCKED: Planner mode is active. Tools are disabled. "
                "Output your plan as text only."
            )
            return PreflightResult(passed=False, failures=failures)
        
        # Advance step counter
        self.circuit_breaker.advance_step()
        
        # Check each tool call
        for tc in tool_calls:
            path = tc.arguments.get("path") or tc.arguments.get("file_path") or ""
            
            # Check 1: Intent exhaustion (strict recovery ladder)
            is_exhausted, reason, intent = self.circuit_breaker.is_intent_exhausted(tc)
            if is_exhausted:
                # Check for OVERRIDE in model output
                override_used = False
                if "OVERRIDE:" in model_output.upper():
                    if self.circuit_breaker.use_override(intent):
                        warnings.append(
                            f"OVERRIDE accepted for intent '{intent}'. "
                            f"This is your last chance for this intent."
                        )
                        override_used = True
                    else:
                        failures.append(
                            f"OVERRIDE already used for '{intent}'. Cannot override again."
                        )
                        forced_plan_mode = True
                        intent_blocked = intent
                        continue
                
                if not override_used:
                    # Get recovery action
                    state = self.circuit_breaker.intent_states.get(intent, IntentState())
                    action_name, action_desc = get_recovery_action(
                        intent, state.failure_count, state.last_error
                    )
                    
                    failures.append(
                        f"🪜 INTENT EXHAUSTED: {reason}\n"
                        f"→ Recovery action: {action_desc}\n"
                        f"→ To override: output 'OVERRIDE: [new evidence/changed assumption]' (1 use per intent)"
                    )
                    forced_plan_mode = True
                    intent_blocked = intent
                    continue
            
            # Check 2: Circuit breaker (exact call)
            is_tripped, reason = self.circuit_breaker.is_tripped(tc)
            if is_tripped:
                cap = TOOL_CAPABILITIES.get(tc.name, {})
                alternatives = cap.get("unsupported_alternatives", {}) or cap.get("blocked_alternatives", {})
                alt_text = ""
                if path:
                    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
                    if ext in alternatives:
                        alt_text = f"\n→ Alternative: {alternatives[ext]}"
                
                failures.append(
                    f"CIRCUIT BREAKER: {reason}. "
                    f"STOP retrying and try a DIFFERENT approach.{alt_text}"
                )
                continue
            
            # Check 3: Path gate - block calls to known-bad paths
            if path and self.circuit_breaker.is_bad_path(path):
                failures.append(
                    f"PATH GATE: '{path}' previously failed (not found).\n"
                    f"→ Verify path exists with list_files before retrying.\n"
                    f"→ Or try a different path."
                )
                continue
            
            # Check 4: Tool capability limits with alternatives
            cap = TOOL_CAPABILITIES.get(tc.name, {})
            if cap and path:
                ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
                
                # Blocked types
                blocked = cap.get("blocked_types", [])
                if ext in blocked:
                    alt = cap.get("blocked_alternatives", {}).get(ext, "Use shell tool")
                    failures.append(
                        f"BLOCKED: '{tc.name}' cannot handle {ext} files.\n"
                        f"→ Alternative: {alt}"
                    )
                    continue
                
                # Unsupported types (warning + alternative)
                supported = cap.get("supported_types")
                if supported and ext and ext not in supported:
                    alt = cap.get("unsupported_alternatives", {}).get(ext)
                    if alt:
                        warnings.append(
                            f"'{tc.name}' doesn't support {ext}.\n"
                            f"→ Alternative: {alt}"
                        )
                    else:
                        warnings.append(
                            f"'{tc.name}' may not support {ext} files. "
                            f"Supported: {', '.join(supported)}"
                        )
            
            # Check 5: Path normalization
            if path:
                analysis = self.path_resolver.analyze_path(path, tc.name)
                if analysis.needs_rewrite and analysis.rewrite:
                    analysis.rewrite.tool_call_id = tc.id
                    rewrites.append(analysis.rewrite)
                    if analysis.rewrite.safety == RewriteSafety.RISKY:
                        warnings.append(
                            f"Path may need rewrite: '{path}' → '{analysis.normalized_path}' "
                            f"({analysis.rewrite.reason})"
                        )
        
        passed = len(failures) == 0
        return PreflightResult(
            passed=passed, 
            failures=failures, 
            warnings=warnings,
            rewrites=rewrites,
            forced_plan_mode=forced_plan_mode,
            intent_blocked=intent_blocked,
        )
    
    def check_verification_needed(
        self,
        tool_calls: List[ToolCall],
        high_impact_only: bool = True,
    ) -> List[str]:
        """Determine if verification is needed after these tool calls.
        
        Selective verification: only verify high-impact operations to save budget.
        
        Args:
            tool_calls: Completed tool calls
            high_impact_only: If True, only suggest verification for high-impact ops
            
        Returns:
            List of verification suggestions
        """
        suggestions = []
        
        write_tools = ["write_file", "edit_file", "create_file"]
        mkdir_patterns = ["mkdir", "md ", "new-item"]
        high_impact_files = ["config", ".env", "settings", "main", "index", "__init__"]
        
        for tc in tool_calls:
            path = tc.arguments.get("path") or tc.arguments.get("file_path") or ""
            
            # Directory creation always needs verification
            if tc.name == "shell":
                cmd = str(tc.arguments.get("command") or tc.arguments.get("cmd") or "").lower()
                if any(pattern in cmd for pattern in mkdir_patterns):
                    suggestions.append(
                        "VERIFY: Confirm directory was created with list_files"
                    )
                    continue
            
            # Write operations - selective verification
            if tc.name in write_tools:
                is_high_impact = any(keyword in path.lower() for keyword in high_impact_files)
                was_bad_path = self.circuit_breaker.is_bad_path(path) if path else False
                
                if not high_impact_only or is_high_impact or was_bad_path:
                    suggestions.append(
                        f"VERIFY: Confirm '{path}' was created with list_files or read_file"
                    )
        
        return suggestions


def create_preflight_checker() -> PreflightChecker:
    """Factory function to create a preflight checker with fresh state."""
    return PreflightChecker(
        circuit_breaker=CircuitBreakerState(),
        path_resolver=PathResolver(),
    )
