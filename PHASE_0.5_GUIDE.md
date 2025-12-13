# Phase 0.5 — Tool-Disciplined and Measurable Agent

**Status**: ✅ Implemented

## Overview

Phase 0.5 addresses the core problem of agent "thrashing" by enforcing structured workflows and making progress measurable. The agent now follows a disciplined "plan → tools → verify → summarize" approach.

## What Was Added

### 1. Tool Budget + Tool-First Policy

**Location**: `flow/plans.py`, `core/state.py`, `flow/loops.py`

**What it does**:
- Enforces a maximum number of tool calls per step (default: 10)
- Prevents the agent from spamming tool calls indefinitely
- System prompt now includes explicit "tool-first workflow" guidance

**How it works**:
```python
# ExecutionContext now tracks tool usage
context.max_tools_per_step = 10
context.tools_used_this_step = 0

# Before each tool call
if not context.can_use_tool():
    # Stop and summarize progress
    
# After each tool call
context.record_tool_use()

# Reset counter on new step
context.add_step(step)  # Resets tools_used_this_step to 0
```

**System Prompt Enhancement**:
The agent now receives explicit instructions:
```
TOOL-FIRST WORKFLOW (Phase 0.5 - Required):
1. LIST/READ → Explore before acting
2. WRITE → Make targeted changes  
3. TEST → Verify your changes work
4. SUMMARIZE → Report results

ANTI-PATTERNS TO AVOID:
❌ Writing code without running tests
❌ Calling shell repeatedly when errors occur
❌ Making changes without reading existing code first
```

### 2. Judge Upgrades — Actionable Guidance

**Location**: `flow/judge.py`

**What it does**:
- Detects when agent writes code without running tests
- Detects when agent calls shell repeatedly with errors
- Emits specific "DO THIS NEXT" guidance

**New Method**: `check_workflow_discipline(steps: List[Step]) -> Judgment`

**Examples**:
```python
# Detects code without tests
judgment = judge.check_workflow_discipline(steps)
# Returns: Judgment(
#   passed=False,
#   reason="Code was written but tests were not run",
#   suggestion="DO THIS NEXT: Run tests to verify your code changes work correctly."
# )

# Detects repeated errors
judgment = judge.check_workflow_discipline(steps)
# Returns: Judgment(
#   passed=False,
#   reason="Calling shell repeatedly without reading errors",
#   suggestion="DO THIS NEXT: Read and analyze the error: ..."
# )
```

**Integration**: The judge guidance is automatically added to the conversation as system messages to guide the agent's next action.

### 3. Eval Harness v0

**Location**: `eval_harness.py`

**What it does**:
- Runs a fixed set of test tasks
- Measures: success/fail, tool calls, time, whether tests ran
- Generates JSON reports for regression tracking

**Usage**:
```bash
# Run all tasks
python eval_harness.py

# Run specific task
python eval_harness.py --task simple_file_creation

# Save to custom file
python eval_harness.py --output my_results.json

# Verbose logging
python eval_harness.py --verbose
```

**Output**:
```
============================================================
EVALUATION HARNESS v0 - RESULTS
============================================================

Total Tasks: 4
Successful: 3
Success Rate: 75.0%
Total Tool Calls: 42
Total Time: 12.34s
Tasks with Tests Run: 2

------------------------------------------------------------
TASK DETAILS
------------------------------------------------------------

✓ simple_file_creation
  Tools: 2, Time: 1.23s, Tests: No

✓ create_python_function
  Tools: 15, Time: 5.67s, Tests: Yes
```

**Built-in Tasks**:
1. `simple_file_creation` - Create a basic text file
2. `list_and_read` - List and read files
3. `create_python_function` - Create Python code and test it
4. `fix_syntax_error` - Fix a syntax error

**Extending**: Add new tasks by modifying `_define_tasks()` in `EvalHarness` class.

## Changes to Core Components

### `core/state.py`
- Added `max_tools_per_step: int` to `ExecutionContext`
- Added `tools_used_this_step: int` to track current step's tool usage
- Added `can_use_tool()` method to check budget
- Added `record_tool_use()` method to increment counter
- Modified `add_step()` to reset tool counter

### `flow/plans.py`
- Added `enable_tool_discipline: bool` parameter to `create_system_prompt()`
- Enhanced system prompt with tool-first workflow rules
- Added anti-patterns section
- Added tool budget notice

### `flow/judge.py`
- Added `check_workflow_discipline()` method
- Tracks when code is written (`last_write_step`)
- Tracks repeated shell errors (`shell_error_count`)
- Returns actionable "DO THIS NEXT" suggestions

### `flow/loops.py`
- Integrated `AgentJudge` (optional, enabled by default)
- Checks tool budget before execution
- Adds judge guidance to conversation as system messages
- Records tool use for budget tracking
- Checks tool result quality

## Testing

All new functionality is thoroughly tested:

**Test Files**:
- `tests/core/test_state_phase05.py` - Tool budget enforcement
- `tests/flow/test_judge_phase05.py` - Judge workflow discipline checks

**Run Tests**:
```bash
# Run Phase 0.5 tests
python -m pytest tests/flow/test_judge_phase05.py tests/core/test_state_phase05.py -v

# Run all flow tests
python -m pytest tests/flow/ -v
```

**Test Coverage**:
- ✅ Tool budget initialization
- ✅ Tool budget enforcement at limit
- ✅ Tool counter reset on new step
- ✅ Judge detects code without tests
- ✅ Judge detects repeated shell errors
- ✅ Judge passes when workflow is correct
- ✅ Existing judge functionality preserved

## Usage Example

```python
from flow.loops import AgentLoop
from core.state import AgentState, ConversationState, ExecutionContext, generate_run_id

# Create execution context with tool budget
execution = ExecutionContext(
    run_id=generate_run_id(),
    conversation_id="test",
    max_tools_per_step=5,  # Limit to 5 tools per step
    max_steps=20,
)

# Create agent loop with judge enabled
loop = AgentLoop(
    gateway=gateway,
    tools=tools,
    rule_engine=rule_engine,
    max_steps=20,
    enable_judge=True,  # Enable Phase 0.5 judge guidance
)

# Run agent - will now follow tool-first workflow
result = await loop.run(state, "Create a Python function and test it")
```

## Configuration Options

### Tool Budget
```python
# In ExecutionContext
max_tools_per_step = 10  # Default: 10 tools per step
```

### Judge
```python
# In AgentLoop
enable_judge = True  # Default: True, set to False to disable
```

### System Prompt
```python
# In create_system_prompt()
enable_tool_discipline = True  # Default: True, set to False for old behavior
```

## Benefits

1. **Prevents Thrashing**: Tool budget prevents infinite loops of tool calls
2. **Enforces Best Practices**: Agent must follow list→read→write→test workflow
3. **Actionable Feedback**: Judge provides specific "do this next" guidance
4. **Measurable Quality**: Eval harness makes agent behavior quantifiable
5. **Regression Detection**: JSON reports allow tracking improvements/regressions

## Acceptance Criteria

✅ **Tool budget enforced**: Agent cannot exceed max_tools_per_step  
✅ **Judge provides guidance**: Detects anti-patterns and suggests corrections  
✅ **Eval harness works**: Runs tasks and reports metrics  
✅ **Tests pass**: All new tests pass, existing tests preserved  
✅ **Agent runs tests after writing**: Judge enforces test-after-write discipline

## Future Improvements

Potential enhancements for Phase 0.5+:
- [ ] Dynamic tool budget based on task complexity
- [ ] More sophisticated loop detection (semantic similarity)
- [ ] Integration with real agent execution in eval harness
- [ ] More benchmark tasks in eval harness
- [ ] Judge learning from successful vs failed executions
- [ ] Tool usage analytics and reporting

## Migration Guide

### For Existing Code

**No breaking changes!** Phase 0.5 enhancements are additive.

**Default behavior**: Tool discipline is enabled by default.

**To opt out**:
```python
# Disable judge
loop = AgentLoop(..., enable_judge=False)

# Disable tool discipline in prompt
prompt = create_system_prompt(tools, enable_tool_discipline=False)

# Increase tool budget
context = ExecutionContext(..., max_tools_per_step=100)
```

### For New Projects

Simply use the default settings - Phase 0.5 enhancements are active out of the box.

## Related Files

- `core/state.py` - ExecutionContext with tool budget
- `flow/plans.py` - System prompt with tool-first policy
- `flow/judge.py` - Judge with workflow discipline checks
- `flow/loops.py` - AgentLoop with judge integration
- `eval_harness.py` - Evaluation harness v0
- `tests/core/test_state_phase05.py` - Tool budget tests
- `tests/flow/test_judge_phase05.py` - Judge workflow tests

## See Also

- [Phase 0.2 Demo](PHASE_0.2_DEMO.md) - Basic agent functionality
- [Phase 0.3/0.4 Guide](PHASE_0.3_0.4_GUIDE.md) - Dynamic tools and skills
- [System Prompt Guide](SYSTEM_PROMPT_GUIDE.md) - Tool calling format
