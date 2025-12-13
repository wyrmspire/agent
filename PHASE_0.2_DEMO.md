# Phase 0.2: Data Scientist Architecture Demo

This document demonstrates the new Phase 0.2 features that transform the agent into a "Financial Analyst workstation."

## Overview

Phase 0.2 adds:
1. **System Hardening** - Robust parsing, validation, resource limits, and traceability
2. **Workspace Isolation** - Safe "jail" for generated data separate from source code
3. **Data Inspection** - Peek at large datasets without loading them fully
4. **Persistent Python** - Stateful execution for data analysis workflows

## 1. System Hardening

### Tag-Based Parsing (Robust for Multi-line Code)

The model can now use XML-style tags for tool calls that handle complex inputs:

```python
# Old (fragile):
# shell "cd workspace && python train.py"

# New (robust):
<tool name="pyexe">
{
  "code": "import pandas as pd\ndf = pd.read_csv('prices.csv')\nprint(df.head())"
}
</tool>
```

This handles:
- Multi-line Python code
- Nested quotes
- Special characters

### Runtime Validation

All tool arguments are now validated against JSON schemas before execution:

```python
# If model sends wrong type:
# {"path": 123}  # Should be string

# Result: Clean error message
# "Invalid arguments: 123 is not of type 'string'"
```

### Resource Limits (Circuit Breaker)

The workspace monitors resources to prevent crashes:

```python
from core.sandb import get_default_workspace

ws = get_default_workspace()

# Check before expensive operations
ws.check_resources()  # Raises ResourceLimitError if:
                      # - Workspace > 5GB
                      # - RAM < 10% free

# Get stats
stats = ws.get_resource_stats()
# {
#   "workspace_size_gb": 0.5,
#   "workspace_limit_gb": 5.0,
#   "ram_used_percent": 65.0,
#   "ram_free_percent": 35.0
# }
```

### Traceability (Run IDs)

Every execution now has a unique run_id for debugging:

```python
from core.state import generate_run_id

run_id = generate_run_id()
# "run_1702473600_a1b2c3d4"

# This run_id flows through:
# - All log messages
# - Tool executions
# - File operations
# - Error traces

# To debug a failed run:
# grep "run_1702473600_a1b2c3d4" logs/agent.log
```

## 2. Workspace Isolation

The workspace is a "jail" that keeps generated data separate from source code.

```python
from core.sandb import get_default_workspace

ws = get_default_workspace()

# All file operations are within ./workspace/
safe_path = ws.resolve("data/prices.csv")
# /path/to/agent/workspace/data/prices.csv

# Attempts to escape are blocked
ws.resolve("../servr/api.py")
# WorkspaceError: Path is outside workspace

# Access to sensitive dirs is blocked
ws.resolve("../boot/setup.py")
# WorkspaceError: Access to 'boot/' is blocked for safety
```

### File Tools with Workspace

File tools now automatically use the workspace:

```python
# write_file creates files in workspace only
<tool name="write_file">
{
  "path": "data/synthetic_prices.csv",
  "content": "timestamp,open,high,low,close\n..."
}
</tool>
# Creates: ./workspace/data/synthetic_prices.csv

# read_file only reads from workspace
<tool name="read_file">
{
  "path": "data/synthetic_prices.csv"
}
</tool>
# Reads from: ./workspace/data/synthetic_prices.csv
```

## 3. Data Inspection (data_view)

The `data_view` tool lets you peek at large datasets without loading them fully.

### Get Column Names

```python
<tool name="data_view">
{
  "path": "prices_1m_bars.csv",
  "operation": "columns"
}
</tool>

# Output:
# Columns (6):
#   1. timestamp
#   2. open
#   3. high
#   4. low
#   5. close
#   6. volume
```

### Peek at First N Rows

```python
<tool name="data_view">
{
  "path": "prices_1m_bars.csv",
  "operation": "head",
  "n_rows": 5
}
</tool>

# Output: Formatted table with first 5 rows
```

### Get Shape (Row/Column Count)

```python
<tool name="data_view">
{
  "path": "prices_1m_bars.csv",
  "operation": "shape"
}
</tool>

# Output:
# Shape: 1000000 rows × 6 columns
# Columns: timestamp, open, high, low, close, volume
```

### View Last N Rows

```python
<tool name="data_view">
{
  "path": "prices_1m_bars.csv",
  "operation": "tail",
  "n_rows": 5
}
</tool>

# Output: Last 5 rows
```

## 4. Persistent Python (pyexe)

The `pyexe` tool maintains a persistent Python session, like Jupyter.

### Load Data Once, Use Multiple Times

```python
# Step 1: Load data (takes time)
<tool name="pyexe">
{
  "code": "import pandas as pd\ndf = pd.read_csv('prices_1m_bars.csv')\nprint(f'Loaded {len(df)} rows')"
}
</tool>

# Output: "Loaded 1000000 rows"

# Step 2: Analyze (df is still in memory!)
<tool name="pyexe">
{
  "code": "print(df.describe())"
}
</tool>

# Step 3: More analysis (still has df!)
<tool name="pyexe">
{
  "code": "print(df['close'].mean())"
}
</tool>
```

### Train a Model Without Crashing the LLM Server

The Python subprocess runs **isolated** from the model server:

```python
<tool name="pyexe">
{
  "code": "import torch\nimport torch.nn as nn\n\n# This runs in a separate process\n# If it crashes the GPU, the model server stays up\n\nmodel = nn.Sequential(\n    nn.Linear(10, 50),\n    nn.ReLU(),\n    nn.Linear(50, 1)\n)\n\nprint('Model created')"
}
</tool>
```

### Reset Session

```python
<tool name="pyexe">
{
  "code": "print('New task')",
  "reset": true
}
</tool>

# Clears all variables and starts fresh
```

## Complete Workflow Example

Here's how the agent analyzes financial data:

```python
# 1. Check what's in workspace
<tool name="list_files">
{"path": "."}
</tool>

# 2. Peek at data structure
<tool name="data_view">
{
  "path": "btc_1m_bars.csv",
  "operation": "shape"
}
</tool>
# Output: "Shape: 525600 rows × 6 columns"

# 3. Load data in persistent Python
<tool name="pyexe">
{
  "code": "import pandas as pd\nimport numpy as np\n\ndf = pd.read_csv('btc_1m_bars.csv')\nprint(f'Loaded {len(df)} bars')\nprint(df.head())"
}
</tool>

# 4. Analyze price patterns
<tool name="pyexe">
{
  "code": "# Calculate returns\ndf['returns'] = df['close'].pct_change()\nprint('Mean return:', df['returns'].mean())\nprint('Volatility:', df['returns'].std())"
}
</tool>

# 5. Create synthetic data
<tool name="pyexe">
{
  "code": "# Generate synthetic price action\nsynthetic = pd.DataFrame({\n    'timestamp': pd.date_range('2024-01-01', periods=1000, freq='1min'),\n    'close': 100 + np.cumsum(np.random.randn(1000) * 0.5)\n})\n\nsynthetic.to_csv('synthetic_prices.csv', index=False)\nprint(f'Generated {len(synthetic)} synthetic bars')"
}
</tool>

# 6. Verify output
<tool name="data_view">
{
  "path": "synthetic_prices.csv",
  "operation": "head",
  "n_rows": 10
}
</tool>
```

## Benefits

1. **Safety**: Workspace isolation prevents accidents with source code
2. **Efficiency**: Load data once, analyze multiple times
3. **Scalability**: Inspect million-row datasets without context limits
4. **Reliability**: Tag-based parsing handles complex code, validation catches errors early
5. **Debuggability**: Run IDs make it easy to trace execution
6. **Stability**: Resource limits prevent system crashes

## Configuration

Enable/disable features in `.env`:

```bash
# Model configuration
AGENT_MODEL_PATH=/path/to/model

# Tool configuration
AGENT_ENABLE_FILES=true
AGENT_ENABLE_DATA_VIEW=true
AGENT_ENABLE_PYEXE=true

# Resource limits (in core/sandb.py)
# - Max workspace size: 5GB
# - Min free RAM: 10%
```

## Testing

All features are thoroughly tested:

```bash
# Run all tests
pytest tests/

# Test workspace isolation
pytest tests/core/test_sandb.py

# Test file tools with workspace
pytest tests/tools/test_files_workspace.py

# Test data view
pytest tests/tools/test_dview.py
```

## Architecture

```
agent/
├── workspace/          # Isolated data directory (THE JAIL)
│   ├── data/
│   │   └── prices.csv
│   └── models/
│       └── trained_cnn.pth
├── servr/             # Model server (PROTECTED)
│   └── api.py
├── core/
│   └── sandb.py       # Workspace manager
├── tool/
│   ├── files.py       # Workspace-aware file ops
│   ├── dview.py       # Data inspection
│   └── pyexe.py       # Persistent Python
└── boot/
    └── setup.py       # Centralized config
```

The agent can now:
- Generate massive datasets in `workspace/data/`
- Train models using `pyexe` without crashing the server
- Inspect datasets efficiently with `data_view`
- Keep everything isolated from source code

This transforms it from "Chatbot that can read files" to "Financial Analyst workstation."
