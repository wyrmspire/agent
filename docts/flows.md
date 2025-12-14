# Agent Flows

This document describes how the agent operates, including standard reasoning loops and specialized protocols.

## Core Loop

The basic reasoning loop (`flow/loops.py`) follows this cycle:
1.  **Observe**: Receive user input/tool output.
2.  **Think**: Decide what to do (using available tools).
3.  **Act**: Call a tool.
4.  **Repeat**: Until the task is done or max steps reached.

---

## 1. Patch Protocol (Code Modification)

**When to use**: Whenever you need to modify project files (source code, tests, docs, config) outside of the sandbox `workspace/`.

1.  **Draft**:
    *   Research the codebase using `search_chunks` and `read_file`.
    *   Formulate a plan.
    *   Call `create_patch` with:
        *   `plan`: What/Why/How.
        *   `diff`: The actual code changes.
        *   `tests`: How to verify the changes.
2.  **Proposed**:
    *   The tool saves the patch to `workspace/patches/`.
    *   It returns a command for the user to apply it (e.g., `python tool/patch.py apply <id>`).
3.  **Review & Apply** (Human-in-the-loop):
    *   The user reviews the plan and diff.
    *   The user (or a separate process) checks the tests.
    *   If approved, the patch is applied.

**Why?** This prevents the agent from destructively modifying the codebase without oversight and ensures all changes are planned and reversible.

---

## 2. Task Queue Flow (Long-Running Tasks)

**When to use**: When a request is too complex for a single context window (risk of OOM or token limits), or requires multiple distinct stages.

1.  **Breakdown**:
    *   Agent analyzes the request.
    *   Agent calls `queue_add` multiple times to create subtasks. (e.g., "Implement Feature A", "Write Tests for A", "Refactor B").
2.  **Execution Loop**:
    *   Agent calls `queue_next` to pick up the top task.
    *   Agent performs the work for *that specific task*.
    *   Agent calls `queue_done` (success) or `queue_fail` (blocker).
    *   *Checkpoint**: State is saved to disk.
3.  **Completion**:
    *   When `queue_next` returns nothing, the entire workflow is done.

**Why?** This ensures "bounded execution". The agent clears its context between tasks, simulating infinite memory/attention span.

---

## 3. Retrieval Flow (VectorGit)

**When to use**: When answering questions about the codebase or finding where to implement a feature.

1.  **Search**:
    *   Agent calls `search_chunks` with a query (e.g., "auth middleware").
2.  **Cite**:
    *   The tool returns chunks with IDs (e.g., `chunk_123ab`).
    *   Agent uses these IDs in its reasoning.
3.  **Answer**:
    *   Agent synthesizes an answer based *only* on the retrieved chunks (RAG).

**Why?** Prevents hallucinations and ensures the agent is looking at the actual, current code.

---

## Standard Safety Rules

*   **No Dangerous Commands**: `rm -rf`, `format`, `dd` are blocked.
*   **No Sensitive Access**: `.ssh/`, `/etc/shadow` are blocked.
*   **Workspace Sandbox**: `write_file` is preferred for `workspace/`.
*   **Patch Requirement**: Modifications to `src/` or `tests/` MUST use the Patch Protocol.
