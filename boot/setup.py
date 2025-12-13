"""
boot/setup.py - Configuration and Environment Setup

This module handles:
- Loading environment variables
- Reading configuration files
- Setting up paths
- Configuring logging

Responsibilities:
- Find and load .env files
- Parse config files (YAML/JSON/TOML)
- Set up Python path
- Initialize logging

Rules:
- No business logic
- Only configuration loading
- Fail fast if critical config is missing
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional


def get_project_root() -> Path:
    """Get the project root directory."""
    # Assume boot/ is at project root
    return Path(__file__).parent.parent


def load_env_file(env_path: Optional[Path] = None) -> None:
    """Load environment variables from .env file.
    
    Args:
        env_path: Path to .env file. If None, searches in project root.
    """
    if env_path is None:
        env_path = get_project_root() / ".env"
    
    if not env_path.exists():
        return
    
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


def load_config() -> Dict[str, Any]:
    """Load configuration from environment and files.
    
    Returns:
        Configuration dictionary
    """
    # Load .env file first
    load_env_file()
    
    # Build config from environment
    config = {
        # Server config
        "host": os.getenv("AGENT_HOST", "0.0.0.0"),
        "port": int(os.getenv("AGENT_PORT", "8000")),
        "enable_http": os.getenv("AGENT_ENABLE_HTTP", "false").lower() == "true",
        
        # Gateway selection: "local" (default) or "gemini"
        "gateway": os.getenv("AGENT_GATEWAY", "local"),
        
        # Model config (for local gateway)
        "model": os.getenv("AGENT_MODEL", "qwen2.5-coder"),
        "model_url": os.getenv("AGENT_MODEL_URL", "http://localhost:1234/v1"),
        "model_api_key": os.getenv("AGENT_MODEL_API_KEY", ""),
        "model_path": os.getenv("AGENT_MODEL_PATH", ""),
        
        # Gemini config (reads from .env, NOT .env.example)
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        
        # Agent config
        "max_steps": int(os.getenv("AGENT_MAX_STEPS", "20")),
        "temperature": float(os.getenv("AGENT_TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv("AGENT_MAX_TOKENS", "4096")),
        
        # Tool config
        "enable_shell": os.getenv("AGENT_ENABLE_SHELL", "true").lower() == "true",
        "enable_files": os.getenv("AGENT_ENABLE_FILES", "true").lower() == "true",
        "enable_fetch": os.getenv("AGENT_ENABLE_FETCH", "true").lower() == "true",
        "enable_data_view": os.getenv("AGENT_ENABLE_DATA_VIEW", "true").lower() == "true",
        "enable_pyexe": os.getenv("AGENT_ENABLE_PYEXE", "true").lower() == "true",
        
        # Storage config
        "store_type": os.getenv("AGENT_STORE_TYPE", "memory"),
        "store_path": os.getenv("AGENT_STORE_PATH", "./data"),
        
        # Paths
        "project_root": str(get_project_root()),
    }
    
    return config


def setup_logging(level: str = None, session_id: str = None) -> str:
    """Setup logging configuration with file and console output.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        session_id: Optional session ID for log file name
        
    Returns:
        Path to the session log file
    """
    from datetime import datetime
    
    if level is None:
        level = os.getenv("AGENT_LOG_LEVEL", "INFO")
    
    # Convert string to logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logs directory
    project_root = get_project_root()
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Generate session log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if session_id:
        log_filename = f"session_{timestamp}_{session_id[:8]}.log"
    else:
        log_filename = f"session_{timestamp}.log"
    log_path = logs_dir / log_filename
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (shows INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (captures everything with verbose format)
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Log session start
    logging.info(f"Session log started: {log_path}")
    
    return str(log_path)


def setup_python_path() -> None:
    """Add project root to Python path."""
    project_root = get_project_root()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
