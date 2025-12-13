"""
flow/plans.py - Planning and Prompts

This module handles planning prompts and system instructions.
It tells the model HOW to use tools effectively.

Responsibilities:
- System prompts for tool-using agents
- Planning strategies
- Few-shot examples

Rules:
- Prompts should be clear and concise
- Include examples of good tool usage
- Explain when to use vs not use tools
"""

from typing import List
from core.types import Message, MessageRole, Tool


def create_system_prompt(tools: List[Tool]) -> str:
    """Create system prompt for tool-using agent.
    
    This prompt instructs the model on:
    - Its role as a helpful assistant
    - How to use tools effectively
    - When to call tools vs answer directly
    
    Args:
        tools: Available tools
        
    Returns:
        System prompt string
    """
    base_prompt = """You are a helpful AI assistant with access to tools.

Your goal is to help the user accomplish their task efficiently.

Guidelines:
1. Think step by step about what the user needs
2. Use tools when you need information or to take actions
3. Answer directly when you already have the information
4. Be concise but thorough
5. If a tool fails, try a different approach or explain the limitation

CRITICAL - Tool Call Format:
To call a tool, use this EXACT XML format:
<tool name="tool_name">{"arg1": "value1", "arg2": "value2"}</tool>

Examples:
- List files: <tool name="list_files">{"path": "."}</tool>
- Read file: <tool name="read_file">{"path": "data/config.json"}</tool>
- Write file: <tool name="write_file">{"path": "output.txt", "content": "Hello world"}</tool>
- Shell command: <tool name="shell">{"cmd": "echo hello"}</tool>
- Fetch URL: <tool name="fetch">{"url": "https://example.com"}</tool>

IMPORTANT:
- Use "." for current directory, not absolute paths like "C:\\"
- All file paths are relative to the workspace directory
- Arguments must be valid JSON inside the tool tag
- Only call ONE tool at a time and wait for the result
"""
    
    if tools:
        tools_section = "\n\nAvailable tools:\n"
        for tool in tools:
            tools_section += f"- {tool.name}: {tool.description}\n"
        base_prompt += tools_section
    
    return base_prompt


def create_planner_prompt(task: str) -> str:
    """Create a planning prompt for complex tasks.
    
    This breaks down the task into steps.
    
    Args:
        task: User's task
        
    Returns:
        Planning prompt
    """
    return f"""Let's break down this task step by step:

Task: {task}

What steps are needed? What tools should be used?"""


def get_tool_usage_examples() -> List[dict]:
    """Get few-shot examples of good tool usage.
    
    Returns:
        List of example conversations
    """
    return [
        {
            "user": "What files are in the current directory?",
            "assistant_thinking": "I need to list files in the current directory.",
            "tool_call": {"name": "list_files", "args": {"path": "."}},
            "tool_result": "📁 src/\n📄 README.md\n📄 main.py",
            "assistant_response": "The current directory contains:\n- A 'src' folder\n- README.md file\n- main.py file",
        },
        {
            "user": "What's 2 + 2?",
            "assistant_thinking": "This is simple arithmetic. I can answer directly.",
            "tool_call": None,
            "tool_result": None,
            "assistant_response": "2 + 2 = 4",
        },
    ]


def format_tool_error(tool_name: str, error: str) -> str:
    """Format a tool error message for the model.
    
    Args:
        tool_name: Name of the tool that failed
        error: Error message
        
    Returns:
        Formatted error message
    """
    return f"Tool '{tool_name}' failed with error: {error}\n\nPlease try a different approach or let the user know about this limitation."
