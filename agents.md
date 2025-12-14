# Agent Development Journey

This document chronicles the development of this agent system and provides guidance for building robust AI agents.

## Our Journey: Phase by Phase

### Phase 0.1-0.2: Foundation
**Goal:** Get a working agent loop

- Built basic chat loop with tool calling
- Implemented tag-based parsing for tool calls
- Added file operations (read, write, list)
- Created shell and HTTP tools

**Lesson:** Start with the simplest possible loop that works. `prompt → model → tool → response`.

### Phase 0.3-0.4: Intelligence
**Goal:** Give the agent memory and skills

- Added in-memory vector store for conversations
- Implemented memory tool (store/search)
- Created skill promotion system
- Built dynamic skill loading

**Lesson:** Memory is power. Agents without memory forget everything between turns.

### Phase 0.5: Safety
**Goal:** Prevent the agent from causing harm

- Implemented workspace isolation
- Added blocked directories and commands
- Created resource monitoring (disk, RAM)
- Built rule engine for authorization

**Lesson:** Sandboxing is non-negotiable. Never trust agent output to be safe.

### Phase 0.6-0.7: Discipline
**Goal:** Make the agent follow protocols

- Created Patch Protocol for code changes
- Built patch manager with plan/diff/tests
- Added citation discipline (chunk IDs)
- Implemented judge for workflow enforcement

**Lesson:** Agents need guardrails. Left alone, they hallucinate and cause chaos.

### Phase 0.8: Durability
**Goal:** Survive long-running tasks

- Built VectorGit for code retrieval
- Created Task Queue for bounded execution
- Implemented checkpoints for resume
- Added deterministic chunk IDs

**Lesson:** Split big tasks into small, checkpointed units. OOM is the enemy.

### Phase 1.2-1.3: Production
**Goal:** Ship-quality reliability

- Atomic writes for crash safety
- Corruption detection and self-healing
- Inverted index for O(1) search
- 10-100x performance improvements

**Lesson:** Production means surviving crashes, not just working in demos.

---

## How to Develop Agents Properly

### 1. Start Simple

```
User Input → Model → Response
```

Don't add tools until the basic loop works. Don't add memory until tools work. Build incrementally.

### 2. Sandbox Everything

The agent WILL try to:
- Write to sensitive locations
- Execute dangerous commands
- Exceed resource limits

Build restrictions BEFORE giving capabilities:
- File operations: workspace only
- Shell: blocked patterns
- Resources: circuit breakers

### 3. Define Protocols

Agents without protocols are chaos. Define rules:

| Action | Protocol |
|--------|----------|
| Modify code | Patch Protocol (propose → review → apply) |
| Long task | Task Queue (break down → checkpoint) |
| Answer questions | Retrieval first (search → cite) |

### 4. Make It Resumable

Assume crashes will happen:
- Atomic writes (never partial state)
- Checkpoints (save progress)
- Idempotent operations (re-run safely)

### 5. Test Ruthlessly

Tests we run:
- Unit tests for each tool
- Integration tests for workflows
- Smoke tests for quick health check
- Determinism tests (same input → same output)

```bash
pytest tests/ -v          # Full suite
./smoke_test.sh           # Quick check
```

### 6. Observe Everything

Log these:
- Tool calls (start, end, duration)
- Token usage per request
- Error rates and types
- Performance metrics

Without observability, debugging is impossible.

---

## Architecture Principles

### Layers

```
boot/   → Entry point (start here)
core/   → Types and protocols (no dependencies)
gate/   → Model gateway (OpenAI-compatible)
tool/   → Real tools (files, shell, patch, queue)
flow/   → Agent loop (orchestration)
store/  → Memory (chunks, vectors, checkpoints)
servr/  → API server (optional)
```

### Dependency Rules

1. `core/` depends on NOTHING
2. Adapters (`gate/`, `tool/`, `store/`) depend only on `core/`
3. `flow/` depends on core + adapters
4. `boot/` wires everything together

### Tool Design

Tools should be:
- **Pure-ish**: inputs → outputs, minimal side effects
- **Safe**: validate inputs, never throw to caller
- **Observable**: log tool_call_id for tracing

```python
class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    async def execute(self, arguments: Dict) -> ToolResult:
        try:
            # Do work
            return ToolResult(output="success", success=True)
        except Exception as e:
            return ToolResult(error=str(e), success=False)
```

---

## Common Pitfalls

### 1. "Let the model figure it out"

**Wrong:** Give model broad capabilities, hope for the best.

**Right:** Define strict protocols, enforce with code.

### 2. "Memory will solve everything"

**Wrong:** Stuff all context into memory, let RAG handle it.

**Right:** Chunk semantically, cite precisely, verify retrieval.

### 3. "Patches are overkill"

**Wrong:** Let agent directly write to source files.

**Right:** Propose → Review → Apply. Always reviewable.

### 4. "One big context window"

**Wrong:** Keep adding to conversation until OOM.

**Right:** Task queue with checkpoints, bounded execution.

### 5. "Tests are slow"

**Wrong:** Skip tests to move faster.

**Right:** Tests catch regressions. Smoke test in seconds.

---

## Recommended Development Flow

### Adding a New Tool

1. Define interface in `tool/bases.py` pattern
2. Implement tool in `tool/my_tool.py`
3. Register in `tool/index.py`
4. Add tests in `tests/tools/test_my_tool.py`
5. Document in `SYSTEM_PROMPT_GUIDE.md`

### Adding a New Feature

1. Write failing test first
2. Implement minimum viable version
3. Add error handling
4. Add logging
5. Update documentation
6. Run full test suite

### Debugging Issues

1. Check logs with `tool_call_id`
2. Reproduce with specific input
3. Add targeted test
4. Fix and verify
5. Check for regressions

---

## Key Files

| File | Purpose |
|------|---------|
| `cli.py` | Main entry point |
| `flow/loops.py` | Agent reasoning loop |
| `tool/index.py` | Tool registry |
| `core/rules.py` | Safety rules |
| `core/sandb.py` | Workspace isolation |
| `store/chunks.py` | Code chunking |
| `store/vectors.py` | Vector search |

---

## Current Status

**Phase:** 1.3 (Operational Durability)

**What Works:**
- ✅ Crash-safe storage
- ✅ Fast search (inverted index)
- ✅ Self-healing vectors
- ✅ Full tool suite

**What's Next (Phase 1.4):**
- Hybrid search (RRF)
- Contextual embeddings
- Improved explain prompts

See `PHASE_1_ROADMAP.md` for details.
