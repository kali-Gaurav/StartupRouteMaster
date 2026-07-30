---
description: Finalize a swarm task and log findings into corporate memory.
---

# Report Swarm Findings

## Objective
To finalize a swarm's task and log their technical findings into the Leader's temporary growth memory.

## Workflow Execution
1. **Analyze Input**: Check if the Founder provided the required arguments: `<SwarmID> "<Outcome Summary>" "<Technical Findings>"`.
2. **Missing Input**: If arguments are missing (e.g., just `/report` was typed), ask the Founder: "Which SWARM-ID are you reporting on, what is the brief outcome, and what are the specific technical findings to remember?" Stop and wait for their reply.
3. **// turbo** Once arguments are provided, run the report logic: `python .agent/protocols/core_engine.py . report <SwarmID> "<Outcome Summary>" "<Technical Findings>"`
4. **Experience Harvesting**: Inform the Founder that these findings have been automatically added to the **Collective Experience Ledger** for all future projects.
5. **Upgrade Path**: Remind the Founder they can use `/upgrade <Leader>` to permanently harden these learnings.
6. **Auto-Healing (Failure Handling)**: If the `<Outcome Summary>` indicates a technical failure (e.g., "Tests failed"), the Leader must immediately trigger the **Resilience Protocol** (QA -> Fixer) before notifying the Founder.
