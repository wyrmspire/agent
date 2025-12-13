"""
model/qwen5/confs.py - Qwen 2.5 Coder Configuration

This module contains configuration for Qwen 2.5 Coder models.

Model variants:
- qwen2.5-coder-0.5b
- qwen2.5-coder-1.5b
- qwen2.5-coder-3b
- qwen2.5-coder-7b
- qwen2.5-coder-14b
- qwen2.5-coder-32b

Rules:
- No model files here (too large)
- Only configuration and metadata
- Paths to model files if local
"""

from typing import Dict, Any


# Model configurations
QWEN_MODELS = {
    "qwen2.5-coder-0.5b": {
        "name": "Qwen2.5-Coder-0.5B",
        "context_length": 32768,
        "supports_tools": True,
        "supports_vision": False,
        "recommended_temperature": 0.7,
        "recommended_top_p": 0.9,
    },
    "qwen2.5-coder-1.5b": {
        "name": "Qwen2.5-Coder-1.5B",
        "context_length": 32768,
        "supports_tools": True,
        "supports_vision": False,
        "recommended_temperature": 0.7,
        "recommended_top_p": 0.9,
    },
    "qwen2.5-coder-7b": {
        "name": "Qwen2.5-Coder-7B",
        "context_length": 131072,
        "supports_tools": True,
        "supports_vision": False,
        "recommended_temperature": 0.7,
        "recommended_top_p": 0.9,
    },
    "qwen2.5-coder-14b": {
        "name": "Qwen2.5-Coder-14B",
        "context_length": 131072,
        "supports_tools": True,
        "supports_vision": False,
        "recommended_temperature": 0.7,
        "recommended_top_p": 0.9,
    },
    "qwen2.5-coder-32b": {
        "name": "Qwen2.5-Coder-32B",
        "context_length": 131072,
        "supports_tools": True,
        "supports_vision": False,
        "recommended_temperature": 0.7,
        "recommended_top_p": 0.9,
    },
}


# LM Studio defaults
LM_STUDIO_CONFIG = {
    "base_url": "http://localhost:1234/v1",
    "timeout": 60.0,
    "max_retries": 3,
    "supports_streaming": True,
    "supports_function_calling": True,
}


# System prompt for tool use
QWEN_TOOL_SYSTEM_PROMPT = """You are Qwen 2.5 Coder, a helpful AI coding assistant.

You have access to tools that can help you accomplish tasks. When you need information or need to perform an action, use the appropriate tool.

Guidelines for tool use:
1. Think about what information you need
2. Use tools to gather that information
3. Synthesize the results into a helpful response
4. If a tool fails, try an alternative approach

Always provide clear, accurate, and helpful responses."""


def get_model_config(model_name: str) -> Dict[str, Any]:
    """Get configuration for a Qwen model.
    
    Args:
        model_name: Name of the model
        
    Returns:
        Model configuration dict
        
    Raises:
        ValueError: If model name is not recognized
    """
    if model_name not in QWEN_MODELS:
        # Try fuzzy match
        for key in QWEN_MODELS:
            if model_name.lower() in key.lower():
                model_name = key
                break
        else:
            raise ValueError(f"Unknown model: {model_name}")
    
    return QWEN_MODELS[model_name]


def get_default_model() -> str:
    """Get default model name."""
    return "qwen2.5-coder-7b"
