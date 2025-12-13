# Agent

A clean, well-architected local agent server for Qwen 2.5 Coder (and other coding models).

## Overview

This is a **local-first agent server** that gives coding models full access to tools in a safe, extensible way.

**Key features:**
- 🏠 **Local-first** - Runs on your machine, talks to LM Studio
- 🛠️ **Tool-powered** - Real filesystem, shell, and HTTP access
- 🔒 **Safe** - Rule-based validation prevents dangerous operations
- 🧩 **Modular** - Clean architecture with pluggable components
- 📝 **Well-documented** - Every module has clear purpose and rules

## Architecture

```
boot/   → Entry point and dependency wiring
core/   → Core types, protocols, and rules (no dependencies)
gate/   → Model gateway (LM Studio, OpenAI-compatible)
tool/   → Real tools (files, shell, fetch)
flow/   → Agent reasoning loop
store/  → Memory (short-term and long-term)
servr/  → API server (optional)
model/  → Model configurations
tests/  → Test suite
docts/  → Documentation
```

See [docts/archi.md](docts/archi.md) for detailed architecture.

## Quick Start

### Prerequisites

1. **LM Studio** running with a model loaded
   - Default: http://localhost:1234
   - Load a Qwen 2.5 Coder model (or compatible)

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

Create a `.env` file (optional):

```bash
# Model configuration
AGENT_MODEL=qwen2.5-coder-7b
AGENT_MODEL_URL=http://localhost:1234/v1

# Agent configuration
AGENT_MAX_STEPS=20
AGENT_TEMPERATURE=0.7

# Tool configuration
AGENT_ENABLE_SHELL=true
AGENT_ENABLE_FILES=true
AGENT_ENABLE_FETCH=true

# Logging
AGENT_LOG_LEVEL=INFO
```

See [boot/setup.py](boot/setup.py) for all configuration options.

## Tools

Built-in tools:
- **list_files** - List files in a directory
- **read_file** - Read file contents
- **write_file** - Write content to a file
- **shell** - Execute shell commands (with safety rules)
- **fetch** - Fetch content from URLs

See [docts/tools.md](docts/tools.md) for details and how to create custom tools.

## Testing

Run tests:

```bash
# All tests
python -m pytest tests/

# Specific test module
python tests/tools/ttool.py
python tests/flows/tflow.py
python tests/gates/tgate.py
```

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
├── boot/          # Entry point and wiring
│   ├── mains.py   # Main entry point
│   ├── setup.py   # Configuration loading
│   └── wires.py   # Dependency injection
├── core/          # Core contracts (no dependencies)
│   ├── types.py   # Message, Tool, Step types
│   ├── proto.py   # Request/response schemas
│   ├── state.py   # Agent state objects
│   └── rules.py   # Safety and auth rules
├── gate/          # Model gateway
│   ├── bases.py   # Abstract interface
│   ├── lmstd.py   # LM Studio adapter
│   └── embed.py   # Embedding gateway
├── tool/          # Real tools
│   ├── bases.py   # Tool interface
│   ├── files.py   # File tools
│   ├── shell.py   # Shell tool
│   ├── fetch.py   # HTTP tool
│   └── index.py   # Tool registry
├── flow/          # Agent logic
│   ├── loops.py   # Main agent loop
│   ├── plans.py   # Planning prompts
│   ├── execs.py   # Tool execution
│   └── judge.py   # Verifier
├── store/         # Memory
│   ├── bases.py   # Store interfaces
│   ├── short.py   # Short-term memory
│   ├── longg.py   # Long-term memory
│   └── vects.py   # Vector store
├── servr/         # API server
│   ├── servr.py   # Server setup
│   └── routs.py   # Route handlers
├── model/         # Model configs
│   ├── qwen5/     # Qwen configs
│   └── embed/     # Embedding configs
├── tests/         # Tests
│   ├── tools/     # Tool tests
│   ├── flows/     # Flow tests
│   └── gates/     # Gateway tests
├── docts/         # Documentation
│   ├── archi.md   # Architecture
│   ├── tools.md   # Tools guide
│   └── flows.md   # Flows guide
├── cli.py         # CLI demo
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
