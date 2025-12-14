#!/bin/bash
# smoke_test.sh - Quick system health check
#
# This script verifies core functionality in < 30 seconds.
# Run this after changes to ensure nothing is broken.
#
# Exit codes:
#   0 = All checks passed
#   1 = One or more checks failed

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect Python command (Windows often has 'python' not 'python3')
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python not found. Install Python 3.10+"
    exit 1
fi

# Set PYTHONPATH for imports
export PYTHONPATH="$SCRIPT_DIR"

# Create secure temporary directory
TEMP_DIR=$(mktemp -d -t smoke_test.XXXXXX 2>/dev/null || mktemp -d)
trap "rm -rf '$TEMP_DIR'" EXIT

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

function check() {
    local name="$1"
    shift
    echo -n "Checking $name... "
    
    local log_file="$TEMP_DIR/output.log"
    if "$@" > "$log_file" 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Error output:"
        sed 's/^/    /' "$log_file" | head -20
        FAILED=$((FAILED + 1))
        return 1
    fi
}

function run_check() {
    eval "$@"
}

echo "=================================="
echo "Agent System Smoke Test"
echo "=================================="
echo ""

# Check 1: Python is available
check "Python availability" run_check "$PYTHON_CMD --version"

# Check 2: Core imports work
check "Core module imports" run_check "$PYTHON_CMD -c 'import core.types, core.state, core.sandb, core.patch, core.trace'"

# Check 3: Flow imports work
check "Flow module imports" run_check "$PYTHON_CMD -c 'import flow.loops, flow.judge, flow.plans'"

# Check 4: Tool imports work
check "Tool module imports" run_check "$PYTHON_CMD -c 'import tool.bases, tool.files, tool.index'"

# Check 5: Gate imports work
check "Gate module imports" run_check "$PYTHON_CMD -c 'import gate.bases, gate.mock'"

# Check 6: Workspace can be created
check "Workspace creation" run_check "$PYTHON_CMD -c '
from core.sandb import Workspace
ws = Workspace(\"./workspace\")
assert ws.root.exists(), \"Workspace directory not created\"
print(\"Workspace OK\")
'"

# Check 7: Workspace isolation works
check "Workspace isolation" run_check "$PYTHON_CMD -c '
from core.sandb import Workspace, WorkspaceError
ws = Workspace(\"./workspace\")
try:
    ws.resolve(\"../core/types.py\")
    raise Exception(\"Should have blocked access outside workspace\")
except WorkspaceError:
    print(\"Isolation OK\")
'"

# Check 8: Resource checking works
check "Resource monitoring" run_check "$PYTHON_CMD -c '
from core.sandb import Workspace
ws = Workspace(\"./workspace\")
stats = ws.get_resource_stats()
assert \"workspace_size_gb\" in stats, \"Resource stats missing\"
assert \"ram_free_percent\" in stats, \"RAM stats missing\"
print(f\"Resources: {stats[\"workspace_size_gb\"]:.2f}GB workspace, {stats[\"ram_free_percent\"]:.1f}% RAM free\")
'"

# Check 9: Judge can run
check "Judge functionality" run_check "$PYTHON_CMD -c '
from flow.judge import AgentJudge
from core.types import Step, StepType
judge = AgentJudge()
judgment = judge.check_progress([])
assert judgment.passed, \"Judge failed on empty steps\"
print(\"Judge OK\")
'"

# Check 10: Patch manager works
check "Patch manager" run_check "$PYTHON_CMD -c '
import os
from core.patch import PatchManager
temp_dir = os.environ.get(\"TEMP_DIR\", \"/tmp\")
pm = PatchManager(workspace_dir=f\"{temp_dir}/smoke_test_workspace\")
assert pm.patches_dir.exists(), \"Patches directory not created\"
stats = pm.get_stats()
assert \"total_patches\" in stats, \"Patch stats missing\"
print(\"Patch manager OK\")
'" env TEMP_DIR="$TEMP_DIR"

# Check 11: Tool registry works
check "Tool registry" run_check "$PYTHON_CMD -c '
from tool.index import create_default_registry
registry = create_default_registry()
tools = registry.get_tools()
assert len(tools) > 0, \"No tools registered\"
print(f\"Tool registry OK: {len(tools)} tools\")
'"

# Check 12: Mock gateway works
check "Mock gateway" run_check "$PYTHON_CMD -c '
import asyncio
from gate.mock import MockGateway
from core.types import Message, MessageRole

async def test():
    gateway = MockGateway()
    messages = [Message(role=MessageRole.USER, content=\"test\")]
    response = await gateway.complete(messages, tools=[])
    assert response.content, \"No response from mock gateway\"
    print(\"Mock gateway OK\")

asyncio.run(test())
'"

# Check 13: Run ID generation works
check "Run ID generation" run_check "$PYTHON_CMD -c '
from core.state import generate_run_id, generate_conversation_id
run_id = generate_run_id()
assert run_id.startswith(\"run_\"), \"Invalid run_id format\"
conv_id = generate_conversation_id()
assert conv_id.startswith(\"conv_\"), \"Invalid conversation_id format\"
print(f\"ID generation OK: {run_id}, {conv_id}\")
'"

# Check 14: Error taxonomy works
check "Error taxonomy" run_check "$PYTHON_CMD -c '
from core.patch import BlockedBy, create_tool_error, format_tool_error
error = create_tool_error(
    blocked_by=BlockedBy.WORKSPACE,
    error_code=\"TEST_ERROR\",
    message=\"Test error message\"
)
formatted = format_tool_error(error)
assert \"Blocked by: workspace\" in formatted, \"Error format incorrect\"
assert \"ERROR [TEST_ERROR]\" in formatted, \"Error format incorrect\"
print(\"Error taxonomy OK\")
'"

# Check 15: TraceLogger works
check "Traceability" run_check "$PYTHON_CMD -c '
from core.trace import TraceLogger
from core.types import ToolCall, ToolResult
tracer = TraceLogger(run_id=\"test_run_123\")
tc = ToolCall(id=\"tc_001\", name=\"test_tool\", arguments={\"foo\": \"bar\"})
tracer.log_tool_call(tc)
result = ToolResult(tool_call_id=\"tc_001\", output=\"success\", success=True)
tracer.log_tool_result(result, elapsed_ms=42.5, tool_name=\"test_tool\")
print(\"Traceability OK\")
'"

# Check 16: VectorGit ingest → query → cite workflow (Phase 1.0)
check "VectorGit workflow (ingest→query→cite)" run_check "$PYTHON_CMD -c '
import os
import shutil
from pathlib import Path
from tool.vectorgit import VectorGit

# Create test repo
test_dir = Path(\"$TEMP_DIR/vg_test\")
if test_dir.exists():
    shutil.rmtree(test_dir)
test_dir.mkdir(parents=True)

# Create sample file
(test_dir / \"sample.py\").write_text(\"def hello():\\n    return \\\"world\\\"\")

# Initialize VectorGit
vg = VectorGit(workspace_path=\"$TEMP_DIR/vg_workspace\", index_name=\"smoke_test\")

# Ingest
count = vg.ingest(str(test_dir))
assert count > 0, \"Ingest failed: no chunks created\"

# Query
results = vg.query(\"hello\", top_k=5)
assert len(results) > 0, \"Query failed: no results found\"

# Verify citation (chunk_id present)
assert \"chunk_id\" in results[0], \"Citation missing: no chunk_id in results\"
chunk_id = results[0][\"chunk_id\"]
assert chunk_id.startswith(\"chunk_\"), f\"Invalid chunk_id format: {chunk_id}\"

print(f\"VectorGit workflow OK: ingested {count} chunks, found {len(results)} results with citations\")
'"

# Summary
echo ""
echo "=================================="
echo "Summary"
echo "=================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
    echo ""
    echo -e "${RED}Some checks failed. See output above for details.${NC}"
    exit 1
else
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
fi
