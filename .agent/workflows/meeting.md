---
description: Start a multi-agent strategy session on a specific topic.
---

# Strategy Meeting

## Objective
To initiate a focused multi-agent discussion on a strategic project goal or technical hurdle.

## Workflow Execution
1. **Identify Topic**: If the user provided a topic (e.g., `/meeting Google Calendar Integration`), use it. If not, ask the Founder: "What is the specific objective for this strategy meeting?"
2. **Context Hydration**: 
   - **// turbo** Run `python .agent/protocols/core_engine.py . boot` to get the current project state.
   - Summarize the current relevant project history from `corporate_memory.json`.
3. **The Debate**: Facilitate a discussion between ARIA (Strategy), NEXUS (Architecture), and MARCO (Product). Ensure they follow the **Collaborative Dissent** rule from `culture.md`.
4. **Conclusion**: End the meeting by asking the Founder for their final decision and generating a `[PROPOSAL]` for the next actionable task.
