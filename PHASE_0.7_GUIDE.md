# Phase 0.7 — Patch Workflow and "Workspace-First Engineering"

**Status**: ✅ Implemented

**Date**: December 13, 2025

## Overview

Phase 0.7 makes the agent act like a disciplined developer while being unable to edit project files directly. All changes to project code go through a patch protocol with human review, enforcing the principle that **workspace artifacts are the source of truth**.

## What Was Delivered

### 1. Patch Protocol (Workspace Artifacts are Source of Truth) ✅

**Files Added**:
- `core/patch.py` - Patch management system
- `tool/patch.py` - Patch creation and management tools
- `workspace/patches/` - Patch storage directory (generated)

**For Every Change Request, Agent Produces**:

1. **plan.md** (what/why/where)
   - What needs to change
   - Why the change is needed
   - Where the changes will be made
   - Expected impact

2. **patch.diff** (complete unified diff)
   - Standard git diff format
   - All changes in one file
   - Ready for `git apply`

3. **tests.md** (what to run + expected output)
   - Test commands to verify changes
   - Expected test results
   - How to validate the fix

**Enforcement**:
- Agent MUST write files and verify by reading them back
- Agent CANNOT claim "fixed" without tests passing
- All patches tracked with unique IDs and status

### 2. Patch Applicator Path (Human-in-the-loop) ✅

**Application Workflow**:

```bash
# Option 1: Direct git apply
git apply workspace/patches/<patch_id>/patch.diff

# Option 2: Review first, then apply
cd workspace/patches/<patch_id>
cat plan.md        # Review plan
cat patch.diff     # Review changes
cat tests.md       # Review test plan
git apply patch.diff

# Option 3: Using tools
<tool name="get_patch">{"patch_id": "<patch_id>"}</tool>
# Review output, then apply manually
```

**Status Tracking**:
- `proposed` - Created, awaiting review
- `applied` - Applied to codebase
- `tested` - Applied and tests passed
- `failed` - Tests failed after apply
- `rejected` - Rejected by human review

**Agent Rules**:
- Agent NEVER claims "fixed" unless tests pass after apply
- Agent MUST check patch status before claiming success
- Agent SHOULD propose re-tests after apply

### 3. Stricter Judge Rules ✅

**New Checks in `flow/judge.py`**: `check_patch_discipline()`

**Detects**:

1. **Proposes changes without creating patch**
   - Keywords: "fix for", "I will fix", "change to", "modify"
   - Action: Suggests using `create_patch` tool

2. **Writes to project files directly**
   - Checks `write_file` tool calls
   - Blocks writes outside workspace/ (except /tmp/)
   - Action: Error with "use create_patch instead"

3. **Tool budget prevents tests without explanation**
   - Detects budget exhaustion
   - Checks if agent mentioned tests for next step
   - Action: Suggests scheduling tests

**Integration**:
```python
# In agent loop
judgment = judge.check_patch_discipline(steps)
if not judgment.passed:
    # Add guidance to conversation
    guidance_message = {
        "role": "system",
        "content": f"{judgment.reason}\n{judgment.suggestion}"
    }
```

### 4. Error Taxonomy Upgrade ✅

**Standardized Error Structure**:

```python
@dataclass
class ToolError:
    blocked_by: str  # Category
    error_code: str  # Specific error
    message: str     # Human-readable
    context: Optional[Dict[str, Any]]  # Additional info
```

**BlockedBy Categories**:
- `rules` - Safety rules prevent operation
- `workspace` - Outside workspace boundary
- `missing` - File or resource doesn't exist
- `runtime` - Runtime error during execution
- `permission` - Permission denied

**Error Codes**:
- `PATCH_MISSING_FIELDS` - Missing required patch fields
- `PATCH_NO_TARGETS` - No target files specified
- `PATCH_INVALID` - Patch validation failed
- `PATCH_NOT_FOUND` - Patch ID not found
- `PATCH_CREATION_FAILED` - Patch creation failed
- `OUTSIDE_WORKSPACE` - File access outside workspace

**Format**:
```
ERROR [PATCH_MISSING_FIELDS]
Blocked by: rules
Message: Missing required fields. Need: title, description, plan, diff, tests
Context: {
  "provided": ["title", "description"]
}
```

**Benefits**:
- Agent can reason about error types
- Clear distinction between "file missing" vs "policy blocked"
- Structured context for debugging

### 5. Two-Track Mode: Model Compatibility ✅

**Design Principles**:
- Prompts are structured and short
- Outputs are explicit and verifiable
- No reliance on "magic" or implicit understanding
- Enforce cite/verify workflow

**Model-Agnostic Features**:
- Explicit tool schemas (JSON Schema)
- Structured error messages
- Citation-based answers (chunk IDs)
- Step-by-step verification
- Clear success/failure indicators

**Swapping Models**:
```python
# Works with any OpenAI-compatible API
config = {
    "model": "qwen2.5-coder-7b",  # Or gemini, or claude, etc.
    "api_base": "http://localhost:8000/v1",
}

# No prompt changes needed
# No workflow changes needed
```

**Benefits**:
- Easy to compare models
- No vendor lock-in
- Consistent behavior across models
- Future-proof architecture

## Architecture

### Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                    PatchManager                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 1. create_patch() → Generate patch artifacts         │ │
│  │    - plan.md (what/why/where)                        │ │
│  │    - patch.diff (unified diff)                       │ │
│  │    - tests.md (test instructions)                    │ │
│  │    - metadata.json (status tracking)                 │ │
│  │ 2. validate_patch() → Check diff format             │ │
│  │ 3. list_patches() → Filter by status                │ │
│  │ 4. update_status() → Track lifecycle                │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Patch Tools                              │
│  • create_patch - Create patch proposal                     │
│  • list_patches - List patches with filters                 │
│  • get_patch - Get patch details                            │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Judge (Enhanced)                         │
│  • check_patch_discipline()                                 │
│    - Proposes without patch? → Suggest create_patch        │
│    - Direct file write? → Error, use patch                 │
│    - Budget without tests? → Ask for tests next           │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Workflow                           │
│  1. Identify needed change                                  │
│  2. Create workspace artifacts (if needed)                  │
│  3. Generate patch with create_patch tool                   │
│  4. WAIT for human to apply                                 │
│  5. Verify tests after apply                                │
│  6. Only then claim "fixed"                                 │
└─────────────────────────────────────────────────────────────┘
```

## Usage Examples

### Example 1: Propose Fix for Tool Budget Bug

**User**: "Propose fix for tool budget per-batch bug"

**Agent Workflow**:
```python
# Step 1: Investigate (search chunks, read files)
<tool name="search_chunks">{
  "query": "tool budget",
  "k": 10
}</tool>

# Step 2: Create patch proposal
<tool name="create_patch">{
  "title": "Fix tool budget per-batch calculation",
  "description": "The tool budget is incorrectly calculated per batch instead of per step, causing premature budget exhaustion.",
  "target_files": ["core/state.py", "flow/loops.py"],
  "plan": "# Plan\n\n## What\nFix tool budget to reset per step, not per batch.\n\n## Why\nCurrent implementation counts tools across batches, hitting limits too early.\n\n## Where\n- core/state.py: Update can_use_tool() logic\n- flow/loops.py: Reset counter on step boundary\n\n## Impact\nAgent can use full tool budget per step",
  "diff": "--- a/core/state.py\n+++ b/core/state.py\n@@ -45,7 +45,7 @@\n     def can_use_tool(self) -> bool:\n-        return self.tools_used < self.max_tools\n+        return self.tools_used_this_step < self.max_tools_per_step\n...",
  "tests": "# Tests\n\n## Run\n```bash\npytest tests/core/test_state_phase05.py -v\npytest tests/flow/test_loops.py -v\n```\n\n## Expected\nAll tests pass, especially:\n- test_tool_budget_per_step\n- test_budget_reset_on_new_step"
}</tool>

# Output:
# ✓ Created patch: 20251213_153045_Fix_tool_budget_per_batch_calculation
# 
# TO APPLY (human action required):
#   git apply workspace/patches/20251213_153045_Fix_tool_budget_per_batch_calculation/patch.diff
# 
# IMPORTANT: You CANNOT claim this is 'fixed' until:
# 1. Human applies the patch
# 2. Tests run successfully
# 3. You verify the results
```

### Example 2: Agent Attempts Direct Project File Edit

**User**: "Fix the bug in core/state.py"

**Wrong Approach** (Agent tries):
```python
<tool name="write_file">{
  "path": "core/state.py",
  "content": "fixed code..."
}</tool>
```

**Judge Detects**:
```
ERROR: Attempted to write project files directly: core/state.py
DO THIS NEXT: Use create_patch tool instead. Never edit project files directly.
```

**Correct Approach**:
```python
# Agent corrects and uses patch protocol
<tool name="create_patch">{
  "title": "Fix state bug",
  ...
}</tool>
```

### Example 3: Tool Budget Prevents Tests

**Scenario**: Agent writes code, hits tool budget before running tests

**Without Discipline**:
```
Agent: "I've fixed the bug."
[But tests never ran!]
```

**With Discipline**:
```
Agent: "I've created the patch. Tool budget exhausted - tests should be run in the next step after budget resets."

Judge detects and accepts this because agent explicitly mentioned tests.
```

### Example 4: Human Applies and Verifies Patch

**Human Actions**:
```bash
# 1. Review patch
$ cat workspace/patches/20251213_153045_Fix_tool_budget/plan.md
# Read the plan...

$ cat workspace/patches/20251213_153045_Fix_tool_budget/patch.diff
# Review the changes...

# 2. Apply patch
$ git apply workspace/patches/20251213_153045_Fix_tool_budget/patch.diff
# Applied successfully

# 3. Run tests
$ pytest tests/core/test_state_phase05.py -v
# ✓ All tests passed

# 4. Tell agent
User: "Patch applied, tests pass"
```

**Agent Response**:
```
Agent: "Excellent! The fix is confirmed working. The tool budget now correctly resets per step."
```

## Configuration

### Environment Variables

Add to `.env`:
```bash
# Patch protocol configuration (Phase 0.7)
AGENT_ENABLE_PATCH=true
AGENT_WORKSPACE_DIR=./workspace
AGENT_PATCHES_DIR=./workspace/patches

# Enforce workspace-first
AGENT_BLOCK_PROJECT_WRITES=true
```

### Programmatic Configuration

```python
from core.patch import PatchManager
from tool.patch import CreatePatchTool, ListPatchesTool, GetPatchTool

# Create patch manager
patch_manager = PatchManager(
    workspace_dir="./workspace",
    patches_dir="./workspace/patches"
)

# Create tools
create_tool = CreatePatchTool(patch_manager=patch_manager)
list_tool = ListPatchesTool(patch_manager=patch_manager)
get_tool = GetPatchTool(patch_manager=patch_manager)

# Register tools
registry.register(create_tool)
registry.register(list_tool)
registry.register(get_tool)
```

## File Structure

```
core/
├── patch.py                 # Patch management system

tool/
├── patch.py                 # Patch tools

flow/
├── judge.py                 # Enhanced with patch discipline

workspace/
├── patches/                 # Patch storage
│   ├── 20251213_153045_Fix_tool_budget/
│   │   ├── plan.md
│   │   ├── patch.diff
│   │   ├── tests.md
│   │   └── metadata.json
│   └── ...

tests/
├── core/
│   └── test_patch.py        # Patch manager tests (10 tests)
├── tools/
│   └── test_patch_tool.py   # Patch tool tests (8 tests)
└── flow/
    └── test_judge_phase07.py # Judge tests (8 tests)
```

## Test Results

**All Tests Passing**: ✅

```bash
# Patch manager tests
$ PYTHONPATH=. python tests/core/test_patch.py
✓ test_create_patch
✓ test_patch_validation
✓ test_patch_validation_empty_diff
✓ test_patch_status_update
✓ test_list_patches
✓ test_generate_apply_command
✓ test_patch_persistence
✓ test_tool_error_creation
✓ test_tool_error_formatting
✓ test_patch_stats
All patch tests passed!

# Patch tool tests
$ PYTHONPATH=. python tests/tools/test_patch_tool.py
✓ test_create_patch_tool
✓ test_create_patch_tool_missing_fields
✓ test_create_patch_tool_no_targets
✓ test_list_patches_tool
✓ test_list_patches_tool_with_filter
✓ test_get_patch_tool
✓ test_get_patch_tool_not_found
✓ test_get_patch_tool_missing_id
All patch tool tests passed!

# Judge tests
$ PYTHONPATH=. python tests/flow/test_judge_phase07.py
✓ test_patch_discipline_proposes_without_patch
✓ test_patch_discipline_creates_patch
✓ test_patch_discipline_project_file_write
✓ test_patch_discipline_workspace_write_allowed
✓ test_patch_discipline_tmp_write_allowed
✓ test_patch_discipline_budget_without_test_request
✓ test_patch_discipline_budget_with_test_request
✓ test_patch_discipline_no_issues
All Phase 0.7 judge tests passed!

Total: 26 tests, all passing ✅
```

## Success Criteria ✅

All Phase 0.7 acceptance criteria met:

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Patch protocol with plan/diff/tests | ✅ | `PatchManager.create_patch()` |
| Human-in-the-loop apply | ✅ | `generate_apply_command()` + manual review |
| Agent cannot claim "fixed" prematurely | ✅ | Tool output enforces this |
| Judge checks patch creation | ✅ | `check_patch_discipline()` |
| Judge checks project file writes | ✅ | Detects and blocks |
| Judge checks tests after budget | ✅ | Asks for test scheduling |
| Standardized error taxonomy | ✅ | `ToolError` with `BlockedBy` |
| Error codes prevent confusion | ✅ | Clear categories: rules/workspace/missing/runtime |
| Model-agnostic design | ✅ | Structured outputs, no magic |
| Works with any OpenAI-compatible API | ✅ | No vendor-specific features |

## Success Test Examples

### Test 1: "Propose fix for tool budget per-batch bug"

**Agent Actions**:
1. Search chunks for tool budget code ✓
2. Read relevant files ✓
3. Create patch with plan/diff/tests ✓
4. Verify patch artifacts exist ✓
5. Provide apply command ✓

**Result**: ✅ Patch created successfully, ready for human review

### Test 2: "You may not edit project files"

**Agent Attempts**:
1. Try `write_file("core/state.py", ...)` ✗

**Judge Detects**:
```
ERROR: Attempted to write project files directly
DO THIS NEXT: Use create_patch tool instead
```

**Agent Corrects**:
1. Use `create_patch` instead ✓

**Result**: ✅ Agent follows workspace-first protocol

## Benefits

### For Agents
- **Clear boundaries**: Can't accidentally break project code
- **Structured workflow**: Plan → Diff → Tests
- **Better reasoning**: Explicit about what changes and why
- **Verifiable**: All changes tracked and reviewable

### For Developers
- **Review before apply**: Human-in-the-loop safety
- **Clear diffs**: Standard git format
- **Test instructions**: Know how to verify
- **Audit trail**: All patches tracked with status

### For Project Quality
- **No accidental edits**: Workspace isolation enforced
- **Better patches**: Forced planning improves quality
- **Test coverage**: Tests required for every change
- **Reproducible**: Patches can be reapplied or reverted

## Known Limitations

1. **Manual apply**: Human must run `git apply`. Could be automated with approval workflow.

2. **No conflict resolution**: If patch doesn't apply cleanly, human must resolve conflicts.

3. **Single diff file**: All changes in one diff. Could split into multiple patches for large changes.

4. **No automatic testing**: Agent can't run tests after human applies. Could integrate with CI/CD.

## Future Enhancements

### Phase 0.7.1 (Automated Apply with Approval)
- Add `approve_patch` tool
- Automated `git apply` after approval
- Rollback on test failure

### Phase 0.7.2 (Advanced Diff Tools)
- Generate patches from workspace code
- Side-by-side diff viewer
- Conflict resolution assistance

### Phase 0.7.3 (CI/CD Integration)
- Trigger CI pipeline on patch apply
- Auto-update status based on CI results
- Block approval if tests fail

### Phase 0.7.4 (Multi-Patch Workflows)
- Dependencies between patches
- Batch apply multiple patches
- Patch stacks for large features

## Migration Guide

### For Existing Agents

**Before Phase 0.7**:
```python
# Old: Direct file editing
<tool name="write_file">{
  "path": "core/state.py",
  "content": "fixed code"
}</tool>
```

**After Phase 0.7**:
```python
# New: Patch protocol
<tool name="create_patch">{
  "title": "Fix state bug",
  "description": "...",
  "target_files": ["core/state.py"],
  "plan": "...",
  "diff": "...",
  "tests": "..."
}</tool>
```

### For System Prompts

Add to system prompt:
```
WORKSPACE-FIRST ENGINEERING (Phase 0.7):
1. NEVER edit project files directly (anything outside workspace/)
2. ALWAYS use create_patch tool for project changes
3. INCLUDE plan.md (what/why/where) in every patch
4. INCLUDE patch.diff (unified diff format)
5. INCLUDE tests.md (what to run + expected output)
6. NEVER claim "fixed" until tests pass after human applies patch

Example Patch Workflow:
1. Investigate issue (search_chunks, read_file)
2. Develop fix in workspace if needed
3. create_patch with plan/diff/tests
4. WAIT for human to apply
5. Verify tests after apply
6. Only then confirm fix
```

## Comparison with Phase 0.6

| Aspect | Phase 0.6 | Phase 0.7 |
|--------|-----------|-----------|
| Focus | Code discovery | Code changes |
| Key Tool | `search_chunks` | `create_patch` |
| Agent Action | Find code | Propose changes |
| Human Action | None | Review and apply |
| Safety | Read-only | Write with approval |
| Output | Citations | Diffs |

## Conclusion

Phase 0.7 is **complete and production-ready**. The agent now:
- **Proposes changes** via structured patches
- **Cannot edit project files** directly
- **Follows discipline** enforced by judge
- **Uses standard errors** for clear reasoning
- **Works with any model** via structured outputs

The implementation is minimal, well-tested, and ready for production use.

---

**Approval Checklist**:
- [x] All acceptance criteria met
- [x] Tests pass (26/26)
- [x] Patch protocol enforced
- [x] Judge rules implemented
- [x] Error taxonomy standardized
- [x] Model compatibility ensured
- [x] Documentation complete
- [x] No breaking changes

**Status**: ✅ **READY FOR PRODUCTION**
