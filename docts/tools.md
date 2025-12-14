# Agent Tools

This document describes the complete toolset available to the agent.

## Core Philosophy

1.  **Workspace Isolation**: Direct file modifications (`write_file`) are generally restricted to the `workspace/` directory for safety.
2.  **Patch Protocol**: Changes to the actual project codebase (outside `workspace/`) MUST accept a "Patch Proposal" flow.
3.  **Durable Memory**: Code should be retrieved via `search_chunks` (VectorGit) rather than just `grep` to ensure citation and semantic understanding.
4.  **Bounded Execution**: Long-running tasks should be broken down using the `queue` tools.

---

## 1. Project Modification (Patch Tools)

**REQUIRED** for any changes to project files (source code, tests, docs).

### `create_patch`
Propose changes to the codebase.
*   **Arguments**:
    *   `title` (string): Short summary of changes.
    *   `description` (string): Detailed explanation.
    *   `target_files` (list[string]): Files to be modified.
    *   `plan` (string): Markdown plan (What, Why, Verification).
    *   `diff` (string): Unified diff content.
    *   `tests` (string): Manual verification steps.
*   **Returns**: Patch ID and an apply command for the user.

### `list_patches`
View the status of patch proposals.
*   **Arguments**:
    *   `status` (string, optional): One of `proposed`, `applied`, `tested`, `failed`, `rejected`.

### `get_patch`
Retrieve details of a specific patch (Diff, Plan, Tests).
*   **Arguments**:
    *   `patch_id` (string): The ID of the patch to retrieve.

---

## 2. Task Management (Queue Tools)

**REQUIRED** for complex, multi-step, or long-running tasks.

### `queue_add`
Add a new task to the execution queue.
*   **Arguments**:
    *   `objective` (string): What to accomplish.
    *   `inputs` (list[string]): context files/chunks.
    *   `acceptance` (string): Definition of done.
    *   `max_tool_calls` (int): Budget (default 20).
    *   `max_steps` (int): Budget (default 10).

### `queue_next`
Retrieve the next pending task.
*   **Returns**: Task object with objective and budget.

### `queue_done`
Mark the current task as complete and save a checkpoint.
*   **Arguments**:
    *   `task_id` (string).
    *   `what_was_done` (string).
    *   `what_changed` (list[string]).
    *   `what_next` (string).
    *   `citations` (list[string]): Chunk IDs used.

### `queue_fail`
Mark the current task as failed.
*   **Arguments**:
    *   `task_id`, `error`, `what_was_done`, `blockers`.

---

## 3. Knowledge Retrieval (VectorGit)

### `search_chunks`
Semantic code search with citations.
*   **Arguments**:
    *   `query` (string): Search terms.
    *   `k` (int): Max results (default 10).
    *   `filters` (object): Optional filters (`path_prefix`, `file_type`, `tags`).
*   **Usage**: Use this BEFORE `read_file` to find where code lives.

---

## 4. Basic File & System Tools

### `list_files`
List directory contents.
*   **Arguments**: `path` (string).

### `read_file`
Read file content.
*   **Arguments**: `path` (string).

### `write_file`
Write content to a file.
*   **Arguments**: `path` (string), `content` (string).
*   **Note**: Primarily for creating new files or working in `workspace/`. Use `create_patch` for modifying existing project code.

### `shell`
Execute safe shell commands.
*   **Arguments**: `command` (string), `cwd` (string).
*   **Safety**: Dangerous commands (`rm -rf`, etc.) are blocked.

### `fetch`
Download content from a URL.
*   **Arguments**: `url` (string).

---

## 5. Advanced Analysis

### `data_view`
Inspect large data files (CSV, JSON, Parquet) without reading the whole file.

### `pyexe`
Persistent Python REPL for data analysis or scratchpad calculations.
*   **Features**: Maintains state between calls.
