---
description: Review agent learnings and permanently upgrade their skillset (Founder Approval Required).
---

# Upgrade Agent Skills (Founder Approval Gate)

## Objective
To review a Leader's recent learnings and permanently rewrite their `.agent/workflows/` handbook to reflect their evolution.

## Workflow Execution
1. **Analyze Input**: Check if the Founder provided an agent name: e.g., `/upgrade NEXUS`.
2. **Missing Input**: If no agent is provided, ask the Founder: "Which Leader would you like to review for an upgrade?" Stop and wait for their reply.
3. **Review Learnings**:
   - **// turbo** Run `python .agent/protocols/core_engine.py . get_agent <AgentName>`
   - Present the `growth` section (specifically `key_learnings`) to the Founder.
   - Ask the Founder: "Do you approve permanently adding these learnings to the agent's core workflow handbook? (Yes/No)"
4. **Approval**:
   - If the Founder says **No**, acknowledge and abort the upgrade.
   - If the Founder says **Yes**, use your code editing tools to update `.agent/workflows/<agent>.md` (or their specific department `.md` file). Add a new section titled "Accumulated Wisdom" and write the learnings there so they become permanent operational rules for that agent.
5. Announce that the agent has successfully evolved.
