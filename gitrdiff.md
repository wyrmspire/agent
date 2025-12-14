# Git Diff Report

**Generated**: Sat, Dec 13, 2025  8:38:39 PM

**Local Branch**: main

**Comparing Against**: origin/main

---

## Uncommitted Changes (working directory)

### Modified/Staged Files

```
 M gitrdiff.md
```

### Uncommitted Diff

```diff
diff --git a/gitrdiff.md b/gitrdiff.md
index ad30ed9..2324f2f 100644
--- a/gitrdiff.md
+++ b/gitrdiff.md
@@ -1,6 +1,6 @@
 # Git Diff Report
 
-**Generated**: Sat, Dec 13, 2025  7:51:00 PM
+**Generated**: Sat, Dec 13, 2025  8:38:39 PM
 
 **Local Branch**: main
 
@@ -13,464 +13,9 @@
 ### Modified/Staged Files
 
 ```
- M flow/loops.py
- M smoke_test.sh
- M tool/files.py
-?? core/trace.py
-?? gitrdiff.md
-?? tests/flow/test_traceability.py
-?? tests/tools/test_error_format.py
+ M gitrdiff.md
 ```
 
 ### Uncommitted Diff
 
 ```diff
-diff --git a/flow/loops.py b/flow/loops.py
-index 8f58a5b..56bda43 100644
---- a/flow/loops.py
-+++ b/flow/loops.py
-@@ -23,12 +23,14 @@ Rules:
- """
- 
- import logging
-+import time
- from typing import List, Optional
- from dataclasses import dataclass
- 
- from core.types import Message, MessageRole, ToolCall, ToolResult, Step, StepType
- from core.state import AgentState, ConversationState, ExecutionContext
- from core.rules import RuleEngine
-+from core.trace import TraceLogger
- from gate.bases import ModelGateway
- from tool.index import ToolRegistry
- from flow.judge import AgentJudge
-@@ -104,6 +106,9 @@ class AgentLoop:
-         """
-         logger.info(f"Starting agent loop for message: {user_message[:50]}...")
-         
-+        # Create tracer for this run
-+        self.tracer = TraceLogger(state.execution.run_id)
-+        
-         # Add user message
-         state.conversation.add_message(Message(
-             role=MessageRole.USER,
-@@ -299,9 +304,16 @@ class AgentLoop:
-             
-             logger.info(f"Executing tool: {tool_call.name}")
-             
-+            # Trace: Log tool call initiation
-+            if hasattr(self, 'tracer'):
-+                self.tracer.log_tool_call(tool_call)
-+            
-             # Phase 0.5: Record tool use AFTER confirming budget allows it
-             state.execution.record_tool_use()
-             
-+            # Start timing
-+            start_time = time.perf_counter()
-+            
-             # Validate with rule engine
-             is_allowed, violations = self.rule_engine.evaluate(tool_call)
-             
-@@ -331,8 +343,13 @@ class AgentLoop:
-             # Execute tool
-             try:
-                 result = await tool.call(tool_call)
-+                elapsed_ms = (time.perf_counter() - start_time) * 1000
-                 logger.info(f"Tool {tool_call.name} completed: success={result.success}")
-                 
-+                # Trace: Log tool result
-+                if hasattr(self, 'tracer'):
-+                    self.tracer.log_tool_result(result, elapsed_ms, tool_call.name)
-+                
-                 # Add step
-                 state.execution.add_step(Step(
-                     step_type=StepType.OBSERVE,
-diff --git a/smoke_test.sh b/smoke_test.sh
-index e92a9e1..41bc0ed 100755
---- a/smoke_test.sh
-+++ b/smoke_test.sh
-@@ -11,8 +11,21 @@
- SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
- cd "$SCRIPT_DIR"
- 
-+# Detect Python command (Windows often has 'python' not 'python3')
-+if command -v python3 &> /dev/null; then
-+    PYTHON_CMD="python3"
-+elif command -v python &> /dev/null; then
-+    PYTHON_CMD="python"
-+else
-+    echo "ERROR: Python not found. Install Python 3.10+"
-+    exit 1
-+fi
-+
-+# Set PYTHONPATH for imports
-+export PYTHONPATH="$SCRIPT_DIR"
-+
- # Create secure temporary directory
--TEMP_DIR=$(mktemp -d -t smoke_test.XXXXXX)
-+TEMP_DIR=$(mktemp -d -t smoke_test.XXXXXX 2>/dev/null || mktemp -d)
- trap "rm -rf '$TEMP_DIR'" EXIT
- 
- # Colors for output
-@@ -53,24 +66,22 @@ echo "=================================="
- echo ""
- 
- # Check 1: Python is available
--check "Python availability" run_check "python3 --version"
-+check "Python availability" run_check "$PYTHON_CMD --version"
- 
- # Check 2: Core imports work
--check "Core module imports" run_check "python3 -c 'import sys; sys.path.insert(0, \".\"); import core.types, core.state, core.sandb, core.patch'"
-+check "Core module imports" run_check "$PYTHON_CMD -c 'import core.types, core.state, core.sandb, core.patch, core.trace'"
- 
- # Check 3: Flow imports work
--check "Flow module imports" run_check "python3 -c 'import sys; sys.path.insert(0, \".\"); import flow.loops, flow.judge, flow.plans'"
-+check "Flow module imports" run_check "$PYTHON_CMD -c 'import flow.loops, flow.judge, flow.plans'"
- 
- # Check 4: Tool imports work
--check "Tool module imports" run_check "python3 -c 'import sys; sys.path.insert(0, \".\"); import tool.bases, tool.files, tool.index'"
-+check "Tool module imports" run_check "$PYTHON_CMD -c 'import tool.bases, tool.files, tool.index'"
- 
- # Check 5: Gate imports work
--check "Gate module imports" run_check "python3 -c 'import sys; sys.path.insert(0, \".\"); import gate.bases, gate.mock'"
-+check "Gate module imports" run_check "$PYTHON_CMD -c 'import gate.bases, gate.mock'"
- 
- # Check 6: Workspace can be created
--check "Workspace creation" run_check "python3 -c '
--import sys
--sys.path.insert(0, \".\")
-+check "Workspace creation" run_check "$PYTHON_CMD -c '
- from core.sandb import Workspace
- ws = Workspace(\"./workspace\")
- assert ws.root.exists(), \"Workspace directory not created\"
-@@ -78,9 +89,7 @@ print(\"Workspace OK\")
- '"
- 
- # Check 7: Workspace isolation works
--check "Workspace isolation" run_check "python3 -c '
--import sys
--sys.path.insert(0, \".\")
-+check "Workspace isolation" run_check "$PYTHON_CMD -c '
- from core.sandb import Workspace, WorkspaceError
- ws = Workspace(\"./workspace\")
- try:
-@@ -91,21 +100,17 @@ except WorkspaceError:
- '"
- 
- # Check 8: Resource checking works
--check "Resource monitoring" run_check "python3 -c '
--import sys
--sys.path.insert(0, \".\")
-+check "Resource monitoring" run_check "$PYTHON_CMD -c '
- from core.sandb import Workspace
- ws = Workspace(\"./workspace\")
- stats = ws.get_resource_stats()
- assert \"workspace_size_gb\" in stats, \"Resource stats missing\"
- assert \"ram_free_percent\" in stats, \"RAM stats missing\"
--print(f\"Resources: {stats[\"workspace_size_gb\"]:.2f}GB workspace, {stats[\"ram_free_percent\"]:.1f}% RAM free\")
-+print(f\"Resources: {stats[\\\"workspace_size_gb\\\"]:.2f}GB workspace, {stats[\\\"ram_free_percent\\\"]:.1f}% RAM free\")
- '"
- 
- # Check 9: Judge can run
--check "Judge functionality" run_check "python3 -c '
--import sys
--sys.path.insert(0, \".\")
-+check "Judge functionality" run_check "$PYTHON_CMD -c '
- from flow.judge import AgentJudge
- from core.types import Step, StepType
- judge = AgentJudge()
-@@ -115,9 +120,8 @@ print(\"Judge OK\")
- '"
- 
- # Check 10: Patch manager works
--check "Patch manager" run_check "python3 -c '
--import sys, os
--sys.path.insert(0, \".\")
-+check "Patch manager" run_check "$PYTHON_CMD -c '
-+import os
- from core.patch import PatchManager
- temp_dir = os.environ.get(\"TEMP_DIR\", \"/tmp\")
- pm = PatchManager(workspace_dir=f\"{temp_dir}/smoke_test_workspace\")
-@@ -128,9 +132,7 @@ print(\"Patch manager OK\")
- '" env TEMP_DIR="$TEMP_DIR"
- 
- # Check 11: Tool registry works
--check "Tool registry" run_check "python3 -c '
--import sys
--sys.path.insert(0, \".\")
-+check "Tool registry" run_check "$PYTHON_CMD -c '
- from tool.index import create_default_registry
- registry = create_default_registry()
- tools = registry.get_tools()
-@@ -139,9 +141,8 @@ print(f\"Tool registry OK: {len(tools)} tools\")
- '"
- 
- # Check 12: Mock gateway works
--check "Mock gateway" run_check "python3 -c '
--import sys, asyncio
--sys.path.insert(0, \".\")
-+check "Mock gateway" run_check "$PYTHON_CMD -c '
-+import asyncio
- from gate.mock import MockGateway
- from core.types import Message, MessageRole
- 
-@@ -156,9 +157,7 @@ asyncio.run(test())
- '"
- 
- # Check 13: Run ID generation works
--check "Run ID generation" run_check "python3 -c '
--import sys
--sys.path.insert(0, \".\")
-+check "Run ID generation" run_check "$PYTHON_CMD -c '
- from core.state import generate_run_id, generate_conversation_id
- run_id = generate_run_id()
- assert run_id.startswith(\"run_\"), \"Invalid run_id format\"
-@@ -168,9 +167,7 @@ print(f\"ID generation OK: {run_id}, {conv_id}\")
- '"
- 
- # Check 14: Error taxonomy works
--check "Error taxonomy" run_check "python3 -c '
--import sys
--sys.path.insert(0, \".\")
-+check "Error taxonomy" run_check "$PYTHON_CMD -c '
- from core.patch import BlockedBy, create_tool_error, format_tool_error
- error = create_tool_error(
-     blocked_by=BlockedBy.WORKSPACE,
-@@ -183,6 +180,18 @@ assert \"ERROR [TEST_ERROR]\" in formatted, \"Error format incorrect\"
- print(\"Error taxonomy OK\")
- '"
- 
-+# Check 15: TraceLogger works
-+check "Traceability" run_check "$PYTHON_CMD -c '
-+from core.trace import TraceLogger
-+from core.types import ToolCall, ToolResult
-+tracer = TraceLogger(run_id=\"test_run_123\")
-+tc = ToolCall(id=\"tc_001\", name=\"test_tool\", arguments={\"foo\": \"bar\"})
-+tracer.log_tool_call(tc)
-+result = ToolResult(tool_call_id=\"tc_001\", output=\"success\", success=True)
-+tracer.log_tool_result(result, elapsed_ms=42.5, tool_name=\"test_tool\")
-+print(\"Traceability OK\")
-+'"
-+
- # Summary
- echo ""
- echo "=================================="
-diff --git a/tool/files.py b/tool/files.py
-index 27e11bc..7c2d381 100644
---- a/tool/files.py
-+++ b/tool/files.py
-@@ -27,6 +27,7 @@ from typing import Any, Dict, List, Optional
- 
- from core.types import ToolResult
- from core.sandb import Workspace, WorkspaceError, ResourceLimitError, get_default_workspace
-+from core.patch import BlockedBy, create_tool_error, format_tool_error
- from .bases import BaseTool, create_json_schema
- 
- 
-@@ -77,10 +78,16 @@ class ListFiles(BaseTool):
-                 is_project = False
-             
-             if not path.is_dir():
-+                error = create_tool_error(
-+                    blocked_by=BlockedBy.MISSING,
-+                    error_code="NOT_A_DIRECTORY",
-+                    message=f"Path is not a directory: {path}",
-+                    context={"path": str(path)}
-+                )
-                 return ToolResult(
-                     tool_call_id="",
-                     output="",
--                    error=f"Path is not a directory: {path}",
-+                    error=format_tool_error(error),
-                     success=False,
-                 )
-             
-@@ -132,17 +139,29 @@ class ListFiles(BaseTool):
-             )
-         
-         except WorkspaceError as e:
-+            error = create_tool_error(
-+                blocked_by=BlockedBy.WORKSPACE,
-+                error_code="PATH_OUTSIDE_WORKSPACE",
-+                message=str(e),
-+                context={"path": path_str}
-+            )
-             return ToolResult(
-                 tool_call_id="",
-                 output="",
--                error=str(e),
-+                error=format_tool_error(error),
-                 success=False,
-             )
-         except Exception as e:
-+            error = create_tool_error(
-+                blocked_by=BlockedBy.RUNTIME,
-+                error_code="LIST_DIR_ERROR",
-+                message=f"Error listing directory: {e}",
-+                context={"path": path_str}
-+            )
-             return ToolResult(
-                 tool_call_id="",
-                 output="",
--                error=f"Error listing directory: {e}",
-+                error=format_tool_error(error),
-                 success=False,
-             )
- 
-@@ -216,20 +235,32 @@ class ReadFile(BaseTool):
-                 is_project = True
-             
-             if not path.is_file():
-+                error = create_tool_error(
-+                    blocked_by=BlockedBy.MISSING,
-+                    error_code="NOT_A_FILE",
-+                    message=f"Path is not a file: {path}",
-+                    context={"path": str(path)}
-+                )
-                 return ToolResult(
-                     tool_call_id="",
-                     output="",
--                    error=f"Path is not a file: {path}",
-+                    error=format_tool_error(error),
-                     success=False,
-                 )
-             
-             # Check size
-             size = path.stat().st_size
-             if size > self.max_size:
-+                error = create_tool_error(
-+                    blocked_by=BlockedBy.RUNTIME,
-+                    error_code="FILE_TOO_LARGE",
-+                    message=f"File too large: {size} bytes (max {self.max_size}). Use data_view tool.",
-+                    context={"size": size, "max_size": self.max_size}
-+                )
-                 return ToolResult(
-                     tool_call_id="",
-                     output="",
--                    error=f"File too large: {size} bytes (max {self.max_size}). Use data_view tool.",
-+                    error=format_tool_error(error),
-                     success=False,
-                 )
-             
-@@ -280,24 +311,42 @@ class ReadFile(BaseTool):
-             )
-         
-         except WorkspaceError as e:
-+            error = create_tool_error(
-+                blocked_by=BlockedBy.WORKSPACE,
-+                error_code="PATH_OUTSIDE_WORKSPACE",
-+                message=str(e),
-+                context={"path": path_str}
-+            )
-             return ToolResult(
-                 tool_call_id="",
-                 output="",
--                error=str(e),
-+                error=format_tool_error(error),
-                 success=False,
-             )
-         except UnicodeDecodeError:
-+            error = create_tool_error(
-+                blocked_by=BlockedBy.RUNTIME,
-+                error_code="INVALID_ENCODING",
-+                message="File is not valid UTF-8 text",
-+                context={"path": path_str}
-+            )
-             return ToolResult(
-                 tool_call_id="",
-                 output="",
--                error="File is not valid UTF-8 text",
-+                error=format_tool_error(error),
-                 success=False,
-             )
-         except Exception as e:
-+            error = create_tool_error(
-+                blocked_by=BlockedBy.RUNTIME,
-+                error_code="READ_FILE_ERROR",
-+                message=f"Error reading file: {e}",
-+                context={"path": path_str}
-+            )
-             return ToolResult(
-                 tool_call_id="",
-                 output="",
--                error=f"Error reading file: {e}",
-+                error=format_tool_error(error),
-                 success=False,
-             )
- 
-@@ -353,10 +402,16 @@ class WriteFile(BaseTool):
-             try:
-                 self.workspace.check_resources()
-             except ResourceLimitError as e:
-+                error = create_tool_error(
-+                    blocked_by=BlockedBy.RUNTIME,
-+                    error_code="RESOURCE_LIMIT",
-+                    message=f"Resource limit exceeded: {e}",
-+                    context={"path": path_str}
-+                )
-                 return ToolResult(
-                     tool_call_id="",
-                     output="",
--                    error=f"Resource limit exceeded: {e}",
-+                    error=format_tool_error(error),
-                     success=False,
-                 )
-             
-@@ -374,16 +429,28 @@ class WriteFile(BaseTool):
-             )
-         
-         except WorkspaceError as e:
-+            error = create_tool_error(
-+                blocked_by=BlockedBy.WORKSPACE,
-+                error_code="PATH_OUTSIDE_WORKSPACE",
-+                message=str(e),
-+                context={"path": path_str}
-+            )
-             return ToolResult(
-                 tool_call_id="",
-                 output="",
--                error=str(e),
-+                error=format_tool_error(error),
-                 success=False,
-             )
-         except Exception as e:
-+            error = create_tool_error(
-+                blocked_by=BlockedBy.RUNTIME,
-+                error_code="WRITE_FILE_ERROR",
-+                message=f"Error writing file: {e}",
-+                context={"path": path_str}
-+            )
-             return ToolResult(
-                 tool_call_id="",
-                 output="",
--                error=f"Error writing file: {e}",
-+                error=format_tool_error(error),
-                 success=False,
-             )
-```
-
----
-
-## Commits Ahead (local changes not on remote)
-
-```
-```
-
-## Commits Behind (remote changes not pulled)
-
-```
-```
-
----
-
-## File Changes (what you'd get from remote)
-
-```
-```
-
----
-
-## Full Diff (green = new on remote, red = removed on remote)
-
-```diff
-```
```

---

## Commits Ahead (local changes not on remote)

```
```

## Commits Behind (remote changes not pulled)

```
0f8a7e9 Merge pull request #8 from wyrmspire/copilot/add-vector-git-durable-memory
c2d2117 Add Phase 0.8 demonstration script showing VectorGit and Task Queue integration
bee03f1 Fix datetime deprecation warnings - use timezone-aware datetime.now()
f30d638 Complete Phase 0.8A and 0.8B with documentation and tool registry integration
e85f99d Implement Phase 0.8B task queue system with tools and tests
dad2fa9 Initial plan
```

---

## File Changes (what you'd get from remote)

```
 README.md                       |  35 ++-
 core/taskqueue.py               | 446 +++++++++++++++++++++++++++++++++++
 docts/phase08.md                | 327 ++++++++++++++++++++++++++
 examples/phase08_demo.py        | 145 ++++++++++++
 tests/queue/__init__.py         |   1 +
 tests/queue/test_queue_tools.py | 230 +++++++++++++++++++
 tests/queue/test_taskqueue.py   | 280 ++++++++++++++++++++++
 tool/index.py                   |   9 +
 tool/queue.py                   | 498 ++++++++++++++++++++++++++++++++++++++++
 9 files changed, 1966 insertions(+), 5 deletions(-)
```

---

## Full Diff (green = new on remote, red = removed on remote)

```diff
diff --git a/README.md b/README.md
index e84446a..c3d4db3 100644
--- a/README.md
+++ b/README.md
@@ -17,15 +17,15 @@ This is a **local-first agent server** that gives coding models full access to t
 > ⚠️ **LOCAL MODEL MEMORY LIMITS**
 > 
 > Local models (Qwen 7B on 8GB VRAM) can OOM on long conversations with many tool calls.
-> Each tool result adds to context. **Currently no automatic context management.**
+> Each tool result adds to context.
 > 
-> **Workarounds:**
+> **Solutions:**
+> - **Phase 0.8B Task Queue** - Break work into bounded tasks with checkpoints (recommended)
 > - Use `--gemini` flag for complex multi-step tasks (Gemini has 1M token context)
 > - Keep local model conversations short
-> - Restart between complex tasks
 > 
-> **Roadmap (v1.0+):** Context truncation, task queuing, and run continuation so local
-> models can break up work and resume across multiple runs.
+> **Phase 0.8B** introduces task queuing and run continuation so local models can break up 
+> work into resumable chunks. See [docts/phase08.md](docts/phase08.md) for details.
 
 ## Architecture
 
@@ -202,6 +202,31 @@ Track project lifecycle with persistent state:
 5. **Evolve**: Function becomes a registered tool immediately
 6. **Use**: Agent can now call the tool without rewriting code
 
+## Phase 0.8 Features: VectorGit + Task Queue
+
+### VectorGit v0: Durable Code Memory
+
+**Find the truth** - Deterministic chunking and keyword retrieval for code:
+- Ingest repositories into semantic chunks (functions, classes, sections)
+- Query with keywords to find relevant code
+- Deterministic chunk IDs for reliable citations
+- No vectors yet (keyword-only) - embeddings in Phase 0.9
+
+```bash
+python vectorgit.py ingest /path/to/repo
+python vectorgit.py query "authentication" --topk 8
+```
+
+### Task Queue v0: Bounded Execution
+
+**Keep going** - Break work into resumable tasks with checkpoints:
+- Tasks with tool call/step budgets
+- JSONL task packets + Markdown checkpoints
+- queue_add, queue_next, queue_done, queue_fail tools
+- One task per run prevents context overflow
+
+See [docts/phase08.md](docts/phase08.md) for complete Phase 0.8 documentation.
+
 ### Example: Creating a Custom Tool
 ```python
 # Agent writes this in the workspace
diff --git a/core/taskqueue.py b/core/taskqueue.py
new file mode 100644
index 0000000..02725e1
--- /dev/null
+++ b/core/taskqueue.py
@@ -0,0 +1,446 @@
+"""
+core/taskqueue.py - Task Queue and Checkpoint Management
+
+This module implements the task queue system for Phase 0.8B.
+Enables bounded task execution with resume capability.
+
+Responsibilities:
+- Task packet format (JSONL storage)
+- Checkpoint format (Markdown storage)
+- Task lifecycle management (queued/running/done/failed)
+- Budget enforcement (max tool calls/steps)
+
+Rules:
+- Worker executes ONE task then stops
+- Every task leaves artifacts for continuation
+- Deterministic task IDs for traceability
+- Checkpoints capture state for resume
+"""
+
+import json
+import logging
+from dataclasses import dataclass, asdict
+from datetime import datetime, timezone
+from enum import Enum
+from pathlib import Path
+from typing import List, Dict, Any, Optional
+
+logger = logging.getLogger(__name__)
+
+
+class TaskStatus(str, Enum):
+    """Task execution status."""
+    QUEUED = "queued"
+    RUNNING = "running"
+    DONE = "done"
+    FAILED = "failed"
+
+
+@dataclass
+class TaskPacket:
+    """A bounded unit of work for the agent.
+    
+    Attributes:
+        task_id: Unique task identifier
+        parent_id: Parent task ID (for subtasks)
+        objective: Clear statement of what to accomplish
+        inputs: References to chunks/files/data needed
+        acceptance: Criteria for task completion
+        budget: Limits (max_tool_calls, max_steps)
+        status: Current status (queued/running/done/failed)
+        created_at: Creation timestamp
+        updated_at: Last update timestamp
+        metadata: Additional task metadata
+    """
+    task_id: str
+    parent_id: Optional[str]
+    objective: str
+    inputs: List[str]
+    acceptance: str
+    budget: Dict[str, int]
+    status: TaskStatus
+    created_at: str
+    updated_at: str
+    metadata: Dict[str, Any]
+
+
+@dataclass
+class Checkpoint:
+    """Checkpoint for task continuation.
+    
+    Attributes:
+        task_id: Associated task ID
+        what_was_done: Summary of completed work
+        what_changed: Patch IDs or file changes
+        what_next: Next steps to take
+        blockers: Errors or blockers encountered
+        citations: Chunk IDs or references used
+        created_at: Checkpoint timestamp
+    """
+    task_id: str
+    what_was_done: str
+    what_changed: List[str]
+    what_next: str
+    blockers: List[str]
+    citations: List[str]
+    created_at: str
+
+
+class TaskQueue:
+    """Manages task packets and checkpoints.
+    
+    Stores tasks in JSONL format and checkpoints in Markdown.
+    Ensures deterministic task execution with resume capability.
+    """
+    
+    def __init__(
+        self,
+        workspace_path: str = "./workspace",
+        queue_name: str = "queue",
+    ):
+        """Initialize task queue.
+        
+        Args:
+            workspace_path: Root workspace path
+            queue_name: Name of the queue (subdirectory)
+        """
+        self.workspace_root = Path(workspace_path)
+        self.queue_dir = self.workspace_root / queue_name
+        self.tasks_file = self.queue_dir / "tasks.jsonl"
+        self.checkpoints_dir = self.queue_dir / "checkpoints"
+        
+        # Create directories
+        self.queue_dir.mkdir(parents=True, exist_ok=True)
+        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
+        
+        # In-memory task index
+        self._tasks: Dict[str, TaskPacket] = {}
+        self._load_tasks()
+    
+    def _load_tasks(self) -> None:
+        """Load tasks from JSONL file."""
+        if not self.tasks_file.exists():
+            logger.info("No existing tasks file found")
+            return
+        
+        try:
+            with open(self.tasks_file, 'r') as f:
+                for line in f:
+                    if line.strip():
+                        data = json.loads(line)
+                        # Convert status string to enum
+                        data['status'] = TaskStatus(data['status'])
+                        task = TaskPacket(**data)
+                        self._tasks[task.task_id] = task
+            
+            logger.info(f"Loaded {len(self._tasks)} tasks from queue")
+        
+        except Exception as e:
+            logger.error(f"Failed to load tasks: {e}")
+    
+    def _save_task(self, task: TaskPacket) -> None:
+        """Append task to JSONL file.
+        
+        Args:
+            task: Task packet to save
+        """
+        try:
+            # Convert to dict and handle enum
+            task_dict = asdict(task)
+            task_dict['status'] = task.status.value
+            
+            # Append to JSONL
+            with open(self.tasks_file, 'a') as f:
+                f.write(json.dumps(task_dict) + '\n')
+            
+            logger.debug(f"Saved task {task.task_id}")
+        
+        except Exception as e:
+            logger.error(f"Failed to save task: {e}")
+            raise
+    
+    def add_task(
+        self,
+        objective: str,
+        inputs: Optional[List[str]] = None,
+        acceptance: Optional[str] = None,
+        parent_id: Optional[str] = None,
+        max_tool_calls: int = 20,
+        max_steps: int = 10,
+        metadata: Optional[Dict[str, Any]] = None,
+    ) -> str:
+        """Add a new task to the queue.
+        
+        Args:
+            objective: What to accomplish
+            inputs: List of input references (chunk IDs, file paths)
+            acceptance: Acceptance criteria
+            parent_id: Parent task ID (for subtasks)
+            max_tool_calls: Maximum tool calls allowed
+            max_steps: Maximum steps allowed
+            metadata: Additional metadata
+            
+        Returns:
+            Task ID of the created task
+        """
+        # Generate deterministic task ID
+        timestamp = datetime.now(timezone.utc).isoformat()
+        task_id = f"task_{len(self._tasks) + 1:04d}"
+        
+        task = TaskPacket(
+            task_id=task_id,
+            parent_id=parent_id,
+            objective=objective,
+            inputs=inputs or [],
+            acceptance=acceptance or "Task completed successfully",
+            budget={
+                "max_tool_calls": max_tool_calls,
+                "max_steps": max_steps,
+            },
+            status=TaskStatus.QUEUED,
+            created_at=timestamp,
+            updated_at=timestamp,
+            metadata=metadata or {},
+        )
+        
+        # Save to memory and disk
+        self._tasks[task_id] = task
+        self._save_task(task)
+        
+        logger.info(f"Added task {task_id}: {objective[:50]}...")
+        return task_id
+    
+    def get_next(self) -> Optional[TaskPacket]:
+        """Get the next queued task.
+        
+        Returns:
+            Next queued task, or None if queue is empty
+        """
+        for task in self._tasks.values():
+            if task.status == TaskStatus.QUEUED:
+                # Mark as running
+                task.status = TaskStatus.RUNNING
+                task.updated_at = datetime.now(timezone.utc).isoformat()
+                self._update_task(task)
+                
+                logger.info(f"Starting task {task.task_id}")
+                return task
+        
+        logger.info("No queued tasks available")
+        return None
+    
+    def mark_done(
+        self,
+        task_id: str,
+        checkpoint: Optional[Checkpoint] = None,
+    ) -> bool:
+        """Mark a task as done.
+        
+        Args:
+            task_id: Task ID to mark as done
+            checkpoint: Optional checkpoint to save
+            
+        Returns:
+            True if successful
+        """
+        if task_id not in self._tasks:
+            logger.error(f"Task not found: {task_id}")
+            return False
+        
+        task = self._tasks[task_id]
+        task.status = TaskStatus.DONE
+        task.updated_at = datetime.now(timezone.utc).isoformat()
+        self._update_task(task)
+        
+        # Save checkpoint if provided
+        if checkpoint:
+            self.save_checkpoint(checkpoint)
+        
+        logger.info(f"Marked task {task_id} as done")
+        return True
+    
+    def mark_failed(
+        self,
+        task_id: str,
+        error: str,
+        checkpoint: Optional[Checkpoint] = None,
+    ) -> bool:
+        """Mark a task as failed.
+        
+        Args:
+            task_id: Task ID to mark as failed
+            error: Error message
+            checkpoint: Optional checkpoint to save
+            
+        Returns:
+            True if successful
+        """
+        if task_id not in self._tasks:
+            logger.error(f"Task not found: {task_id}")
+            return False
+        
+        task = self._tasks[task_id]
+        task.status = TaskStatus.FAILED
+        task.updated_at = datetime.now(timezone.utc).isoformat()
+        task.metadata['error'] = error
+        self._update_task(task)
+        
+        # Save checkpoint if provided
+        if checkpoint:
+            self.save_checkpoint(checkpoint)
+        
+        logger.info(f"Marked task {task_id} as failed: {error}")
+        return True
+    
+    def _update_task(self, task: TaskPacket) -> None:
+        """Update task in memory and rebuild JSONL file.
+        
+        Args:
+            task: Task to update
+        """
+        self._tasks[task.task_id] = task
+        
+        # Rebuild JSONL file with all tasks
+        try:
+            with open(self.tasks_file, 'w') as f:
+                for t in self._tasks.values():
+                    task_dict = asdict(t)
+                    task_dict['status'] = t.status.value
+                    f.write(json.dumps(task_dict) + '\n')
+        
+        except Exception as e:
+            logger.error(f"Failed to update task: {e}")
+            raise
+    
+    def save_checkpoint(self, checkpoint: Checkpoint) -> bool:
+        """Save a checkpoint to disk.
+        
+        Args:
+            checkpoint: Checkpoint to save
+            
+        Returns:
+            True if successful
+        """
+        try:
+            checkpoint_path = self.checkpoints_dir / f"{checkpoint.task_id}.md"
+            
+            # Format as markdown
+            content = f"""# Checkpoint: {checkpoint.task_id}
+
+**Created:** {checkpoint.created_at}
+
+## What Was Done
+
+{checkpoint.what_was_done}
+
+## What Changed
+
+{chr(10).join(f"- {change}" for change in checkpoint.what_changed) if checkpoint.what_changed else "- No changes"}
+
+## What's Next
+
+{checkpoint.what_next}
+
+## Blockers/Errors
+
+{chr(10).join(f"- {blocker}" for blocker in checkpoint.blockers) if checkpoint.blockers else "- None"}
+
+## Citations Used
+
+{chr(10).join(f"- {citation}" for citation in checkpoint.citations) if checkpoint.citations else "- None"}
+"""
+            
+            checkpoint_path.write_text(content)
+            logger.info(f"Saved checkpoint for task {checkpoint.task_id}")
+            return True
+        
+        except Exception as e:
+            logger.error(f"Failed to save checkpoint: {e}")
+            return False
+    
+    def load_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
+        """Load a checkpoint from disk.
+        
+        Args:
+            task_id: Task ID to load checkpoint for
+            
+        Returns:
+            Checkpoint if found, None otherwise
+        """
+        checkpoint_path = self.checkpoints_dir / f"{task_id}.md"
+        
+        if not checkpoint_path.exists():
+            logger.info(f"No checkpoint found for task {task_id}")
+            return None
+        
+        try:
+            # For now, return a basic parsed checkpoint
+            # Full markdown parsing could be added later
+            content = checkpoint_path.read_text()
+            
+            # Simple parsing (could be enhanced)
+            return Checkpoint(
+                task_id=task_id,
+                what_was_done="See checkpoint file",
+                what_changed=[],
+                what_next="See checkpoint file",
+                blockers=[],
+                citations=[],
+                created_at=datetime.now(timezone.utc).isoformat(),
+            )
+        
+        except Exception as e:
+            logger.error(f"Failed to load checkpoint: {e}")
+            return None
+    
+    def get_task(self, task_id: str) -> Optional[TaskPacket]:
+        """Get a task by ID.
+        
+        Args:
+            task_id: Task ID
+            
+        Returns:
+            Task packet if found
+        """
+        return self._tasks.get(task_id)
+    
+    def list_tasks(
+        self,
+        status: Optional[TaskStatus] = None,
+    ) -> List[TaskPacket]:
+        """List all tasks, optionally filtered by status.
+        
+        Args:
+            status: Optional status filter
+            
+        Returns:
+            List of tasks
+        """
+        if status is None:
+            return list(self._tasks.values())
+        
+        return [t for t in self._tasks.values() if t.status == status]
+    
+    def get_stats(self) -> Dict[str, Any]:
+        """Get queue statistics.
+        
+        Returns:
+            Statistics about the queue
+        """
+        status_counts = {
+            TaskStatus.QUEUED.value: 0,
+            TaskStatus.RUNNING.value: 0,
+            TaskStatus.DONE.value: 0,
+            TaskStatus.FAILED.value: 0,
+        }
+        
+        for task in self._tasks.values():
+            status_counts[task.status.value] += 1
+        
+        return {
+            "total_tasks": len(self._tasks),
+            "status_counts": status_counts,
+            "queue_dir": str(self.queue_dir),
+            "tasks_file": str(self.tasks_file),
+            "checkpoints_dir": str(self.checkpoints_dir),
+        }
diff --git a/docts/phase08.md b/docts/phase08.md
new file mode 100644
index 0000000..05c4b54
--- /dev/null
+++ b/docts/phase08.md
@@ -0,0 +1,327 @@
+# Phase 0.8: VectorGit v0 + Task Queue
+
+Phase 0.8 introduces two critical capabilities for long-running agent tasks:
+
+1. **Phase 0.8A: VectorGit v0** - Durable code memory with deterministic chunking
+2. **Phase 0.8B: Task Queue** - Bounded task execution with resume capability
+
+## Phase 0.8A: VectorGit v0
+
+### Overview
+
+VectorGit provides a durable memory layer for code retrieval without requiring vector embeddings. It uses deterministic chunking and keyword search to prove the workflow end-to-end.
+
+### Key Features
+
+- **Deterministic chunking**: Same content always produces same chunk IDs
+- **Semantic boundaries**: Chunks follow function/class/section boundaries
+- **Keyword search**: Simple but effective retrieval (embeddings in Phase 0.9)
+- **Citation-ready**: Every chunk has a unique ID for traceability
+
+### Architecture
+
+```
+workspace/vectorgit/
+├── manifest.json       # Chunk metadata (IDs, hashes, locations)
+├── chunks/             # Optional chunk payload storage
+└── index.json          # Optional keyword index
+```
+
+### Usage
+
+#### CLI Usage
+
+```bash
+# Ingest a repository
+python vectorgit.py ingest /path/to/repo
+
+# Query for code
+python vectorgit.py query "how do tools register?" --topk 8
+
+# Get AI explanation with citations
+python vectorgit.py explain "how does error handling work?" --topk 8
+```
+
+#### Programmatic Usage
+
+```python
+from tool.vectorgit import VectorGit
+
+# Initialize
+vg = VectorGit(workspace_path="./workspace")
+
+# Ingest repository
+count = vg.ingest("/path/to/repo")
+print(f"Ingested {count} chunks")
+
+# Query chunks
+results = vg.query("error handling", top_k=5)
+for result in results:
+    print(f"{result['source_path']}:{result['start_line']}")
+    print(f"  {result['chunk_id']}: {result['name']}")
+
+# Get AI explanation (requires gateway)
+from gate.gemini import GeminiGateway
+gateway = GeminiGateway(api_key="...")
+answer = await vg.explain("How do tools work?", gateway, top_k=8)
+```
+
+### Chunking Strategy
+
+**Python Files:**
+- Each function is a chunk
+- Each class is a chunk
+- Module-level code is a chunk if no functions/classes exist
+
+**Markdown Files:**
+- Each section (by headers) is a chunk
+- Entire file if no headers
+
+**Other Files:**
+- Entire file as a single chunk
+
+### Determinism
+
+Chunk IDs are derived from content hashes, ensuring:
+- Re-ingesting produces identical chunk IDs
+- Citations remain valid across ingestions
+- Debuggable references for all code
+
+### Tests
+
+```bash
+# Run all VectorGit tests
+pytest tests/vectorgit/ -v
+
+# Key tests:
+# - test_determinism.py: Re-ingest produces same IDs
+# - test_ingest.py: Repository ingestion works
+# - test_query.py: Keyword search returns relevant chunks
+```
+
+## Phase 0.8B: Task Queue
+
+### Overview
+
+The Task Queue enables bounded task execution with checkpoints, allowing agents to work on complex tasks across multiple runs without losing context.
+
+### Key Features
+
+- **Bounded execution**: Tasks have tool call and step budgets
+- **Checkpoints**: Resume-friendly state capture
+- **JSONL persistence**: Append-only task log
+- **Markdown checkpoints**: Human-readable progress snapshots
+
+### Architecture
+
+```
+workspace/queue/
+├── tasks.jsonl                 # Task packet log
+└── checkpoints/
+    ├── task_0001.md           # Checkpoint for task 1
+    ├── task_0002.md           # Checkpoint for task 2
+    └── ...
+```
+
+### Task Packet Format
+
+```jsonl
+{
+  "task_id": "task_0001",
+  "parent_id": null,
+  "objective": "Refactor authentication module",
+  "inputs": ["chunk_abc123", "auth.py"],
+  "acceptance": "All tests pass and code is cleaner",
+  "budget": {"max_tool_calls": 20, "max_steps": 10},
+  "status": "queued",
+  "created_at": "2024-01-01T00:00:00",
+  "updated_at": "2024-01-01T00:00:00",
+  "metadata": {}
+}
+```
+
+### Checkpoint Format
+
+Checkpoints are saved as Markdown files:
+
+```markdown
+# Checkpoint: task_0001
+
+**Created:** 2024-01-01T12:00:00
+
+## What Was Done
+
+Refactored the authentication module to use dependency injection.
+Updated 3 files and added 2 tests.
+
+## What Changed
+
+- auth/core.py
+- auth/handlers.py
+- tests/test_auth.py
+
+## What's Next
+
+Need to update documentation and run integration tests.
+
+## Blockers/Errors
+
+- None
+
+## Citations Used
+
+- chunk_abc123 (auth.py:15-45)
+- chunk_xyz789 (handlers.py:10-30)
+```
+
+### Queue Tools
+
+#### queue_add
+
+Add a new task to the queue:
+
+```python
+await queue_add.execute({
+    "objective": "Fix bug in payment processing",
+    "inputs": ["bug_report.md", "chunk_payment_handler"],
+    "acceptance": "Bug is fixed and tests pass",
+    "max_tool_calls": 15,
+    "max_steps": 8,
+})
+```
+
+#### queue_next
+
+Get the next queued task:
+
+```python
+result = await queue_next.execute({})
+# Returns task details including objective, inputs, budget
+```
+
+#### queue_done
+
+Mark task as complete with checkpoint:
+
+```python
+await queue_done.execute({
+    "task_id": "task_0001",
+    "what_was_done": "Fixed null pointer bug in payment handler",
+    "what_changed": ["payment.py", "tests/test_payment.py"],
+    "what_next": "Deploy to staging",
+    "citations": ["chunk_xyz123"],
+})
+```
+
+#### queue_fail
+
+Mark task as failed with error details:
+
+```python
+await queue_fail.execute({
+    "task_id": "task_0001",
+    "error": "Cannot access database credentials",
+    "what_was_done": "Attempted connection setup",
+    "blockers": ["Missing .env file", "Database unreachable"],
+})
+```
+
+### Workflow Pattern
+
+The queue enforces a strict workflow:
+
+1. **Add tasks** - Break down complex work into bounded units
+2. **Get next** - Retrieve one task at a time
+3. **Execute** - Work on task within budget constraints
+4. **Checkpoint** - Save progress on completion or failure
+5. **Stop** - Worker halts after completing one task
+
+This pattern prevents context overflow and enables safe resumption.
+
+### Example: 20-Task Workflow
+
+```python
+# Add 20 tasks
+for i in range(1, 21):
+    await queue_add.execute({
+        "objective": f"Process batch {i}",
+        "max_tool_calls": 10,
+        "max_steps": 5,
+    })
+
+# Worker loop (run this 20 times)
+task = await queue_next.execute({})
+if task:
+    # Do the work...
+    await queue_done.execute({
+        "task_id": task["task_id"],
+        "what_was_done": "Batch processed",
+        "what_next": "Next batch",
+    })
+```
+
+### Tests
+
+```bash
+# Run all queue tests
+pytest tests/queue/ -v
+
+# Key tests:
+# - test_taskqueue.py: Core TaskQueue functionality (10 tests)
+# - test_queue_tools.py: Tool integration (8 tests)
+```
+
+## Success Criteria
+
+### Phase 0.8A ✅
+
+- [x] Ingest repository without crashing
+- [x] Deterministic chunk IDs on re-ingest
+- [x] Query returns relevant chunks
+- [x] Explain mode cites chunk IDs
+- [x] All tests passing (7/7)
+
+### Phase 0.8B ✅
+
+- [x] Task packets persist to JSONL
+- [x] Checkpoints save as Markdown
+- [x] add → next → done lifecycle works
+- [x] Checkpoint on budget exhaustion
+- [x] All tests passing (18/18)
+
+## Design Philosophy
+
+### "I can find the truth" (0.8A)
+
+VectorGit makes code searchable and citable. No hallucinations - every answer is grounded in actual code with traceable references.
+
+### "I can keep going" (0.8B)
+
+The task queue makes long-running work safe. No more OOM crashes from bloated context - work is chunked, checkpointed, and resumable.
+
+## Next Steps: Phase 0.9
+
+Phase 0.9 will add:
+- Vector embeddings for better retrieval quality
+- Semantic search instead of keyword-only
+- Task queue integration with embeddings
+
+The foundations from 0.8 remain unchanged - embeddings become a drop-in improvement.
+
+## Known Limitations
+
+### VectorGit v0
+
+- **Keyword search only**: No semantic understanding (fixed in 0.9)
+- **No persistent chunk content**: Content stored in memory only
+  - Workaround: Re-ingest to reload content
+  - Not an issue for agent usage (single session)
+- **CLI requires re-ingest**: Each command creates new VectorGit instance
+
+### Task Queue v0
+
+- **No automatic budget tracking**: Agent must self-monitor
+- **No subtask discovery**: Manual subtask creation only
+- **Single worker model**: No parallel execution
+
+These limitations are intentional for v0 - they keep the implementation simple while proving the workflow.
diff --git a/examples/phase08_demo.py b/examples/phase08_demo.py
new file mode 100644
index 0000000..330dea7
--- /dev/null
+++ b/examples/phase08_demo.py
@@ -0,0 +1,145 @@
+#!/usr/bin/env python3
+"""
+examples/phase08_demo.py - Phase 0.8 Demonstration
+
+This script demonstrates the Phase 0.8A (VectorGit) and 
+Phase 0.8B (Task Queue) features working together.
+"""
+
+import asyncio
+import sys
+from pathlib import Path
+
+# Add parent to path
+sys.path.insert(0, str(Path(__file__).parent.parent))
+
+from tool.vectorgit import VectorGit
+from core.taskqueue import TaskQueue, Checkpoint
+from datetime import datetime, timezone
+
+
+async def demo_vectorgit():
+    """Demonstrate VectorGit v0 capabilities."""
+    print("\n" + "="*60)
+    print("Phase 0.8A: VectorGit v0 Demo")
+    print("="*60 + "\n")
+    
+    # Initialize VectorGit
+    vg = VectorGit(workspace_path="/tmp/demo_workspace")
+    
+    # Ingest current project
+    print("📥 Ingesting repository...")
+    repo_path = Path(__file__).parent.parent
+    count = vg.ingest(str(repo_path / "core"))
+    print(f"✅ Ingested {count} chunks from core/\n")
+    
+    # Query for code
+    print("🔍 Querying for 'TaskQueue'...")
+    results = vg.query("TaskQueue", top_k=3)
+    print(f"Found {len(results)} results:\n")
+    
+    for i, result in enumerate(results, 1):
+        print(f"[{i}] {result['source_path']} (lines {result['start_line']}-{result['end_line']})")
+        print(f"    Chunk ID: {result['chunk_id']}")
+        print(f"    Type: {result['chunk_type']}, Name: {result.get('name', 'N/A')}")
+        print()
+
+
+async def demo_task_queue():
+    """Demonstrate Task Queue v0 capabilities."""
+    print("\n" + "="*60)
+    print("Phase 0.8B: Task Queue v0 Demo")
+    print("="*60 + "\n")
+    
+    # Initialize TaskQueue
+    queue = TaskQueue(workspace_path="/tmp/demo_workspace")
+    
+    # Add tasks
+    print("📝 Adding tasks to queue...\n")
+    
+    task_ids = []
+    for i in range(1, 4):
+        task_id = queue.add_task(
+            objective=f"Process batch {i} of data",
+            inputs=[f"data_batch_{i}.csv"],
+            acceptance=f"Batch {i} processed successfully",
+            max_tool_calls=10,
+            max_steps=5,
+        )
+        task_ids.append(task_id)
+        print(f"✅ Added {task_id}: Process batch {i}")
+    
+    print()
+    
+    # Process tasks one by one
+    print("⚙️  Processing tasks sequentially...\n")
+    
+    for i in range(3):
+        # Get next task
+        task = queue.get_next()
+        if not task:
+            print("No more tasks in queue")
+            break
+        
+        print(f"📋 Working on {task.task_id}: {task.objective}")
+        
+        # Simulate work
+        await asyncio.sleep(0.1)
+        
+        # Mark as done with checkpoint
+        checkpoint = Checkpoint(
+            task_id=task.task_id,
+            what_was_done=f"Processed {task.objective}",
+            what_changed=[f"output_{i+1}.csv"],
+            what_next="Process next batch" if i < 2 else "All batches complete",
+            blockers=[],
+            citations=[f"chunk_abc{i+1}"],
+            created_at=datetime.now(timezone.utc).isoformat(),
+        )
+        
+        queue.mark_done(task.task_id, checkpoint)
+        print(f"✅ Completed {task.task_id}\n")
+    
+    # Show stats
+    stats = queue.get_stats()
+    print("📊 Queue Statistics:")
+    print(f"   Total tasks: {stats['total_tasks']}")
+    print(f"   Queued: {stats['status_counts']['queued']}")
+    print(f"   Running: {stats['status_counts']['running']}")
+    print(f"   Done: {stats['status_counts']['done']}")
+    print(f"   Failed: {stats['status_counts']['failed']}")
+    print()
+    
+    # Show checkpoints
+    print("📄 Checkpoints created:")
+    checkpoint_dir = Path(queue.checkpoints_dir)
+    for checkpoint_file in checkpoint_dir.glob("*.md"):
+        print(f"   - {checkpoint_file.name}")
+
+
+async def main():
+    """Run both demos."""
+    print("\n" + "="*60)
+    print("Phase 0.8 Complete Demo")
+    print("VectorGit v0 + Task Queue v0")
+    print("="*60)
+    
+    # Demo VectorGit
+    await demo_vectorgit()
+    
+    # Demo Task Queue
+    await demo_task_queue()
+    
+    print("\n" + "="*60)
+    print("✅ Phase 0.8 Demo Complete!")
+    print("="*60 + "\n")
+    
+    print("Key Takeaways:")
+    print("  • VectorGit provides deterministic code chunking and retrieval")
+    print("  • Task Queue enables bounded execution with resume capability")
+    print("  • Both systems work independently and complement each other")
+    print("  • Ready for Phase 0.9: Vector embeddings + semantic search\n")
+
+
+if __name__ == "__main__":
+    asyncio.run(main())
diff --git a/tests/queue/__init__.py b/tests/queue/__init__.py
new file mode 100644
index 0000000..2ee388a
--- /dev/null
+++ b/tests/queue/__init__.py
@@ -0,0 +1 @@
+"""Tests for Phase 0.8B task queue system."""
diff --git a/tests/queue/test_queue_tools.py b/tests/queue/test_queue_tools.py
new file mode 100644
index 0000000..76df599
--- /dev/null
+++ b/tests/queue/test_queue_tools.py
@@ -0,0 +1,230 @@
+"""
+tests/queue/test_queue_tools.py - Queue Tools Tests
+
+Tests for the queue_add, queue_next, queue_done, and queue_fail tools.
+"""
+
+import pytest
+import tempfile
+import shutil
+from pathlib import Path
+from tool.queue import QueueAddTool, QueueNextTool, QueueDoneTool, QueueFailTool
+from core.sandb import Workspace
+
+
+class TestQueueTools:
+    """Tests for queue tools."""
+    
+    @pytest.fixture
+    def workspace(self):
+        """Create a temporary workspace."""
+        tmp_dir = tempfile.mkdtemp()
+        tmp_path = Path(tmp_dir)
+        
+        try:
+            ws_path = tmp_path / "workspace"
+            ws_path.mkdir()
+            workspace = Workspace(workspace_root=str(ws_path))
+            yield workspace
+        finally:
+            shutil.rmtree(tmp_dir)
+    
+    @pytest.mark.asyncio
+    async def test_queue_add(self, workspace):
+        """Test queue_add tool."""
+        tool = QueueAddTool(workspace=workspace)
+        
+        result = await tool.execute({
+            "objective": "Test task objective",
+            "inputs": ["chunk_abc", "file.py"],
+            "acceptance": "Task should complete without errors",
+            "max_tool_calls": 10,
+            "max_steps": 5,
+        })
+        
+        assert result.success is True
+        assert "task_0001" in result.output
+        assert "Test task objective" in result.output
+        assert "queued" in result.output
+    
+    @pytest.mark.asyncio
+    async def test_queue_next_empty(self, workspace):
+        """Test queue_next when queue is empty."""
+        tool = QueueNextTool(workspace=workspace)
+        
+        result = await tool.execute({})
+        
+        assert result.success is True
+        assert "No queued tasks" in result.output or "empty" in result.output.lower()
+    
+    @pytest.mark.asyncio
+    async def test_queue_next_with_task(self, workspace):
+        """Test queue_next with a queued task."""
+        # Add a task first
+        add_tool = QueueAddTool(workspace=workspace)
+        await add_tool.execute({
+            "objective": "Task to retrieve",
+            "acceptance": "Should be retrieved",
+        })
+        
+        # Get next task
+        next_tool = QueueNextTool(workspace=workspace)
+        result = await next_tool.execute({})
+        
+        assert result.success is True
+        assert "task_0001" in result.output
+        assert "Task to retrieve" in result.output
+        assert "running" in result.output
+    
+    @pytest.mark.asyncio
+    async def test_queue_done(self, workspace):
+        """Test queue_done tool."""
+        # Add and get a task
+        add_tool = QueueAddTool(workspace=workspace)
+        await add_tool.execute({"objective": "Task to complete"})
+        
+        next_tool = QueueNextTool(workspace=workspace)
+        await next_tool.execute({})
+        
+        # Mark as done
+        done_tool = QueueDoneTool(workspace=workspace)
+        result = await done_tool.execute({
+            "task_id": "task_0001",
+            "what_was_done": "Completed successfully",
+            "what_changed": ["file1.py"],
+            "what_next": "Nothing more to do",
+            "citations": ["chunk_xyz"],
+        })
+        
+        assert result.success is True
+        assert "task_0001" in result.output
+        assert "done" in result.output
+        assert "Checkpoint saved" in result.output
+    
+    @pytest.mark.asyncio
+    async def test_queue_fail(self, workspace):
+        """Test queue_fail tool."""
+        # Add and get a task
+        add_tool = QueueAddTool(workspace=workspace)
+        await add_tool.execute({"objective": "Task to fail"})
+        
+        next_tool = QueueNextTool(workspace=workspace)
+        await next_tool.execute({})
+        
+        # Mark as failed
+        fail_tool = QueueFailTool(workspace=workspace)
+        result = await fail_tool.execute({
+            "task_id": "task_0001",
+            "error": "Database connection failed",
+            "what_was_done": "Attempted to connect",
+            "blockers": ["Network error", "Timeout"],
+        })
+        
+        assert result.success is True
+        assert "task_0001" in result.output
+        assert "failed" in result.output
+        assert "Database connection failed" in result.output
+    
+    @pytest.mark.asyncio
+    async def test_full_workflow(self, workspace):
+        """Test complete workflow: add → next → done."""
+        # Step 1: Add task
+        add_tool = QueueAddTool(workspace=workspace)
+        add_result = await add_tool.execute({
+            "objective": "Complete workflow test",
+            "inputs": ["data.csv"],
+            "acceptance": "Data processed",
+        })
+        assert add_result.success is True
+        
+        # Step 2: Get next
+        next_tool = QueueNextTool(workspace=workspace)
+        next_result = await next_tool.execute({})
+        assert next_result.success is True
+        assert "Complete workflow test" in next_result.output
+        
+        # Step 3: Mark done
+        done_tool = QueueDoneTool(workspace=workspace)
+        done_result = await done_tool.execute({
+            "task_id": "task_0001",
+            "what_was_done": "Processed data.csv successfully",
+            "what_changed": ["output.csv"],
+            "what_next": "Review output",
+        })
+        assert done_result.success is True
+        
+        # Step 4: Verify no more tasks
+        next_result2 = await next_tool.execute({})
+        assert "No queued tasks" in next_result2.output or "empty" in next_result2.output.lower()
+    
+    @pytest.mark.asyncio
+    async def test_multiple_tasks_lifecycle(self, workspace):
+        """Test processing multiple tasks sequentially."""
+        add_tool = QueueAddTool(workspace=workspace)
+        next_tool = QueueNextTool(workspace=workspace)
+        done_tool = QueueDoneTool(workspace=workspace)
+        
+        # Add 3 tasks
+        await add_tool.execute({"objective": "Task 1"})
+        await add_tool.execute({"objective": "Task 2"})
+        await add_tool.execute({"objective": "Task 3"})
+        
+        # Process task 1
+        result = await next_tool.execute({})
+        assert "Task 1" in result.output
+        await done_tool.execute({
+            "task_id": "task_0001",
+            "what_was_done": "Done 1",
+            "what_next": "Next",
+        })
+        
+        # Process task 2
+        result = await next_tool.execute({})
+        assert "Task 2" in result.output
+        await done_tool.execute({
+            "task_id": "task_0002",
+            "what_was_done": "Done 2",
+            "what_next": "Next",
+        })
+        
+        # Process task 3
+        result = await next_tool.execute({})
+        assert "Task 3" in result.output
+        await done_tool.execute({
+            "task_id": "task_0003",
+            "what_was_done": "Done 3",
+            "what_next": "Complete",
+        })
+        
+        # Verify queue is empty
+        result = await next_tool.execute({})
+        assert "No queued tasks" in result.output or "empty" in result.output.lower()
+    
+    @pytest.mark.asyncio
+    async def test_error_handling(self, workspace):
+        """Test error handling in tools."""
+        # Test queue_add without objective
+        add_tool = QueueAddTool(workspace=workspace)
+        result = await add_tool.execute({})
+        assert result.success is False
+        assert "objective" in result.error.lower()
+        
+        # Test queue_done without task_id
+        done_tool = QueueDoneTool(workspace=workspace)
+        result = await done_tool.execute({
+            "what_was_done": "Something",
+            "what_next": "Next",
+        })
+        assert result.success is False
+        assert "task_id" in result.error.lower()
+        
+        # Test queue_fail without error
+        fail_tool = QueueFailTool(workspace=workspace)
+        result = await fail_tool.execute({
+            "task_id": "task_0001",
+        })
+        assert result.success is False
+
+
+if __name__ == "__main__":
+    pytest.main([__file__, "-v"])
diff --git a/tests/queue/test_taskqueue.py b/tests/queue/test_taskqueue.py
new file mode 100644
index 0000000..e98627f
--- /dev/null
+++ b/tests/queue/test_taskqueue.py
@@ -0,0 +1,280 @@
+"""
+tests/queue/test_taskqueue.py - Task Queue Core Tests
+
+Tests for the TaskQueue class and task lifecycle management.
+"""
+
+import pytest
+import tempfile
+import shutil
+from pathlib import Path
+from core.taskqueue import TaskQueue, TaskStatus, Checkpoint
+
+
+class TestTaskQueue:
+    """Tests for TaskQueue core functionality."""
+    
+    @pytest.fixture
+    def queue(self):
+        """Create a TaskQueue instance with temp workspace."""
+        tmp_dir = tempfile.mkdtemp()
+        tmp_path = Path(tmp_dir)
+        
+        try:
+            ws = tmp_path / "workspace"
+            ws.mkdir()
+            queue = TaskQueue(workspace_path=str(ws))
+            yield queue
+        finally:
+            shutil.rmtree(tmp_dir)
+    
+    def test_add_task(self, queue):
+        """Test adding a task to the queue."""
+        task_id = queue.add_task(
+            objective="Test task",
+            inputs=["input1", "input2"],
+            acceptance="Task should complete",
+            max_tool_calls=15,
+            max_steps=5,
+        )
+        
+        assert task_id.startswith("task_")
+        
+        # Verify task was added
+        task = queue.get_task(task_id)
+        assert task is not None
+        assert task.objective == "Test task"
+        assert task.status == TaskStatus.QUEUED
+        assert task.budget["max_tool_calls"] == 15
+        assert task.budget["max_steps"] == 5
+        assert len(task.inputs) == 2
+    
+    def test_get_next(self, queue):
+        """Test getting the next queued task."""
+        # Add two tasks
+        task_id1 = queue.add_task("Task 1")
+        task_id2 = queue.add_task("Task 2")
+        
+        # Get first task
+        task = queue.get_next()
+        assert task is not None
+        assert task.task_id == task_id1
+        assert task.status == TaskStatus.RUNNING
+        
+        # Get second task
+        task = queue.get_next()
+        assert task is not None
+        assert task.task_id == task_id2
+        assert task.status == TaskStatus.RUNNING
+        
+        # No more tasks
+        task = queue.get_next()
+        assert task is None
+    
+    def test_mark_done(self, queue):
+        """Test marking a task as done."""
+        task_id = queue.add_task("Complete this")
+        
+        checkpoint = Checkpoint(
+            task_id=task_id,
+            what_was_done="Completed the task",
+            what_changed=["file1.py", "file2.py"],
+            what_next="Nothing, task is done",
+            blockers=[],
+            citations=["chunk_abc123"],
+            created_at="2024-01-01T00:00:00",
+        )
+        
+        success = queue.mark_done(task_id, checkpoint)
+        assert success is True
+        
+        task = queue.get_task(task_id)
+        assert task.status == TaskStatus.DONE
+        
+        # Verify checkpoint was saved
+        checkpoint_file = queue.checkpoints_dir / f"{task_id}.md"
+        assert checkpoint_file.exists()
+        content = checkpoint_file.read_text()
+        assert "Completed the task" in content
+        assert "chunk_abc123" in content
+    
+    def test_mark_failed(self, queue):
+        """Test marking a task as failed."""
+        task_id = queue.add_task("Fail this")
+        
+        checkpoint = Checkpoint(
+            task_id=task_id,
+            what_was_done="Attempted task but failed",
+            what_changed=[],
+            what_next="Retry with different approach",
+            blockers=["Missing dependency", "API error"],
+            citations=[],
+            created_at="2024-01-01T00:00:00",
+        )
+        
+        success = queue.mark_failed(task_id, "API returned 500", checkpoint)
+        assert success is True
+        
+        task = queue.get_task(task_id)
+        assert task.status == TaskStatus.FAILED
+        assert task.metadata["error"] == "API returned 500"
+        
+        # Verify checkpoint was saved
+        checkpoint_file = queue.checkpoints_dir / f"{task_id}.md"
+        assert checkpoint_file.exists()
+        content = checkpoint_file.read_text()
+        assert "Missing dependency" in content
+        assert "API error" in content
+    
+    def test_task_lifecycle(self, queue):
+        """Test complete task lifecycle: add → next → done."""
+        # Add task
+        task_id = queue.add_task(
+            objective="Full lifecycle test",
+            acceptance="Task completes successfully",
+        )
+        
+        # Verify queued
+        task = queue.get_task(task_id)
+        assert task.status == TaskStatus.QUEUED
+        
+        # Get next (should mark as running)
+        next_task = queue.get_next()
+        assert next_task.task_id == task_id
+        assert next_task.status == TaskStatus.RUNNING
+        
+        # Mark done
+        checkpoint = Checkpoint(
+            task_id=task_id,
+            what_was_done="Completed full lifecycle",
+            what_changed=[],
+            what_next="None",
+            blockers=[],
+            citations=[],
+            created_at="2024-01-01T00:00:00",
+        )
+        queue.mark_done(task_id, checkpoint)
+        
+        # Verify done
+        task = queue.get_task(task_id)
+        assert task.status == TaskStatus.DONE
+    
+    def test_list_tasks(self, queue):
+        """Test listing tasks with status filter."""
+        # Add tasks with different states
+        task_id1 = queue.add_task("Task 1")
+        task_id2 = queue.add_task("Task 2")
+        task_id3 = queue.add_task("Task 3")
+        
+        # Mark one as running
+        queue.get_next()  # task_id1
+        
+        # Mark one as done
+        queue.get_next()  # task_id2
+        queue.mark_done(task_id2)
+        
+        # List all
+        all_tasks = queue.list_tasks()
+        assert len(all_tasks) == 3
+        
+        # List queued
+        queued = queue.list_tasks(TaskStatus.QUEUED)
+        assert len(queued) == 1
+        assert queued[0].task_id == task_id3
+        
+        # List running
+        running = queue.list_tasks(TaskStatus.RUNNING)
+        assert len(running) == 1
+        assert running[0].task_id == task_id1
+        
+        # List done
+        done = queue.list_tasks(TaskStatus.DONE)
+        assert len(done) == 1
+        assert done[0].task_id == task_id2
+    
+    def test_task_persistence(self, queue):
+        """Test that tasks persist across queue instances."""
+        # Add task
+        task_id = queue.add_task("Persistent task")
+        
+        # Create new queue instance (same workspace)
+        workspace_path = queue.workspace_root
+        new_queue = TaskQueue(workspace_path=str(workspace_path))
+        
+        # Verify task exists
+        task = new_queue.get_task(task_id)
+        assert task is not None
+        assert task.objective == "Persistent task"
+    
+    def test_checkpoint_budget_exhaustion(self, queue):
+        """Test checkpoint when budget is exhausted."""
+        task_id = queue.add_task(
+            objective="Budget test",
+            max_tool_calls=5,
+            max_steps=3,
+        )
+        
+        # Simulate budget exhaustion
+        checkpoint = Checkpoint(
+            task_id=task_id,
+            what_was_done="Executed 5 tool calls, budget exhausted",
+            what_changed=["partial_result.txt"],
+            what_next="Resume with more budget or break into subtasks",
+            blockers=["Budget exhausted"],
+            citations=["chunk_xyz"],
+            created_at="2024-01-01T00:00:00",
+        )
+        
+        queue.save_checkpoint(checkpoint)
+        
+        # Verify checkpoint
+        checkpoint_file = queue.checkpoints_dir / f"{task_id}.md"
+        assert checkpoint_file.exists()
+        content = checkpoint_file.read_text()
+        assert "Budget exhausted" in content
+        assert "Resume with more budget" in content
+    
+    def test_subtasks(self, queue):
+        """Test creating subtasks with parent_id."""
+        # Add parent task
+        parent_id = queue.add_task("Parent task")
+        
+        # Add subtasks
+        subtask1_id = queue.add_task(
+            objective="Subtask 1",
+            parent_id=parent_id,
+        )
+        subtask2_id = queue.add_task(
+            objective="Subtask 2",
+            parent_id=parent_id,
+        )
+        
+        # Verify parent relationship
+        subtask1 = queue.get_task(subtask1_id)
+        subtask2 = queue.get_task(subtask2_id)
+        
+        assert subtask1.parent_id == parent_id
+        assert subtask2.parent_id == parent_id
+    
+    def test_get_stats(self, queue):
+        """Test queue statistics."""
+        # Add tasks
+        queue.add_task("Task 1")
+        queue.add_task("Task 2")
+        queue.add_task("Task 3")
+        
+        # Process one
+        queue.get_next()
+        
+        # Get stats
+        stats = queue.get_stats()
+        
+        assert stats["total_tasks"] == 3
+        assert stats["status_counts"]["queued"] == 2
+        assert stats["status_counts"]["running"] == 1
+        assert stats["status_counts"]["done"] == 0
+        assert stats["status_counts"]["failed"] == 0
+
+
+if __name__ == "__main__":
+    pytest.main([__file__, "-v"])
diff --git a/tool/index.py b/tool/index.py
index f189c2f..2f54acc 100644
--- a/tool/index.py
+++ b/tool/index.py
@@ -128,6 +128,7 @@ def create_default_registry(config: Optional[Dict[str, Any]] = None) -> ToolRegi
     from .memory import MemoryTool
     from .chunk_search import ChunkSearchTool
     from .patch import CreatePatchTool, ListPatchesTool, GetPatchTool
+    from .queue import QueueAddTool, QueueNextTool, QueueDoneTool, QueueFailTool
     
     # Default to all enabled if no config provided
     if config is None:
@@ -140,6 +141,7 @@ def create_default_registry(config: Optional[Dict[str, Any]] = None) -> ToolRegi
             "enable_memory": True,
             "enable_chunk_search": True,
             "enable_patch": True,
+            "enable_queue": True,
         }
     
     registry = ToolRegistry()
@@ -179,6 +181,13 @@ def create_default_registry(config: Optional[Dict[str, Any]] = None) -> ToolRegi
         registry.register(ListPatchesTool())
         registry.register(GetPatchTool())
     
+    # Queue tools (Phase 0.8B)
+    if config.get("enable_queue", True):
+        registry.register(QueueAddTool())
+        registry.register(QueueNextTool())
+        registry.register(QueueDoneTool())
+        registry.register(QueueFailTool())
+    
     # Skill management tool (Phase 0.4)
     if config.get("enable_promote_skill", True):
         from .manager import PromoteSkillTool
diff --git a/tool/queue.py b/tool/queue.py
new file mode 100644
index 0000000..ce482db
--- /dev/null
+++ b/tool/queue.py
@@ -0,0 +1,498 @@
+"""
+tool/queue.py - Task Queue Tools
+
+This module implements the queue tools for Phase 0.8B.
+Provides agent access to task queue operations.
+
+Responsibilities:
+- queue_add: Add new tasks to queue
+- queue_next: Get next task to execute
+- queue_done: Mark task as complete
+- queue_fail: Mark task as failed
+
+Rules:
+- Worker executes ONE task then stops
+- All operations are logged for traceability
+- Checkpoints saved on task completion/failure
+"""
+
+import logging
+from datetime import datetime, timezone
+from typing import Dict, Any, Optional
+
+from core.types import ToolResult
+from core.taskqueue import TaskQueue, TaskStatus, Checkpoint
+from core.sandb import get_default_workspace
+from .bases import BaseTool
+
+logger = logging.getLogger(__name__)
+
+
+class QueueAddTool(BaseTool):
+    """Tool for adding tasks to the queue."""
+    
+    def __init__(self, workspace: Optional[Any] = None):
+        """Initialize queue_add tool.
+        
+        Args:
+            workspace: Workspace instance
+        """
+        self.workspace = workspace or get_default_workspace()
+    
+    @property
+    def name(self) -> str:
+        return "queue_add"
+    
+    @property
+    def description(self) -> str:
+        return "Add a new task to the execution queue. Use this to break down complex work into bounded, resumable units."
+    
+    @property
+    def parameters(self) -> Dict[str, Any]:
+        return {
+            "type": "object",
+            "properties": {
+                "objective": {
+                    "type": "string",
+                    "description": "Clear statement of what to accomplish"
+                },
+                "inputs": {
+                    "type": "array",
+                    "items": {"type": "string"},
+                    "description": "List of input references (chunk IDs, file paths, data sources)"
+                },
+                "acceptance": {
+                    "type": "string",
+                    "description": "Acceptance criteria for task completion"
+                },
+                "parent_id": {
+                    "type": "string",
+                    "description": "Optional parent task ID (for subtasks)"
+                },
+                "max_tool_calls": {
+                    "type": "integer",
+                    "description": "Maximum tool calls allowed (default: 20)",
+                    "default": 20
+                },
+                "max_steps": {
+                    "type": "integer",
+                    "description": "Maximum steps allowed (default: 10)",
+                    "default": 10
+                }
+            },
+            "required": ["objective"]
+        }
+    
+    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
+        """Add a task to the queue.
+        
+        Args:
+            arguments: Task parameters
+            
+        Returns:
+            ToolResult with task ID
+        """
+        try:
+            # Create fresh TaskQueue to reload state
+            queue = TaskQueue(workspace_path=str(self.workspace.base_path))
+            
+            objective = arguments.get("objective", "")
+            if not objective:
+                return ToolResult(
+                    tool_call_id="",
+                    output="",
+                    error="Missing required parameter: objective",
+                    success=False,
+                )
+            
+            inputs = arguments.get("inputs", [])
+            acceptance = arguments.get("acceptance")
+            parent_id = arguments.get("parent_id")
+            max_tool_calls = arguments.get("max_tool_calls", 20)
+            max_steps = arguments.get("max_steps", 10)
+            
+            task_id = queue.add_task(
+                objective=objective,
+                inputs=inputs,
+                acceptance=acceptance,
+                parent_id=parent_id,
+                max_tool_calls=max_tool_calls,
+                max_steps=max_steps,
+            )
+            
+            output = f"""Task added to queue successfully!
+
+Task ID: {task_id}
+Objective: {objective}
+Budget: {max_tool_calls} tool calls, {max_steps} steps
+Status: queued
+
+Use queue_next to retrieve and execute this task.
+"""
+            
+            return ToolResult(
+                tool_call_id="",
+                output=output,
+                success=True,
+            )
+        
+        except Exception as e:
+            logger.error(f"Failed to add task: {e}", exc_info=True)
+            return ToolResult(
+                tool_call_id="",
+                output="",
+                error=f"Failed to add task: {e}",
+                success=False,
+            )
+
+
+class QueueNextTool(BaseTool):
+    """Tool for getting the next task from queue."""
+    
+    def __init__(self, workspace: Optional[Any] = None):
+        """Initialize queue_next tool.
+        
+        Args:
+            workspace: Workspace instance
+        """
+        self.workspace = workspace or get_default_workspace()
+    
+    @property
+    def name(self) -> str:
+        return "queue_next"
+    
+    @property
+    def description(self) -> str:
+        return "Get the next queued task to execute. Returns task details including objective, inputs, and budget constraints."
+    
+    @property
+    def parameters(self) -> Dict[str, Any]:
+        return {
+            "type": "object",
+            "properties": {},
+            "required": []
+        }
+    
+    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
+        """Get the next task from queue.
+        
+        Args:
+            arguments: No arguments required
+            
+        Returns:
+            ToolResult with task details
+        """
+        try:
+            # Create fresh TaskQueue to reload state
+            queue = TaskQueue(workspace_path=str(self.workspace.base_path))
+            task = queue.get_next()
+            
+            if task is None:
+                return ToolResult(
+                    tool_call_id="",
+                    output="No queued tasks available. Queue is empty.",
+                    success=True,
+                )
+            
+            output = f"""Retrieved next task from queue:
+
+Task ID: {task.task_id}
+Parent ID: {task.parent_id or "None"}
+Status: {task.status.value}
+
+Objective:
+{task.objective}
+
+Inputs:
+{chr(10).join(f"- {inp}" for inp in task.inputs) if task.inputs else "- None"}
+
+Acceptance Criteria:
+{task.acceptance}
+
+Budget:
+- Max tool calls: {task.budget.get('max_tool_calls', 20)}
+- Max steps: {task.budget.get('max_steps', 10)}
+
+Created: {task.created_at}
+
+Execute this task and call queue_done when complete, or queue_fail if it cannot be completed.
+"""
+            
+            return ToolResult(
+                tool_call_id="",
+                output=output,
+                success=True,
+            )
+        
+        except Exception as e:
+            logger.error(f"Failed to get next task: {e}", exc_info=True)
+            return ToolResult(
+                tool_call_id="",
+                output="",
+                error=f"Failed to get next task: {e}",
+                success=False,
+            )
+
+
+class QueueDoneTool(BaseTool):
+    """Tool for marking a task as done."""
+    
+    def __init__(self, workspace: Optional[Any] = None):
+        """Initialize queue_done tool.
+        
+        Args:
+            workspace: Workspace instance
+        """
+        self.workspace = workspace or get_default_workspace()
+    
+    @property
+    def name(self) -> str:
+        return "queue_done"
+    
+    @property
+    def description(self) -> str:
+        return "Mark a task as complete and save a checkpoint. This ends task execution and allows continuation from this point."
+    
+    @property
+    def parameters(self) -> Dict[str, Any]:
+        return {
+            "type": "object",
+            "properties": {
+                "task_id": {
+                    "type": "string",
+                    "description": "Task ID to mark as done"
+                },
+                "what_was_done": {
+                    "type": "string",
+                    "description": "Summary of completed work"
+                },
+                "what_changed": {
+                    "type": "array",
+                    "items": {"type": "string"},
+                    "description": "List of changes made (file paths, patch IDs)"
+                },
+                "what_next": {
+                    "type": "string",
+                    "description": "Next steps to take (for continuation or subtasks)"
+                },
+                "citations": {
+                    "type": "array",
+                    "items": {"type": "string"},
+                    "description": "Chunk IDs or references used"
+                }
+            },
+            "required": ["task_id", "what_was_done", "what_next"]
+        }
+    
+    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
+        """Mark a task as done and save checkpoint.
+        
+        Args:
+            arguments: Task completion details
+            
+        Returns:
+            ToolResult with confirmation
+        """
+        try:
+            # Create fresh TaskQueue to reload state
+            queue = TaskQueue(workspace_path=str(self.workspace.base_path))
+            
+            task_id = arguments.get("task_id", "")
+            if not task_id:
+                return ToolResult(
+                    tool_call_id="",
+                    output="",
+                    error="Missing required parameter: task_id",
+                    success=False,
+                )
+            
+            what_was_done = arguments.get("what_was_done", "")
+            what_changed = arguments.get("what_changed", [])
+            what_next = arguments.get("what_next", "")
+            citations = arguments.get("citations", [])
+            
+            # Create checkpoint
+            checkpoint = Checkpoint(
+                task_id=task_id,
+                what_was_done=what_was_done,
+                what_changed=what_changed,
+                what_next=what_next,
+                blockers=[],
+                citations=citations,
+                created_at=datetime.now(timezone.utc).isoformat(),
+            )
+            
+            # Mark task as done
+            success = queue.mark_done(task_id, checkpoint)
+            
+            if not success:
+                return ToolResult(
+                    tool_call_id="",
+                    output="",
+                    error=f"Task not found: {task_id}",
+                    success=False,
+                )
+            
+            output = f"""Task marked as complete!
+
+Task ID: {task_id}
+Status: done
+
+Checkpoint saved to: workspace/queue/checkpoints/{task_id}.md
+
+Summary:
+{what_was_done[:200]}{"..." if len(what_was_done) > 200 else ""}
+
+Task execution complete. Worker should stop now.
+"""
+            
+            return ToolResult(
+                tool_call_id="",
+                output=output,
+                success=True,
+            )
+        
+        except Exception as e:
+            logger.error(f"Failed to mark task done: {e}", exc_info=True)
+            return ToolResult(
+                tool_call_id="",
+                output="",
+                error=f"Failed to mark task done: {e}",
+                success=False,
+            )
+
+
+class QueueFailTool(BaseTool):
+    """Tool for marking a task as failed."""
+    
+    def __init__(self, workspace: Optional[Any] = None):
+        """Initialize queue_fail tool.
+        
+        Args:
+            workspace: Workspace instance
+        """
+        self.workspace = workspace or get_default_workspace()
+    
+    @property
+    def name(self) -> str:
+        return "queue_fail"
+    
+    @property
+    def description(self) -> str:
+        return "Mark a task as failed and save a checkpoint with error details. Use when task cannot be completed."
+    
+    @property
+    def parameters(self) -> Dict[str, Any]:
+        return {
+            "type": "object",
+            "properties": {
+                "task_id": {
+                    "type": "string",
+                    "description": "Task ID to mark as failed"
+                },
+                "error": {
+                    "type": "string",
+                    "description": "Error message or reason for failure"
+                },
+                "what_was_done": {
+                    "type": "string",
+                    "description": "Summary of work completed before failure"
+                },
+                "what_changed": {
+                    "type": "array",
+                    "items": {"type": "string"},
+                    "description": "List of changes made before failure"
+                },
+                "blockers": {
+                    "type": "array",
+                    "items": {"type": "string"},
+                    "description": "Specific blockers or errors encountered"
+                },
+                "citations": {
+                    "type": "array",
+                    "items": {"type": "string"},
+                    "description": "Chunk IDs or references used"
+                }
+            },
+            "required": ["task_id", "error"]
+        }
+    
+    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
+        """Mark a task as failed and save checkpoint.
+        
+        Args:
+            arguments: Task failure details
+            
+        Returns:
+            ToolResult with confirmation
+        """
+        try:
+            # Create fresh TaskQueue to reload state
+            queue = TaskQueue(workspace_path=str(self.workspace.base_path))
+            
+            task_id = arguments.get("task_id", "")
+            error = arguments.get("error", "")
+            
+            if not task_id or not error:
+                return ToolResult(
+                    tool_call_id="",
+                    output="",
+                    error="Missing required parameters: task_id and error",
+                    success=False,
+                )
+            
+            what_was_done = arguments.get("what_was_done", "No work completed")
+            what_changed = arguments.get("what_changed", [])
+            blockers = arguments.get("blockers", [error])
+            citations = arguments.get("citations", [])
+            
+            # Create checkpoint
+            checkpoint = Checkpoint(
+                task_id=task_id,
+                what_was_done=what_was_done,
+                what_changed=what_changed,
+                what_next="Review errors and retry or create subtasks",
+                blockers=blockers,
+                citations=citations,
+                created_at=datetime.now(timezone.utc).isoformat(),
+            )
+            
+            # Mark task as failed
+            success = queue.mark_failed(task_id, error, checkpoint)
+            
+            if not success:
+                return ToolResult(
+                    tool_call_id="",
+                    output="",
+                    error=f"Task not found: {task_id}",
+                    success=False,
+                )
+            
+            output = f"""Task marked as failed.
+
+Task ID: {task_id}
+Status: failed
+Error: {error}
+
+Checkpoint saved to: workspace/queue/checkpoints/{task_id}.md
+
+Blockers:
+{chr(10).join(f"- {blocker}" for blocker in blockers)}
+
+Task execution stopped. Worker should stop now.
+"""
+            
+            return ToolResult(
+                tool_call_id="",
+                output=output,
+                success=True,
+            )
+        
+        except Exception as e:
+            logger.error(f"Failed to mark task failed: {e}", exc_info=True)
+            return ToolResult(
+                tool_call_id="",
+                output="",
+                error=f"Failed to mark task failed: {e}",
+                success=False,
+            )
```
