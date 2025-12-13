"""
servr/api.py - Python Model Server

This module implements a simple FastAPI server to host the Python model.
It exposes an OpenAI-compatible API so the agent can use it as a standard gateway.

Endpoints:
- POST /v1/chat/completions: Generate completions
- GET /health: Health check

Usage:
    uvicorn servr.api:app --host 0.0.0.0 --port 8000
"""

import bitsandbytes # Trigger potential DLL load fix
import time
import logging
import json
import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any, Union
import torch
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

# Import configuration loader
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from boot.setup import load_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model_server")

app = FastAPI(title="Agent Model Server")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------------
# OpenAI API Types
# -------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str = "default"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str

class ChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-default"
    object: str = "chat.completion"
    created: int = int(time.time())
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Dict[str, int]

# -------------------------------------------------------------------------
# Model Logic (Placeholder)
# -------------------------------------------------------------------------

# -------------------------------------------------------------------------
# Model Logic (Transfomers)
# -------------------------------------------------------------------------

from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

class ModelEngine:
    """Real Python model engine using Transformers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize model engine with configuration.
        
        Args:
            config: Configuration dictionary from boot.setup
        """
        # Load model path from config (fallback to environment or default)
        self.model_path = config.get("model_path") or r"C:\Users\wyrms\.cache\huggingface\hub\models--Qwen--Qwen2.5-Coder-7B-Instruct\snapshots\c03e6d358207e414f1eca0bb1891e29f1db0e242"
        self.model_name = config.get("model", "qwen2.5-coder-7b-instruct")
        self.ready = False
        self.model = None
        self.tokenizer = None
        logger.info(f"Initializing model engine with path: {self.model_path}")
        
    def load(self):
        """Load the model (real loading)."""
        logger.info(f"Loading model from {self.model_path}...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, 
                trust_remote_code=True
            )
            
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16
            )
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                device_map="auto",
                torch_dtype=torch.float16,
                quantization_config=quantization_config,
                low_cpu_mem_usage=True,
            )
            self.ready = True
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise e
        
    def generate(self, messages: List[Message], **kwargs) -> Union[str, Dict[str, Any]]:
        """Generate a response using the model."""
        
        # Convert Pydantic messages to dicts for chat template
        msg_dicts = []
        for m in messages:
            msg_dict = {"role": m.role, "content": m.content}
            msg_dicts.append(msg_dict)
            
        # Apply chat template
        prompt = self.tokenizer.apply_chat_template(
            msg_dicts, 
            tokenize=False, 
            add_generation_prompt=True
        )
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=kwargs.get("max_tokens", 512) or 512,
                temperature=kwargs.get("temperature", 0.7),
                do_sample=True,
            )
            
        # Decode
        # We process only the new tokens to avoid echoing the prompt
        new_tokens = outputs[0][inputs.input_ids.shape[1]:]
        response_text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        
        # ---------------------------------------------------------------------
        # Tag-Based Tool Parser (Robust for Multi-line Code)
        # ---------------------------------------------------------------------
        # Use XML-style tags to extract tool calls reliably.
        # This handles multi-line Python code, nested quotes, etc.
        # Format: <tool name="tool_name">{"arg": "value"}</tool>
        
        tool_calls = self._parse_tool_calls(response_text)
        
        # If tools detected, return structured response
        if tool_calls:
            return {
                "content": response_text,  # Keep reasoning
                "tool_calls": tool_calls
            }
        
        return response_text
    
    def _parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Parse tool calls from text using tag-based format.
        
        Expected format:
            <tool name="tool_name">{"arg1": "value1", "arg2": "value2"}</tool>
        
        This is much more robust than regex for handling:
        - Multi-line code blocks
        - Nested quotes
        - Special characters
        
        Args:
            text: Response text from model
            
        Returns:
            List of tool call dictionaries
        """
        tool_calls = []
        
        # Pattern to match tool tags with name attribute
        # We use re.DOTALL to match across newlines
        pattern = r'<tool\s+name="([^"]+)">(.*?)</tool>'
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for match in matches:
            tool_name = match.group(1)
            tool_args_str = match.group(2).strip()
            
            try:
                # Parse JSON arguments
                tool_args = json.loads(tool_args_str)
                
                # Create tool call
                tool_calls.append({
                    "id": f"call_{tool_name}_{int(time.time() * 1000)}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(tool_args)
                    }
                })
                logger.info(f"Parsed tool call: {tool_name}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool arguments for {tool_name}: {e}")
                logger.debug(f"Arguments string: {tool_args_str}")
        
        # Fallback: Try legacy regex patterns for backward compatibility
        # This ensures existing prompts still work during transition
        if not tool_calls:
            tool_calls = self._parse_legacy_format(text)
        
        return tool_calls
    
    def _parse_legacy_format(self, text: str) -> List[Dict[str, Any]]:
        """Legacy parser for backward compatibility.
        
        Supports simple patterns like:
        - list_files <path>
        - fetch <url>
        
        Args:
            text: Response text
            
        Returns:
            List of tool calls
        """
        import shlex
        tool_calls = []
        
        # Check for list_files
        ls_match = re.search(r"list_files\s+([^\s\n]+)", text)
        if ls_match:
            tool_calls.append({
                "id": f"call_ls_{int(time.time())}",
                "type": "function",
                "function": {
                    "name": "list_files",
                    "arguments": json.dumps({"path": ls_match.group(1)})
                }
            })
        
        # Check for fetch
        fetch_match = re.search(r"fetch\s+(https?://[^\s\n]+)", text)
        if fetch_match:
            tool_calls.append({
                "id": f"call_fetch_{int(time.time())}",
                "type": "function",
                "function": {
                    "name": "fetch",
                    "arguments": json.dumps({"url": fetch_match.group(1)})
                }
            })
        
        return tool_calls

# Load configuration
config = load_config()
logger.info("Configuration loaded")

# Global model instance
engine = ModelEngine(config)

@app.on_event("startup")
async def startup_event():
    engine.load()

# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "ok", "ready": engine.ready}

@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI compatible)."""
    return {
        "object": "list",
        "data": [
            {
                "id": engine.model_name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "user",
            }
        ]
    }

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    if not engine.ready:
        raise HTTPException(status_code=503, detail="Model not ready")
        
    logger.info(f"Received request: {len(request.messages)} messages")
    
    # Generate content
    response_data = engine.generate(request.messages)
    
    # Construct response
    if isinstance(response_data, dict) and "tool_calls" in response_data:
        # It's a tool call response
        message = Message(
            role="assistant",
            content=response_data.get("content", ""), # Tool calls can have null content or empty string
            tool_calls=response_data["tool_calls"]
        )
        finish_reason = "tool_calls"
    else:
        # It's a standard text response
        message = Message(
            role="assistant",
            content=str(response_data)
        )
        finish_reason = "stop"
    
    choice = ChatCompletionResponseChoice(
        index=0,
        message=message,
        finish_reason=finish_reason
    )
    
    return ChatCompletionResponse(
        id=f"chatcmpl-{int(time.time())}",
        model=request.model,
        choices=[choice],
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
