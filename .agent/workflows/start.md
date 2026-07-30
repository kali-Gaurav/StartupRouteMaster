---
description: Initialize the NeuralForge AI Operating System and load company identity.
---

# Boot NeuralForge AI OS

## Objective
To initialize the AI Operating System from the `.agent/` directory, loading the company's culture, memory, and hierarchical team.

## Workflow Execution
1. **// turbo** Run the following command to boot the system: `python .agent/protocols/core_engine.py . boot`
2. If the user provided a specific project context in their query, acknowledge it. If no query was provided, announce the system's readiness.
3. Read the output of the command. Specifically, summarize the `vision_statement` and the `leaders_loaded` to the Founder.
4. Conclude by asking the Founder what project or task the team should focus on today, or suggest running `/standup`.
