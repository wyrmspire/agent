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

from typing import List, Optional, Dict, Any
from core.types import Message, MessageRole, Tool


def create_system_prompt(
    tools: List[Tool],
    project_context: Optional[Dict[str, Any]] = None,
    enable_tool_discipline: bool = True,
) -> str:
    """Create system prompt for tool-using agent.
    
    This prompt instructs the model on:
    - Its role as a helpful assistant
    - How to use tools effectively
    - When to call tools vs answer directly
    - Tool-first workflow discipline (Phase 0.5)
    
    Args:
        tools: Available tools
        project_context: Optional project context
        enable_tool_discipline: Enable Phase 0.5 tool discipline rules
        
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
    
    # Phase 0.5: Add tool-first discipline
    if enable_tool_discipline:
        base_prompt += """

TOOL-FIRST WORKFLOW (Phase 0.5 - Required):
When working with code, you MUST follow this disciplined workflow:

1. LIST/READ → Explore before acting
   - Use list_files to see what exists
   - Use read_file to understand current code
   - Do NOT skip this step

2. WRITE → Make targeted changes
   - Use write_file or edit_file for modifications
   - Keep changes focused and minimal
   - Document what you changed

3. TEST → Verify your changes work
   - ALWAYS run tests after writing code
   - Use shell to run pytest, unittest, or project-specific tests
   - Read test output carefully

4. SUMMARIZE → Report results
   - Explain what you did
   - Report test results
   - Suggest next steps if needed

ANTI-PATTERNS TO AVOID:
❌ Writing code without running tests
❌ Calling shell repeatedly when errors occur (read the error first!)
❌ Making changes without reading existing code first
❌ Ignoring tool failures

TOOL BUDGET:
- You have a limited number of tool calls per step
- Use them wisely - plan before acting
- If you hit the limit, summarize progress and continue in next step
"""
    
    if tools:
        tools_section = "\n\nAvailable tools:\n"
        for tool in tools:
            tools_section += f"- {tool.name}: {tool.description}\n"
        base_prompt += tools_section
    
    # Add project context if available
    if project_context:
        project_section = f"""

PROJECT CONTEXT:
You are working on a project. Consult the Plan and Lab Notebook below for context.

Project: {project_context.get('name', 'Unknown')}
State: {project_context.get('state', 'Unknown')}
Description: {project_context.get('description', 'No description')}

Current Tasks:
"""
        tasks = project_context.get('tasks', [])
        if tasks:
            for task in tasks:
                status = task.get('status', 'pending')
                desc = task.get('description', '')
                project_section += f"- [{status}] {desc}\n"
        else:
            project_section += "- No tasks defined\n"
        
        # Add recent lab notebook entries
        recent_notes = project_context.get('recent_notes', [])
        if recent_notes:
            project_section += "\nRecent Lab Notebook Entries:\n"
            for note in recent_notes[-5:]:  # Last 5 entries
                project_section += f"  {note}\n"
        
        project_section += """
When working on tasks:
1. Check the current project state and tasks
2. Reference the Lab Notebook for previous findings
3. Update task status as you make progress
4. Add observations to the Lab Notebook
"""
        
        base_prompt += project_section
    
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
