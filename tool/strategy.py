"""
tool/strategy.py - Strategy Management Tools

This module provides tools for agents to work with trading strategies.
It exposes the core strategy functionality through the tool interface.

Tools:
- save_strategy: Save a strategy definition
- load_strategy: Load a saved strategy
- list_strategies: List all saved strategies
- execute_strategy: Execute a strategy on data
- delete_strategy: Delete a saved strategy

Usage:
    from tool.strategy import save_strategy_tool, execute_strategy_tool
    
    # Save a strategy
    result = save_strategy_tool({
        "name": "MA Crossover",
        "description": "Simple moving average crossover",
        "entry_conditions": [...],
        "exit_conditions": [...],
        "parameters": {...}
    })
    
    # Execute on data
    result = execute_strategy_tool({
        "strategy_id": "ma_crossover",
        "data": [...],
        "mode": "backtest"
    })
"""

import logging
from typing import Dict, Any, List, Optional
from core.strategy import (
    Strategy,
    Condition,
    StrategyEngine,
    save_strategy,
    load_strategy,
    list_strategies,
    delete_strategy
)

logger = logging.getLogger(__name__)


def save_strategy_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Save a trading strategy.
    
    Args:
        params: Dictionary containing:
            - name (str): Strategy name
            - description (str): Strategy description
            - entry_conditions (list): List of entry condition dicts
            - exit_conditions (list): List of exit condition dicts
            - parameters (dict): Strategy parameters
            - strategy_id (str, optional): Custom ID for the strategy
    
    Returns:
        Dictionary with:
            - success (bool): Whether save was successful
            - strategy_id (str): ID of saved strategy
            - message (str): Success/error message
    
    Example:
        {
            "name": "MA Crossover",
            "description": "Buy when fast MA crosses above slow MA",
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
    """
    try:
        # Validate required fields
        if "name" not in params:
            return {
                "success": False,
                "strategy_id": None,
                "message": "Error: 'name' is required"
            }
        
        if "entry_conditions" not in params:
            return {
                "success": False,
                "strategy_id": None,
                "message": "Error: 'entry_conditions' is required"
            }
        
        if "exit_conditions" not in params:
            return {
                "success": False,
                "strategy_id": None,
                "message": "Error: 'exit_conditions' is required"
            }
        
        # Parse conditions
        entry_conditions = [
            Condition.from_dict(c) for c in params.get("entry_conditions", [])
        ]
        exit_conditions = [
            Condition.from_dict(c) for c in params.get("exit_conditions", [])
        ]
        
        # Create strategy object
        strategy = Strategy(
            name=params["name"],
            description=params.get("description", ""),
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            parameters=params.get("parameters", {})
        )
        
        # Save to disk
        strategy_id = save_strategy(strategy, params.get("strategy_id"))
        
        return {
            "success": True,
            "strategy_id": strategy_id,
            "message": f"Strategy '{strategy.name}' saved successfully"
        }
    
    except Exception as e:
        logger.error(f"Failed to save strategy: {e}")
        return {
            "success": False,
            "strategy_id": None,
            "message": f"Error saving strategy: {str(e)}"
        }


def load_strategy_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Load a saved strategy.
    
    Args:
        params: Dictionary containing:
            - strategy_id (str): ID of strategy to load
    
    Returns:
        Dictionary with:
            - success (bool): Whether load was successful
            - strategy (dict): Strategy data
            - message (str): Success/error message
    """
    try:
        strategy_id = params["strategy_id"]
        strategy = load_strategy(strategy_id)
        
        return {
            "success": True,
            "strategy": strategy.to_dict(),
            "message": f"Strategy '{strategy.name}' loaded successfully"
        }
    
    except FileNotFoundError:
        return {
            "success": False,
            "strategy": None,
            "message": f"Strategy '{params['strategy_id']}' not found"
        }
    
    except Exception as e:
        logger.error(f"Failed to load strategy: {e}")
        return {
            "success": False,
            "strategy": None,
            "message": f"Error loading strategy: {str(e)}"
        }


def list_strategies_tool(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all saved strategies.
    
    Args:
        params: Optional parameters (none required)
    
    Returns:
        Dictionary with:
            - success (bool): Whether operation was successful
            - strategies (list): List of strategy metadata
            - count (int): Number of strategies found
    """
    try:
        strategies = list_strategies()
        
        return {
            "success": True,
            "strategies": strategies,
            "count": len(strategies)
        }
    
    except Exception as e:
        logger.error(f"Failed to list strategies: {e}")
        return {
            "success": False,
            "strategies": [],
            "count": 0,
            "message": f"Error listing strategies: {str(e)}"
        }


def execute_strategy_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a strategy on data.
    
    Args:
        params: Dictionary containing:
            - strategy_id (str): ID of strategy to execute
            - data (list): List of bars/candles with OHLCV data
            - mode (str): Execution mode ("backtest" or "replay")
    
    Returns:
        Dictionary with:
            - success (bool): Whether execution was successful
            - results (dict): Execution results with trades and statistics
            - message (str): Success/error message
    
    Example data format:
        [
            {
                "timestamp": "2024-01-01T00:00:00",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1000,
                "ma_fast": 100.5,  # Pre-calculated indicators
                "ma_slow": 99.8
            },
            ...
        ]
    """
    try:
        # Load strategy
        strategy_id = params["strategy_id"]
        strategy = load_strategy(strategy_id)
        
        # Get data and mode
        data = params["data"]
        mode = params.get("mode", "backtest")
        
        if mode not in ["backtest", "replay"]:
            return {
                "success": False,
                "results": None,
                "message": f"Invalid mode '{mode}'. Must be 'backtest' or 'replay'"
            }
        
        # Execute strategy
        engine = StrategyEngine(strategy)
        results = engine.execute(data, mode=mode)
        
        return {
            "success": True,
            "results": results,
            "message": f"Strategy executed successfully in {mode} mode"
        }
    
    except FileNotFoundError:
        return {
            "success": False,
            "results": None,
            "message": f"Strategy '{params['strategy_id']}' not found"
        }
    
    except Exception as e:
        logger.error(f"Failed to execute strategy: {e}")
        return {
            "success": False,
            "results": None,
            "message": f"Error executing strategy: {str(e)}"
        }


def delete_strategy_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a saved strategy.
    
    Args:
        params: Dictionary containing:
            - strategy_id (str): ID of strategy to delete
    
    Returns:
        Dictionary with:
            - success (bool): Whether deletion was successful
            - message (str): Success/error message
    """
    try:
        strategy_id = params["strategy_id"]
        deleted = delete_strategy(strategy_id)
        
        if deleted:
            return {
                "success": True,
                "message": f"Strategy '{strategy_id}' deleted successfully"
            }
        else:
            return {
                "success": False,
                "message": f"Strategy '{strategy_id}' not found"
            }
    
    except Exception as e:
        logger.error(f"Failed to delete strategy: {e}")
        return {
            "success": False,
            "message": f"Error deleting strategy: {str(e)}"
        }


# Tool registration metadata
STRATEGY_TOOLS = {
    "save_strategy": {
        "function": save_strategy_tool,
        "description": "Save a trading strategy for later use in backtest or replay mode",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Strategy name"},
                "description": {"type": "string", "description": "Strategy description"},
                "entry_conditions": {
                    "type": "array",
                    "description": "List of entry condition objects",
                    "items": {"type": "object"}
                },
                "exit_conditions": {
                    "type": "array",
                    "description": "List of exit condition objects",
                    "items": {"type": "object"}
                },
                "parameters": {
                    "type": "object",
                    "description": "Strategy parameters"
                },
                "strategy_id": {
                    "type": "string",
                    "description": "Optional custom ID for the strategy"
                }
            },
            "required": ["name", "entry_conditions", "exit_conditions"]
        }
    },
    "load_strategy": {
        "function": load_strategy_tool,
        "description": "Load a saved strategy",
        "parameters": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string", "description": "ID of strategy to load"}
            },
            "required": ["strategy_id"]
        }
    },
    "list_strategies": {
        "function": list_strategies_tool,
        "description": "List all saved strategies",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "execute_strategy": {
        "function": execute_strategy_tool,
        "description": "Execute a strategy on data in backtest or replay mode",
        "parameters": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string", "description": "ID of strategy to execute"},
                "data": {
                    "type": "array",
                    "description": "List of bars/candles with OHLCV data and indicators",
                    "items": {"type": "object"}
                },
                "mode": {
                    "type": "string",
                    "description": "Execution mode: 'backtest' or 'replay'",
                    "enum": ["backtest", "replay"]
                }
            },
            "required": ["strategy_id", "data"]
        }
    },
    "delete_strategy": {
        "function": delete_strategy_tool,
        "description": "Delete a saved strategy",
        "parameters": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string", "description": "ID of strategy to delete"}
            },
            "required": ["strategy_id"]
        }
    }
}
