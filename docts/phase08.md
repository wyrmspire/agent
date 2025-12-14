# Phase 0.8: VectorGit v0 + Task Queue

Phase 0.8 introduces two critical capabilities for long-running agent tasks:

1. **Phase 0.8A: VectorGit v0** - Durable code memory with deterministic chunking
2. **Phase 0.8B: Task Queue** - Bounded task execution with resume capability

## Phase 0.8A: VectorGit v0

### Overview

VectorGit provides a durable memory layer for code retrieval without requiring vector embeddings. It uses deterministic chunking and keyword search to prove the workflow end-to-end.

### Key Features

- **Deterministic chunking**: Same content always produces same chunk IDs
- **Semantic boundaries**: Chunks follow function/class/section boundaries
- **Keyword search**: Simple but effective retrieval (embeddings in Phase 0.9)
- **Citation-ready**: Every chunk has a unique ID for traceability

### Architecture

```
workspace/vectorgit/
├── manifest.json       # Chunk metadata (IDs, hashes, locations)
├── chunks/             # Optional chunk payload storage
└── index.json          # Optional keyword index
```

### Usage

#### CLI Usage

```bash
# Ingest a repository
python vectorgit.py ingest /path/to/repo

# Query for code
python vectorgit.py query "how do tools register?" --topk 8

# Get AI explanation with citations
python vectorgit.py explain "how does error handling work?" --topk 8
```

#### Programmatic Usage

```python
from tool.vectorgit import VectorGit

# Initialize
vg = VectorGit(workspace_path="./workspace")

# Ingest repository
count = vg.ingest("/path/to/repo")
print(f"Ingested {count} chunks")

# Query chunks
results = vg.query("error handling", top_k=5)
for result in results:
    print(f"{result['source_path']}:{result['start_line']}")
    print(f"  {result['chunk_id']}: {result['name']}")

# Get AI explanation (requires gateway)
from gate.gemini import GeminiGateway
gateway = GeminiGateway(api_key="...")
answer = await vg.explain("How do tools work?", gateway, top_k=8)
```

### Chunking Strategy

**Python Files:**
- Each function is a chunk
- Each class is a chunk
- Module-level code is a chunk if no functions/classes exist

**Markdown Files:**
- Each section (by headers) is a chunk
- Entire file if no headers

**Other Files:**
- Entire file as a single chunk

### Determinism

Chunk IDs are derived from content hashes, ensuring:
- Re-ingesting produces identical chunk IDs
- Citations remain valid across ingestions
- Debuggable references for all code

### Tests

```bash
# Run all VectorGit tests
pytest tests/vectorgit/ -v

# Key tests:
# - test_determinism.py: Re-ingest produces same IDs
# - test_ingest.py: Repository ingestion works
# - test_query.py: Keyword search returns relevant chunks
```

## Phase 0.8B: Task Queue

### Overview

The Task Queue enables bounded task execution with checkpoints, allowing agents to work on complex tasks across multiple runs without losing context.

### Key Features

- **Bounded execution**: Tasks have tool call and step budgets
- **Checkpoints**: Resume-friendly state capture
- **JSONL persistence**: Append-only task log
- **Markdown checkpoints**: Human-readable progress snapshots

### Architecture

```
workspace/queue/
├── tasks.jsonl                 # Task packet log
└── checkpoints/
    ├── task_0001.md           # Checkpoint for task 1
    ├── task_0002.md           # Checkpoint for task 2
    └── ...
```

### Task Packet Format

```jsonl
{
  "task_id": "task_0001",
  "parent_id": null,
  "objective": "Refactor authentication module",
  "inputs": ["chunk_abc123", "auth.py"],
  "acceptance": "All tests pass and code is cleaner",
  "budget": {"max_tool_calls": 20, "max_steps": 10},
  "status": "queued",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00",
  "metadata": {}
}
```

### Checkpoint Format

Checkpoints are saved as Markdown files:

```markdown
# Checkpoint: task_0001

**Created:** 2024-01-01T12:00:00

## What Was Done

Refactored the authentication module to use dependency injection.
Updated 3 files and added 2 tests.

## What Changed

- auth/core.py
- auth/handlers.py
- tests/test_auth.py

## What's Next

Need to update documentation and run integration tests.

## Blockers/Errors

- None

## Citations Used

- chunk_abc123 (auth.py:15-45)
- chunk_xyz789 (handlers.py:10-30)
```

### Queue Tools

#### queue_add

Add a new task to the queue:

```python
await queue_add.execute({
    "objective": "Fix bug in payment processing",
    "inputs": ["bug_report.md", "chunk_payment_handler"],
    "acceptance": "Bug is fixed and tests pass",
    "max_tool_calls": 15,
    "max_steps": 8,
})
```

#### queue_next

Get the next queued task:

```python
result = await queue_next.execute({})
# Returns task details including objective, inputs, budget
```

#### queue_done

Mark task as complete with checkpoint:

```python
await queue_done.execute({
    "task_id": "task_0001",
    "what_was_done": "Fixed null pointer bug in payment handler",
    "what_changed": ["payment.py", "tests/test_payment.py"],
    "what_next": "Deploy to staging",
    "citations": ["chunk_xyz123"],
})
```

#### queue_fail

Mark task as failed with error details:

```python
await queue_fail.execute({
    "task_id": "task_0001",
    "error": "Cannot access database credentials",
    "what_was_done": "Attempted connection setup",
    "blockers": ["Missing .env file", "Database unreachable"],
})
```

### Workflow Pattern

The queue enforces a strict workflow:

1. **Add tasks** - Break down complex work into bounded units
2. **Get next** - Retrieve one task at a time
3. **Execute** - Work on task within budget constraints
4. **Checkpoint** - Save progress on completion or failure
5. **Stop** - Worker halts after completing one task

This pattern prevents context overflow and enables safe resumption.

### Example: 20-Task Workflow

```python
# Add 20 tasks
for i in range(1, 21):
    await queue_add.execute({
        "objective": f"Process batch {i}",
        "max_tool_calls": 10,
        "max_steps": 5,
    })

# Worker loop (run this 20 times)
task = await queue_next.execute({})
if task:
    # Do the work...
    await queue_done.execute({
        "task_id": task["task_id"],
        "what_was_done": "Batch processed",
        "what_next": "Next batch",
    })
```

### Tests

```bash
# Run all queue tests
pytest tests/queue/ -v

# Key tests:
# - test_taskqueue.py: Core TaskQueue functionality (10 tests)
# - test_queue_tools.py: Tool integration (8 tests)
```

## Success Criteria

### Phase 0.8A ✅

- [x] Ingest repository without crashing
- [x] Deterministic chunk IDs on re-ingest
- [x] Query returns relevant chunks
- [x] Explain mode cites chunk IDs
- [x] All tests passing (7/7)

### Phase 0.8B ✅

- [x] Task packets persist to JSONL
- [x] Checkpoints save as Markdown
- [x] add → next → done lifecycle works
- [x] Checkpoint on budget exhaustion
- [x] All tests passing (18/18)

## Design Philosophy

### "I can find the truth" (0.8A)

VectorGit makes code searchable and citable. No hallucinations - every answer is grounded in actual code with traceable references.

### "I can keep going" (0.8B)

The task queue makes long-running work safe. No more OOM crashes from bloated context - work is chunked, checkpointed, and resumable.

## Next Steps: Phase 0.9

Phase 0.9 will add:
- Vector embeddings for better retrieval quality
- Semantic search instead of keyword-only
- Task queue integration with embeddings

The foundations from 0.8 remain unchanged - embeddings become a drop-in improvement.

## Known Limitations

### VectorGit v0

- **Keyword search only**: No semantic understanding (fixed in 0.9)
- **No persistent chunk content**: Content stored in memory only
  - Workaround: Re-ingest to reload content
  - Not an issue for agent usage (single session)
- **CLI requires re-ingest**: Each command creates new VectorGit instance

### Task Queue v0

- **No automatic budget tracking**: Agent must self-monitor
- **No subtask discovery**: Manual subtask creation only
- **Single worker model**: No parallel execution

These limitations are intentional for v0 - they keep the implementation simple while proving the workflow.
