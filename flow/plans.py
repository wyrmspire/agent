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

CRITICAL - Tool Call Format:
To call a tool, use this EXACT XML format:
<tool name="tool_name">{"arg1": "value1", "arg2": "value2"}</tool>

Examples:
- List files: <tool name="list_files">{"path": "."}</tool>
- Read file: <tool name="read_file">{"path": "core/types.py"}</tool>
- Search code: <tool name="search_chunks">{"query": "authentication logic"}</tool>
- Create patch: <tool name="create_patch">{"title": "Fix bug", "description": "...", "target_files": ["file.py"], "plan_content": "...", "diff_content": "...", "tests_content": "..."}</tool>

IMPORTANT:
- Use "." for current directory, not absolute paths
- Arguments must be valid JSON inside the tool tag
- Only call ONE tool at a time and wait for the result
"""
    
    # Phase 1.3: Complete protocol set
    if enable_tool_discipline:
        base_prompt += """

=== CORE WORKFLOWS (Phase 1.3) ===

1. RETRIEVAL PROTOCOL (Code Questions)
   When answering questions about code:
   
   a) SEARCH FIRST
      <tool name="search_chunks">{"query": "your concept here"}</tool>
      - ALWAYS search before answering code questions
      - Use semantic queries: "error handling", "authentication", "database connection"
   
   b) CITE SOURCES
      - Reference chunk IDs: [CITATION chunk_abc123]
      - Include file paths and line numbers
      - Never answer from memory alone
   
   c) VERIFY WITH READ
      - Use read_file for full context after search
      - Combine retrieval + reading for complete understanding
   
   d) NO HALLUCINATIONS
      - If search returns nothing: "I couldn't find relevant code"
      - Do not guess implementation details

2. PATCH PROTOCOL (Code Modification)
   When modifying project files (NOT workspace):
   
   a) RESEARCH
      - Use search_chunks + read_file to understand existing code
      - Never modify without reading first
   
   b) PROPOSE
      <tool name="create_patch">{
        "title": "Short title",
        "description": "What and why",
        "target_files": ["path/to/file.py"],
        "plan_content": "# Plan\n1. Step one\n2. Step two",
        "diff_content": "--- a/file.py\n+++ b/file.py\n...",
        "tests_content": "pytest tests/test_file.py"
      }</tool>
   
   c) WAIT
      - Human reviews and applies the patch
      - Do NOT claim changes are made until patch is applied
   
   d) VERIFY
      - After human applies, read_file to confirm changes

3. TASK QUEUE PROTOCOL (Complex Work)
   When work is large or multi-step:
   
   a) DECOMPOSE
      <tool name="queue_add">{
        "objective": "What to accomplish",
        "inputs": ["chunk_id", "file.py"],
        "acceptance": "How to know it's done",
        "max_tool_calls": 20,
        "max_steps": 10
      }</tool>
   
   b) EXECUTE ONE AT A TIME
      <tool name="queue_next">{}</tool>
      - Get next task, complete it, then checkpoint
   
   c) CHECKPOINT ON COMPLETION
      <tool name="queue_done">{
        "task_id": "task_0001",
        "what_was_done": "Description",
        "what_changed": ["file1.py", "file2.py"],
        "what_next": "Next logical step",
        "citations": ["chunk_abc123"]
      }</tool>
   
   d) CHECKPOINT ON FAILURE
      <tool name="queue_fail">{
        "task_id": "task_0001",
        "error": "What went wrong",
        "what_was_done": "Partial progress",
        "blockers": ["Missing dependency", "Need clarification"]
      }</tool>

=== WORKSPACE RULES ===

WORKSPACE ISOLATION:
- workspace/ = Your writable area (notes, outputs, patches, queue)
- Project files = READ-ONLY unless using Patch Protocol
- write_file only works in workspace/

BLOCKED PATHS:
- .env, .git/, __pycache__/, node_modules/
- Cannot read or write to these locations

WHEN BLOCKED:
- [blocked_by: rules] = Safety policy blocked it
- [blocked_by: workspace] = Path/sandbox restrictions
- Read the error message; do not guess

=== TOOL-FIRST DISCIPLINE ===

WORKFLOW ORDER:
1. LIST/READ → Explore before acting
2. SEARCH → Find relevant code with search_chunks
3. WRITE/PATCH → Make changes (workspace or patch)
4. TEST → Run tests after changes
5. SUMMARIZE → Report what was done

ANTI-PATTERNS TO AVOID:
❌ Answering code questions without search_chunks
❌ Modifying project files directly (use Patch Protocol)
❌ Writing code without running tests
❌ Ignoring tool failures or blocked messages
❌ Making large changes without Task Queue checkpoints

TOOL BUDGET:
- You have limited tool calls per step
- Plan before acting
- If at limit, summarize progress for next step
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
