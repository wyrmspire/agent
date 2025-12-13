# Architecture

This document describes the architecture of the agent system.

## Overview

This is a **local-first agent server** designed to give coding models (like Qwen 2.5 Coder) full access to tools in a safe, extensible way.

Key principles:
- **Backend-only** - No UI, just the core system
- **Model-agnostic** - Works with LM Studio now, others later
- **Tool-powered** - Real filesystem, shell, and HTTP access
- **Clean separation** - Each module has one clear responsibility

## Architecture Layers

```
┌─────────────────────────────────────┐
│         boot/ (Entry)               │  ← Start here
├─────────────────────────────────────┤
│         core/ (Contracts)           │  ← Types, protocols, rules
├─────────────────────────────────────┤
│    ┌──────────┬──────────┬────────┐ │
│    │  gate/   │  tool/   │ store/ │ │  ← Adapters
│    │ (Model)  │ (Tools)  │ (Mem)  │ │
│    └──────────┴──────────┴────────┘ │
├─────────────────────────────────────┤
│         flow/ (Agent Logic)         │  ← Orchestration
├─────────────────────────────────────┤
│         servr/ (API - Optional)     │  ← HTTP server
└─────────────────────────────────────┘
```

## Module Responsibilities

### boot/ - Entry & Wiring
**Purpose**: One obvious start point that wires everything together.

Files:
- `mains.py` - Entry point, starts CLI chat loop
- `setup.py` - Load config, env vars, logging
- `wires.py` - Dependency injection container

**Key point**: This is the smallest runnable path: prompt → model → optional tool → final answer.

### core/ - Contracts & Truth
**Purpose**: The spine. Defines all core types and protocols.

Files:
- `types.py` - Message, Tool, Step types
- `proto.py` - Request/response schemas
- `state.py` - Agent state objects
- `rules.py` - Safety and authorization rules

**Key point**: No dependencies on other modules. Everything else depends on core/.

### gate/ - Model Gateway
**Purpose**: One interface for model communication, regardless of backend.

Files:
- `bases.py` - Abstract ModelGateway interface
- `lmstd.py` - LM Studio adapter (OpenAI-compatible)
- `embed.py` - Embedding gateway

**Key point**: Tool definitions must match OpenAI schema. Parameters MUST have `type: "object"`.

### tool/ - Real Tools
**Purpose**: Execute real actions in the world.

Files:
- `bases.py` - BaseTool interface
- `files.py` - File system tools (list, read, write)
- `shell.py` - Shell command execution
- `fetch.py` - HTTP requests
- `index.py` - Tool registry

**Key point**: Tools are pure-ish (inputs → outputs). They return structured results, never throw exceptions to caller.

### flow/ - Agent Intelligence
**Purpose**: Orchestrate reasoning: call model → detect tool → run tool → feed back → finalize.

Files:
- `loops.py` - Main agent loop
- `plans.py` - Planning prompts and strategies
- `execs.py` - Safe tool execution utilities
- `judge.py` - Verifier and critic

**Key point**: Max turns prevents infinite loops. Supports native function calling and JSON fallback.

### store/ - Memory & Recall
**Purpose**: Give agent long-term memory without vendor lock-in.

Files:
- `bases.py` - Abstract store interfaces
- `short.py` - Short-term memory (in-memory)
- `longg.py` - Long-term memory (SQLite)
- `vects.py` - Vector store for semantic search

**Key point**: Retrieval returns citations + snippets. Pluggable (memory → SQLite → Postgres → Qdrant).

### servr/ - API Server
**Purpose**: Optional HTTP server for remote access.

Files:
- `servr.py` - HTTP server setup
- `routs.py` - API route handlers

**Key point**: OpenAI-compatible API format for easy integration.

### model/ - Model Assets
**Purpose**: Model configurations and metadata (no actual model files).

Directories:
- `qwen5/` - Qwen 2.5 Coder configs
- `embed/` - Embedding model configs

**Key point**: Only configs here. Model files are too large for repo.

## Dependency Rules

```
boot/
  ↓ depends on
core/  ← Independent
  ↓ used by
gate/, tool/, store/  ← Adapters (parallel, independent)
  ↓ used by
flow/  ← Orchestration
  ↓ used by
servr/  ← API layer (optional)
```

**Critical rules**:
1. core/ depends on NOTHING
2. Adapters (gate/, tool/, store/) only depend on core/
3. flow/ depends on core/ + adapters
4. boot/ wires everything together
5. servr/ is optional

## Data Flow

### Simple question (no tools):
```
User input
  → AgentLoop.run()
  → ModelGateway.complete()
  → Model responds
  → Return final answer
```

### Tool-using flow:
```
User input
  → AgentLoop.run()
  → ModelGateway.complete()
  → Model requests tool call
  → RuleEngine validates
  → ToolRegistry looks up tool
  → Tool executes
  → Result fed back to model
  → ModelGateway.complete() (again)
  → Model provides final answer
  → Return final answer
```

## Configuration

Environment variables (see boot/setup.py):
- `AGENT_MODEL` - Model name (default: qwen2.5-coder-7b)
- `AGENT_MODEL_URL` - LM Studio URL (default: http://localhost:1234)
- `AGENT_MAX_STEPS` - Max reasoning steps (default: 20)
- `AGENT_ENABLE_SHELL` - Enable shell tool (default: true)
- `AGENT_ENABLE_FILES` - Enable file tools (default: true)
- `AGENT_LOG_LEVEL` - Logging level (default: INFO)

## Day 1 Acceptance Criteria

The system must:
1. ✅ Start a CLI chat session
2. ✅ Answer "hi" without crashing
3. ✅ Execute one toy tool successfully
4. ✅ Show clear errors for invalid tool schemas

## Future Enhancements

Not implemented yet, but designed for:
- [ ] Web UI
- [ ] VS Code extension
- [ ] Multiple model backends (OpenAI, Anthropic, local)
- [ ] Advanced memory (vector search, summaries)
- [ ] Multi-agent coordination
- [ ] Streaming responses
- [ ] Function calling fallback (JSON mode)
