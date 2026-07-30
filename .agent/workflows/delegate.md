---
description: Delegate a technical task to a specialized sub-agent swarm.
---

# Delegate Task to Swarm

## Objective
To spawn a specialized sub-agent swarm for a specific, focused execution task.

## Workflow Execution
1. **Analyze Input**: Check if the Founder provided the required arguments: `<Leader> <SubAgent> <Task>`.
2. **Missing Input**: If arguments are missing (e.g., just `/delegate` was typed), ask the Founder: "Which Leader is delegating, which Sub-Agent type is needed, and what is the exact task?" Stop and wait for their reply.
3. **// turbo** Once arguments are provided, run the delegation logic: `python .agent/protocols/core_engine.py . delegate <Leader> <SubAgent> "<Task>"`
4. Report the resulting `SWARM-ID` back to the Founder. State that the swarm is now active and will require a `/report` when the technical task is finalized.
