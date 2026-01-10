# Saved Strategies

This directory contains saved trading strategies in JSON format.

## What are these files?

Each `.json` file represents a complete trading strategy with:
- Entry conditions (when to enter a trade)
- Exit conditions (when to exit a trade)
- Parameters (strategy settings)
- Metadata (creation date, version, etc.)

## How do I use them?

### From Python

```python
from core.strategy import load_strategy, StrategyEngine

# Load a strategy
strategy = load_strategy("ma_crossover")

# Execute on your data
engine = StrategyEngine(strategy)
results = engine.execute(your_data, mode="backtest")
```

### From Tools (Agent)

```python
from tool.strategy import execute_strategy_tool

# Execute a saved strategy
result = execute_strategy_tool({
    "strategy_id": "ma_crossover",
    "data": your_data,
    "mode": "backtest"  # or "replay"
})
```

### From API

```bash
# Execute a strategy via HTTP
curl -X POST http://localhost:8000/strategies/ma_crossover/execute \
  -H "Content-Type: application/json" \
  -d '{
    "data": [...],
    "mode": "backtest"
  }'
```

## Strategy Format

Each strategy JSON has this structure:

```json
{
  "name": "Strategy Name",
  "description": "What the strategy does",
  "entry_conditions": [
    {
      "type": "condition_type",
      "params": {...}
    }
  ],
  "exit_conditions": [
    {
      "type": "condition_type",
      "params": {...}
    }
  ],
  "parameters": {
    "custom_param": value
  },
  "metadata": {
    "created_at": "ISO timestamp",
    "version": "1.0"
  }
}
```

## Available Condition Types

- `price_above` - Price is above a value
- `price_below` - Price is below a value
- `price_crosses_above` - Price crosses above a value
- `price_crosses_below` - Price crosses below a value
- `indicator_above` - Indicator is above a value
- `indicator_below` - Indicator is below a value
- `indicator_crosses_above` - Indicator crosses above another indicator or value
- `indicator_crosses_below` - Indicator crosses below another indicator or value
- `and` - Logical AND (all child conditions must be true)
- `or` - Logical OR (at least one child condition must be true)
- `not` - Logical NOT (inverts child condition)

## Key Feature: Unified Engine

The same engine executes strategies in both **backtest** and **replay** modes, ensuring:
- ✅ Consistent results
- ✅ No future data leakage
- ✅ Same trade triggers in both modes

## Documentation

For detailed documentation, see:
- `docts/strategy_engine.md` - Complete API reference
- `docts/strategy_integration.md` - Integration guide
- `examples/strategy_demo.py` - Working examples

## Example Strategies in This Directory

- `ma_crossover.json` - Moving average crossover strategy
- `rsi_mean_reversion.json` - RSI-based mean reversion
- `multi_condition_breakout.json` - Complex multi-condition strategy

## Creating New Strategies

You can create strategies in three ways:

1. **Via Python:**
```python
from core.strategy import Strategy, Condition, save_strategy

strategy = Strategy(
    name="My Strategy",
    description="...",
    entry_conditions=[...],
    exit_conditions=[...],
    parameters={...}
)

save_strategy(strategy, "my_strategy")
```

2. **Via Tool:**
```python
from tool.strategy import save_strategy_tool

save_strategy_tool({
    "name": "My Strategy",
    "entry_conditions": [...],
    "exit_conditions": [...],
    "parameters": {...}
})
```

3. **Manually:** Create a JSON file following the format above.

## Version Control

These JSON files can (and should) be version controlled with git!

```bash
git add strategies/my_new_strategy.json
git commit -m "Add new trading strategy"
```

This allows you to:
- Track strategy evolution
- Collaborate on strategy development
- Rollback to previous versions
- Share strategies across teams

## Notes

- Strategies require pre-calculated indicators in your data
- All timestamps should be in ISO 8601 format
- The engine evaluates conditions point-in-time (no lookahead)
- Strategies are immutable once saved (create new version if needed)
