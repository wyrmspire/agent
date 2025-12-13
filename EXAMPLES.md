# Examples

This document shows example interactions with the agent system.

## CLI Chat Examples

### Example 1: Simple Greeting (No Tools)

```
You: hi

Agent: Hello! I'm here to help you with coding tasks and general assistance. I have access to various tools that allow me to interact with your file system, execute commands, and fetch web content. What would you like help with today?

(1 steps)
```

**What happened**: Agent answered directly without using any tools.

### Example 2: List Files

```
You: What files are in the current directory?

Agent: Let me check that for you.

[Using tool: list_files(path=".")]

The current directory contains:
- 📁 boot/ (directory)
- 📁 core/ (directory)
- 📁 gate/ (directory)
- 📁 tool/ (directory)
- 📁 flow/ (directory)
- 📁 store/ (directory)
- 📁 servr/ (directory)
- 📁 model/ (directory)
- 📁 tests/ (directory)
- 📁 docts/ (directory)
- 📄 README.md (2,543 bytes)
- 📄 cli.py (4,304 bytes)
- 📄 requirements.txt (110 bytes)
- 📄 .gitignore (418 bytes)

(2 steps)
```

**What happened**: Agent used the `list_files` tool to get directory contents.

### Example 3: Read File

```
You: Show me the README.md file

Agent: I'll read that file for you.

[Using tool: read_file(path="README.md")]

Here's the content of README.md:

# Agent

A clean, well-architected local agent server for Qwen 2.5 Coder...

[file contents shown]

(2 steps)
```

**What happened**: Agent used `read_file` tool to get file contents.

### Example 4: Multi-Step Tool Use

```
You: Find all Python files in the boot directory and show me the first one

Agent: I'll help you with that. Let me first list the files in the boot directory.

[Using tool: list_files(path="boot")]

Found these Python files in boot/:
- mains.py
- setup.py  
- wires.py

Let me read the first one for you.

[Using tool: read_file(path="boot/mains.py")]

Here's the content of boot/mains.py:

[file contents shown]

(3 steps)
```

**What happened**: Agent used two tools in sequence - first to list files, then to read one.

### Example 5: Shell Command

```
You: What Python version is installed?

Agent: I'll check that for you.

[Using tool: shell(command="python3 --version")]

You have Python 3.12.0 installed.

(2 steps)
```

**What happened**: Agent used `shell` tool to execute a command.

### Example 6: Fetch URL

```
You: Get the GitHub API info for this repo

Agent: I'll fetch that information.

[Using tool: fetch(url="https://api.github.com/repos/wyrmspire/agent")]

Here's the repository information:
- Name: agent
- Description: llm agent home
- Stars: 0
- Forks: 0
- Language: Python
- Created: 2024-12-13

(2 steps)
```

**What happened**: Agent used `fetch` tool to get URL content.

### Example 7: Safety Rule Violation

```
You: Delete all files with rm -rf /

Agent: I cannot execute that command. The safety rules prevent dangerous operations like:
- rm -rf / (could delete entire filesystem)
- Operations on system directories
- Commands that could cause data loss

If you need to delete specific files, please specify them individually and I can help safely.

(1 steps)
```

**What happened**: Rule engine blocked the dangerous command.

## Programmatic Usage

### Example 1: Basic Agent Loop

```python
import asyncio
from core.types import MessageRole
from core.state import AgentState, ConversationState, ExecutionContext
from core.rules import get_default_engine
from gate.lmstd import LMStudioGateway
from tool.index import create_default_registry
from flow.loops import AgentLoop

async def main():
    # Setup components
    gateway = LMStudioGateway(
        base_url="http://localhost:1234/v1",
        model="qwen2.5-coder-7b"
    )
    
    tools = create_default_registry()
    rules = get_default_engine()
    
    loop = AgentLoop(
        gateway=gateway,
        tools=tools,
        rule_engine=rules,
        max_steps=20
    )
    
    # Create state
    state = AgentState(
        conversation=ConversationState(id="conv-123"),
        execution=ExecutionContext(
            run_id="run-456",
            conversation_id="conv-123"
        )
    )
    
    # Run agent
    result = await loop.run(state, "What files are here?")
    
    print(f"Answer: {result.final_answer}")
    print(f"Steps: {result.steps_taken}")
    
    await gateway.close()

asyncio.run(main())
```

### Example 2: Custom Tool

```python
from tool.bases import BaseTool, create_json_schema
from core.types import ToolResult
from typing import Dict, Any

class AddNumbersTool(BaseTool):
    """Simple tool that adds two numbers."""
    
    @property
    def name(self) -> str:
        return "add_numbers"
    
    @property
    def description(self) -> str:
        return "Add two numbers together and return the sum"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "a": {
                    "type": "number",
                    "description": "First number"
                },
                "b": {
                    "type": "number",
                    "description": "Second number"
                }
            },
            required=["a", "b"]
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        a = arguments["a"]
        b = arguments["b"]
        result = a + b
        
        return ToolResult(
            tool_call_id="",
            output=f"{a} + {b} = {result}",
            success=True
        )

# Register the tool
from tool.index import ToolRegistry

registry = ToolRegistry()
registry.register(AddNumbersTool())
```

### Example 3: Custom Safety Rule

```python
from core.rules import SafetyRule, RuleEngine

# Create custom rule
no_network = SafetyRule(
    name="no_network_commands",
    forbidden_patterns=[
        "curl",
        "wget",
        "nc",
        "telnet",
        "ftp"
    ]
)

# Add to engine
engine = RuleEngine()
engine.add_rule(no_network)

# Now all shell tools will be validated against this rule
```

### Example 4: Memory Usage

```python
from store.short import ShortMemory
from core.types import Message, MessageRole

# Create memory store
memory = ShortMemory(max_messages_per_conversation=100)

# Save messages
await memory.save_message(
    "conv-123",
    Message(role=MessageRole.USER, content="Hello")
)

await memory.save_message(
    "conv-123",
    Message(role=MessageRole.ASSISTANT, content="Hi there!")
)

# Retrieve messages
messages = await memory.get_messages("conv-123")
print(f"Conversation has {len(messages)} messages")
```

### Example 5: Tool Execution with Validation

```python
from tool.files import ReadFile
from core.types import ToolCall
from flow.execs import ToolExecutor, ExecutionConfig

# Create executor
executor = ToolExecutor(
    config=ExecutionConfig(
        timeout=30.0,
        log_args=True,
        log_results=True
    )
)

# Create tool and tool call
tool = ReadFile()
tool_call = ToolCall(
    id="call-123",
    name="read_file",
    arguments={"path": "README.md"}
)

# Execute safely
result = await executor.execute(tool, tool_call)

if result.success:
    print(f"File content: {result.output}")
else:
    print(f"Error: {result.error}")
```

## Configuration Examples

### Example 1: .env File

```bash
# Model configuration
AGENT_MODEL=qwen2.5-coder-7b
AGENT_MODEL_URL=http://localhost:1234/v1

# Agent behavior
AGENT_MAX_STEPS=20
AGENT_TEMPERATURE=0.7
AGENT_MAX_TOKENS=4096

# Tool settings
AGENT_ENABLE_SHELL=true
AGENT_ENABLE_FILES=true
AGENT_ENABLE_FETCH=true

# Storage
AGENT_STORE_TYPE=sqlite
AGENT_STORE_PATH=./data/memory.db

# Logging
AGENT_LOG_LEVEL=INFO
```

### Example 2: Programmatic Configuration

```python
from boot.setup import load_config

# Load default config
config = load_config()

# Override specific settings
config["max_steps"] = 10
config["temperature"] = 0.5
config["enable_shell"] = False

# Use in components
from flow.loops import AgentLoop

loop = AgentLoop(
    gateway=gateway,
    tools=tools,
    rule_engine=rules,
    max_steps=config["max_steps"],
    temperature=config["temperature"]
)
```

## Testing Examples

### Example 1: Test Custom Tool

```python
import pytest
from my_tools import AddNumbersTool
from core.types import ToolCall

@pytest.mark.asyncio
async def test_add_numbers():
    tool = AddNumbersTool()
    
    tool_call = ToolCall(
        id="test-1",
        name="add_numbers",
        arguments={"a": 5, "b": 3}
    )
    
    result = await tool.call(tool_call)
    
    assert result.success
    assert "8" in result.output
```

### Example 2: Test Agent Loop with Mock

```python
import pytest
from tests.flows.tflow import MockGateway
from flow.loops import AgentLoop

@pytest.mark.asyncio
async def test_my_workflow():
    # Setup mock gateway
    gateway = MockGateway()
    gateway.add_response("I'll help with that")
    
    # Setup loop
    loop = AgentLoop(gateway, tools, rules)
    
    # Run test
    result = await loop.run(state, "test input")
    
    assert result.success
    assert "help" in result.final_answer.lower()
```

## Common Patterns

### Pattern 1: Retry on Failure

```python
async def run_with_retry(loop, state, message, max_retries=3):
    for attempt in range(max_retries):
        result = await loop.run(state, message)
        
        if result.success:
            return result
        
        print(f"Attempt {attempt + 1} failed, retrying...")
    
    return result
```

### Pattern 2: Tool Result Validation

```python
from flow.judge import AgentJudge

judge = AgentJudge()

# After tool execution
judgment = judge.check_tool_result(result)

if not judgment.passed:
    print(f"Tool issue: {judgment.reason}")
    if judgment.suggestion:
        print(f"Suggestion: {judgment.suggestion}")
```

### Pattern 3: Streaming Responses

```python
async def stream_response(gateway, messages, tools):
    async for chunk in gateway.stream_complete(messages, tools):
        print(chunk.delta, end="", flush=True)
        
        if chunk.finish_reason:
            print(f"\n[Finished: {chunk.finish_reason}]")
            break
```

### Pattern 4: Conversation Management

```python
from store.longg import SQLiteMemory

# Setup persistent memory
memory = SQLiteMemory("./data/conversations.db")

# Save entire conversation
for message in state.messages:
    await memory.save_message(conversation_id, message)

# Later, restore conversation
messages = await memory.get_messages(conversation_id)
state.conversation.messages = messages
```

## Troubleshooting Examples

### Issue: Tool Not Found

```python
# Check if tool is registered
if not tools.has("my_tool"):
    print(f"Tool 'my_tool' not found")
    print(f"Available tools: {tools.list()}")
    
    # Register it
    tools.register(MyTool())
```

### Issue: Schema Validation Error

```python
# Validate tool schema
tool = MyTool()
schema = tool.parameters

assert schema["type"] == "object", "Schema must have type='object'"
assert "properties" in schema, "Schema must have properties"

# Convert to OpenAI format
openai_tool = {
    "type": "function",
    "function": {
        "name": tool.name,
        "description": tool.description,
        "parameters": schema  # Must be object schema
    }
}
```

### Issue: LM Studio Connection

```python
# Health check
gateway = LMStudioGateway("http://localhost:1234/v1")

healthy = await gateway.health_check()

if not healthy:
    print("Cannot connect to LM Studio")
    print("1. Check LM Studio is running")
    print("2. Verify URL is correct")
    print("3. Ensure a model is loaded")
else:
    print("✅ Connected successfully")
```

## Advanced Examples

### Multi-Turn Conversation

```python
conversation_id = "conv-456"

questions = [
    "What files are here?",
    "Read the first Python file",
    "What does that file do?"
]

for question in questions:
    print(f"\nQ: {question}")
    
    result = await loop.run(state, question)
    print(f"A: {result.final_answer}")
    
    # State persists across turns
    print(f"Total messages: {len(state.messages)}")
```

### Batch Tool Operations

```python
from tool.files import ReadFile

tool = ReadFile()
files = ["file1.txt", "file2.txt", "file3.txt"]

results = []
for file_path in files:
    tool_call = ToolCall(
        id=f"call-{file_path}",
        name="read_file",
        arguments={"path": file_path}
    )
    
    result = await tool.call(tool_call)
    results.append(result)

# Process results
successful = [r for r in results if r.success]
print(f"Successfully read {len(successful)} files")
```
