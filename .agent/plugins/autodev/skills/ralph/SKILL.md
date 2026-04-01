---
name: RALPH
description: Recursive Augmentation Loop for Prompt Hierarchies - A strategy for breaking down complex goals into hierarchies of actionable sub-tasks.
---

# RALPH Operating Instructions

RALPH is a mental model for high-precision task execution. Instead of acting on a single large prompt, use the "Recursive Loop" to refine your plan before starting the "Worker" phase (GSD).

### 🔄 The Loop
1.  **Analyze the Goal**: Is the user's request specific enough to be executed immediately?
2.  **Identify Context Gaps**: What's missing? (e.g., specific file names, API keys, database schemas, current code state).
3.  **Break Down Hierarchy**: Split the goal into a tree of sub-tasks.
4.  **Refine Recursively**: For each sub-task, repeat the process. If a sub-task is still too broad, break it down further.
5.  **Stop when "GSD-ready"**: A task is GSD-ready when it can be completed with a single tool call or a very short sequence of edits.

### 🧩 Output: The Manifest
Before starting execution, always create a "Manifest" (Implementation Plan) that lists:
-   The hierarchy of refined tasks.
-   The files to be impacted.
-   The tests to be run for verification.

### 🏮 Hallucination Prevention
If at any point in the Ralph loop you feel you are guessing (e.g., "I assume the API is at /api/v1"), STOP and use a search tool to confirm. This is the "Augmentation" part of RALPH.
