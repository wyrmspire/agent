"""
model/embed/confs.py - Embedding Model Configuration

This module contains configuration for embedding models.

Supported models:
- text-embedding-3-small (OpenAI-compatible)
- text-embedding-3-large (OpenAI-compatible)
- nomic-embed-text (local)
- all-MiniLM-L6-v2 (local)

Rules:
- No model files here
- Only configuration and metadata
"""

from typing import Dict, Any


# Embedding model configurations
EMBEDDING_MODELS = {
    "text-embedding-3-small": {
        "name": "text-embedding-3-small",
        "dimensions": 1536,
        "max_tokens": 8191,
        "provider": "openai",
    },
    "text-embedding-3-large": {
        "name": "text-embedding-3-large",
        "dimensions": 3072,
        "max_tokens": 8191,
        "provider": "openai",
    },
    "nomic-embed-text": {
        "name": "nomic-embed-text",
        "dimensions": 768,
        "max_tokens": 8192,
        "provider": "local",
    },
    "all-MiniLM-L6-v2": {
        "name": "all-MiniLM-L6-v2",
        "dimensions": 384,
        "max_tokens": 512,
        "provider": "local",
    },
}


def get_embedding_config(model_name: str) -> Dict[str, Any]:
    """Get configuration for an embedding model.
    
    Args:
        model_name: Name of the model
        
    Returns:
        Model configuration dict
        
    Raises:
        ValueError: If model name is not recognized
    """
    if model_name not in EMBEDDING_MODELS:
        raise ValueError(f"Unknown embedding model: {model_name}")
    
    return EMBEDDING_MODELS[model_name]


def get_default_embedding_model() -> str:
    """Get default embedding model name."""
    return "all-MiniLM-L6-v2"
