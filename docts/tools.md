# Tools

This document describes the tool system and how to create custom tools.

## Overview

Tools are actions the agent can take in the real world:
- Read and write files
- Execute shell commands
- Fetch content from URLs
- (Future) Search databases, call APIs, etc.

**Philosophy**: Tools do NOT reason or make decisions. They are pure-ish functions: inputs → outputs.

## Built-in Tools

### list_files
List files and directories in a path.

**Parameters**:
- `path` (string, required) - Directory path to list

**Returns**: List of files with names, types, and sizes.

**Example**:
```json
{
  "name": "list_files",
  "arguments": {
    "path": "."
  }
}
```

### read_file
Read contents of a file.

**Parameters**:
- `path` (string, required) - File path to read

**Returns**: File content as text.

**Limits**: Max 1MB file size, UTF-8 text only.

**Example**:
```json
{
  "name": "read_file",
  "arguments": {
    "path": "README.md"
  }
}
```

### write_file
Write content to a file.

**Parameters**:
- `path` (string, required) - File path to write
- `content` (string, required) - Content to write

**Returns**: Success message with bytes written.

**Example**:
```json
{
  "name": "write_file",
  "arguments": {
    "path": "output.txt",
    "content": "Hello, world!"
  }
}
```

### shell
Execute a shell command.

**Parameters**:
- `command` (string, required) - Command to execute
- `cwd` (string, optional) - Working directory

**Returns**: stdout and stderr output.

**Limits**: 30 second timeout by default.

**Safety**: Subject to rule engine validation. Dangerous commands are blocked.

**Example**:
```json
{
  "name": "shell",
  "arguments": {
    "command": "ls -la"
  }
}
```

### fetch
Fetch content from a URL.

**Parameters**:
- `url` (string, required) - URL to fetch (HTTP or HTTPS)

**Returns**: Response content (text, JSON, XML) or size info for binary.

**Limits**: Max 5MB response size, 30 second timeout.

**Example**:
```json
{
  "name": "fetch",
  "arguments": {
    "url": "https://api.github.com/repos/wyrmspire/agent"
  }
}
```

## Creating Custom Tools

### Step 1: Implement BaseTool

```python
from tool.bases import BaseTool, create_json_schema
from core.types import ToolResult
from typing import Dict, Any

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "What my tool does"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        # CRITICAL: type must be "object"
        return create_json_schema(
            properties={
                "arg1": {
                    "type": "string",
                    "description": "First argument",
                },
            },
            required=["arg1"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        # Do the work
        result = do_something(arguments["arg1"])
        
        # Always return ToolResult
        return ToolResult(
            tool_call_id="",
            output=result,
            success=True,
        )
```

### Step 2: Register the Tool

```python
from tool.index import ToolRegistry

registry = ToolRegistry()
registry.register(MyTool())
```

Or add to boot/wires.py to register automatically.

## Tool Schema Rules

**CRITICAL**: Tool parameter schemas MUST follow these rules:

1. **Root type must be "object"**:
   ```python
   {
       "type": "object",  # REQUIRED
       "properties": {...}
   }
   ```

2. **Use create_json_schema helper**:
   ```python
   from tool.bases import create_json_schema
   
   schema = create_json_schema(
       properties={...},
       required=[...]
   )
   ```

3. **Each property needs type and description**:
   ```python
   {
       "arg_name": {
           "type": "string",  # or "number", "boolean", "array", "object"
           "description": "What this argument does",
       }
   }
   ```

### Why This Matters

LM Studio and OpenAI expect tool schemas in this format:

```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "What it does",
    "parameters": {
      "type": "object",  ← MUST BE "object"
      "properties": {...},
      "required": [...]
    }
  }
}
```

If `parameters.type` is not `"object"`, you'll get errors like:
```
invalid_union_discriminator: Expected 'object'
```

## Tool Result Format

All tools must return `ToolResult`:

```python
from core.types import ToolResult

# Success
ToolResult(
    tool_call_id="call-123",
    output="Result data here",
    success=True,
)

# Failure
ToolResult(
    tool_call_id="call-123",
    output="",
    error="What went wrong",
    success=False,
)
```

**Never throw exceptions**. Always catch and convert to ToolResult.

## Tool Safety

Tools are validated by the RuleEngine before execution.

Default safety rules (see core/rules.py):
- Block dangerous shell commands (rm -rf, dd, mkfs, etc.)
- Block access to sensitive files (/etc/passwd, .ssh keys, etc.)

Add custom rules in boot/wires.py:

```python
from core.rules import SafetyRule, RuleEngine

engine = RuleEngine()
engine.add_rule(SafetyRule(
    name="no_network_access",
    forbidden_patterns=["curl", "wget", "nc"]
))
```

## Tool Execution Flow

```
1. Model requests tool call
   ↓
2. RuleEngine validates
   ↓ (if blocked)
   └→ Return error to model
   ↓ (if allowed)
3. ToolRegistry looks up tool
   ↓
4. Tool.execute() runs
   ↓
5. Result captured (success or error)
   ↓
6. Result fed back to model
   ↓
7. Model incorporates result into answer
```

## Best Practices

1. **Keep tools focused**: One tool = one capability
2. **Validate inputs**: Check arguments before executing
3. **Handle errors gracefully**: Return ToolResult with error, don't throw
4. **Set timeouts**: Prevent hanging operations
5. **Add size limits**: Prevent memory issues
6. **Log execution**: Use logging for debugging
7. **Document parameters**: Clear descriptions help the model
8. **Test thoroughly**: Unit test each tool independently

## Testing Tools

See tests/tools/ttool.py for examples:

```python
import pytest
from tool.bases import BaseTool
from core.types import ToolCall

@pytest.mark.asyncio
async def test_my_tool():
    tool = MyTool()
    
    tool_call = ToolCall(
        id="test-1",
        name="my_tool",
        arguments={"arg1": "value"}
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "expected" in result.output
```

## Debugging Tool Issues

### Tool not being called
- Check tool is registered in registry
- Check tool name matches exactly
- Check model has tools in request

### Tool schema errors
- Verify `parameters.type == "object"`
- Use `create_json_schema()` helper
- Check all properties have type and description

### Tool execution errors
- Check logs for exception details
- Verify input validation
- Test tool in isolation

### Tool results ignored
- Check result is fed back to model
- Verify conversation flow includes tool message
- Check max_steps not reached
