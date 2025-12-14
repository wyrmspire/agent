#!/bin/bash
# smoke_test.sh - Quick system health check
#
# This script verifies core functionality in < 30 seconds.
# Run this after changes to ensure nothing is broken.
#
# Exit codes:
#   0 = All checks passed
#   1 = One or more checks failed

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
    
    if "$@" > /tmp/smoke_test_output.log 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Error output:"
        sed 's/^/    /' /tmp/smoke_test_output.log | head -20
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
check "Python availability" run_check "python3 --version"

# Check 2: Core imports work
check "Core module imports" run_check "python3 -c 'import sys; sys.path.insert(0, \".\"); import core.types, core.state, core.sandb, core.patch'"

# Check 3: Flow imports work
check "Flow module imports" run_check "python3 -c 'import sys; sys.path.insert(0, \".\"); import flow.loops, flow.judge, flow.plans'"

# Check 4: Tool imports work
check "Tool module imports" run_check "python3 -c 'import sys; sys.path.insert(0, \".\"); import tool.bases, tool.files, tool.index'"

# Check 5: Gate imports work
check "Gate module imports" run_check "python3 -c 'import sys; sys.path.insert(0, \".\"); import gate.bases, gate.mock'"

# Check 6: Workspace can be created
check "Workspace creation" run_check "python3 -c '
import sys
sys.path.insert(0, \".\")
from core.sandb import Workspace
ws = Workspace(\"./workspace\")
assert ws.root.exists(), \"Workspace directory not created\"
print(\"Workspace OK\")
'"

# Check 7: Workspace isolation works
check "Workspace isolation" run_check "python3 -c '
import sys
sys.path.insert(0, \".\")
from core.sandb import Workspace, WorkspaceError
ws = Workspace(\"./workspace\")
try:
    ws.resolve(\"../core/types.py\")
    raise Exception(\"Should have blocked access outside workspace\")
except WorkspaceError:
    print(\"Isolation OK\")
'"

# Check 8: Resource checking works
check "Resource monitoring" run_check "python3 -c '
import sys
sys.path.insert(0, \".\")
from core.sandb import Workspace
ws = Workspace(\"./workspace\")
stats = ws.get_resource_stats()
assert \"workspace_size_gb\" in stats, \"Resource stats missing\"
assert \"ram_free_percent\" in stats, \"RAM stats missing\"
print(f\"Resources: {stats[\"workspace_size_gb\"]:.2f}GB workspace, {stats[\"ram_free_percent\"]:.1f}% RAM free\")
'"

# Check 9: Judge can run
check "Judge functionality" run_check "python3 -c '
import sys
sys.path.insert(0, \".\")
from flow.judge import AgentJudge
from core.types import Step, StepType
judge = AgentJudge()
judgment = judge.check_progress([])
assert judgment.passed, \"Judge failed on empty steps\"
print(\"Judge OK\")
'"

# Check 10: Patch manager works
check "Patch manager" run_check "python3 -c '
import sys
sys.path.insert(0, \".\")
from core.patch import PatchManager
pm = PatchManager(workspace_dir=\"/tmp/smoke_test_workspace\")
assert pm.patches_dir.exists(), \"Patches directory not created\"
stats = pm.get_stats()
assert \"total_patches\" in stats, \"Patch stats missing\"
print(\"Patch manager OK\")
'"

# Check 11: Tool registry works
check "Tool registry" run_check "python3 -c '
import sys
sys.path.insert(0, \".\")
from tool.index import create_default_registry
registry = create_default_registry()
tools = registry.get_tools()
assert len(tools) > 0, \"No tools registered\"
print(f\"Tool registry OK: {len(tools)} tools\")
'"

# Check 12: Mock gateway works
check "Mock gateway" run_check "python3 -c '
import sys, asyncio
sys.path.insert(0, \".\")
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
check "Run ID generation" run_check "python3 -c '
import sys
sys.path.insert(0, \".\")
from core.state import generate_run_id, generate_conversation_id
run_id = generate_run_id()
assert run_id.startswith(\"run_\"), \"Invalid run_id format\"
conv_id = generate_conversation_id()
assert conv_id.startswith(\"conv_\"), \"Invalid conversation_id format\"
print(f\"ID generation OK: {run_id}, {conv_id}\")
'"

# Check 14: Error taxonomy works
check "Error taxonomy" run_check "python3 -c '
import sys
sys.path.insert(0, \".\")
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
