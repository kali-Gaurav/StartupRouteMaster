---
description: Autonomous development cycle following RALPH and GSD.
---

# Autonomous Development Workflow

This workflow combines recursive task planning (RALPH) with iterative execution (GSD) for high-performance building.

### ⚙️ Step 1: Goal Initialization
1.  **Understand the goal**: Read the user's high-level request.
2.  **Context Discovery**: Run `list_dir` or `grep_search` to map the system architecture.
3.  **RALPH Refinement**:
    -   Break the goal into sub-goals.
    -   State any assumptions.
    -   Generate an **Implementation Plan (Manifest)**.

### 🔨 Step 2: GSD Execution
1.  **Select Task**: Pick the first GSD-ready task from the manifest.
2.  **Act**: Modify files (`replace_file_content`), run commands, etc.
3.  **Verify**: Run tests (`pytest`, `npm test`) or manually verify via `view_file`.
4.  **Loop**: If successful, pick the next task. If failed, return to Step 1.3 with Error Context.

### 🐇 Step 3: Auditor Feedback (CodeRabbit Link)
1.  **Commit & Push**: Once all tasks are complete, finalize changes.
2.  **Audit Check**: Wait for any feedback (simulated or via user comments).
3.  **Recursive Correction**: If "Auditor (CodeRabbit)" identifies a bug, restart Step 1 with the feedback as the primary goal.

### 🏁 Step 4: Finalization
1.  **Final Verification**: Ensure the entire goal is met.
2.  **Summary**: Provide a clear report of exactly what was changed and why.
