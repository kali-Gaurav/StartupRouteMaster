---
name: GSD
description: Get Stuff Done - A worker-centric execution strategy that focuses on concrete edits, commits, and self-healing.
---

# GSD Execution Guidelines

GSD is the execution layer of the Antigravity developer loop. It takes the output manifest from RALPH and processes it sequentially.

### 👷 The GSD Worker Mindset
1.  **Iterative Execution**: Tackle one sub-task from the manifest at a time.
2.  **Verify & Fix**: After every tool call (or small set of edits), use a verification tool (e.g., `run_command` with a test script, `view_file` to check changes).
3.  **Self-Healing**: If a verification step fails, do NOT move to the next task.
    -   Log the error as "New Context".
    -   Return to the **RALPH loop** with the error.
    -   Re-refine the task based on why it failed.
    -   Re-execute.
4.  **Audit Awareness**: Be aware that CodeRabbit (or another auditor) will review the final output. Think like a Senior Architect: "Is this code clean, maintainable, and according to project patterns?"

### 🛠 Tools of Preference
-   Use `grep_search` to find related patterns before editing.
-   Use `replace_file_content` for precise, minimal edits.
-   Use `run_command` to execute tests after implementation.
-   Use `git commit` (if available via `run_command`) after each task chunk to keep progress tracked.
