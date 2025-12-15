"""
flow/learning_nudge.py - Contextual Learning Prompts

Generates learning prompts based on failure type to help the agent
reflect on specific mistakes.

Phase 2B: Learning Mode Improvements
"""

from typing import Dict, Any, Optional


# Error class to learning prompt mapping
LEARNING_PROMPTS = {
    "PATH_NOT_FOUND": (
        "📚 REFLECT: The path didn't exist.\n"
        "- What directory structure did you expect?\n"
        "- What actually exists? (Use list_files to verify)\n"
        "- How can you verify paths before using them?"
    ),
    "PATH_OUTSIDE_WORKSPACE": (
        "📚 REFLECT: You tried to access a path outside the workspace.\n"
        "- Which paths are writable? (workspace/ only)\n"
        "- For project files, use read_file or create_patch instead"
    ),
    "PERMISSION_DENIED": (
        "📚 REFLECT: Permission was denied.\n"
        "- Are you trying to write outside workspace/?\n"
        "- Is the file locked by another process?"
    ),
    "SYNTAX_ERROR": (
        "📚 REFLECT: There was a syntax error.\n"
        "- What syntax rule was violated?\n"
        "- Common issues: Python True/False, missing quotes, indentation"
    ),
    "TIMEOUT": (
        "📚 REFLECT: The operation timed out.\n"
        "- What made this slow? (large file, network, complex computation)\n"
        "- Can you chunk the work or use streaming?"
    ),
    "SIZE_LIMIT": (
        "📚 REFLECT: The file was too large.\n"
        "- Use head/tail for preview, or pyexe for streaming\n"
        "- Consider sampling or filtering before loading"
    ),
    "ALREADY_EXISTS": (
        "📚 REFLECT: The target already exists.\n"
        "- Check before creating with list_files\n"
        "- Use overwrite if intentional"
    ),
}

# Tool-specific learning prompts for common mistakes
TOOL_LEARNING_PROMPTS = {
    "create_patch": (
        "📚 REFLECT: create_patch requires specific arguments.\n"
        "- Required: file, plan, diff, tests\n"
        "- For workspace files, use write_file directly instead"
    ),
    "pyexe": (
        "📚 REFLECT: pyexe runs in isolated context.\n"
        "- Variables don't persist between calls\n"
        "- Use print() to see output\n"
        "- Python booleans are True/False (capitalized)"
    ),
    "shell": (
        "📚 REFLECT: shell command failed.\n"
        "- On Windows, use CMD syntax (dir, type) not bash (ls, cat)\n"
        "- Quote paths with spaces"
    ),
}


def get_learning_prompt(
    error_class: str,
    tool_name: str,
    error_message: str = "",
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a contextual learning prompt based on failure.
    
    Args:
        error_class: Classified error type (PATH_NOT_FOUND, etc.)
        tool_name: Name of the tool that failed
        error_message: The actual error message
        context: Optional additional context
        
    Returns:
        Learning prompt string
    """
    # Check for tool-specific prompt first
    if tool_name in TOOL_LEARNING_PROMPTS:
        tool_prompt = TOOL_LEARNING_PROMPTS[tool_name]
    else:
        tool_prompt = ""
    
    # Get error class prompt
    error_prompt = LEARNING_PROMPTS.get(error_class, "")
    
    if not error_prompt and not tool_prompt:
        # Generic fallback
        return (
            "📚 REFLECT: This operation failed.\n"
            f"- Tool: {tool_name}\n"
            f"- Error: {error_message[:100] if error_message else 'unknown'}\n"
            "- What caused this? How can you avoid it next time?"
        )
    
    # Combine prompts if both exist
    if error_prompt and tool_prompt:
        return f"{error_prompt}\n\n{tool_prompt}"
    
    return error_prompt or tool_prompt


def format_pending_failures(failures: list) -> str:
    """Format pending failures for display in learning requirement message.
    
    Args:
        failures: List of failure dicts with tool, error, step
        
    Returns:
        Formatted string summarizing failures
    """
    if not failures:
        return "No pending failures."
    
    lines = ["Pending failures to reflect on:"]
    for i, f in enumerate(failures[:3], 1):  # Show max 3
        tool = f.get("tool", "unknown")
        error = f.get("error", "")[:50]
        step = f.get("step", "?")
        lines.append(f"  {i}. [{tool}] Step {step}: {error}...")
    
    if len(failures) > 3:
        lines.append(f"  ... and {len(failures) - 3} more")
    
    return "\n".join(lines)


def create_playbook_template(failure: Dict[str, Any]) -> str:
    """Create a structured playbook template for a failure.
    
    Args:
        failure: Failure dict with tool, error, args
        
    Returns:
        Markdown template for agent to fill in
    """
    tool = failure.get("tool", "unknown")
    error = failure.get("error", "unknown error")
    
    return f"""Use memory(operation='learn', content='...') with this structure:

TRIGGER: {tool} failed
SYMPTOM: {error[:100]}
ROOT CAUSE: [What actually caused this?]
SOLUTION: [What's the correct approach?]
TEST: [How to verify the fix works?]
"""
