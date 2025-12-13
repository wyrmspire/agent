# Agent Flows

This document describes how the agent reasoning loop works.

## Overview

The agent flow is the core intelligence: it decides when to use tools, executes them, and synthesizes results into answers.

**Key concept**: This is the smallest runnable path:
```
prompt → model → optional tool → final answer
```

## Main Loop

The agent loop (flow/loops.py) implements this cycle:

```
1. Receive user input
2. Add to conversation history
3. Call model with history + available tools
4. Check model response:
   a. If tool calls → execute tools → go to step 3
   b. If final answer → return to user
5. If max steps reached → stop and return
```

### Loop Parameters

```python
AgentLoop(
    gateway=model_gateway,      # How to talk to model
    tools=tool_registry,         # Available tools
    rule_engine=rule_engine,     # Safety rules
    max_steps=20,                # Max reasoning steps
    temperature=0.7,             # Sampling temperature
)
```

## Two Modes

### Mode 1: Native Function Calling (Best)

When the model backend supports function calling (like LM Studio with Qwen 2.5):

```
User: "What files are in the current directory?"
  ↓
Model: [tool_call: list_files(path=".")]
  ↓
Tool: "📁 src/, 📄 README.md, 📄 main.py"
  ↓
Model: "The current directory contains: a 'src' folder, README.md, and main.py"
```

### Mode 2: Structured JSON (Fallback)

When function calling is flaky or unavailable:

```
User: "List files"
  ↓
Model: [JSON] {"tool": "list_files", "args": {"path": "."}}
  ↓
Parser: Extract tool call from JSON
  ↓
Tool: Execute
  ↓
Model: Get result and respond
```

(Mode 2 is not yet implemented but the architecture supports it)

## Execution Context

Each run has an ExecutionContext (core/state.py):

```python
ExecutionContext(
    run_id="run-123",           # Unique run ID
    conversation_id="conv-456", # Which conversation
    available_tools=[...],      # Tools for this run
    current_step=0,             # Current step number
    max_steps=20,               # Stop after this many
    steps=[...],                # History of steps taken
)
```

Steps track what happened:
- THINK: Model reasoning
- CALL_TOOL: Tool call request
- OBSERVE: Tool result
- RESPOND: Final answer
- ERROR: Something went wrong

## Safety and Rules

Before executing tools, the RuleEngine validates them:

```python
is_allowed, violations = rule_engine.evaluate(tool_call)

if not is_allowed:
    return ToolResult(
        error=violations[0].reason,
        success=False
    )
```

See core/rules.py for safety rules.

## Tool Execution

Tools are executed by flow/loops.py:

```python
async def _execute_tools(self, state, tool_calls):
    results = []
    
    for tool_call in tool_calls:
        # 1. Validate with rules
        is_allowed, violations = self.rule_engine.evaluate(tool_call)
        if not is_allowed:
            results.append(error_result)
            continue
        
        # 2. Look up tool
        tool = self.tools.get(tool_call.name)
        if not tool:
            results.append(not_found_result)
            continue
        
        # 3. Execute
        result = await tool.call(tool_call)
        results.append(result)
    
    return results
```

**Key point**: Exceptions are caught and converted to ToolResult. Never throw to caller.

## Planning and Prompts

The system prompt (flow/plans.py) tells the model how to use tools:

```
You are a helpful AI assistant with access to tools.

Guidelines:
1. Think step by step about what the user needs
2. Use tools when you need information
3. Answer directly when you already know
4. Be concise but thorough
5. If a tool fails, try a different approach

Available tools:
- list_files: List files in a directory
- read_file: Read file contents
- ...
```

## Verification and Quality

The AgentJudge (flow/judge.py) monitors execution:

- **Progress check**: Is agent making progress?
- **Loop detection**: Is agent calling the same tool repeatedly?
- **Tool result check**: Did tool succeed? Is result sensible?
- **Final answer check**: Is answer complete and helpful?

Judgments are advisory (not blocking) but logged for debugging.

## Error Handling

Errors are caught at multiple levels:

### 1. Tool Execution
```python
try:
    result = await tool.execute(args)
except Exception as e:
    result = ToolResult(error=str(e), success=False)
```

### 2. Loop Level
```python
try:
    final_answer = await self._reasoning_loop(state)
except Exception as e:
    logger.error(f"Loop error: {e}")
    return LoopResult(
        success=False,
        final_answer="I encountered an error",
        error=str(e)
    )
```

### 3. Top Level
```python
try:
    result = await loop.run(state, user_message)
except Exception as e:
    # Handle gracefully
    return error_response
```

## Observability

All execution is logged:

```python
logger.info(f"Starting agent loop")
logger.info(f"Step {step_num}/{max_steps}")
logger.info(f"Model requested {len(tool_calls)} tool calls")
logger.info(f"Executing tool: {tool_call.name}")
logger.info(f"Tool {tool_call.name} completed: success={result.success}")
```

Logs include:
- Request payloads (redacted secrets)
- Tool call name + args + duration
- Response status + errors
- Step transitions

## Example Flows

### Simple Question (No Tools)
```
User: "What's 2 + 2?"
  ↓
Model: "2 + 2 = 4"
  ↓
Steps: 1
Done
```

### Single Tool Use
```
User: "What's in README.md?"
  ↓
Model: [tool: read_file(path="README.md")]
  ↓
Tool: "# Agent\nLLM agent home"
  ↓
Model: "README.md contains the title 'Agent' and text 'LLM agent home'"
  ↓
Steps: 2
Done
```

### Multi-Step Tool Use
```
User: "Find all Python files and show the first one"
  ↓
Model: [tool: list_files(path=".")]
  ↓
Tool: "📄 main.py, 📄 test.py, 📁 src/"
  ↓
Model: [tool: read_file(path="main.py")]
  ↓
Tool: "import sys\n..."
  ↓
Model: "I found main.py and test.py. Here's main.py: [content]"
  ↓
Steps: 3
Done
```

### Max Steps Reached
```
User: "Complex task"
  ↓
Model: [tool: ...]
  ↓
Tool: result
  ↓
Model: [tool: ...]
  ↓
... (repeat) ...
  ↓
Steps: 20 (max reached)
  ↓
Return: "I've reached the maximum steps. Please simplify the request."
```

## Configuration

Flow behavior can be configured:

```python
# In boot/setup.py
config = {
    "max_steps": 20,           # Max reasoning steps
    "temperature": 0.7,        # Sampling temperature
    "max_tokens": 4096,        # Max tokens per request
    "enable_shell": True,      # Enable shell tool
    "enable_files": True,      # Enable file tools
}
```

Environment variables:
- `AGENT_MAX_STEPS` - Max reasoning steps
- `AGENT_TEMPERATURE` - Sampling temperature

## Best Practices

1. **Set appropriate max_steps**: Too low = incomplete, too high = expensive
2. **Use system prompts**: Guide model behavior with clear instructions
3. **Monitor judgments**: Watch for loops and stuck states
4. **Log everything**: Structured logging helps debugging
5. **Handle timeouts**: Tools should timeout, not hang
6. **Validate schemas**: Ensure tool schemas are correct
7. **Test flows**: Use mock gateway to test loop logic

## Debugging

### Agent not using tools
- Check tools are in registry
- Check tools are passed to model
- Check system prompt mentions tools
- Check model supports function calling

### Agent loops infinitely
- Check max_steps is set
- Check judge for loop detection
- Add more specific system prompts

### Tools fail
- Check logs for exceptions
- Verify tool schemas
- Test tools in isolation

### Wrong final answer
- Check tool results are fed back
- Verify conversation flow
- Check model is using tool results
