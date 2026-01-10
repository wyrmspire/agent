# Strategy Engine Integration Guide

## Overview

This guide explains how to integrate the Unified Strategy Engine with existing workflows for trading strategy development, backtesting, and replay visualization.

## Workflow Integration

### Previous Workflow (Divergent)

**Before:**
```
┌─────────────────────┐
│  Strategy Creator   │
│  (Entry/Exit Logic) │
└──────────┬──────────┘
           │
           ├──────────────────────────┐
           │                          │
           ▼                          ▼
    ┌──────────┐              ┌──────────────┐
    │ Backtest │              │ Replay Mode  │
    │  Engine  │              │ (Diverged!)  │
    └──────────┘              └──────────────┘
         │                           │
         ▼                           ▼
    Results (🔍)              Visualization (👁️)
```

**Problem:** Different logic for backtest and replay → divergence over time

### New Unified Workflow

**After:**
```
┌─────────────────────┐
│  Strategy Creator   │
│  (Entry/Exit Logic) │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────────┐
    │  Save Strategy   │ ← Press 💾 (Magnifying Glass button)
    │   to Registry    │
    └──────────┬───────┘
               │
               ▼
    ┌──────────────────────┐
    │  Unified Engine      │ ← Same logic for both!
    │  (StrategyEngine)    │
    └─────┬───────────┬────┘
          │           │
          ▼           ▼
    ┌─────────┐   ┌──────────┐
    │Backtest │   │  Replay  │
    │  Mode   │   │   Mode   │
    └─────────┘   └──────────┘
         │             │
         ▼             ▼
    Results (🔍)  Viz (👁️)
```

**Solution:** Single engine ensures consistency

## Button Workflow

### Magnifying Glass Button (💾 Save)

**Before:** Created new trigger logic for scanner
**After:** Saves strategy to registry

```python
# When user presses "Save" (magnifying glass):
def on_save_button_click(strategy_definition):
    """Save strategy instead of creating new trigger logic."""
    
    # Convert strategy definition to unified format
    unified_strategy = {
        "name": strategy_definition["name"],
        "description": strategy_definition["description"],
        "entry_conditions": convert_conditions(strategy_definition["entry"]),
        "exit_conditions": convert_conditions(strategy_definition["exit"]),
        "parameters": strategy_definition["params"]
    }
    
    # Save to registry
    from tool.strategy import save_strategy_tool
    result = save_strategy_tool(unified_strategy)
    
    if result["success"]:
        strategy_id = result["strategy_id"]
        print(f"✓ Strategy saved! ID: {strategy_id}")
        print(f"  Now available in scanner dropdown")
    
    return strategy_id
```

### Scanner Dropdown

**Before:** List of scanners with separate logic
**After:** List of saved strategies

```python
def get_scanner_dropdown_options():
    """Get list of strategies for scanner dropdown."""
    from tool.strategy import list_strategies_tool
    
    result = list_strategies_tool()
    
    if result["success"]:
        # Convert to dropdown format
        options = [
            {
                "id": s["id"],
                "label": s["name"],
                "description": s["description"]
            }
            for s in result["strategies"]
        ]
        return options
    
    return []
```

### Eyeball Button (👁️ Visualize)

**Before:** Used separate replay logic
**After:** Uses unified engine with mode="replay"

```python
def on_eyeball_button_click(strategy_id, data):
    """Plot trades on chart using replay mode."""
    from tool.strategy import execute_strategy_tool
    
    # Execute in replay mode (same engine as backtest!)
    result = execute_strategy_tool({
        "strategy_id": strategy_id,
        "data": data,
        "mode": "replay"
    })
    
    if result["success"]:
        trades = result["results"]["trades"]
        
        # Plot trades on chart
        for trade in trades:
            plot_trade_marker(
                timestamp=trade["timestamp"],
                price=trade["price"],
                type=trade["type"],  # "entry" or "exit"
                color="green" if trade["type"] == "entry" else "red"
            )
    
    return trades
```

## Migration Path

### Step 1: Convert Existing Strategy Creator Output

If you have existing strategy creator that outputs in a different format:

```python
def convert_legacy_strategy(legacy_strategy):
    """Convert legacy strategy format to unified format."""
    
    # Map legacy condition types to unified types
    condition_map = {
        "price_above": "price_above",
        "price_below": "price_below",
        "ma_cross_up": "indicator_crosses_above",
        "ma_cross_down": "indicator_crosses_below",
        # ... add your mappings
    }
    
    entry_conditions = []
    for cond in legacy_strategy["entry_triggers"]:
        entry_conditions.append({
            "type": condition_map.get(cond["type"], cond["type"]),
            "params": cond["params"]
        })
    
    exit_conditions = []
    for cond in legacy_strategy["exit_triggers"]:
        exit_conditions.append({
            "type": condition_map.get(cond["type"], cond["type"]),
            "params": cond["params"]
        })
    
    return {
        "name": legacy_strategy["name"],
        "description": legacy_strategy.get("description", ""),
        "entry_conditions": entry_conditions,
        "exit_conditions": exit_conditions,
        "parameters": legacy_strategy.get("parameters", {})
    }
```

### Step 2: Update Backtest Code

Replace old backtest logic:

```python
# OLD - Don't use this anymore
def old_backtest(strategy, data):
    # ... custom backtest logic ...
    pass

# NEW - Use unified engine
from core.strategy import StrategyEngine

def new_backtest(strategy, data):
    """Use unified engine for backtesting."""
    engine = StrategyEngine(strategy)
    results = engine.execute(data, mode="backtest")
    return results
```

### Step 3: Update Replay Code

Replace old replay logic:

```python
# OLD - Don't use this anymore
def old_replay(scanner_config, data):
    # ... separate replay logic (DIVERGED!) ...
    pass

# NEW - Use unified engine
from core.strategy import load_strategy, StrategyEngine

def new_replay(strategy_id, data):
    """Use unified engine for replay."""
    strategy = load_strategy(strategy_id)
    engine = StrategyEngine(strategy)
    results = engine.execute(data, mode="replay")
    return results
```

## Agent Integration

For agents working with strategies programmatically:

```python
# Example: Agent creates and tests a strategy

# 1. Agent generates strategy based on analysis
strategy_definition = {
    "name": "Agent Generated MA Strategy",
    "description": "Created by analysis of price patterns",
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
}

# 2. Save the strategy
from tool.strategy import save_strategy_tool
result = save_strategy_tool(strategy_definition)
strategy_id = result["strategy_id"]

# 3. Load contract data
import json
with open("continuous_contract.json", "r") as f:
    contract_data = json.load(f)

# 4. Calculate indicators (agent can do this)
# ... indicator calculation code ...

# 5. Execute strategy
from tool.strategy import execute_strategy_tool
backtest_results = execute_strategy_tool({
    "strategy_id": strategy_id,
    "data": contract_data,
    "mode": "backtest"
})

# 6. Analyze results
stats = backtest_results["results"]["statistics"]
if stats["win_rate"] > 0.6:
    print(f"✓ Good strategy! Win rate: {stats['win_rate']:.1%}")
else:
    print(f"✗ Poor performance. Win rate: {stats['win_rate']:.1%}")
    # Agent can iterate and improve...
```

## Continuous Contract Integration

Working with continuous contract JSON files:

```python
import json
from core.strategy import load_strategy, StrategyEngine

def run_strategy_on_contract(strategy_id, contract_file):
    """Execute a saved strategy on continuous contract data.
    
    Args:
        strategy_id: ID of saved strategy
        contract_file: Path to continuous contract JSON
    
    Returns:
        Trade results and statistics
    """
    
    # 1. Load contract data
    with open(contract_file, "r") as f:
        data = json.load(f)
    
    # 2. Ensure data has required fields
    required_fields = ["timestamp", "close"]
    for bar in data:
        for field in required_fields:
            if field not in bar:
                raise ValueError(f"Missing required field: {field}")
    
    # 3. Calculate indicators if needed
    # (This depends on what indicators your strategy uses)
    # Example: calculate_indicators(data)
    
    # 4. Load strategy
    strategy = load_strategy(strategy_id)
    
    # 5. Execute
    engine = StrategyEngine(strategy)
    results = engine.execute(data, mode="backtest")
    
    # 6. Return results
    return {
        "trades": results["trades"],
        "statistics": results["statistics"],
        "strategy_name": strategy.name
    }

# Usage
results = run_strategy_on_contract("ma_crossover", "ES_continuous.json")
print(f"Strategy: {results['strategy_name']}")
print(f"Total trades: {results['statistics']['total_trades']}")
print(f"Win rate: {results['statistics']['win_rate']:.1%}")
```

## Future Development

The unified strategy engine enables:

1. **Agent Improvement**: Agents can load, modify, and re-save strategies
2. **Version Control**: Strategies are JSON files → can be git tracked
3. **Sharing**: Export/import strategies between systems
4. **Optimization**: Agents can optimize parameters systematically
5. **Backtesting Suite**: Run multiple strategies on same data
6. **Live Trading**: Same engine can be used (with real-time data)

## Tags and Metadata

Strategies support custom metadata for organization:

```python
# When saving, add custom tags/metadata
strategy_with_tags = {
    "name": "My Strategy",
    "description": "...",
    "entry_conditions": [...],
    "exit_conditions": [...],
    "parameters": {...},
    "metadata": {
        "tags": ["momentum", "trend-following", "tested"],
        "author": "agent_v1",
        "tested_on": "ES_continuous_2020-2024",
        "performance": {
            "win_rate": 0.62,
            "max_drawdown": 0.15
        },
        "version": "1.0"
    }
}

# Agents can filter by tags
def get_momentum_strategies():
    strategies = list_strategies()
    return [
        s for s in strategies 
        if "momentum" in s.get("metadata", {}).get("tags", [])
    ]
```

## Testing Your Integration

Verify the integration works:

```python
def test_integration():
    """Test that backtest and replay produce same results."""
    from tool.strategy import save_strategy_tool, execute_strategy_tool
    
    # 1. Create test strategy
    strategy = {
        "name": "Integration Test",
        "description": "Testing consistency",
        "entry_conditions": [
            {"type": "price_above", "params": {"value": 100.0}}
        ],
        "exit_conditions": [
            {"type": "price_below", "params": {"value": 100.0}}
        ],
        "parameters": {}
    }
    
    result = save_strategy_tool(strategy)
    strategy_id = result["strategy_id"]
    
    # 2. Create test data
    data = [
        {"timestamp": "2024-01-01T00:00:00", "close": 95.0},
        {"timestamp": "2024-01-01T01:00:00", "close": 105.0},
        {"timestamp": "2024-01-01T02:00:00", "close": 95.0},
    ]
    
    # 3. Run in both modes
    backtest = execute_strategy_tool({
        "strategy_id": strategy_id,
        "data": data,
        "mode": "backtest"
    })
    
    replay = execute_strategy_tool({
        "strategy_id": strategy_id,
        "data": data,
        "mode": "replay"
    })
    
    # 4. Verify results match
    assert len(backtest["results"]["trades"]) == len(replay["results"]["trades"])
    print("✓ Integration test passed! Backtest and replay are unified.")
    
    return True

# Run the test
test_integration()
```

## Summary

The unified strategy engine simplifies your workflow:

1. **Save** strategies instead of creating new trigger logic (💾)
2. **Scanner dropdown** now lists saved strategies
3. **Replay mode** uses same engine as backtest (👁️)
4. **Agents** can use strategies via simple API
5. **No divergence** between backtest and replay

For detailed API documentation, see `docts/strategy_engine.md`
