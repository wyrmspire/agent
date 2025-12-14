# Agent

A clean, well-architected local agent server for Qwen 2.5 Coder (and other coding models).

## Overview

This is a **local-first agent server** that gives coding models full access to tools in a safe, extensible way.

**Key features:**
- 🏠 **Local-first** - Runs on your machine with OpenAI-compatible APIs
- 🛠️ **Tool-powered** - Real filesystem, shell, HTTP, and memory access
- 🔒 **Safe** - Workspace isolation and rule-based validation
- 🧩 **Modular** - Clean architecture with pluggable components
- 🚀 **Dynamic** - Agent can create and promote its own tools
- 📝 **Well-documented** - Every module has clear purpose and rules

> ⚠️ **LOCAL MODEL MEMORY LIMITS**
> 
> Local models (Qwen 7B on 8GB VRAM) can OOM on long conversations with many tool calls.
> Each tool result adds to context. **Currently no automatic context management.**
> 
> **Workarounds:**
> - Use `--gemini` flag for complex multi-step tasks (Gemini has 1M token context)
> - Keep local model conversations short
> - Restart between complex tasks
> 
> **Roadmap (v1.0+):** Context truncation, task queuing, and run continuation so local
> models can break up work and resume across multiple runs.

## Architecture

```
boot/   → Entry point and dependency wiring
core/   → Core types, protocols, skills compiler (no dependencies)
gate/   → Model gateway (OpenAI-compatible APIs)
tool/   → Real tools (files, shell, fetch, memory, dynamic)
flow/   → Agent reasoning loop and project planner
store/  → Memory (short-term, long-term, vector store)
servr/  → API server (optional)
model/  → Model configurations
tests/  → Comprehensive test suite
docts/  → Documentation
```

See [docts/archi.md](docts/archi.md) for detailed architecture.

## How It Works

### Agent Loop
- **Entry**: Python CLI (`python cli.py`) or programmatic via `flow/loops.py`
- **Loop**: `User Input → Model Call → Tool Detection → Tool Execution → Response`
- **Max Steps**: Configurable limit (default: 20) prevents infinite loops
- **Async**: Built on Python asyncio for concurrent tool execution

### Tool System
- **Location**: All tools live in `tool/` directory
- **Interface**: Tools implement `BaseTool` with `name`, `description`, `parameters`, and `execute()`
- **Schema**: OpenAI function calling format (JSON Schema with `type: "object"`)
- **Registry**: `tool/index.py` manages tool discovery and lookup
- **Dynamic**: Agent can create and promote Python functions to tools at runtime (Phase 0.4)

### Model Gateway
- **Abstraction**: `gate/bases.py` defines `ModelGateway` interface
- **Implementations**:
  - `gate/lmstd.py` - OpenAI-compatible API adapter (LM Studio, Ollama, vLLM, etc.)
  - `gate/mock.py` - Mock gateway for testing
  - `servr/api.py` - Native model server (loads Transformers models directly)
- **Protocol**: OpenAI `/v1/chat/completions` format with tool calling

### HTTP Layer
- **Model Server**: FastAPI server (`servr/api.py`) on port 8000
- **Client**: `httpx` async client for model API calls
- **Tool Parsing**: Server parses `<tool>` XML tags OR Python-style function calls from model output

### State & Memory
| Layer | Implementation | Persistence |
|-------|---------------|-------------|
| Conversation | `core/state.py` (in-memory) | Session only |
| Short-term | `store/short.py` (in-memory) | Session only |
| Long-term | `store/longg.py` (SQLite) | Disk |
| Vector search | `store/vects.py` (pickle) | Disk |
| Project state | `flow/planner.py` (JSON) | `workspace/project.json` |
| Skills | `workspace/skills/*.py` | Disk (Python files) |

### Local-Only Design
- ✅ **100% local** - No cloud dependencies, no API keys required
- ✅ **Offline capable** - Works with local models (Qwen, CodeLlama, etc.)
- ✅ **Privacy** - All data stays on your machine
- ✅ **Workspace isolation** - Agent sandboxed to `workspace/` directory
- ⚡ **Optional**: Can connect to external OpenAI-compatible APIs if desired

## Quick Start

### Prerequisites

1. **OpenAI-compatible API** endpoint
   - **Native server**: Run `bash runsv.sh` to start the built-in model server on port 8000
   - **External**: LM Studio, Ollama, vLLM, or any OpenAI-compatible server
   - Default: http://localhost:8000/v1
   - Compatible models: Qwen 2.5 Coder, CodeLlama, DeepSeek Coder, etc.

2. **Python 3.10+**

### Installation

```bash
# Clone the repo
git clone https://github.com/wyrmspire/agent.git
cd agent

# Install dependencies
pip install -r requirements.txt
```

### Run CLI Demo

```bash
python cli.py
```

This starts an interactive chat session. Try:
- "Hi" - Simple greeting (no tools)
- "What files are in the current directory?" - Uses list_files tool
- "Read the README.md file" - Uses read_file tool

Type `quit` or `exit` to stop.

## Configuration

Create a `.env` file (or copy from `.env.example`):

```bash
# Model configuration
AGENT_MODEL=qwen2.5-coder-7b
AGENT_MODEL_URL=http://localhost:8000/v1

# Agent configuration
AGENT_MAX_STEPS=20
AGENT_TEMPERATURE=0.7

# Tool configuration
AGENT_ENABLE_SHELL=true
AGENT_ENABLE_FILES=true
AGENT_ENABLE_FETCH=true
AGENT_ENABLE_DATA_VIEW=true
AGENT_ENABLE_PYEXE=true

# Logging
AGENT_LOG_LEVEL=INFO
```

See [boot/setup.py](boot/setup.py) for all configuration options.

## Tools

### Built-in Tools (Phase 0.1-0.2)
- **list_files** - List files in workspace
- **read_file** - Read file contents
- **write_file** - Write content to files
- **shell** - Execute shell commands (with safety rules)
- **fetch** - Fetch content from URLs
- **data_view** - Inspect large datasets (CSV peek, shape, columns)
- **pyexe** - Persistent Python REPL for data analysis

### Phase 0.3 Tools (Memory & Planning)
- **memory** - Store and search long-term memories
  - Operations: store (save info), search (find relevant memories)
  - Persistent across sessions

### Phase 0.4 Tools (Dynamic Tool Loading)
- **promote_skill** - Upgrade Python functions to registered tools
  - Validates syntax, type hints, and docstrings
  - Canonizes to workspace/skills/
  - Hot-reloads into registry

The agent can now **create its own tools** by writing Python functions and promoting them!

See [docts/tools.md](docts/tools.md) for details and how to create custom tools.

## Phase 0.3 Features: Planning & Memory

### Project State Machine (`flow/planner.py`)
Track project lifecycle with persistent state:
- States: planning → executing → reviewing → complete
- Tasks with status tracking
- Lab notebook for observations
- Integrated with system prompt

### Long-Term Memory
- Vector store with disk persistence
- Semantic search (keyword-based for now, embedding-ready)
- Store important information across sessions
- Memory tool for agent access

## Phase 0.4 Features: Dynamic Tool Loading

### The Workflow
1. **Develop**: Agent writes code in `pyexe` to solve a problem
2. **Perfect**: Agent debugs and refines until it works
3. **Formalize**: Agent rewrites as clean function with type hints and docstring
4. **Promote**: Agent calls `promote_skill` tool
5. **Evolve**: Function becomes a registered tool immediately
6. **Use**: Agent can now call the tool without rewriting code

### Example: Creating a Custom Tool
```python
# Agent writes this in the workspace
def calculate_rsi(prices: list[float], period: int = 14) -> list[float]:
    """Calculate Relative Strength Index for price data."""
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return [rsi]  # Simplified for example

# Agent promotes it
<tool name="promote_skill">{
  "file_path": "rsi_calculator.py",
  "function_name": "calculate_rsi",
  "tool_name": "calculate_rsi"
}</tool>

# Now available as a tool!
<tool name="calculate_rsi">{
  "prices": [100, 102, 101, 103, 105],
  "period": 14
}</tool>
```

### Skills Directory
- Location: `workspace/skills/`
- Canonized, permanent functions
- Auto-loaded on startup
- Executed safely via `pyexe` subprocess

## Testing

### Quick Health Check

Run the smoke test to verify system health after changes:

```bash
./smoke_test.sh
```

This runs 14 checks in <30 seconds to verify core functionality.

### Full Test Suite

Run comprehensive tests:

```bash
# Run all tests
PYTHONPATH=. python tests/tools/ttool.py
PYTHONPATH=. python tests/flows/tflow.py
PYTHONPATH=. python tests/gates/tgate.py

# Phase 0.3 tests
PYTHONPATH=. python tests/flow/test_planner.py
PYTHONPATH=. python tests/store/test_vects_persist.py
PYTHONPATH=. python tests/tools/test_memory.py

# Phase 0.4 tests
PYTHONPATH=. python tests/core/test_skills.py
PYTHONPATH=. python tests/tools/test_promote_skill.py

# Or use pytest (if installed)
pytest tests/ -v
```

**Test Coverage**: 42+ tests for Phase 0.3 & 0.4, all passing

## Day 1 Acceptance Criteria

✅ Start a CLI chat session  
✅ Answer "hi" without crashing  
✅ Execute a tool successfully  
✅ Show clear errors for invalid schemas  

## Documentation

- [Architecture](docts/archi.md) - System design and module responsibilities
- [Tools](docts/tools.md) - Tool system and creating custom tools
- [Flows](docts/flows.md) - Agent reasoning loop and execution

## Safety

Default safety rules prevent:
- Dangerous shell commands (rm -rf, dd, mkfs, etc.)
- Access to sensitive files (/etc/passwd, .ssh keys, etc.)

Add custom rules in [boot/wires.py](boot/wires.py).

## Project Structure

```
agent/
├── boot/           # Entry point and wiring
│   ├── mains.py    # Main entry point
│   ├── setup.py    # Configuration loading
│   └── wires.py    # Dependency injection
├── core/           # Core contracts (no dependencies)
│   ├── types.py    # Message, Tool, Step types
│   ├── proto.py    # Request/response schemas
│   ├── state.py    # Agent state objects
│   ├── rules.py    # Safety and auth rules
│   ├── sandb.py    # Workspace sandbox isolation
│   └── skills.py   # Skill compiler (Phase 0.4)
├── gate/           # Model gateway
│   ├── bases.py    # Abstract interface
│   ├── lmstd.py    # LM Studio / OpenAI adapter
│   ├── mock.py     # Mock gateway for testing
│   └── embed.py    # Embedding gateway
├── tool/           # Real tools
│   ├── bases.py    # Tool interface
│   ├── files.py    # File tools (list, read, write)
│   ├── shell.py    # Shell tool
│   ├── fetch.py    # HTTP tool
│   ├── dview.py    # Data view tool (Phase 0.2)
│   ├── pyexe.py    # Python executor (Phase 0.2)
│   ├── memory.py   # Memory tool (Phase 0.3)
│   ├── dynamic.py  # Dynamic tool wrapper (Phase 0.4)
│   ├── manager.py  # Skill promotion tool (Phase 0.4)
│   └── index.py    # Tool registry
├── flow/           # Agent logic
│   ├── loops.py    # Main agent loop
│   ├── plans.py    # Planning prompts
│   ├── planner.py  # Project state machine (Phase 0.3)
│   ├── execs.py    # Tool execution
│   └── judge.py    # Verifier
├── store/          # Memory
│   ├── bases.py    # Store interfaces
│   ├── short.py    # Short-term memory
│   ├── longg.py    # Long-term memory
│   └── vects.py    # Vector store (persistent)
├── servr/          # API server
│   ├── api.py      # FastAPI model server
│   └── routs.py    # Route handlers
├── model/          # Model configs
│   ├── qwen5/      # Qwen configs
│   └── embed/      # Embedding configs
├── tests/          # Tests
│   ├── tools/      # Tool tests
│   ├── flows/      # Flow tests
│   ├── gates/      # Gateway tests
│   ├── core/       # Core tests (skills)
│   └── store/      # Store tests
├── docts/          # Documentation
│   ├── archi.md    # Architecture
│   ├── tools.md    # Tools guide
│   └── flows.md    # Flows guide
├── workspace/      # Agent workspace (sandboxed)
│   └── skills/     # Promoted skill functions
├── cli.py          # CLI demo
├── runsv.sh        # Start native model server
└── requirements.txt
```

## Contributing

This is a clean foundation. Contributions welcome!

Guidelines:
- Keep modules focused and independent
- Follow existing patterns
- Add tests for new features
- Update documentation

## License

MIT

## Acknowledgments

Designed as the "perfect nest" - a stable substrate for agent development with:
- Clear separation of concerns
- No duplicate responsibilities
- Everything has one home
- Easy to understand and extend
