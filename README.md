# Agent

A clean, well-architected local agent server for coding models.

## Overview

**Local-first agent server** with full tool access in a safe, extensible way.

**Phase:** 1.3 (Operational Durability)

**Key features:**
- 🏠 **Local-first** - Runs on your machine with OpenAI-compatible APIs
- 🛠️ **17 Tools** - Files, shell, patches, queue, search, memory
- 🔒 **Safe** - Workspace isolation, Patch Protocol, rule-based validation
- 💾 **Crash-safe** - Atomic writes, corruption detection, self-healing
- ⚡ **Fast** - O(1) keyword search, 10-100x speedup on large repos
- 📋 **Resumable** - Task Queue with checkpoints for long-running work

## Quick Start

```bash
# Install
git clone https://github.com/wyrmspire/agent.git
cd agent
pip install -r requirements.txt

# Run
python cli.py
```

## Architecture

```
boot/   → Entry point and dependency wiring
core/   → Core types, protocols (no dependencies)
gate/   → Model gateway (OpenAI-compatible)
tool/   → 17 tools (files, shell, patch, queue, search)
flow/   → Agent reasoning loop
store/  → Memory (chunks, vectors, checkpoints)
servr/  → API server (optional)
tests/  → Comprehensive test suite
```

See [docts/archi.md](docts/archi.md) for details.

## Workflow Protocols

### Patch Protocol (Code Modification)
1. **Propose**: `create_patch` with plan, diff, tests
2. **Review**: Human reviews the patch
3. **Apply**: Patch applied if valid

### Task Queue (Long-Running Work)
1. **Queue**: `queue_add` breaks work into subtasks
2. **Execute**: `queue_next` gets one task at a time
3. **Checkpoint**: `queue_done` saves progress

### Retrieval Protocol (Code Questions)
1. **Search**: `search_chunks` before answering
2. **Cite**: Reference chunk IDs in responses
3. **Verify**: `read_file` for full context

## Tools

| Category | Tools |
|----------|-------|
| **Files** | `list_files`, `read_file`, `write_file` |
| **Shell** | `shell` |
| **HTTP** | `fetch` |
| **Search** | `search_chunks` |
| **Patch** | `create_patch`, `list_patches`, `get_patch` |
| **Queue** | `queue_add`, `queue_next`, `queue_done`, `queue_fail` |
| **Data** | `data_view`, `pyexe` |
| **Memory** | `memory` |

See [docts/tools.md](docts/tools.md) for complete reference.

## Configuration

```bash
# .env
AGENT_MODEL=qwen2.5-coder-7b
AGENT_MODEL_URL=http://localhost:8000/v1
AGENT_ENABLE_PATCH=true
AGENT_ENABLE_QUEUE=true
AGENT_ENABLE_CHUNK_SEARCH=true
```

## Testing

```bash
pytest tests/ -v            # Full suite
./smoke_test.sh             # Quick health check
```

## Documentation

| Document | Description |
|----------|-------------|
| [SYSTEM_PROMPT_GUIDE.md](SYSTEM_PROMPT_GUIDE.md) | Tool calling guide |
| [PHASE_1_ROADMAP.md](PHASE_1_ROADMAP.md) | Current roadmap |
| [agents.md](agents.md) | Development journey |
| [docts/archi.md](docts/archi.md) | Architecture |
| [docts/tools.md](docts/tools.md) | Tool reference |
| [docts/flows.md](docts/flows.md) | Workflow patterns |

## Phase 1.3 Features

- ✅ **Crash-safe storage** - Atomic writes, never partial state
- ✅ **Corruption detection** - Self-healing on startup
- ✅ **O(1) keyword search** - Inverted index
- ✅ **Fast vector search** - O(N) top-K with argpartition
- ✅ **Stale chunk detection** - Clean re-ingestion

See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for details.

## License

MIT
