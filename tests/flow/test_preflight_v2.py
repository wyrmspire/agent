"""
tests/flow/test_preflight_v2.py - Tests for Phase B Preflight Enhancements

Tests for:
- Intent classification
- Intent-based circuit breaker
- Recovery ladder
- Path normalization with safe rewrites
- OVERRIDE escape hatch
"""

import pytest
from unittest.mock import MagicMock

from core.types import ToolCall
from flow.preflight import (
    PreflightChecker,
    CircuitBreakerState,
    PreflightResult,
    PathResolver,
    PathRewrite,
    RewriteSafety,
    TOOL_CAPABILITIES,
    _classify_intent,
    get_recovery_action,
    create_preflight_checker,
)


class TestIntentClassification:
    """Tests for intent classification."""
    
    def test_read_file_classified_as_inspect(self):
        """read_file should be classified as inspect_file."""
        tc = ToolCall(id="1", name="read_file", arguments={"path": "test.py"})
        assert _classify_intent(tc) == "inspect_file"
    
    def test_data_view_classified_as_inspect(self):
        """data_view should be classified as inspect_file."""
        tc = ToolCall(id="1", name="data_view", arguments={"path": "data.csv"})
        assert _classify_intent(tc) == "inspect_file"
    
    def test_list_files_data_classified_as_find_data(self):
        """list_files with 'data' in path should be find_data."""
        tc = ToolCall(id="1", name="list_files", arguments={"path": "workspace/data/"})
        assert _classify_intent(tc) == "find_data"
    
    def test_list_files_generic_classified_as_explore(self):
        """list_files without 'data' should be explore_directory."""
        tc = ToolCall(id="1", name="list_files", arguments={"path": "workspace/"})
        assert _classify_intent(tc) == "explore_directory"
    
    def test_shell_find_classified_as_find_data(self):
        """shell with find command should be find_data."""
        tc = ToolCall(id="1", name="shell", arguments={"command": "find . -name '*.csv'"})
        assert _classify_intent(tc) == "find_data"
    
    def test_shell_mkdir_classified_as_create_structure(self):
        """shell with mkdir should be create_structure."""
        tc = ToolCall(id="1", name="shell", arguments={"command": "mkdir new_folder"})
        assert _classify_intent(tc) == "create_structure"
    
    def test_write_file_md_classified_as_write_document(self):
        """write_file for .md should be write_document."""
        tc = ToolCall(id="1", name="write_file", arguments={"path": "notes.md"})
        assert _classify_intent(tc) == "write_document"
    
    def test_write_file_py_classified_as_write_code(self):
        """write_file for .py should be write_code."""
        tc = ToolCall(id="1", name="write_file", arguments={"path": "script.py"})
        assert _classify_intent(tc) == "write_code"


class TestIntentBasedCircuitBreaker:
    """Tests for intent-based circuit breaker."""
    
    def test_intent_exhaustion_after_threshold(self):
        """Intent should be exhausted after 3 failures."""
        cb = CircuitBreakerState()
        
        # Simulate 3 failures with different files but same intent
        tc1 = ToolCall(id="1", name="read_file", arguments={"path": "a.py"})
        tc2 = ToolCall(id="2", name="read_file", arguments={"path": "b.py"})
        tc3 = ToolCall(id="3", name="read_file", arguments={"path": "c.py"})
        
        cb.current_step = 1
        cb.record_failure(tc1, "file not found")
        cb.current_step = 2
        cb.record_failure(tc2, "file not found")
        cb.current_step = 3
        cb.record_failure(tc3, "file not found")
        
        # New call with same intent should be exhausted
        tc4 = ToolCall(id="4", name="read_file", arguments={"path": "d.py"})
        cb.current_step = 4
        is_exhausted, reason, intent = cb.is_intent_exhausted(tc4)
        
        assert is_exhausted
        assert "inspect_file" in (intent or "")
        assert "failed" in (reason or "").lower()
    
    def test_deterministic_error_counts_double(self):
        """PATH_NOT_FOUND should count double toward threshold (trips faster)."""
        cb = CircuitBreakerState()
        
        # Only 2 failures with deterministic errors
        # Each counts as 2, so total = 4, which exceeds threshold of 3
        tc1 = ToolCall(id="1", name="read_file", arguments={"path": "missing1.py"})
        tc2 = ToolCall(id="2", name="read_file", arguments={"path": "missing2.py"})
        
        cb.current_step = 1
        cb.record_failure(tc1, "file not found")  # Counts as 2
        cb.current_step = 2
        cb.record_failure(tc2, "no such file")    # Counts as 2, total 4
        
        # Check intent state directly
        intent_state = cb.intent_states.get("inspect_file")
        assert intent_state is not None, "Intent should be tracked"
        # Each deterministic error adds +1 extra, so 2 errors = 4 count
        assert intent_state.failure_count >= 4, f"Expected >= 4, got {intent_state.failure_count}"
    
    def test_override_resets_intent(self):
        """Using OVERRIDE should reset the intent failure count."""
        cb = CircuitBreakerState()
        
        # Exhaust intent
        for i in range(3):
            tc = ToolCall(id=str(i), name="read_file", arguments={"path": f"file{i}.py"})
            cb.current_step = i + 1
            cb.record_failure(tc, "some error")
        
        # Use override
        success = cb.use_override("inspect_file")
        assert success
        
        # Intent should no longer be exhausted
        tc = ToolCall(id="4", name="read_file", arguments={"path": "new.py"})
        cb.current_step = 5
        is_exhausted, _, _ = cb.is_intent_exhausted(tc)
        assert not is_exhausted
    
    def test_override_only_works_once(self):
        """OVERRIDE should only work once per intent."""
        cb = CircuitBreakerState()
        
        success1 = cb.use_override("inspect_file")
        success2 = cb.use_override("inspect_file")
        
        assert success1
        assert not success2


class TestRecoveryLadder:
    """Tests for recovery ladder."""
    
    def test_first_failure_suggests_retry(self):
        """First failure should suggest retry."""
        action_name, desc = get_recovery_action("test", 1, "error")
        assert action_name == "retry_once"
    
    def test_second_failure_suggests_switch_tool(self):
        """Second failure should suggest switching tools."""
        action_name, desc = get_recovery_action("test", 2, "error")
        assert action_name == "switch_tool"
    
    def test_third_failure_suggests_switch_approach(self):
        """Third failure should suggest switching approach."""
        action_name, desc = get_recovery_action("test", 3, "error")
        assert action_name == "switch_approach"
    
    def test_many_failures_force_plan(self):
        """Many failures should force planning."""
        action_name, desc = get_recovery_action("test", 5, "error")
        assert action_name == "stop_and_plan"


class TestPathResolver:
    """Tests for path resolution and normalization."""
    
    def test_slash_normalization_is_safe(self):
        """Slash normalization should be marked as safe rewrite."""
        resolver = PathResolver()
        analysis = resolver.analyze_path("workspace/data/file.csv", "read_file")
        
        # On Windows, forward slashes may be normalized to backslashes
        if analysis.needs_rewrite and analysis.rewrite:
            assert analysis.rewrite.safety == RewriteSafety.SAFE
    
    def test_redundant_workspace_prefix_is_safe(self):
        """workspace/workspace/ normalization should be safe."""
        resolver = PathResolver()
        analysis = resolver.analyze_path("workspace/workspace/file.txt", "write_file")
        
        assert analysis.needs_rewrite
        assert analysis.rewrite is not None
        assert analysis.rewrite.safety == RewriteSafety.SAFE
        assert "workspace/workspace" not in analysis.normalized_path


class TestToolCapabilities:
    """Tests for tool capability matrix with alternatives."""
    
    def test_json_has_alternative_for_data_view(self):
        """data_view should have alternative for .json files."""
        caps = TOOL_CAPABILITIES.get("data_view", {})
        alts = caps.get("unsupported_alternatives", {})
        assert ".json" in alts
        assert "pyexe" in alts[".json"].lower() or "read_file" in alts[".json"].lower()
    
    def test_zip_has_alternative_for_read_file(self):
        """read_file should have alternative for .zip files."""
        caps = TOOL_CAPABILITIES.get("read_file", {})
        alts = caps.get("blocked_alternatives", {})
        assert ".zip" in alts
        assert "unzip" in alts[".zip"].lower()


class TestPreflightIntentExhaustion:
    """Integration tests for preflight with intent exhaustion."""
    
    def test_preflight_blocks_on_exhausted_intent(self):
        """Preflight should block when intent is exhausted."""
        checker = create_preflight_checker()
        
        # Exhaust the intent
        for i in range(3):
            tc = ToolCall(id=str(i), name="read_file", arguments={"path": f"file{i}.py"})
            checker.circuit_breaker.current_step = i + 1
            checker.circuit_breaker.record_failure(tc, "not found")
        
        # New call should be blocked
        tc = ToolCall(id="4", name="read_file", arguments={"path": "another.py"})
        checker.circuit_breaker.current_step = 4
        result = checker.check([tc], mode="builder")
        
        assert not result.passed
        assert result.forced_plan_mode
        assert "INTENT EXHAUSTED" in result.failures[0] or "intent" in result.failures[0].lower()
    
    def test_preflight_accepts_override(self):
        """Preflight should accept OVERRIDE in model output."""
        checker = create_preflight_checker()
        
        # Exhaust the intent
        for i in range(3):
            tc = ToolCall(id=str(i), name="read_file", arguments={"path": f"file{i}.py"})
            checker.circuit_breaker.current_step = i + 1
            checker.circuit_breaker.record_failure(tc, "not found")
        
        # New call with OVERRIDE in model output
        tc = ToolCall(id="4", name="read_file", arguments={"path": "another.py"})
        checker.circuit_breaker.current_step = 4
        result = checker.check([tc], mode="builder", model_output="OVERRIDE: found the correct directory")
        
        assert result.passed or "OVERRIDE accepted" in str(result.warnings)
    
    def test_preflight_shows_alternative_on_block(self):
        """Preflight blocked message should include alternative."""
        checker = create_preflight_checker()
        
        # Try to use data_view on .json (not in supported_types)
        tc = ToolCall(id="1", name="data_view", arguments={"path": "data.json"})
        result = checker.check([tc], mode="builder")
        
        # Should have warning with alternative
        if result.warnings:
            alt_text = " ".join(result.warnings).lower()
            assert "alternative" in alt_text or "pyexe" in alt_text or "read_file" in alt_text
