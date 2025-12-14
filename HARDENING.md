# System Hardening Plan

## Overview

This document outlines the hardening tasks to improve system reliability, debuggability, and performance. Each goal includes:
- **Current State**: What already exists
- **Gap**: What's missing
- **Test Command**: How to verify it works
- **Success Criteria**: What "done" looks like

## Status Legend
- ✅ **COMPLETE**: Fully implemented and tested
- 🔧 **IN PROGRESS**: Partially implemented
- ⏸️ **BLOCKED**: Waiting on dependencies
- 📋 **PLANNED**: Not started

---

## Goal 1: Tool-Call Traceability 🔧

**Intent**: Every tool result must be traceable back to its exact tool call via logging and IDs.

### Current State
- ✅ `tool_call_id` exists in `ToolCall` and `ToolResult` types
- ✅ `run_id` exists in `ExecutionContext` for tracing execution runs
- ⚠️ Logging doesn't consistently link tool_call_id → ToolResult
- ⚠️ No grep-able format for tracing tool calls across logs

### Gap
- Need consistent log format: `[run_id={run_id}] [tool_call_id={id}] Tool: {name} → {status}`
- Need log entries at key points:
  1. Tool call initiated
  2. Tool executing
  3. Tool completed (success/failure)
  4. Tool result returned to model

### Test Commands
```bash
# 1. Run agent with tool calls and capture logs
python cli.py --mock > /tmp/agent_trace.log 2>&1 <<EOF
List files in the workspace
quit
EOF

# 2. Verify tool_call_id appears in logs
grep -E "tool_call_id=[a-z0-9-]+" /tmp/agent_trace.log

# 3. Verify we can trace from call → result
grep "tool_call_id=tc_123" /tmp/agent_trace.log | grep -E "(CALL|RESULT)"

# PASS: Should see matching tool_call_id in both CALL and RESULT lines
# FAIL: If tool_call_id missing or inconsistent
```

### Success Criteria
- [ ] Every tool call logs with format: `[run_id=X] [tool_call_id=Y] CALL Tool={name}`
- [ ] Every tool result logs with format: `[run_id=X] [tool_call_id=Y] RESULT success={bool}`
- [ ] Can grep logs by `tool_call_id` to see full lifecycle
- [ ] Can grep logs by `run_id` to see all tools in a run

### Implementation
1. Add structured logging to `flow/loops.py` in `_execute_tools()`
2. Add logging to `tool/bases.py` in `BaseTool.call()`
3. Add tests in `tests/flow/test_traceability.py`

---

## Goal 2: Workspace Anchoring ✅

**Intent**: Artifacts always land in the same place regardless of working directory.

### Current State
- ✅ `core/sandb.py` implements workspace isolation
- ✅ All file operations go through `Workspace.resolve()`
- ✅ Workspace root is absolute path (not relative to cwd)
- ✅ Tests verify workspace boundary enforcement

### Gap
- ⚠️ Some tools might use relative paths without workspace resolution
- ⚠️ Need verification that ALL file tools use workspace

### Test Commands
```bash
# 1. Run from different directories
cd /home/runner/work/agent/agent
python cli.py --mock <<EOF
Create a file called test.txt
quit
EOF
ls -la workspace/test.txt

cd /tmp
python /home/runner/work/agent/agent/cli.py --mock <<EOF
Create a file called test2.txt
quit
EOF
ls -la /home/runner/work/agent/agent/workspace/test2.txt

# PASS: Both files appear in same workspace/
# FAIL: Files in different locations
```

### Success Criteria
- [x] Workspace root is always absolute path
- [x] All file tools use `Workspace.resolve()`
- [ ] Test suite verifies workspace consistency across cwds
- [ ] Documentation clarifies workspace anchoring

### Implementation
1. Add test in `tests/core/test_sandb_anchoring.py` that changes cwd
2. Audit all tools in `tool/` to verify they use workspace
3. Document in README.md

---

## Goal 3: Smoke Runner Script 📋

**Intent**: Single command to verify system health after changes.

### Current State
- ⚠️ No unified smoke test script
- ✅ Test suite exists (`pytest tests/ -v`)
- ⚠️ Tests require dependencies installation
- ⚠️ No quick "is it broken?" check

### Gap
- Need `./smoke_test.sh` that runs in <30 seconds
- Should check:
  1. Python imports work
  2. Core modules load
  3. Basic agent loop works (with --mock)
  4. File tools can create/read in workspace
  5. Judge runs without errors

### Test Commands
```bash
# Run smoke test
./smoke_test.sh

# PASS: Exit code 0, "All checks passed" message
# FAIL: Non-zero exit, shows which check failed
```

### Success Criteria
- [ ] `smoke_test.sh` exists and is executable
- [ ] Runs in < 30 seconds
- [ ] Tests core functionality without external dependencies
- [ ] Provides clear pass/fail output
- [ ] Returns proper exit codes (0=pass, 1=fail)

### Implementation
1. Create `smoke_test.sh` with:
   - Import check (`python -c "import core, flow, tool, gate"`)
   - Mock agent run (1 turn with read_file tool)
   - Workspace write/read test
   - Judge check (ensure it runs)
2. Add to README.md usage section
3. Add to CI/CD pipeline

---

## Goal 4: Deterministic Chunk IDs 🔧

**Intent**: Chunk IDs must be stable across re-ingestion for reliable citations.

### Current State
- ✅ `store/chunks.py` uses hash-based chunk IDs
- ✅ Format: `chunk_{chunk_hash}` where hash is from content
- ⚠️ Hash includes file path, so renaming file changes chunk_id
- ⚠️ No test verifying chunk_id stability

### Gap
- Need to decide: should chunk_id change when file moves?
  - **Option A**: Hash content only (stable across moves)
  - **Option B**: Hash content + relative path (stable for same location)
- Need test proving re-ingestion gives same chunk_ids

### Test Commands
```bash
# 1. Ingest a test repo twice
python -c "
from store.chunks import ChunkManager
cm = ChunkManager(chunks_dir='/tmp/test_chunks_1')
cm.ingest_directory('tests/fixtures/sample_repo')
chunks1 = list(cm.chunks.keys())

cm2 = ChunkManager(chunks_dir='/tmp/test_chunks_2')
cm2.ingest_directory('tests/fixtures/sample_repo')
chunks2 = list(cm2.chunks.keys())

assert chunks1 == chunks2, 'Chunk IDs differ!'
print('PASS: Chunk IDs are deterministic')
"

# 2. Verify chunk_id format
python -c "
from store.chunks import ChunkManager
cm = ChunkManager()
# Check that IDs match pattern: chunk_{hex_hash}
import re
for chunk_id in cm.chunks.keys():
    assert re.match(r'^chunk_[a-f0-9]+$', chunk_id), f'Bad ID: {chunk_id}'
print('PASS: Chunk IDs match expected format')
"

# PASS: Both ingestions produce identical chunk_ids
# FAIL: chunk_ids differ between runs
```

### Success Criteria
- [ ] Chunk IDs are deterministic (same input → same IDs)
- [ ] Chunk ID format documented: `chunk_{hash}`
- [ ] Test verifies stability across re-ingestion
- [ ] Decision documented: what goes into hash

### Implementation
1. Review `store/chunks.py` hash generation
2. Add test in `tests/store/test_chunk_determinism.py`
3. Document chunk_id format in `store/chunks.py` docstring
4. Consider: exclude file path from hash for move-stability

---

## Goal 5: Patch Validation 🔧

**Intent**: Patches must be reviewable and predictable before apply.

### Current State
- ✅ `core/patch.py` implements patch protocol
- ✅ `validate_patch()` checks diff format and files exist
- ✅ Patches stored in `workspace/patches/{id}/`
- ⚠️ No test for malformed diffs
- ⚠️ Validation is advisory (warnings, not blocking)

### Gap
- Need stricter validation:
  1. Diff must apply cleanly (git apply --check)
  2. Target files must exist
  3. Diff must not be empty
  4. Plan and tests files required
- Need test suite for patch validation edge cases

### Test Commands
```bash
# 1. Create valid patch
python -c "
from core.patch import PatchManager
pm = PatchManager()
patch = pm.create_patch(
    title='test_patch',
    description='Test',
    target_files=['core/types.py'],
    plan_content='# Plan\nFix bug',
    diff_content='--- a/core/types.py\n+++ b/core/types.py\n@@ -1,1 +1,1 @@\n-old\n+new',
    tests_content='# Tests\npytest tests/',
)
valid, err = pm.validate_patch(patch.patch_id)
assert valid, f'Valid patch rejected: {err}'
print('PASS: Valid patch accepted')
"

# 2. Test invalid diff
python -c "
from core.patch import PatchManager
pm = PatchManager()
patch = pm.create_patch(
    title='bad_patch',
    description='Test',
    target_files=['core/types.py'],
    plan_content='# Plan',
    diff_content='not a real diff',
    tests_content='# Tests',
)
valid, err = pm.validate_patch(patch.patch_id)
assert not valid, 'Invalid diff accepted!'
print(f'PASS: Invalid diff rejected: {err}')
"

# PASS: Valid patches accepted, invalid rejected
# FAIL: Validation too strict or too lenient
```

### Success Criteria
- [ ] `validate_patch()` checks all required files
- [ ] Invalid diffs are rejected with clear error
- [ ] Empty diffs are rejected
- [ ] Test suite covers edge cases (empty, malformed, missing files)
- [ ] Validation errors include actionable guidance

### Implementation
1. Enhance `core/patch.py:validate_patch()`
2. Add test suite in `tests/core/test_patch_validation.py`
3. Document validation rules in patch.py

---

## Goal 6: Judge Enforcement 🔧

**Intent**: Discipline rules must be invoked during operations, not just advisory.

### Current State
- ✅ `flow/judge.py` implements judgment system
- ✅ Judge checks progress, loops, tool results, workflow discipline
- ⚠️ Judge is optional (can be disabled)
- ⚠️ Judge judgments are advisory (don't block execution)
- ⚠️ No guarantee judge runs on every tool execution

### Gap
- Need mandatory judge invocation after each tool execution
- Judge warnings should be surfaced to model in tool results
- Need test proving judge catches violations
- Consider: should judge block operations or just warn?

### Test Commands
```bash
# 1. Verify judge runs on tool execution
python -c "
from flow.loops import AgentLoop
from flow.judge import AgentJudge
from gate.mock import MockGateway
from tool.index import create_default_registry
from core.rules import get_default_engine
from core.state import AgentState, ConversationState, ExecutionContext

gateway = MockGateway()
tools = create_default_registry()
rules = get_default_engine()
loop = AgentLoop(gateway, tools, rules, enable_judge=True)

# Verify judge is enabled
assert loop.judge is not None, 'Judge not enabled!'
print('PASS: Judge is enabled')
"

# 2. Test judge catches workflow violations
python -c "
from flow.judge import AgentJudge
from core.types import Step, StepType, ToolCall, ToolResult

judge = AgentJudge()
steps = [
    Step(
        step_type=StepType.CALL_TOOL,
        content='',
        tool_calls=[ToolCall(id='1', name='write_file', arguments={'path': 'test.py'})]
    ),
    Step(
        step_type=StepType.OBSERVE,
        content='',
        tool_results=[ToolResult(tool_call_id='1', output='File written')]
    ),
]
judgment = judge.check_workflow_discipline(steps)
assert not judgment.passed, 'Judge should detect missing tests!'
print(f'PASS: Judge caught violation: {judgment.reason}')
"

# PASS: Judge runs and catches violations
# FAIL: Judge doesn't run or misses violations
```

### Success Criteria
- [ ] Judge runs after every tool execution (not optional)
- [ ] Judge judgments appear in tool results as warnings
- [ ] Test suite verifies judge catches common violations
- [ ] Judge mode configurable: advisory vs. blocking
- [ ] Documentation explains when judge blocks vs. warns

### Implementation
1. Make judge mandatory in `flow/loops.py`
2. Surface judge warnings in `ToolResult.output`
3. Add test suite in `tests/flow/test_judge_enforcement.py`
4. Add config option for judge strictness

---

## Goal 7: Error Shaping 🔧

**Intent**: All errors follow consistent taxonomy for better debuggability.

### Current State
- ✅ `core/patch.py` defines `BlockedBy` enum (rules, workspace, missing, runtime, permission)
- ✅ `ToolError` dataclass with structured fields
- ⚠️ Not all tools use `BlockedBy` taxonomy
- ⚠️ Error messages inconsistent across tools
- ⚠️ No standard format for error output

### Gap
- All tools should use `create_tool_error()` helper
- Error format should be: `ERROR [code]\nBlocked by: {category}\nMessage: {msg}`
- Need migration guide for existing tools
- Need test proving errors follow format

### Test Commands
```bash
# 1. Test that errors include BlockedBy
python -c "
from core.patch import BlockedBy, create_tool_error, format_tool_error

error = create_tool_error(
    blocked_by=BlockedBy.WORKSPACE,
    error_code='PATH_OUTSIDE_WORKSPACE',
    message='Cannot access /etc/passwd',
    context={'path': '/etc/passwd'}
)

formatted = format_tool_error(error)
assert 'Blocked by: workspace' in formatted
assert 'ERROR [PATH_OUTSIDE_WORKSPACE]' in formatted
print('PASS: Error formatting correct')
print(formatted)
"

# 2. Test real tool error
python -c "
import asyncio
from tool.files import WriteFileTool
from core.types import ToolCall

tool = WriteFileTool()
result = asyncio.run(tool.execute({
    'path': '/etc/passwd',
    'content': 'malicious',
}))

assert not result.success
assert 'blocked_by' in result.error or 'Blocked by' in result.error
print('PASS: Tool error includes BlockedBy')
print(result.error)
"

# PASS: All errors follow taxonomy
# FAIL: Errors missing BlockedBy or inconsistent format
```

### Success Criteria
- [ ] All tools import and use `create_tool_error()`
- [ ] All tool errors include `BlockedBy` category
- [ ] Error format standardized across all tools
- [ ] Test suite verifies error format compliance
- [ ] Migration guide for updating existing tools

### Implementation
1. Audit all tools in `tool/` directory
2. Update tools to use `create_tool_error()`
3. Add test in `tests/tools/test_error_format.py`
4. Document error taxonomy in `core/patch.py`

---

## Goal 8: Performance Guardrails 📋

**Intent**: Prevent runaway processes from crashing the system.

### Current State
- ✅ `core/sandb.py` implements resource monitoring
- ✅ `check_resources()` circuit breaker checks disk and RAM
- ✅ `ResourceLimitError` for resource exhaustion
- ⚠️ Not all expensive operations call `check_resources()`
- ⚠️ No timeout enforcement for long-running tools
- ⚠️ No CPU throttling for compute-heavy operations

### Gap
- Mandatory `check_resources()` before expensive operations
- Tool execution timeout (kill if > threshold)
- Process CPU limiting for pyexe and shell tools
- Memory tracking per tool execution
- Test that simulates resource exhaustion

### Test Commands
```bash
# 1. Test resource limit enforcement
python -c "
from core.sandb import Workspace, ResourceLimitError

# Create workspace with tiny limits
ws = Workspace(
    workspace_root='/tmp/test_ws',
    max_workspace_size_gb=0.001,  # 1MB
    min_free_ram_percent=99.0,    # Will definitely fail
)

try:
    ws.check_resources()
    print('FAIL: Should have raised ResourceLimitError')
except ResourceLimitError as e:
    print(f'PASS: Resource limit enforced: {e}')
"

# 2. Test that file tool checks resources
python -c "
import asyncio
from tool.files import WriteFileTool
from core.sandb import Workspace

tool = WriteFileTool()
# This should check resources before writing
result = asyncio.run(tool.execute({
    'path': 'test.txt',
    'content': 'x' * 1000000,  # 1MB
}))
print(f'Tool result: {result.success}')
"

# 3. Test tool timeout (simulate)
python -c "
import asyncio
import time
from core.types import ToolCall, ToolResult

async def slow_tool(args):
    '''Simulates a tool that takes too long'''
    await asyncio.sleep(60)  # 60 seconds
    return ToolResult(tool_call_id='test', output='Done')

async def test_timeout():
    try:
        result = await asyncio.wait_for(slow_tool({}), timeout=5.0)
        print('FAIL: Timeout not enforced')
    except asyncio.TimeoutError:
        print('PASS: Tool timed out after 5 seconds')

asyncio.run(test_timeout())
"

# PASS: Resource limits enforced, timeouts work
# FAIL: Can exhaust resources or tools hang forever
```

### Success Criteria
- [ ] All expensive tools call `check_resources()` before execution
- [ ] Tool execution has configurable timeout (default: 30s)
- [ ] Long-running processes are killable
- [ ] Memory usage tracked per tool
- [ ] Test suite includes resource exhaustion scenarios
- [ ] Documentation explains resource limits

### Implementation
1. Add timeout wrapper in `tool/bases.py:call()`
2. Audit expensive tools (pyexe, shell, fetch) for `check_resources()`
3. Add CPU/memory limits to shell command execution
4. Add test suite in `tests/core/test_resource_limits.py`
5. Document resource limits in README.md

---

## Implementation Order (Recommended)

### Phase 1: Quick Wins (1-2 days)
1. ✅ **Workspace Anchoring** - Already mostly done, just add tests
2. 📋 **Smoke Runner Script** - High value, low effort
3. 🔧 **Tool-Call Traceability** - Improve logging, easy to add

### Phase 2: Reliability (2-3 days)
4. 🔧 **Judge Enforcement** - Make judge mandatory
5. 🔧 **Error Shaping** - Migrate tools to BlockedBy taxonomy
6. 🔧 **Patch Validation** - Enhance validation logic

### Phase 3: Robustness (2-3 days)
7. 🔧 **Deterministic Chunk IDs** - Verify and test stability
8. 📋 **Performance Guardrails** - Add timeouts and limits

---

## Testing Strategy

### Unit Tests
- Each goal has dedicated test file in `tests/`
- Tests must be deterministic and fast (< 1s each)
- Tests use fixtures and mocks where appropriate

### Integration Tests
- Smoke test covers end-to-end flow
- Each hardening goal has integration test
- Tests run in CI/CD pipeline

### Regression Tests
- Add tests for any bugs found during hardening
- Ensure fixes don't regress in future

---

## Success Metrics

### Before Hardening
- ⚠️ No single-command health check
- ⚠️ Tool errors inconsistent
- ⚠️ Judge is optional
- ⚠️ Unclear if chunk IDs are stable
- ⚠️ Some operations don't check resources

### After Hardening
- ✅ `./smoke_test.sh` verifies system health
- ✅ All errors follow BlockedBy taxonomy
- ✅ Judge runs on every tool execution
- ✅ Chunk IDs proven deterministic
- ✅ Resource limits enforced consistently
- ✅ Every tool call is traceable via logs

---

## Future Considerations (Post-Hardening)

After hardening, these become the foundation for:
- **Phase 0.8**: VectorGit v0 (durable code memory)
- **Phase 0.9**: VectorGit v1 + Queue v0 (embeddings + continuation)

The hardening work ensures:
- Tool calls are traceable (needed for debugging vector search)
- Errors are shaped (needed for queue retry logic)
- Resources are guarded (needed for long-running ingestion)
- Judge enforces discipline (needed for autonomous operation)

---

## Notes

- This plan is **iterative** - start with quick wins to build momentum
- Each goal is **independently testable** - no need to complete all at once
- Tests are **the definition of done** - if tests pass, goal is complete
- Focus on **small, verifiable changes** - easier to review and debug
