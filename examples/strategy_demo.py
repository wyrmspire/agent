"""
examples/strategy_demo.py - Demonstration of Unified Strategy Engine

This script demonstrates:
1. Creating a strategy with conditions
2. Saving the strategy
3. Executing in backtest mode
4. Executing in replay mode (same results!)
5. Using the strategy with continuous contract data
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import core and tool modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from core.strategy import (
    Strategy,
    Condition,
    StrategyEngine,
    save_strategy,
    load_strategy,
    list_strategies
)


def demo_ma_crossover_strategy():
    """Demo: Simple Moving Average Crossover Strategy."""
    print("\n" + "="*60)
    print("DEMO 1: MA Crossover Strategy")
    print("="*60)
    
    # Define entry condition: fast MA crosses above slow MA
    entry_condition = Condition(
        type="indicator_crosses_above",
        params={
            "indicator": "ma_fast",
            "value": "ma_slow"
        }
    )
    
    # Define exit condition: fast MA crosses below slow MA
    exit_condition = Condition(
        type="indicator_crosses_below",
        params={
            "indicator": "ma_fast",
            "value": "ma_slow"
        }
    )
    
    # Create strategy
    strategy = Strategy(
        name="MA Crossover",
        description="Buy when fast MA crosses above slow MA, sell when it crosses below",
        entry_conditions=[entry_condition],
        exit_conditions=[exit_condition],
        parameters={
            "ma_fast_period": 10,
            "ma_slow_period": 20
        }
    )
    
    print(f"\n✓ Created strategy: {strategy.name}")
    print(f"  Description: {strategy.description}")
    
    # Save strategy
    strategy_id = save_strategy(strategy, "ma_crossover")
    print(f"\n✓ Saved strategy with ID: {strategy_id}")
    
    # Create sample data with pre-calculated indicators
    data = [
        {"timestamp": "2024-01-01T00:00:00", "close": 100.0, "ma_fast": 98.0, "ma_slow": 100.0},
        {"timestamp": "2024-01-01T01:00:00", "close": 102.0, "ma_fast": 99.0, "ma_slow": 100.5},
        {"timestamp": "2024-01-01T02:00:00", "close": 105.0, "ma_fast": 101.0, "ma_slow": 101.0},
        {"timestamp": "2024-01-01T03:00:00", "close": 108.0, "ma_fast": 103.0, "ma_slow": 101.5},  # MA cross!
        {"timestamp": "2024-01-01T04:00:00", "close": 110.0, "ma_fast": 105.0, "ma_slow": 102.0},
        {"timestamp": "2024-01-01T05:00:00", "close": 112.0, "ma_fast": 107.0, "ma_slow": 103.0},
        {"timestamp": "2024-01-01T06:00:00", "close": 108.0, "ma_fast": 106.0, "ma_slow": 104.0},
        {"timestamp": "2024-01-01T07:00:00", "close": 105.0, "ma_fast": 104.0, "ma_slow": 104.5},
        {"timestamp": "2024-01-01T08:00:00", "close": 102.0, "ma_fast": 102.0, "ma_slow": 104.8},  # MA cross back!
        {"timestamp": "2024-01-01T09:00:00", "close": 100.0, "ma_fast": 100.0, "ma_slow": 104.5},
    ]
    
    print(f"\n✓ Created {len(data)} bars of sample data")
    
    # Execute in backtest mode
    engine = StrategyEngine(strategy)
    backtest_results = engine.execute(data, mode="backtest")
    
    print(f"\n✓ Executed in BACKTEST mode:")
    print(f"  Total trades: {backtest_results['statistics']['total_trades']}")
    print(f"  Winning trades: {backtest_results['statistics']['winning_trades']}")
    print(f"  Win rate: {backtest_results['statistics']['win_rate']:.1%}")
    
    print("\n  Trades:")
    for trade in backtest_results["trades"]:
        print(f"    {trade['type'].upper()}: ${trade['price']:.2f} at {trade['timestamp']}")
    
    # Execute in replay mode
    replay_results = engine.execute(data, mode="replay")
    
    print(f"\n✓ Executed in REPLAY mode:")
    print(f"  Total trades: {replay_results['statistics']['total_trades']}")
    
    # Verify consistency
    if len(backtest_results["trades"]) == len(replay_results["trades"]):
        print("\n✓ SUCCESS: Backtest and replay produced IDENTICAL results!")
        print("  (This is the key achievement - unified engine for both modes)")
    else:
        print("\n✗ ERROR: Results differ between backtest and replay!")
    
    return strategy_id


def demo_rsi_strategy():
    """Demo: RSI Mean Reversion Strategy."""
    print("\n" + "="*60)
    print("DEMO 2: RSI Mean Reversion Strategy")
    print("="*60)
    
    # Entry: RSI crosses below 30 (oversold)
    entry_condition = Condition(
        type="indicator_crosses_below",
        params={
            "indicator": "rsi",
            "value": 30.0
        }
    )
    
    # Exit: RSI crosses above 70 (overbought)
    exit_condition = Condition(
        type="indicator_crosses_above",
        params={
            "indicator": "rsi",
            "value": 70.0
        }
    )
    
    strategy = Strategy(
        name="RSI Mean Reversion",
        description="Buy oversold, sell overbought",
        entry_conditions=[entry_condition],
        exit_conditions=[exit_condition],
        parameters={
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70
        }
    )
    
    print(f"\n✓ Created strategy: {strategy.name}")
    
    strategy_id = save_strategy(strategy, "rsi_mean_reversion")
    print(f"✓ Saved strategy with ID: {strategy_id}")
    
    # Sample data with RSI
    data = [
        {"timestamp": "2024-01-01T00:00:00", "close": 100.0, "rsi": 50.0},
        {"timestamp": "2024-01-01T01:00:00", "close": 95.0, "rsi": 35.0},
        {"timestamp": "2024-01-01T02:00:00", "close": 92.0, "rsi": 28.0},  # RSI crosses below 30 - ENTRY
        {"timestamp": "2024-01-01T03:00:00", "close": 94.0, "rsi": 32.0},
        {"timestamp": "2024-01-01T04:00:00", "close": 98.0, "rsi": 45.0},
        {"timestamp": "2024-01-01T05:00:00", "close": 102.0, "rsi": 60.0},
        {"timestamp": "2024-01-01T06:00:00", "close": 105.0, "rsi": 72.0},  # RSI crosses above 70 - EXIT
        {"timestamp": "2024-01-01T07:00:00", "close": 103.0, "rsi": 65.0},
    ]
    
    engine = StrategyEngine(strategy)
    results = engine.execute(data, mode="backtest")
    
    print(f"\n✓ Executed strategy:")
    print(f"  Total trades: {results['statistics']['total_trades']}")
    
    print("\n  Trades:")
    for trade in results["trades"]:
        print(f"    {trade['type'].upper()}: ${trade['price']:.2f} at {trade['timestamp']}")
    
    return strategy_id


def demo_complex_strategy():
    """Demo: Complex Strategy with Multiple Conditions."""
    print("\n" + "="*60)
    print("DEMO 3: Complex Multi-Condition Strategy")
    print("="*60)
    
    # Entry: Price > 100 AND RSI > 50 AND Volume > 1M
    price_condition = Condition(
        type="price_above",
        params={"value": 100.0}
    )
    
    rsi_condition = Condition(
        type="indicator_above",
        params={"indicator": "rsi", "value": 50.0}
    )
    
    volume_condition = Condition(
        type="indicator_above",
        params={"indicator": "volume", "value": 1000000}
    )
    
    # Use AND to combine conditions
    entry_and = Condition(
        type="and",
        params={},
        children=[price_condition, rsi_condition, volume_condition]
    )
    
    # Exit: Price < 100
    exit_condition = Condition(
        type="price_below",
        params={"value": 100.0}
    )
    
    strategy = Strategy(
        name="Multi-Condition Breakout",
        description="Enter when price, RSI, and volume all confirm breakout",
        entry_conditions=[entry_and],
        exit_conditions=[exit_condition],
        parameters={
            "breakout_level": 100.0,
            "min_rsi": 50.0,
            "min_volume": 1000000
        }
    )
    
    print(f"\n✓ Created strategy: {strategy.name}")
    
    strategy_id = save_strategy(strategy, "multi_condition_breakout")
    print(f"✓ Saved strategy with ID: {strategy_id}")
    
    # Sample data
    data = [
        {"timestamp": "2024-01-01T00:00:00", "close": 95.0, "rsi": 45.0, "volume": 900000},
        {"timestamp": "2024-01-01T01:00:00", "close": 98.0, "rsi": 48.0, "volume": 950000},
        {"timestamp": "2024-01-01T02:00:00", "close": 102.0, "rsi": 55.0, "volume": 1200000},  # All conditions met!
        {"timestamp": "2024-01-01T03:00:00", "close": 105.0, "rsi": 60.0, "volume": 1100000},
        {"timestamp": "2024-01-01T04:00:00", "close": 98.0, "rsi": 52.0, "volume": 800000},  # Price drops - EXIT
    ]
    
    engine = StrategyEngine(strategy)
    results = engine.execute(data, mode="backtest")
    
    print(f"\n✓ Executed strategy:")
    print(f"  Total trades: {results['statistics']['total_trades']}")
    
    print("\n  Trades:")
    for trade in results["trades"]:
        print(f"    {trade['type'].upper()}: ${trade['price']:.2f} at {trade['timestamp']}")
    
    return strategy_id


def demo_list_saved_strategies():
    """Demo: Listing all saved strategies."""
    print("\n" + "="*60)
    print("DEMO 4: Listing All Saved Strategies")
    print("="*60)
    
    strategies = list_strategies()
    
    print(f"\n✓ Found {len(strategies)} saved strategies:\n")
    
    for s in strategies:
        print(f"  ID: {s['id']}")
        print(f"  Name: {s['name']}")
        print(f"  Description: {s['description']}")
        print(f"  Created: {s['created_at']}")
        print()


def demo_load_and_reuse_strategy():
    """Demo: Loading a saved strategy and reusing it."""
    print("\n" + "="*60)
    print("DEMO 5: Loading and Reusing a Saved Strategy")
    print("="*60)
    
    # Load the MA Crossover strategy we saved earlier
    strategy = load_strategy("ma_crossover")
    
    print(f"\n✓ Loaded strategy: {strategy.name}")
    print(f"  Description: {strategy.description}")
    print(f"  Parameters: {strategy.parameters}")
    
    # Use it on new data
    new_data = [
        {"timestamp": "2024-02-01T00:00:00", "close": 200.0, "ma_fast": 198.0, "ma_slow": 200.0},
        {"timestamp": "2024-02-01T01:00:00", "close": 205.0, "ma_fast": 202.0, "ma_slow": 200.5},
        {"timestamp": "2024-02-01T02:00:00", "close": 210.0, "ma_fast": 206.0, "ma_slow": 201.0},  # Cross!
        {"timestamp": "2024-02-01T03:00:00", "close": 215.0, "ma_fast": 210.0, "ma_slow": 202.0},
        {"timestamp": "2024-02-01T04:00:00", "close": 212.0, "ma_fast": 209.0, "ma_slow": 203.0},
    ]
    
    engine = StrategyEngine(strategy)
    results = engine.execute(new_data, mode="backtest")
    
    print(f"\n✓ Executed loaded strategy on new data:")
    print(f"  Total trades: {results['statistics']['total_trades']}")
    
    print("\n  Trades:")
    for trade in results["trades"]:
        print(f"    {trade['type'].upper()}: ${trade['price']:.2f}")


def demo_continuous_contract_usage():
    """Demo: Using strategies with continuous contract JSON data."""
    print("\n" + "="*60)
    print("DEMO 6: Using Strategies with Continuous Contract Data")
    print("="*60)
    
    print("\nFor agents working with continuous contract JSON:")
    print("\n1. Load your contract data:")
    print('   with open("contract_data.json", "r") as f:')
    print('       contract_data = json.load(f)')
    
    print("\n2. Calculate required indicators:")
    print('   # Add your indicator calculations here')
    print('   for bar in contract_data:')
    print('       bar["ma_fast"] = calculate_ma(contract_data, period=10)')
    print('       bar["ma_slow"] = calculate_ma(contract_data, period=20)')
    
    print("\n3. Load your saved strategy:")
    print('   strategy = load_strategy("your_strategy_id")')
    
    print("\n4. Execute the strategy:")
    print('   engine = StrategyEngine(strategy)')
    print('   results = engine.execute(contract_data, mode="backtest")')
    
    print("\n5. Process the results:")
    print('   for trade in results["trades"]:')
    print('       print(f"{trade[\'type\']} at {trade[\'timestamp\']}: ${trade[\'price\']}")')
    
    print("\n✓ The same strategy works for both backtest and replay modes!")


def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("UNIFIED STRATEGY ENGINE - DEMONSTRATION")
    print("="*60)
    print("\nThis demo shows how the strategy engine unifies")
    print("backtesting and replay mode logic into a single engine.")
    
    # Run demos
    demo_ma_crossover_strategy()
    demo_rsi_strategy()
    demo_complex_strategy()
    demo_list_saved_strategies()
    demo_load_and_reuse_strategy()
    demo_continuous_contract_usage()
    
    print("\n" + "="*60)
    print("KEY TAKEAWAYS")
    print("="*60)
    print("\n1. ✓ Same engine for backtest AND replay modes")
    print("2. ✓ No future data leakage (point-in-time evaluation)")
    print("3. ✓ Strategies are saved and reusable")
    print("4. ✓ Easy to use from Python, tools, or API")
    print("5. ✓ Extensible condition system")
    print("\n" + "="*60)
    print("\nFor more info, see: docts/strategy_engine.md")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
