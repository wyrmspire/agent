# Phase 0.3 & 0.4: Planning, Memory, and Dynamic Tools

This guide documents the Phase 0.3 and 0.4 features that transform the agent from a tool-using assistant into a **self-improving, learning system**.

## Table of Contents
1. [Phase 0.3: Planning & Memory](#phase-03-planning--memory)
2. [Phase 0.4: Dynamic Tool Loading](#phase-04-dynamic-tool-loading)
3. [Complete Workflow Example](#complete-workflow-example)

---

## Phase 0.3: Planning & Memory

### Project State Machine (`flow/planner.py`)

The planner implements a state machine for managing project lifecycle:

#### States
- **PLANNING**: Initial design and task breakdown
- **EXECUTING**: Active development
- **REVIEWING**: Quality checks and validation
- **COMPLETE**: Project finished
- **PAUSED**: Temporarily suspended

#### Valid Transitions
```
PLANNING → EXECUTING, PAUSED
EXECUTING → REVIEWING, PAUSED
REVIEWING → EXECUTING, COMPLETE, PAUSED
PAUSED → PLANNING, EXECUTING, REVIEWING
COMPLETE → (terminal state)
```

#### Usage Example

```python
from flow.planner import ProjectStateMachine, ProjectState

# Create state machine
planner = ProjectStateMachine()

# Create project
project = planner.create(
    name="Financial Data Analysis",
    description="Build tools for analyzing market data",
    tasks=[
        {"id": "task1", "description": "Load price data"},
        {"id": "task2", "description": "Calculate indicators"},
        {"id": "task3", "description": "Generate reports"},
    ]
)

# Transition states
planner.transition_to(ProjectState.EXECUTING)

# Update task
planner.update_task("task1", status="complete")

# Add lab notebook entry
planner.add_lab_entry("Successfully loaded 1M rows of BTC price data")

# Get summary
print(planner.get_summary())
```

#### Project.json Format

```json
{
  "name": "Financial Data Analysis",
  "description": "Build tools for analyzing market data",
  "state": "executing",
  "tasks": [
    {
      "id": "task1",
      "description": "Load price data",
      "status": "complete",
      "created_at": "2024-01-01T10:00:00",
      "completed_at": "2024-01-01T10:30:00",
      "notes": "Used pandas, 1M rows"
    }
  ],
  "lab_notebook": [
    "[2024-01-01T10:00:00] Project started",
    "[2024-01-01T10:05:00] State transition: planning → executing",
    "[2024-01-01T10:30:00] Successfully loaded 1M rows of BTC price data"
  ],
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:30:00"
}
```

### System Prompt Integration

The planner integrates with the system prompt automatically:

```python
from flow.plans import create_system_prompt
from flow.planner import ProjectStateMachine

planner = ProjectStateMachine()
# ... create project ...

# Get project context
context = planner.get_context()

# Create system prompt with project awareness
tools = registry.get_tool_definitions()
prompt = create_system_prompt(tools, project_context=context)
```

The agent now sees:
- Current project state and tasks
- Recent lab notebook entries
- Instructions to consult the plan

### Long-Term Memory

#### Vector Store Persistence

```python
from store.vects import SimpleVectorStore

# Create store with persistence
store = SimpleVectorStore(persist_path="./workspace/memory.pkl")

# Add documents
await store.add(
    id="mem_1",
    text="The capital of France is Paris",
    embedding=[0.1, 0.2, ...],  # 768-dimensional
    metadata={"category": "geography"}
)

# Automatically saves to disk
store.save()

# Load on next startup
store2 = SimpleVectorStore(persist_path="./workspace/memory.pkl")
# Automatically loads existing data
print(store2.count())  # 1
```

#### Memory Tool

```python
# Store a memory
<tool name="memory">{
  "operation": "store",
  "content": "RSI above 70 indicates overbought conditions in crypto markets",
  "metadata": {"category": "trading", "indicator": "RSI"}
}</tool>

# Search memories
<tool name="memory">{
  "operation": "search",
  "content": "overbought"
}</tool>
# Returns: "Found 1 relevant memories: RSI above 70 indicates..."
```

---

## Phase 0.4: Dynamic Tool Loading

### The Problem

Previously, the agent could:
- Use tools you provide
- Write Python code in `pyexe`

But it couldn't:
- Create reusable tools
- Avoid rewriting the same code
- Build up capabilities over time

### The Solution: Dynamic Tool Loading

The agent can now **promote Python functions into registered tools**.

### Architecture

#### 1. Skill Compiler (`core/skills.py`)

Parses Python code and generates JSON schemas automatically:

```python
from core.skills import SkillCompiler

compiler = SkillCompiler()

# Parse a Python file
functions = compiler.parse_file("workspace/my_tool.py")

# Generate schema
schema = compiler.get_function_schema("calculate_rsi")
# {
#   "name": "calculate_rsi",
#   "description": "Calculate Relative Strength Index for price data",
#   "parameters": {
#     "type": "object",
#     "properties": {
#       "prices": {"type": "array", "items": {"type": "number"}},
#       "period": {"type": "integer"}
#     },
#     "required": ["prices"]
#   }
# }
```

**Requirements**:
- Functions must have docstrings
- Parameters must have type hints
- Type hints: `str`, `int`, `float`, `bool`, `list`, `dict`, `List[T]`, `Dict[K, V]`, `Optional[T]`

#### 2. Dynamic Tool Wrapper (`tool/dynamic.py`)

Wraps skill functions as tools that execute via `pyexe`:

```python
from tool.dynamic import DynamicTool

# Create dynamic tool
tool = DynamicTool(
    func_info=func_info,  # From compiler
    skill_file="workspace/skills/my_tool.py"
)

# Tool executes in safe subprocess
result = await tool.call(tool_call)
```

**Safety**: Skills never run in the main process. They execute in an isolated `pyexe` subprocess, so crashes don't affect the server.

#### 3. Promote Skill Tool (`tool/manager.py`)

The agent uses this tool to promote skills:

```python
<tool name="promote_skill">{
  "file_path": "my_calculator.py",
  "function_name": "add_numbers",
  "tool_name": "add"
}</tool>
```

**Validation Steps**:
1. ✅ Check file exists in workspace
2. ✅ Parse function signature
3. ✅ Validate docstring present
4. ✅ Validate type hints present
5. ✅ Test syntax (compile check)
6. ✅ Copy to `workspace/skills/` (canonize)
7. ✅ Register as dynamic tool
8. ✅ Hot-reload (immediately available)

### Complete Workflow

#### Step 1: Agent Develops Code

Agent struggles through a problem using `pyexe`:

```python
<tool name="pyexe">{
  "code": "def clean_data(file):\n  import pandas as pd\n  df = pd.read_csv(file)\n  # Remove NaN\n  df = df.dropna()\n  return df"
}</tool>

# Oops, forgot to save
<tool name="pyexe">{
  "code": "def clean_data(file):\n  import pandas as pd\n  df = pd.read_csv(file)\n  df = df.dropna()\n  df.to_csv('cleaned.csv')\n  return 'Done'"
}</tool>

# Works!
```

#### Step 2: Agent Identifies Reusable Pattern

Agent realizes this is useful and should be a permanent tool.

#### Step 3: Agent Formalizes

Agent rewrites with proper structure:

```python
<tool name="write_file">{
  "path": "data_cleaner.py",
  "content": "from typing import List\nimport pandas as pd\n\ndef clean_csv(file_path: str, columns: List[str] = []) -> str:\n    \"\"\"Remove NaN values from CSV and save cleaned version.\n    \n    Args:\n        file_path: Path to input CSV file\n        columns: Optional list of columns to keep\n    \n    Returns:\n        Path to cleaned CSV file\n    \"\"\"\n    df = pd.read_csv(file_path)\n    \n    if columns:\n        df = df[columns]\n    \n    df = df.dropna()\n    \n    output_path = file_path.replace('.csv', '_cleaned.csv')\n    df.to_csv(output_path, index=False)\n    \n    return output_path\n"
}</tool>
```

#### Step 4: Agent Promotes

```python
<tool name="promote_skill">{
  "file_path": "data_cleaner.py",
  "function_name": "clean_csv",
  "tool_name": "clean_csv"
}</tool>

# Output:
# Skill promoted successfully!
# Tool Name: clean_csv
# Function: clean_csv
# Location: skills/clean_csv.py
# The tool is now available for use.
```

#### Step 5: Agent Uses New Tool

Five minutes later:

```python
User: "Clean the Ethereum price data"

<tool name="clean_csv">{
  "file_path": "eth_prices.csv"
}</tool>

# Returns: "eth_prices_cleaned.csv"
```

No code rewriting needed!

### Skills Directory

**Location**: `workspace/skills/`

**Purpose**: Permanent, canonized functions

**Behavior**:
- Auto-loaded on startup via `load_dynamic_skills()`
- Persistent across sessions
- Executed safely via `pyexe` subprocess
- Can be version controlled

**Example Structure**:
```
workspace/
  skills/
    calculate_rsi.py      # Technical indicators
    clean_csv.py          # Data cleaning
    fetch_prices.py       # API integration
    generate_report.py    # Report generation
```

### Type Hint Support

The compiler understands these Python types:

| Python Type | JSON Schema Type | Example |
|------------|------------------|---------|
| `str` | `string` | `name: str` |
| `int` | `integer` | `age: int` |
| `float` | `number` | `price: float` |
| `bool` | `boolean` | `active: bool` |
| `list`, `List` | `array` | `items: list` |
| `dict`, `Dict` | `object` | `config: dict` |
| `List[T]` | `array` with items | `prices: List[float]` |
| `Dict[K, V]` | `object` | `mapping: Dict[str, int]` |
| `Optional[T]` | Type (optional) | `name: Optional[str]` |

### Limitations

**Current** (Phase 0.4):
- Simple keyword search (not semantic yet)
- Basic type hint support (no complex generics)
- No async skills (sync functions only)
- No streaming results

**Future**:
- Semantic search with embeddings
- Advanced type hints (Union, Literal, etc.)
- Async function support
- Streaming execution results
- Skill versioning and rollback

---

## Complete Workflow Example

### Scenario: Building a Crypto Analysis System

#### 1. Plan the Project

```python
<tool name="promote_skill">{
  "file_path": "workspace/project_init.py",
  "function_name": "create_crypto_project"
}</tool>

# Agent creates project with planner
# project.json now tracks state
```

#### 2. Develop Data Loading

```python
<tool name="pyexe">{
  "code": "import pandas as pd\ndf = pd.read_csv('btc.csv')\nprint(df.head())"
}</tool>

# Works! But need to do this for ETH, SOL, etc...
```

#### 3. Promote to Tool

```python
<tool name="write_file">{
  "path": "load_crypto.py",
  "content": "def load_crypto_data(symbol: str) -> str:\n    \"\"\"Load cryptocurrency price data.\"\"\"\n    import pandas as pd\n    df = pd.read_csv(f'{symbol.lower()}.csv')\n    return f'Loaded {len(df)} bars'"
}</tool>

<tool name="promote_skill">{
  "file_path": "load_crypto.py",
  "function_name": "load_crypto_data"
}</tool>
```

#### 4. Store Insights in Memory

```python
<tool name="memory">{
  "operation": "store",
  "content": "BTC shows 200-day MA support at $28,000 level. Historical pattern suggests bounce probability > 70%.",
  "metadata": {"asset": "BTC", "timeframe": "daily"}
}</tool>
```

#### 5. Update Project Status

```python
# Agent updates task status
# Lab notebook entries added automatically
# project.json reflects current state
```

#### 6. Build More Tools

```python
# Agent creates calculate_rsi, bollinger_bands, etc.
# Each promoted to permanent skills
# Builds up capability library
```

#### 7. Future Sessions

Next day, agent has:
- ✅ Load tools for any crypto symbol
- ✅ Technical indicator calculations
- ✅ Memory of previous findings
- ✅ Project state tracking
- ✅ Growing skills library

**The agent is learning and evolving.**

---

## Configuration

### Enable/Disable Features

In `.env`:

```bash
# Phase 0.3
AGENT_ENABLE_MEMORY=true

# Phase 0.4
AGENT_ENABLE_PROMOTE_SKILL=true
AGENT_LOAD_DYNAMIC_SKILLS=true  # Load skills on startup
```

### Paths

```bash
# Project state
./workspace/project.json

# Long-term memory
./workspace/memory.pkl

# Skills library
./workspace/skills/*.py
```

## Testing

All features are thoroughly tested:

```bash
# Phase 0.3 tests (24 tests)
PYTHONPATH=. python tests/flow/test_planner.py       # 9 tests
PYTHONPATH=. python tests/store/test_vects_persist.py  # 6 tests
PYTHONPATH=. python tests/tools/test_memory.py       # 9 tests

# Phase 0.4 tests (18 tests)
PYTHONPATH=. python tests/core/test_skills.py        # 10 tests
PYTHONPATH=. python tests/tools/test_promote_skill.py  # 8 tests
```

**Total: 42 tests, all passing** ✅

## Benefits

### Phase 0.3
1. **Project Continuity**: State persists across sessions
2. **Progress Tracking**: Lab notebook documents journey
3. **Knowledge Base**: Long-term memory accumulates insights
4. **Context Awareness**: System prompt includes project status

### Phase 0.4
1. **Self-Improvement**: Agent creates its own capabilities
2. **Code Reuse**: No need to rewrite solutions
3. **Safety**: Skills run in isolated subprocess
4. **Flexibility**: Any valid Python function can become a tool
5. **Evolution**: Skill library grows over time

## What's Next?

### Potential Phase 0.5 Features
- Semantic memory search with embeddings
- Skill versioning and rollback
- Multi-agent collaboration
- Automated skill documentation
- Skill dependency management
- Performance profiling for skills

---

**The agent has crossed a threshold: It can now improve itself.**
