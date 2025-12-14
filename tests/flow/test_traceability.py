"""
tests/flow/test_traceability.py - Tool-Call Traceability Tests

Verifies that tool calls produce grep-able log output with run_id and tool_call_id.
"""

import asyncio
import logging
import io
import pytest

from core.trace import TraceLogger
from core.types import ToolCall, ToolResult


class TestTraceLogger:
    """Tests for TraceLogger structured logging."""
    
    def test_log_tool_call_format(self, caplog):
        """Test that tool call logs have correct format."""
        tracer = TraceLogger(run_id="test_run_abc123")
        tool_call = ToolCall(
            id="tc_001",
            name="list_files",
            arguments={"path": "."},
        )
        
        with caplog.at_level(logging.INFO, logger="agent.trace"):
            tracer.log_tool_call(tool_call)
        
        # Check log contains required fields
        assert "run_id=test_run_abc123" in caplog.text
        assert "tool_call_id=tc_001" in caplog.text
        assert "CALL" in caplog.text
        assert "Tool=list_files" in caplog.text
    
    def test_log_tool_result_success(self, caplog):
        """Test that successful tool result logs have correct format."""
        tracer = TraceLogger(run_id="test_run_xyz789")
        result = ToolResult(
            tool_call_id="tc_002",
            output="file1.txt\nfile2.txt",
            success=True,
        )
        
        with caplog.at_level(logging.INFO, logger="agent.trace"):
            tracer.log_tool_result(result, elapsed_ms=42.5, tool_name="read_file")
        
        # Check log contains required fields
        assert "run_id=test_run_xyz789" in caplog.text
        assert "tool_call_id=tc_002" in caplog.text
        assert "RESULT success" in caplog.text
        assert "Tool=read_file" in caplog.text
        assert "elapsed=42.5ms" in caplog.text
    
    def test_log_tool_result_error(self, caplog):
        """Test that error tool result logs include error info."""
        tracer = TraceLogger(run_id="test_run_error")
        result = ToolResult(
            tool_call_id="tc_003",
            output="",
            error="File not found: test.txt",
            success=False,
        )
        
        with caplog.at_level(logging.INFO, logger="agent.trace"):
            tracer.log_tool_result(result, elapsed_ms=5.0)
        
        # Check error info is included
        assert "RESULT error" in caplog.text
        assert "File not found" in caplog.text
    
    def test_log_budget_exhausted(self, caplog):
        """Test budget exhaustion logging."""
        tracer = TraceLogger(run_id="test_budget_run")
        
        with caplog.at_level(logging.WARNING, logger="agent.trace"):
            tracer.log_budget_exhausted(skipped_tools=3)
        
        assert "BUDGET_EXHAUSTED" in caplog.text
        assert "skipped=3" in caplog.text
    
    def test_args_truncation(self, caplog):
        """Test that large arguments are truncated."""
        tracer = TraceLogger(run_id="test_truncate")
        tool_call = ToolCall(
            id="tc_large",
            name="write_file",
            arguments={"content": "x" * 1000},  # Very long content
        )
        
        with caplog.at_level(logging.INFO, logger="agent.trace"):
            tracer.log_tool_call(tool_call)
        
        # Should contain truncation indicator
        assert "..." in caplog.text or len(caplog.text) < 1100
    
    def test_grep_pattern_run_id(self, caplog):
        """Test that logs are grep-able by run_id."""
        tracer = TraceLogger(run_id="unique_run_12345")
        
        with caplog.at_level(logging.INFO, logger="agent.trace"):
            tracer.log_tool_call(ToolCall(id="t1", name="test1", arguments={}))
            tracer.log_tool_result(
                ToolResult(tool_call_id="t1", output="ok", success=True),
                elapsed_ms=1.0
            )
        
        # Both lines should have same run_id
        lines = [line for line in caplog.text.split("\n") if "unique_run_12345" in line]
        assert len(lines) == 2


class TestToolCallIdPropagation:
    """Tests that tool_call_id flows through the entire execution path."""
    
    def test_base_tool_sets_tool_call_id(self):
        """Test that BaseTool.call() sets tool_call_id on ToolResult.
        
        This catches the bug where tools return tool_call_id="" but BaseTool
        should overwrite it with the actual tool_call.id.
        """
        import asyncio
        from tool.bases import BaseTool
        
        class MockTool(BaseTool):
            @property
            def name(self):
                return "mock_tool"
            
            @property
            def description(self):
                return "A mock tool for testing"
            
            @property
            def parameters(self):
                return {"type": "object", "properties": {}}
            
            async def execute(self, arguments):
                # Intentionally return empty tool_call_id (the bug we're testing)
                return ToolResult(
                    tool_call_id="",  # Bug: empty id
                    output="success",
                    success=True,
                )
        
        tool = MockTool()
        tool_call = ToolCall(id="tc_expected_123", name="mock_tool", arguments={})
        
        result = asyncio.run(tool.call(tool_call))
        
        # BaseTool.call() should have fixed the tool_call_id
        assert result.tool_call_id == "tc_expected_123", \
            f"Expected tool_call_id='tc_expected_123', got '{result.tool_call_id}'"
    
    def test_tool_result_id_matches_tool_call_id(self):
        """Test that ToolResult.tool_call_id == ToolCall.id after execution."""
        import asyncio
        from tool.files import ListFiles
        from core.sandb import Workspace
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(tmp)
            tool = ListFiles(workspace=ws)
            
            tool_call = ToolCall(
                id="tc_list_files_999",
                name="list_files",
                arguments={"path": "."}
            )
            
            result = asyncio.run(tool.call(tool_call))
            
            assert result.tool_call_id == tool_call.id, \
                f"ToolResult.tool_call_id ({result.tool_call_id}) != ToolCall.id ({tool_call.id})"
