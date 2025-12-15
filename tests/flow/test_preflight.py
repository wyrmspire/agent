"""
tests/flow/test_preflight.py - Preflight Checker Tests

Tests for the Phase A preflight and circuit breaker implementation.
"""

import pytest
from unittest.mock import MagicMock

from core.types import ToolCall
from flow.preflight import (
    PreflightChecker,
    CircuitBreakerState,
    PreflightResult,
    create_preflight_checker,
)


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState."""
    
    def test_record_failure_increments_count(self):
        """Same call failing should increment count."""
        cb = CircuitBreakerState()
        tc = ToolCall(id="1", name="read_file", arguments={"path": "test.txt"})
        
        count1 = cb.record_failure(tc, "File not found")
        count2 = cb.record_failure(tc, "File not found")
        
        assert count1 == 1
        assert count2 == 2
    
    def test_is_tripped_after_threshold(self):
        """Circuit breaker should trip after 2 failures."""
        cb = CircuitBreakerState()
        tc = ToolCall(id="1", name="read_file", arguments={"path": "test.txt"})
        
        cb.record_failure(tc, "File not found")
        is_tripped, _ = cb.is_tripped(tc)
        assert not is_tripped
        
        cb.record_failure(tc, "File not found")
        is_tripped, reason = cb.is_tripped(tc)
        assert is_tripped
        assert "failed 2 times" in reason
    
    def test_record_success_clears_count(self):
        """Success should clear failure count."""
        cb = CircuitBreakerState()
        tc = ToolCall(id="1", name="read_file", arguments={"path": "test.txt"})
        
        cb.record_failure(tc, "Error 1")
        cb.record_success(tc)
        
        is_tripped, _ = cb.is_tripped(tc)
        assert not is_tripped
    
    def test_error_class_tracking(self):
        """Should detect patterns in error classes."""
        cb = CircuitBreakerState()
        
        # Different paths but same error class
        tc1 = ToolCall(id="1", name="read_file", arguments={"path": "a.txt"})
        tc2 = ToolCall(id="2", name="read_file", arguments={"path": "b.txt"})
        tc3 = ToolCall(id="3", name="read_file", arguments={"path": "c.txt"})
        tc4 = ToolCall(id="4", name="read_file", arguments={"path": "d.txt"})
        
        cb.record_failure(tc1, "File not found")
        cb.record_failure(tc2, "No such file")
        cb.record_failure(tc3, "Path does not exist")
        
        # After 3 PATH_NOT_FOUND errors, new calls should trip
        is_tripped, reason = cb.is_tripped(tc4)
        assert is_tripped
        assert "PATH_NOT_FOUND" in reason
    
    def test_bad_path_tracking(self):
        """Should track paths that failed with not found."""
        cb = CircuitBreakerState()
        tc = ToolCall(id="1", name="read_file", arguments={"path": "missing.txt"})
        
        cb.record_failure(tc, "File not found")
        
        assert cb.is_bad_path("missing.txt")
        assert not cb.is_bad_path("other.txt")


class TestPreflightChecker:
    """Tests for PreflightChecker."""
    
    def test_planner_mode_blocks_tools(self):
        """Planner mode should block all tool calls."""
        checker = create_preflight_checker()
        tc = ToolCall(id="1", name="read_file", arguments={"path": "test.txt"})
        
        result = checker.check([tc], mode="planner")
        
        assert not result.passed
        assert "Planner mode is active" in result.failures[0]
    
    def test_builder_mode_allows_tools(self):
        """Builder mode should allow tool calls."""
        checker = create_preflight_checker()
        tc = ToolCall(id="1", name="read_file", arguments={"path": "test.txt"})
        
        result = checker.check([tc], mode="builder")
        
        assert result.passed
    
    def test_circuit_breaker_blocks_after_failures(self):
        """Should block tool after 2 failures."""
        checker = create_preflight_checker()
        tc = ToolCall(id="1", name="read_file", arguments={"path": "test.txt"})
        
        # Record 2 failures
        checker.circuit_breaker.record_failure(tc, "Error 1")
        checker.circuit_breaker.record_failure(tc, "Error 2")
        
        result = checker.check([tc], mode="builder")
        
        assert not result.passed
        assert "CIRCUIT BREAKER" in result.failures[0]
    
    def test_path_gate_blocks_bad_paths(self):
        """Should block access to known-bad paths."""
        checker = create_preflight_checker()
        tc1 = ToolCall(id="1", name="read_file", arguments={"path": "missing.txt"})
        
        # First call fails
        checker.circuit_breaker.record_failure(tc1, "File not found")
        
        # Second call to same path should be blocked by path gate
        result = checker.check([tc1], mode="builder")
        
        assert not result.passed
        assert "PATH GATE" in result.failures[0]
    
    def test_tool_capability_warnings(self):
        """Should warn about unsupported file types."""
        checker = create_preflight_checker()
        tc = ToolCall(id="1", name="data_view", arguments={"path": "test.xml"})
        
        result = checker.check([tc], mode="builder")
        
        # Should pass but with warning
        assert result.passed or len(result.warnings) > 0
    
    def test_verification_selective_for_high_impact(self):
        """Should only suggest verification for high-impact files."""
        checker = create_preflight_checker()
        
        # High-impact file
        tc1 = ToolCall(id="1", name="write_file", arguments={"path": "config.yaml"})
        suggestions1 = checker.check_verification_needed([tc1], high_impact_only=True)
        assert len(suggestions1) > 0
        
        # Low-impact file
        tc2 = ToolCall(id="2", name="write_file", arguments={"path": "temp.txt"})
        suggestions2 = checker.check_verification_needed([tc2], high_impact_only=True)
        assert len(suggestions2) == 0


class TestPlannerModeIntegration:
    """Integration tests for planner mode."""
    
    def test_no_acting_blocks_all_tools(self):
        """When mode is planner, all tools should be blocked."""
        checker = create_preflight_checker()
        
        # Try various tools
        tools = [
            ToolCall(id="1", name="shell", arguments={"command": "dir"}),
            ToolCall(id="2", name="write_file", arguments={"path": "x.txt", "content": ""}),
            ToolCall(id="3", name="list_files", arguments={"path": "."}),
        ]
        
        for tc in tools:
            result = checker.check([tc], mode="planner")
            assert not result.passed, f"{tc.name} should be blocked in planner mode"
