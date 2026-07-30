---
description: Generate a strategic summary of the week's progress, learnings, and budget.
---

# Founder Pulse Report

## Objective
To provide the Founder with a high-level summary of company performance and agent evolution.

## Workflow Execution
1. **Data Aggregation**:
   - Read `.agent/memory/budget.json` for spend tracking.
   - Read `.agent/memory/experience.json` for new lessons.
   - Review the `operational_logs/` for completed milestones.
2. **Analysis (ARIA)**:
   - **Velocity**: How many tasks were moved to `[x]` in `task.md`.
   - **ROI**: Feature progress vs. Token spend (Audit by FELIX).
   - **Evolution**: Identify agents who have reached a "Critical Mass" of new skills.
3. **Founder Briefing**: Present a concise markdown report with:
   - ✅ What we built.
   - 🧠 What we learned (The Global Broadcast).
   - 📈 Team Level-Up status.
4. Conclude by suggesting the primary focus for the upcoming week.
