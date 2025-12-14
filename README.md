# Agent

A clean, well-architected local agent server for Qwen 2.5 Coder (and other coding models).

## Overview

This is a **local-first agent server** that gives coding models full access to tools in a safe, extensible way.

**Key features:**
- 🏠 **Local-first** - Runs on your machine with OpenAI-compatible APIs
- 🛠️ **Tool-powered** - Real filesystem, shell, HTTP, and memory access
- 🔒 **Safe** - Workspace isolation, Patch Protocol, and rule-based validation
- 🧩 **Modular** - Clean architecture with pluggable components
- 🧠 **Durable Memory** - VectorGit (Phase 0.8A) for semantic code retrieval
- 📋 **Task Queue** - Phase 0.8B bounded execution for long-running workflows

> ⚠️ **LOCAL MODEL MEMORY LIMITS**
>
> Local models can OOM on long conversations.
> **Solution (Phase 0.8B):** Use the **Task Queue** tools (`queue_add`, `queue_next`) to break work into small, checkpointed units.

## Architecture

```
boot/   → Entry point and dependency wiring
core/   → Core types, protocols, skills compiler (no dependencies)
gate/   → Model gateway (OpenAI-compatible APIs)
tool/   → Real tools (files, shell, patch, queue, vectorgit)
flow/   → Agent reasoning loop and project planner
store/  → Memory (chunks, checkpoints, vector store)
servr/  → API server (optional)
model/  → Model configurations
tests/  → Comprehensive test suite
docts/  → Documentation
```

See [docts/archi.md](docts/archi.md) for detailed architecture.

## Workflow Protocols

### 1. The Patch Protocol (Project Edits)
To safely modify code, the agent follows a strict propose-and-apply flow:
1.  **Propose**: Agent uses `create_patch` to draft a plan, diff, and tests.
2.  **Review**: You (or the system) review the patch.
3.  **Apply**: The patch is applied only if valid.

### 2. The Task Queue (Complex Tasks)
For large features or refactors:
1.  **Queue**: Agent breaks the goal into subtasks (`queue_add`).
2.  **Execute**: Agent picks up one task at a time (`queue_next`).
3.  **Checkpoint**: Progress is saved to disk (`queue_done`).

## Quick Start

### Prerequisites
1.  **OpenAI-compatible API** (LM Studio, Ollama, etc.)
    *   Default: http://localhost:8000/v1
    *   Model: Qwen 2.5 Coder (recommended)
2.  **Python 3.10+**

### Installation

```bash
git clone https://github.com/wyrmspire/agent.git
cd agent
pip install -r requirements.txt
```

### Run CLI Demo

```bash
python cli.py
```

Try:
- "Analyze this repo" (Uses `search_chunks`)
- "Create a patch to fix X" (Uses `create_patch`)
- "Start a task to refactor Y" (Uses `queue_add`)

## Configuration

Create a `.env` file:

```bash
AGENT_MODEL=qwen2.5-coder-7b
AGENT_MODEL_URL=http://localhost:8000/v1
AGENT_ENABLE_PATCH=true
AGENT_ENABLE_QUEUE=true
AGENT_ENABLE_CHUNK_SEARCH=true
```

## Tools

See [docts/tools.md](docts/tools.md) for the complete reference.

### Core Tools
- **Project**: `create_patch`, `list_patches`, `get_patch`
- **Queue**: `queue_add`, `queue_next`, `queue_done`
- **Memory**: `search_chunks` (VectorGit)
- **System**: `list_files`, `read_file`, `shell`, `fetch`
- **Analysis**: `data_view`, `pyexe`

## Documentation

- [Flows & Protocols](docts/flows.md) - How the agent thinks and works
- [Tools Reference](docts/tools.md) - Detailed tool APIs
- [Architecture](docts/archi.md) - System design

## License

MIT
