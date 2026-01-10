"""
tests/tools/test_strategy_tools.py - Tests for Strategy Tools

Test coverage:
- save_strategy_tool
- load_strategy_tool
- list_strategies_tool
- execute_strategy_tool
- delete_strategy_tool
"""

import pytest
from tool.strategy import (
    save_strategy_tool,
    load_strategy_tool,
    list_strategies_tool,
    execute_strategy_tool,
    delete_strategy_tool
)
from core.strategy import delete_strategy


class TestSaveStrategyTool:
    """Tests for save_strategy_tool."""
    
    def test_save_simple_strategy(self):
        """Test saving a simple strategy."""
        params = {
            "name": "Test Strategy",
            "description": "A test strategy",
            "entry_conditions": [
                {
                    "type": "price_above",
                    "params": {"value": 100.0}
                }
            ],
            "exit_conditions": [
                {
                    "type": "price_below",
                    "params": {"value": 90.0}
                }
            ],
            "parameters": {"param1": 10}
        }
        
        result = save_strategy_tool(params)
        
        assert result["success"] is True
        assert result["strategy_id"] is not None
        assert "saved successfully" in result["message"].lower()
        
        # Cleanup
        delete_strategy(result["strategy_id"])
    
    def test_save_with_custom_id(self):
        """Test saving with a custom strategy ID."""
        params = {
            "name": "Custom ID Test",
            "description": "",
            "entry_conditions": [
                {"type": "price_above", "params": {"value": 100.0}}
            ],
            "exit_conditions": [
                {"type": "price_below", "params": {"value": 90.0}}
            ],
            "parameters": {},
            "strategy_id": "my_custom_id"
        }
        
        result = save_strategy_tool(params)
        
        assert result["success"] is True
        assert result["strategy_id"] == "my_custom_id"
        
        # Cleanup
        delete_strategy("my_custom_id")
    
    def test_save_with_invalid_data(self):
        """Test saving with missing required fields."""
        params = {
            "name": "Invalid Strategy"
            # Missing entry_conditions and exit_conditions
        }
        
        result = save_strategy_tool(params)
        
        assert result["success"] is False
        assert "error" in result["message"].lower()


class TestLoadStrategyTool:
    """Tests for load_strategy_tool."""
    
    def setup_method(self):
        """Set up test strategy."""
        params = {
            "name": "Load Test Strategy",
            "description": "For testing load",
            "entry_conditions": [
                {"type": "price_above", "params": {"value": 100.0}}
            ],
            "exit_conditions": [
                {"type": "price_below", "params": {"value": 90.0}}
            ],
            "parameters": {"test_param": 42},
            "strategy_id": "load_test"
        }
        save_strategy_tool(params)
    
    def teardown_method(self):
        """Clean up test strategy."""
        delete_strategy("load_test")
    
    def test_load_existing_strategy(self):
        """Test loading an existing strategy."""
        result = load_strategy_tool({"strategy_id": "load_test"})
        
        assert result["success"] is True
        assert result["strategy"] is not None
        assert result["strategy"]["name"] == "Load Test Strategy"
        assert result["strategy"]["parameters"]["test_param"] == 42
    
    def test_load_nonexistent_strategy(self):
        """Test loading a strategy that doesn't exist."""
        result = load_strategy_tool({"strategy_id": "does_not_exist"})
        
        assert result["success"] is False
        assert "not found" in result["message"].lower()


class TestListStrategiesTool:
    """Tests for list_strategies_tool."""
    
    def setup_method(self):
        """Set up multiple test strategies."""
        for i in range(3):
            params = {
                "name": f"List Test {i}",
                "description": f"Strategy {i}",
                "entry_conditions": [
                    {"type": "price_above", "params": {"value": 100.0}}
                ],
                "exit_conditions": [
                    {"type": "price_below", "params": {"value": 90.0}}
                ],
                "parameters": {},
                "strategy_id": f"list_test_{i}"
            }
            save_strategy_tool(params)
    
    def teardown_method(self):
        """Clean up test strategies."""
        for i in range(3):
            delete_strategy(f"list_test_{i}")
    
    def test_list_all_strategies(self):
        """Test listing all strategies."""
        result = list_strategies_tool()
        
        assert result["success"] is True
        assert result["count"] >= 3
        assert len(result["strategies"]) >= 3
        
        # Check that our test strategies are in the list
        strategy_ids = [s["id"] for s in result["strategies"]]
        assert "list_test_0" in strategy_ids
        assert "list_test_1" in strategy_ids
        assert "list_test_2" in strategy_ids
    
    def test_list_returns_metadata(self):
        """Test that list returns proper metadata."""
        result = list_strategies_tool()
        
        assert result["success"] is True
        
        # Check structure of returned strategies
        for strategy in result["strategies"]:
            assert "id" in strategy
            assert "name" in strategy
            assert "description" in strategy
            assert "created_at" in strategy


class TestExecuteStrategyTool:
    """Tests for execute_strategy_tool."""
    
    def setup_method(self):
        """Set up test strategy and data."""
        # Create a simple strategy
        params = {
            "name": "Execute Test",
            "description": "For testing execution",
            "entry_conditions": [
                {"type": "price_above", "params": {"value": 100.0}}
            ],
            "exit_conditions": [
                {"type": "price_below", "params": {"value": 100.0}}
            ],
            "parameters": {},
            "strategy_id": "execute_test"
        }
        save_strategy_tool(params)
        
        # Sample data
        self.sample_data = [
            {"timestamp": "2024-01-01T00:00:00", "close": 95.0},
            {"timestamp": "2024-01-01T01:00:00", "close": 105.0},
            {"timestamp": "2024-01-01T02:00:00", "close": 110.0},
            {"timestamp": "2024-01-01T03:00:00", "close": 95.0},
        ]
    
    def teardown_method(self):
        """Clean up test strategy."""
        delete_strategy("execute_test")
    
    def test_execute_in_backtest_mode(self):
        """Test executing strategy in backtest mode."""
        params = {
            "strategy_id": "execute_test",
            "data": self.sample_data,
            "mode": "backtest"
        }
        
        result = execute_strategy_tool(params)
        
        assert result["success"] is True
        assert result["results"] is not None
        assert result["results"]["mode"] == "backtest"
        assert "trades" in result["results"]
        assert "statistics" in result["results"]
    
    def test_execute_in_replay_mode(self):
        """Test executing strategy in replay mode."""
        params = {
            "strategy_id": "execute_test",
            "data": self.sample_data,
            "mode": "replay"
        }
        
        result = execute_strategy_tool(params)
        
        assert result["success"] is True
        assert result["results"]["mode"] == "replay"
    
    def test_execute_with_invalid_mode(self):
        """Test executing with invalid mode."""
        params = {
            "strategy_id": "execute_test",
            "data": self.sample_data,
            "mode": "invalid_mode"
        }
        
        result = execute_strategy_tool(params)
        
        assert result["success"] is False
        assert "invalid mode" in result["message"].lower()
    
    def test_execute_nonexistent_strategy(self):
        """Test executing a strategy that doesn't exist."""
        params = {
            "strategy_id": "does_not_exist",
            "data": self.sample_data,
            "mode": "backtest"
        }
        
        result = execute_strategy_tool(params)
        
        assert result["success"] is False
        assert "not found" in result["message"].lower()
    
    def test_backtest_and_replay_produce_same_results(self):
        """Test that backtest and replay produce identical results."""
        # Execute in backtest mode
        backtest_result = execute_strategy_tool({
            "strategy_id": "execute_test",
            "data": self.sample_data,
            "mode": "backtest"
        })
        
        # Execute in replay mode
        replay_result = execute_strategy_tool({
            "strategy_id": "execute_test",
            "data": self.sample_data,
            "mode": "replay"
        })
        
        # Both should succeed
        assert backtest_result["success"] is True
        assert replay_result["success"] is True
        
        # Trades should be identical
        backtest_trades = backtest_result["results"]["trades"]
        replay_trades = replay_result["results"]["trades"]
        
        assert len(backtest_trades) == len(replay_trades)
        
        for i in range(len(backtest_trades)):
            assert backtest_trades[i]["type"] == replay_trades[i]["type"]
            assert backtest_trades[i]["price"] == replay_trades[i]["price"]
            assert backtest_trades[i]["timestamp"] == replay_trades[i]["timestamp"]


class TestDeleteStrategyTool:
    """Tests for delete_strategy_tool."""
    
    def test_delete_existing_strategy(self):
        """Test deleting an existing strategy."""
        # Create a strategy
        params = {
            "name": "To Delete",
            "description": "",
            "entry_conditions": [
                {"type": "price_above", "params": {"value": 100.0}}
            ],
            "exit_conditions": [
                {"type": "price_below", "params": {"value": 90.0}}
            ],
            "parameters": {},
            "strategy_id": "to_delete"
        }
        save_strategy_tool(params)
        
        # Delete it
        result = delete_strategy_tool({"strategy_id": "to_delete"})
        
        assert result["success"] is True
        assert "deleted successfully" in result["message"].lower()
        
        # Verify it's gone
        load_result = load_strategy_tool({"strategy_id": "to_delete"})
        assert load_result["success"] is False
    
    def test_delete_nonexistent_strategy(self):
        """Test deleting a strategy that doesn't exist."""
        result = delete_strategy_tool({"strategy_id": "does_not_exist"})
        
        assert result["success"] is False
        assert "not found" in result["message"].lower()


class TestEndToEndWorkflow:
    """End-to-end tests for complete workflows."""
    
    def test_complete_workflow(self):
        """Test a complete save -> list -> execute -> delete workflow."""
        # 1. Save a strategy
        save_params = {
            "name": "E2E Test Strategy",
            "description": "End-to-end test",
            "entry_conditions": [
                {"type": "price_above", "params": {"value": 100.0}}
            ],
            "exit_conditions": [
                {"type": "price_below", "params": {"value": 100.0}}
            ],
            "parameters": {"period": 10},
            "strategy_id": "e2e_test"
        }
        
        save_result = save_strategy_tool(save_params)
        assert save_result["success"] is True
        
        # 2. List strategies and verify it's there
        list_result = list_strategies_tool()
        assert list_result["success"] is True
        strategy_ids = [s["id"] for s in list_result["strategies"]]
        assert "e2e_test" in strategy_ids
        
        # 3. Load the strategy
        load_result = load_strategy_tool({"strategy_id": "e2e_test"})
        assert load_result["success"] is True
        assert load_result["strategy"]["name"] == "E2E Test Strategy"
        
        # 4. Execute the strategy
        data = [
            {"timestamp": "2024-01-01T00:00:00", "close": 95.0},
            {"timestamp": "2024-01-01T01:00:00", "close": 105.0},
            {"timestamp": "2024-01-01T02:00:00", "close": 95.0},
        ]
        
        execute_result = execute_strategy_tool({
            "strategy_id": "e2e_test",
            "data": data,
            "mode": "backtest"
        })
        assert execute_result["success"] is True
        assert len(execute_result["results"]["trades"]) > 0
        
        # 5. Delete the strategy
        delete_result = delete_strategy_tool({"strategy_id": "e2e_test"})
        assert delete_result["success"] is True
        
        # 6. Verify it's gone
        load_result2 = load_strategy_tool({"strategy_id": "e2e_test"})
        assert load_result2["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
