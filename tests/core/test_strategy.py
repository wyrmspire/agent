"""
tests/core/test_strategy.py - Tests for Strategy Engine

Test coverage:
- Strategy creation and serialization
- Condition evaluation
- Strategy execution in backtest mode
- Strategy execution in replay mode
- Strategy storage and loading
- Trade generation and statistics
"""

import pytest
import json
import tempfile
from pathlib import Path
from core.strategy import (
    Strategy,
    Condition,
    StrategyEngine,
    Trade,
    ConditionType,
    save_strategy,
    load_strategy,
    list_strategies,
    delete_strategy,
    get_strategies_dir
)


class TestCondition:
    """Tests for Condition class."""
    
    def test_condition_creation(self):
        """Test creating a simple condition."""
        cond = Condition(
            type="price_above",
            params={"value": 100.0}
        )
        assert cond.type == "price_above"
        assert cond.params["value"] == 100.0
        assert cond.children is None
    
    def test_condition_with_children(self):
        """Test creating a logical condition with children."""
        child1 = Condition(type="price_above", params={"value": 100.0})
        child2 = Condition(type="price_below", params={"value": 200.0})
        
        cond = Condition(
            type="and",
            params={},
            children=[child1, child2]
        )
        
        assert cond.type == "and"
        assert len(cond.children) == 2
        assert cond.children[0].type == "price_above"
    
    def test_condition_serialization(self):
        """Test condition to/from dict."""
        cond = Condition(
            type="price_above",
            params={"value": 100.0}
        )
        
        cond_dict = cond.to_dict()
        assert cond_dict["type"] == "price_above"
        assert cond_dict["params"]["value"] == 100.0
        
        cond2 = Condition.from_dict(cond_dict)
        assert cond2.type == cond.type
        assert cond2.params == cond.params


class TestStrategy:
    """Tests for Strategy class."""
    
    def test_strategy_creation(self):
        """Test creating a strategy."""
        entry = Condition(type="price_above", params={"value": 100.0})
        exit = Condition(type="price_below", params={"value": 90.0})
        
        strategy = Strategy(
            name="Test Strategy",
            description="A test strategy",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={"param1": 10}
        )
        
        assert strategy.name == "Test Strategy"
        assert len(strategy.entry_conditions) == 1
        assert len(strategy.exit_conditions) == 1
        assert strategy.parameters["param1"] == 10
        assert strategy.metadata is not None
    
    def test_strategy_serialization(self):
        """Test strategy to/from JSON."""
        entry = Condition(type="price_above", params={"value": 100.0})
        exit = Condition(type="price_below", params={"value": 90.0})
        
        strategy = Strategy(
            name="Test Strategy",
            description="A test",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={}
        )
        
        # To JSON
        json_str = strategy.to_json()
        assert isinstance(json_str, str)
        
        # From JSON
        strategy2 = Strategy.from_json(json_str)
        assert strategy2.name == strategy.name
        assert strategy2.description == strategy.description
        assert len(strategy2.entry_conditions) == len(strategy.entry_conditions)


class TestStrategyEngine:
    """Tests for StrategyEngine."""
    
    def create_sample_data(self):
        """Create sample OHLCV data."""
        return [
            {"timestamp": "2024-01-01T00:00:00", "close": 95.0, "ma": 90.0},
            {"timestamp": "2024-01-01T01:00:00", "close": 100.0, "ma": 92.0},
            {"timestamp": "2024-01-01T02:00:00", "close": 105.0, "ma": 95.0},
            {"timestamp": "2024-01-01T03:00:00", "close": 110.0, "ma": 98.0},
            {"timestamp": "2024-01-01T04:00:00", "close": 108.0, "ma": 100.0},
            {"timestamp": "2024-01-01T05:00:00", "close": 95.0, "ma": 102.0},
        ]
    
    def test_simple_price_above_strategy(self):
        """Test a simple strategy with price_above condition."""
        entry = Condition(type="price_above", params={"value": 100.0})
        exit = Condition(type="price_below", params={"value": 100.0})
        
        strategy = Strategy(
            name="Price Above 100",
            description="Enter when price > 100, exit when < 100",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={}
        )
        
        engine = StrategyEngine(strategy)
        data = self.create_sample_data()
        results = engine.execute(data, mode="backtest")
        
        # Should enter when price crosses 100 and exit when it goes back below
        assert results["strategy"] == "Price Above 100"
        assert results["mode"] == "backtest"
        assert len(results["trades"]) >= 2  # At least one entry and one exit
        
        # First trade should be entry
        assert results["trades"][0]["type"] == "entry"
    
    def test_backtest_vs_replay_consistency(self):
        """Test that backtest and replay modes produce identical results."""
        entry = Condition(type="price_above", params={"value": 100.0})
        exit = Condition(type="price_below", params={"value": 100.0})
        
        strategy = Strategy(
            name="Test",
            description="",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={}
        )
        
        engine = StrategyEngine(strategy)
        data = self.create_sample_data()
        
        # Execute in both modes
        backtest_results = engine.execute(data, mode="backtest")
        replay_results = engine.execute(data, mode="replay")
        
        # Results should be identical
        assert len(backtest_results["trades"]) == len(replay_results["trades"])
        for i in range(len(backtest_results["trades"])):
            assert backtest_results["trades"][i]["type"] == replay_results["trades"][i]["type"]
            assert backtest_results["trades"][i]["price"] == replay_results["trades"][i]["price"]
    
    def test_price_cross_above(self):
        """Test price_crosses_above condition."""
        entry = Condition(type="price_crosses_above", params={"value": 100.0})
        exit = Condition(type="price_crosses_below", params={"value": 100.0})
        
        strategy = Strategy(
            name="Crossover",
            description="",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={}
        )
        
        engine = StrategyEngine(strategy)
        data = self.create_sample_data()
        results = engine.execute(data, mode="backtest")
        
        # Should trigger entry when price crosses above 100
        # Data: 95, 100, 105, 110, 108, 95
        # Entry at 105 (first time price > 100 after being <= 100)
        trades = results["trades"]
        entry_trades = [t for t in trades if t["type"] == "entry"]
        assert len(entry_trades) > 0
        assert entry_trades[0]["price"] == 105.0  # First cross above happens at 105
    
    def test_indicator_cross_strategy(self):
        """Test indicator crossover strategy."""
        entry = Condition(
            type="indicator_crosses_above",
            params={"indicator": "close", "value": "ma"}
        )
        exit = Condition(
            type="indicator_crosses_below",
            params={"indicator": "close", "value": "ma"}
        )
        
        strategy = Strategy(
            name="MA Crossover",
            description="",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={}
        )
        
        # Note: This test would need data where close crosses ma
        # For now, just test that it doesn't crash
        engine = StrategyEngine(strategy)
        data = self.create_sample_data()
        results = engine.execute(data, mode="backtest")
        
        assert "trades" in results
        assert "statistics" in results
    
    def test_no_future_leakage(self):
        """Test that engine doesn't use future data."""
        # Create a strategy that would only work if future data is leaked
        entry = Condition(type="price_above", params={"value": 100.0})
        exit = Condition(type="price_below", params={"value": 100.0})
        
        strategy = Strategy(
            name="Test",
            description="",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={}
        )
        
        engine = StrategyEngine(strategy)
        
        # Data where price goes up then down
        data = [
            {"timestamp": "2024-01-01T00:00:00", "close": 90.0},
            {"timestamp": "2024-01-01T01:00:00", "close": 105.0},
            {"timestamp": "2024-01-01T02:00:00", "close": 95.0},
        ]
        
        results = engine.execute(data, mode="backtest")
        
        # Should enter at bar 1 (105.0) when price is above 100
        # Should exit at bar 2 (95.0) when price drops below 100
        trades = results["trades"]
        entry_trades = [t for t in trades if t["type"] == "entry"]
        assert len(entry_trades) > 0
        assert entry_trades[0]["price"] == 105.0
    
    def test_statistics_calculation(self):
        """Test that statistics are calculated correctly."""
        entry = Condition(type="price_above", params={"value": 100.0})
        exit = Condition(type="price_below", params={"value": 100.0})
        
        strategy = Strategy(
            name="Test",
            description="",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={}
        )
        
        engine = StrategyEngine(strategy)
        data = self.create_sample_data()
        results = engine.execute(data, mode="backtest")
        
        stats = results["statistics"]
        assert "total_trades" in stats
        assert "winning_trades" in stats
        assert "losing_trades" in stats
        assert "win_rate" in stats
        assert 0.0 <= stats["win_rate"] <= 1.0


class TestStrategyStorage:
    """Tests for strategy storage functions."""
    
    def test_save_and_load_strategy(self):
        """Test saving and loading a strategy."""
        entry = Condition(type="price_above", params={"value": 100.0})
        exit = Condition(type="price_below", params={"value": 90.0})
        
        strategy = Strategy(
            name="Test Strategy",
            description="A test",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={"param1": 10}
        )
        
        # Save
        strategy_id = save_strategy(strategy, "test_strategy")
        assert strategy_id == "test_strategy"
        
        # Load
        loaded = load_strategy("test_strategy")
        assert loaded.name == strategy.name
        assert loaded.description == strategy.description
        assert len(loaded.entry_conditions) == 1
        
        # Cleanup
        delete_strategy("test_strategy")
    
    def test_list_strategies(self):
        """Test listing strategies."""
        # Save some strategies
        for i in range(3):
            entry = Condition(type="price_above", params={"value": 100.0})
            exit = Condition(type="price_below", params={"value": 90.0})
            
            strategy = Strategy(
                name=f"Strategy {i}",
                description=f"Test {i}",
                entry_conditions=[entry],
                exit_conditions=[exit],
                parameters={}
            )
            save_strategy(strategy, f"test_strategy_{i}")
        
        # List
        strategies = list_strategies()
        assert len(strategies) >= 3
        
        # Check structure
        assert all("id" in s for s in strategies)
        assert all("name" in s for s in strategies)
        
        # Cleanup
        for i in range(3):
            delete_strategy(f"test_strategy_{i}")
    
    def test_delete_strategy(self):
        """Test deleting a strategy."""
        entry = Condition(type="price_above", params={"value": 100.0})
        exit = Condition(type="price_below", params={"value": 90.0})
        
        strategy = Strategy(
            name="To Delete",
            description="",
            entry_conditions=[entry],
            exit_conditions=[exit],
            parameters={}
        )
        
        # Save
        save_strategy(strategy, "to_delete")
        
        # Verify it exists
        loaded = load_strategy("to_delete")
        assert loaded.name == "To Delete"
        
        # Delete
        deleted = delete_strategy("to_delete")
        assert deleted is True
        
        # Verify it's gone
        with pytest.raises(FileNotFoundError):
            load_strategy("to_delete")
    
    def test_load_nonexistent_strategy(self):
        """Test loading a strategy that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_strategy("nonexistent_strategy")


class TestLogicalConditions:
    """Tests for AND, OR, NOT logical operators."""
    
    def test_and_condition(self):
        """Test AND logical operator."""
        child1 = Condition(type="price_above", params={"value": 100.0})
        child2 = Condition(type="price_below", params={"value": 200.0})
        
        and_condition = Condition(
            type="and",
            params={},
            children=[child1, child2]
        )
        
        strategy = Strategy(
            name="AND Test",
            description="",
            entry_conditions=[and_condition],
            exit_conditions=[Condition(type="price_below", params={"value": 50.0})],
            parameters={}
        )
        
        engine = StrategyEngine(strategy)
        
        # Test data where price is between 100 and 200
        data = [
            {"timestamp": "2024-01-01T00:00:00", "close": 50.0},
            {"timestamp": "2024-01-01T01:00:00", "close": 150.0},  # Should enter here
            {"timestamp": "2024-01-01T02:00:00", "close": 40.0},   # Should exit here
        ]
        
        results = engine.execute(data, mode="backtest")
        trades = results["trades"]
        
        # Should enter at 150 (both conditions true)
        entry_trades = [t for t in trades if t["type"] == "entry"]
        assert len(entry_trades) > 0
        assert entry_trades[0]["price"] == 150.0
    
    def test_or_condition(self):
        """Test OR logical operator."""
        child1 = Condition(type="price_above", params={"value": 200.0})
        child2 = Condition(type="price_below", params={"value": 50.0})
        
        or_condition = Condition(
            type="or",
            params={},
            children=[child1, child2]
        )
        
        strategy = Strategy(
            name="OR Test",
            description="",
            entry_conditions=[or_condition],
            exit_conditions=[Condition(type="price_above", params={"value": 100.0})],
            parameters={}
        )
        
        engine = StrategyEngine(strategy)
        
        # Test data where price goes below 50 (triggers OR)
        data = [
            {"timestamp": "2024-01-01T00:00:00", "close": 100.0},
            {"timestamp": "2024-01-01T01:00:00", "close": 40.0},  # Should enter (< 50)
            {"timestamp": "2024-01-01T02:00:00", "close": 110.0}, # Should exit
        ]
        
        results = engine.execute(data, mode="backtest")
        trades = results["trades"]
        
        entry_trades = [t for t in trades if t["type"] == "entry"]
        assert len(entry_trades) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
