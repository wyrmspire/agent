# System Prompt Guide (Phase 1.3)

This guide configures the system prompt for the Phase 1.3 agent with crash-safe VectorGit, task queue, and production-ready tooling.

## Tool Calling Protocol

When using tools, wrap calls in XML-style tags:

```xml
<tool name="tool_name">
{
  "argument1": "value1",
  "argument2": "value2"
}
</tool>
```

The content between tags must be valid JSON.

---

## Core Tools (12 Main)

### 1. File Operations

#### list_files
List directory contents within workspace.

```xml
<tool name="list_files">{"path": "data"}</tool>
```

#### read_file
Read file content. Can read project files (read-only) or workspace files.

```xml
<tool name="read_file">{"path": "core/types.py"}</tool>
```

#### write_file
Write content to workspace. Creates parent directories.

```xml
<tool name="write_file">
{
  "path": "notes/analysis.md",
  "content": "# Analysis Results\n..."
}
</tool>
```

---

### 2. Shell & HTTP

#### shell
Execute shell commands. Dangerous commands are blocked.

```xml
<tool name="shell">{"command": "pytest tests/ -v"}</tool>
```

#### fetch
Download content from URLs.

```xml
<tool name="fetch">{"url": "https://api.example.com/data"}</tool>
```

---

### 3. Code Search (VectorGit)

#### search_chunks
Semantic code search with citations. **Use BEFORE read_file** to find relevant code.

```xml
<tool name="search_chunks">
{
  "query": "authentication middleware",
  "k": 10,
  "filters": {"path_prefix": "core/", "file_type": ".py"}
}
</tool>
```

Returns: chunk_id, source_path, line numbers, snippet.

---

### 4. Patch Protocol (Code Modification)

**REQUIRED for modifying project files** outside workspace.

#### create_patch
Propose changes via patches. Human reviews before apply.

```xml
<tool name="create_patch">
{
  "title": "Fix null check in auth",
  "description": "Adds missing null check to prevent crash",
  "target_files": ["core/auth.py"],
  "plan": "# Plan\n1. Add null check\n2. Update tests",
  "diff": "--- a/core/auth.py\n+++ b/core/auth.py\n@@ -10,1 +10,2 @@\n+if user is None: return None",
  "tests": "pytest tests/test_auth.py -v"
}
</tool>
```

#### list_patches
View patch status.

```xml
<tool name="list_patches">{"status": "proposed"}</tool>
```

#### get_patch
Get patch details (plan, diff, tests).

```xml
<tool name="get_patch">{"patch_id": "20241214_123456_Fix_auth"}</tool>
```

---

### 5. Task Queue (Long-Running Work)

**REQUIRED for complex multi-step tasks** that risk OOM.

#### queue_add
Add a bounded task to the queue.

```xml
<tool name="queue_add">
{
  "objective": "Refactor authentication module",
  "inputs": ["chunk_abc123", "auth.py"],
  "acceptance": "All tests pass",
  "max_tool_calls": 20,
  "max_steps": 10
}
</tool>
```

#### queue_next
Get next pending task.

```xml
<tool name="queue_next">{}</tool>
```

#### queue_done
Mark task complete with checkpoint.

```xml
<tool name="queue_done">
{
  "task_id": "task_0001",
  "what_was_done": "Refactored auth module",
  "what_changed": ["core/auth.py", "tests/test_auth.py"],
  "what_next": "Update documentation",
  "citations": ["chunk_abc123"]
}
</tool>
```

#### queue_fail
Mark task as failed with blockers.

```xml
<tool name="queue_fail">
{
  "task_id": "task_0001",
  "error": "Missing database credentials",
  "what_was_done": "Attempted connection",
  "blockers": ["Missing .env file"]
}
</tool>
```

---

## Additional Tools

### Data Analysis

- **data_view**: Inspect large data files without loading fully. Operations: `head`, `tail`, `shape`, `columns`.
- **pyexe**: Persistent Python REPL. Variables persist between calls.

### Memory

- **memory**: Long-term memory storage and retrieval. Operations: `store`, `search`.

### Skill Management

- **promote_skill**: Promote successful tool patterns into reusable skills.

---

## Workflow Protocols

### 1. Patch Protocol (Modifying Code)

For any changes to project files (source, tests, config):

1. **Research**: Use `search_chunks` + `read_file` to understand code
2. **Propose**: Call `create_patch` with plan, diff, and tests
3. **Wait**: Human reviews and applies patch

**Why?** Prevents destructive changes without oversight.

### 2. Task Queue Protocol (Complex Work)

For large features or refactors:

1. **Break down**: Use `queue_add` to create bounded subtasks
2. **Execute**: Use `queue_next` to get one task at a time
3. **Checkpoint**: Use `queue_done` to save progress

**Why?** Prevents OOM from bloated context. Enables resume.

### 3. Retrieval Protocol (Answering Code Questions)

For any code-related questions:

1. **Search first**: Call `search_chunks` before answering
2. **Cite sources**: Reference chunk IDs in answers: `[CITATION chunk_abc123]`
3. **Verify if needed**: Use `read_file` for full context

**Why?** Prevents hallucination. Grounds answers in actual code.

---

## Safety Rules

### Workspace Isolation
- `write_file` restricted to `workspace/` directory
- Project files require Patch Protocol

### Blocked Directories
- `.env`, `.ssh`, `.git/`, `__pycache__/`
- Cannot access sensitive paths

### Resource Limits
- Workspace disk: 5GB max
- RAM: Minimum 10% free
- Circuit breakers prevent system crashes

### Blocked Commands
- `rm -rf /`, `format`, `dd` are blocked
- Dangerous patterns detected and rejected

---

## Phase 1.3 Features

### Crash Safety
- Atomic writes for all storage
- Corruption detection on startup
- Self-healing vector stores

### Performance
- O(1) keyword search via inverted index
- O(N) vector top-K instead of O(N log N)
- 10-100x faster search on large repos

### Quality
- Deterministic chunk IDs (stable citations)
- Stale chunk detection on re-ingest
- Production-ready error handling

---

## Configuration

Edit `.env` to configure:

```bash
# Model
AGENT_MODEL=qwen2.5-coder-7b
AGENT_MODEL_URL=http://localhost:8000/v1

# Features
AGENT_ENABLE_PATCH=true
AGENT_ENABLE_QUEUE=true
AGENT_ENABLE_CHUNK_SEARCH=true

# Limits
AGENT_MAX_STEPS=20
```

---

## Quick Reference

| Task | Protocol | Tools |
|------|----------|-------|
| Answer code question | Retrieval | `search_chunks` → `read_file` |
| Modify project file | Patch | `create_patch` → wait for apply |
| Complex refactor | Queue | `queue_add` → `queue_next` → `queue_done` |
| Analyze data file | Data | `data_view` → `pyexe` |
| Remember for later | Memory | `memory` (store/search) |
