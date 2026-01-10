# Unified Strategy Engine Documentation

## Overview

The Unified Strategy Engine provides a consistent execution framework for trading strategies across both **backtest** and **replay** modes. This ensures that the same logic that triggers trades in backtesting is used when running strategies in replay mode, eliminating divergence and ensuring consistency.

## Key Principles

### 1. No Future Data Leakage
The engine evaluates strategies using **point-in-time** data only. At each timestamp, only data up to and including that point is available for decision-making.

### 2. Single Engine for Both Modes
The same `StrategyEngine` class is used for:
- **Backtest Mode**: Testing strategies on historical data
- **Replay Mode**: Visualizing strategy execution on data playback

### 3. Serializable Strategies
Strategies are defined in a JSON-compatible format, making them:
- Easy to save and load
- Version controllable
- Shareable across systems
- Accessible to AI agents

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Strategy Definition                   │
│  (JSON format with entry/exit conditions & parameters)  │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                   Strategy Storage                       │
│        (File-based storage in /strategies dir)          │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                   StrategyEngine                         │
│  • Loads strategy definition                            │
│  • Evaluates conditions at each bar                     │
│  • Generates entry/exit trades                          │
│  • Works identically in backtest and replay modes       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                        Results                           │
│  • List of trades (entry/exit with timestamps)          │
│  • Performance statistics                                │
│  • Ready for visualization or further analysis          │
└─────────────────────────────────────────────────────────┘
```

## Strategy Format

### Basic Structure

```json
{
  "name": "Strategy Name",
  "description": "Human-readable description",
  "entry_conditions": [
    {
      "type": "condition_type",
      "params": {
        "param1": "value1",
        "param2": "value2"
      }
    }
  ],
  "exit_conditions": [
    {
      "type": "condition_type",
      "params": {
        "param1": "value1"
      }
    }
  ],
  "parameters": {
    "custom_param1": 10,
    "custom_param2": 20
  },
  "metadata": {
    "created_at": "2024-01-01T00:00:00",
    "version": "1.0"
  }
}
```

### Condition Types

#### Price-Based Conditions

**`price_above`** - Price is above a value
```json
{
  "type": "price_above",
  "params": {
    "value": 100.0
  }
}
```

**`price_below`** - Price is below a value
```json
{
  "type": "price_below",
  "params": {
    "value": 100.0
  }
}
```

**`price_crosses_above`** - Price crosses above a value
```json
{
  "type": "price_crosses_above",
  "params": {
    "value": 100.0
  }
}
```

**`price_crosses_below`** - Price crosses below a value
```json
{
  "type": "price_crosses_below",
  "params": {
    "value": 100.0
  }
}
```

#### Indicator-Based Conditions

**`indicator_above`** - Indicator value is above a threshold
```json
{
  "type": "indicator_above",
  "params": {
    "indicator": "ma_fast",
    "value": 100.0
  }
}
```

**`indicator_below`** - Indicator value is below a threshold
```json
{
  "type": "indicator_below",
  "params": {
    "indicator": "rsi",
    "value": 30.0
  }
}
```

**`indicator_crosses_above`** - Indicator crosses above a value
```json
{
  "type": "indicator_crosses_above",
  "params": {
    "indicator": "ma_fast",
    "value": "ma_slow"
  }
}
```

**`indicator_crosses_below`** - Indicator crosses below a value
```json
{
  "type": "indicator_crosses_below",
  "params": {
    "indicator": "ma_fast",
    "value": "ma_slow"
  }
}
```

#### Logical Operators

**`and`** - All child conditions must be true
```json
{
  "type": "and",
  "children": [
    {
      "type": "price_above",
      "params": {"value": 100.0}
    },
    {
      "type": "indicator_above",
      "params": {"indicator": "rsi", "value": 50.0}
    }
  ]
}
```

**`or`** - At least one child condition must be true
```json
{
  "type": "or",
  "children": [
    {
      "type": "price_crosses_above",
      "params": {"value": 100.0}
    },
    {
      "type": "indicator_crosses_above",
      "params": {"indicator": "ma_fast", "value": "ma_slow"}
    }
  ]
}
```

**`not`** - Inverts the child condition
```json
{
  "type": "not",
  "children": [
    {
      "type": "indicator_below",
      "params": {"indicator": "rsi", "value": 30.0}
    }
  ]
}
```

## Example Strategies

### 1. Simple Moving Average Crossover

```json
{
  "name": "MA Crossover",
  "description": "Buy when fast MA crosses above slow MA, sell when it crosses below",
  "entry_conditions": [
    {
      "type": "indicator_crosses_above",
      "params": {
        "indicator": "ma_fast",
        "value": "ma_slow"
      }
    }
  ],
  "exit_conditions": [
    {
      "type": "indicator_crosses_below",
      "params": {
        "indicator": "ma_fast",
        "value": "ma_slow"
      }
    }
  ],
  "parameters": {
    "ma_fast_period": 10,
    "ma_slow_period": 20
  }
}
```

### 2. RSI Oversold/Overbought

```json
{
  "name": "RSI Mean Reversion",
  "description": "Buy when RSI is oversold, sell when overbought",
  "entry_conditions": [
    {
      "type": "indicator_crosses_below",
      "params": {
        "indicator": "rsi",
        "value": 30.0
      }
    }
  ],
  "exit_conditions": [
    {
      "type": "indicator_crosses_above",
      "params": {
        "indicator": "rsi",
        "value": 70.0
      }
    }
  ],
  "parameters": {
    "rsi_period": 14
  }
}
```

### 3. Breakout Strategy

```json
{
  "name": "Price Breakout",
  "description": "Buy on breakout above resistance, sell on breakdown below support",
  "entry_conditions": [
    {
      "type": "and",
      "children": [
        {
          "type": "price_crosses_above",
          "params": {"value": 100.0}
        },
        {
          "type": "indicator_above",
          "params": {"indicator": "volume", "value": 1000000}
        }
      ]
    }
  ],
  "exit_conditions": [
    {
      "type": "price_crosses_below",
      "params": {"value": 95.0}
    }
  ],
  "parameters": {
    "resistance_level": 100.0,
    "support_level": 95.0,
    "min_volume": 1000000
  }
}
```

## Data Format

### Input Data Structure

The engine expects data in the following format:

```python
[
    {
        "timestamp": "2024-01-01T00:00:00",  # ISO format timestamp
        "open": 100.0,                        # Opening price
        "high": 102.0,                        # High price
        "low": 99.0,                          # Low price
        "close": 101.0,                       # Closing price
        "volume": 1000000,                    # Volume
        # Pre-calculated indicators (optional)
        "ma_fast": 100.5,
        "ma_slow": 99.8,
        "rsi": 55.0,
        # Any other custom indicators...
    },
    # ... more bars
]
```

**Important Notes:**
- Indicators must be pre-calculated and included in the data
- Data should be sorted chronologically (oldest to newest)
- All bars should have consistent fields

## Usage from Python

### Saving a Strategy

```python
from core.strategy import Strategy, Condition, save_strategy

# Define conditions
entry_condition = Condition(
    type="indicator_crosses_above",
    params={"indicator": "ma_fast", "value": "ma_slow"}
)

exit_condition = Condition(
    type="indicator_crosses_below",
    params={"indicator": "ma_fast", "value": "ma_slow"}
)

# Create strategy
strategy = Strategy(
    name="MA Crossover",
    description="Simple moving average crossover strategy",
    entry_conditions=[entry_condition],
    exit_conditions=[exit_condition],
    parameters={
        "ma_fast_period": 10,
        "ma_slow_period": 20
    }
)

# Save strategy
strategy_id = save_strategy(strategy, "ma_crossover")
print(f"Saved strategy with ID: {strategy_id}")
```

### Loading and Executing a Strategy

```python
from core.strategy import load_strategy, StrategyEngine

# Load strategy
strategy = load_strategy("ma_crossover")

# Prepare data (with pre-calculated indicators)
data = [
    {
        "timestamp": "2024-01-01T00:00:00",
        "close": 100.0,
        "ma_fast": 100.2,
        "ma_slow": 99.8
    },
    # ... more data
]

# Execute in backtest mode
engine = StrategyEngine(strategy)
results = engine.execute(data, mode="backtest")

print(f"Total trades: {results['statistics']['total_trades']}")
print(f"Win rate: {results['statistics']['win_rate']:.2%}")

# Execute in replay mode (same engine!)
results_replay = engine.execute(data, mode="replay")
# Results will be identical - same engine, same logic
```

### Listing All Strategies

```python
from core.strategy import list_strategies

strategies = list_strategies()
for s in strategies:
    print(f"{s['id']}: {s['name']} - {s['description']}")
```

## Usage from Tools (Agent Access)

### Save Strategy Tool

```python
from tool.strategy import save_strategy_tool

result = save_strategy_tool({
    "name": "MA Crossover",
    "description": "Simple MA crossover",
    "entry_conditions": [
        {
            "type": "indicator_crosses_above",
            "params": {"indicator": "ma_fast", "value": "ma_slow"}
        }
    ],
    "exit_conditions": [
        {
            "type": "indicator_crosses_below",
            "params": {"indicator": "ma_fast", "value": "ma_slow"}
        }
    ],
    "parameters": {
        "ma_fast_period": 10,
        "ma_slow_period": 20
    }
})

if result["success"]:
    print(f"Strategy saved with ID: {result['strategy_id']}")
```

### Execute Strategy Tool

```python
from tool.strategy import execute_strategy_tool

result = execute_strategy_tool({
    "strategy_id": "ma_crossover",
    "data": [
        # ... your data here
    ],
    "mode": "backtest"  # or "replay"
})

if result["success"]:
    trades = result["results"]["trades"]
    stats = result["results"]["statistics"]
    print(f"Executed {len(trades)} trades")
    print(f"Win rate: {stats['win_rate']:.2%}")
```

### List Strategies Tool

```python
from tool.strategy import list_strategies_tool

result = list_strategies_tool()
if result["success"]:
    print(f"Found {result['count']} strategies:")
    for s in result["strategies"]:
        print(f"  - {s['id']}: {s['name']}")
```

## Usage from API

### POST /strategies - Save Strategy

```bash
curl -X POST http://localhost:8000/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MA Crossover",
    "description": "Simple moving average crossover",
    "entry_conditions": [...],
    "exit_conditions": [...],
    "parameters": {...}
  }'
```

Response:
```json
{
  "success": true,
  "strategy_id": "ma_crossover",
  "message": "Strategy saved successfully"
}
```

### GET /strategies - List Strategies

```bash
curl http://localhost:8000/strategies
```

Response:
```json
{
  "success": true,
  "strategies": [
    {
      "id": "ma_crossover",
      "name": "MA Crossover",
      "description": "Simple moving average crossover",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "count": 1
}
```

### GET /strategies/{id} - Get Strategy

```bash
curl http://localhost:8000/strategies/ma_crossover
```

Response:
```json
{
  "success": true,
  "strategy": {
    "name": "MA Crossover",
    "description": "...",
    "entry_conditions": [...],
    "exit_conditions": [...],
    "parameters": {...}
  }
}
```

### POST /strategies/{id}/execute - Execute Strategy

```bash
curl -X POST http://localhost:8000/strategies/ma_crossover/execute \
  -H "Content-Type: application/json" \
  -d '{
    "data": [...],
    "mode": "backtest"
  }'
```

Response:
```json
{
  "success": true,
  "results": {
    "strategy": "MA Crossover",
    "mode": "backtest",
    "trades": [
      {
        "timestamp": "2024-01-01T00:00:00",
        "type": "entry",
        "price": 100.5,
        "reason": "Entry condition met"
      },
      {
        "timestamp": "2024-01-02T00:00:00",
        "type": "exit",
        "price": 102.0,
        "reason": "Exit condition met"
      }
    ],
    "statistics": {
      "total_trades": 1,
      "winning_trades": 1,
      "losing_trades": 0,
      "win_rate": 1.0
    }
  }
}
```

## Integration with Continuous Contracts

For agents working with continuous contract JSON data:

```python
import json
from core.strategy import load_strategy, StrategyEngine

# Load continuous contract data
with open("contract_data.json", "r") as f:
    contract_data = json.load(f)

# Ensure data has required fields and indicators
# (You may need to calculate indicators first)
for bar in contract_data:
    # Calculate any missing indicators
    # bar["ma_fast"] = calculate_ma(...)
    # bar["ma_slow"] = calculate_ma(...)
    pass

# Load and execute strategy
strategy = load_strategy("your_strategy_id")
engine = StrategyEngine(strategy)
results = engine.execute(contract_data, mode="backtest")

# Process results
print(f"Strategy: {results['strategy']}")
print(f"Total trades: {results['statistics']['total_trades']}")
for trade in results["trades"]:
    print(f"{trade['type']} at {trade['timestamp']}: ${trade['price']}")
```

## Best Practices

### 1. Pre-calculate Indicators
Always calculate indicators before executing the strategy. The engine does not calculate indicators - it only evaluates conditions based on data provided.

### 2. Use Consistent Field Names
Ensure indicator names in your conditions match the field names in your data exactly.

### 3. Test in Backtest First
Always test strategies in backtest mode on historical data before using in replay mode.

### 4. Version Your Strategies
Use the metadata field to track strategy versions and changes.

### 5. Document Your Conditions
Use clear, descriptive condition types and parameters. Future you (or agents) will appreciate it.

## Troubleshooting

### Problem: No trades generated
**Solution**: Check that:
- Data has the required indicator fields
- Conditions are correctly specified
- Data is sorted chronologically
- There are enough bars (some conditions need previous bars)

### Problem: Indicators not found
**Solution**: Ensure all indicators referenced in conditions are present in the data with exact field name matches.

### Problem: Different results in backtest vs replay
**Solution**: This should NOT happen - it's a bug! The engine uses identical logic. Please report this issue.

## Extending the Engine

### Adding New Condition Types

To add a new condition type, modify `core/strategy.py`:

1. Add to `ConditionType` enum:
```python
class ConditionType(Enum):
    # ... existing types
    YOUR_NEW_TYPE = "your_new_type"
```

2. Add evaluation logic in `_evaluate_condition()`:
```python
elif ctype == ConditionType.YOUR_NEW_TYPE.value:
    # Your evaluation logic here
    return True  # or False based on condition
```

## Summary

The Unified Strategy Engine provides:
- ✅ Consistent execution across backtest and replay modes
- ✅ No future data leakage (point-in-time evaluation)
- ✅ Serializable, version-controlled strategy definitions
- ✅ Easy integration for AI agents via tools and API
- ✅ Extensible condition system
- ✅ File-based storage (no database required)

For questions or issues, please refer to the source code in `core/strategy.py` and `tool/strategy.py`.
