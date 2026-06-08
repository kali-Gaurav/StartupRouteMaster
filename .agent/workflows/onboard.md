---
description: Automatically scan a new codebase and generate a project roadmap and task board.
---

# Autonomous Project Onboarding

## Objective
To allow the NeuralForge team to instantly understand any new codebase and present the Founder with an actionable plan on Day One.

## Workflow Execution
1. **Semantic Indexing**: NEXUS (CTO) will perform a deep code analysis.
   - **// turbo** Run the indexer: `python .agent/protocols/semantic_indexer.py .`
   - This builds the `core_brain.graphml` by parsing the Abstract Syntax Tree (AST) of the entire project.
2. **Initial Scan**: HERA (HR) and NEXUS will analyze the graph nodes.
   - Run `python .agent/protocols/core_engine.py . boot` to see graph stats.
2. **Analysis**:
   - Identify the tech stack, existing architecture, and major dependencies.
   - Identify "Context Gaps" where documentation is missing.
3. **Output Generation**:
   - Create/Update `roadmap.md` with high-level goals.
   - Create/Update `task.md` with immediate prioritized tasks for the team.
4. **Founder Briefing**: Present the current system state and the proposed plan. Ask for approval to start the first task.
