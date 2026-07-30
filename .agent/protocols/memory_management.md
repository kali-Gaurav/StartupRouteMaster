# NeuralForge Memory Management Protocol

To ensure the AI Office evolves and learns like a real company, data must be stored and retrieved systematically.

## 1. Corporate Memory (`memory.json`)
This file is the "History Books" of the company. It stores project-level successes, failures, and technical patterns.

### Storage Rules:
- **Project Snapshots**: Every completed project gets a dedicated entry with a 3-sentence summary.
- **Lessons Learned**: Avoid generic advice. Store specific technical solutions (e.g., "Use batched Redis updates to avoid p99 spikes").
- **Pattern Matching**: When starting a new project, Antigravity must search this file for similar technology stacks or problem sets.

## 2. Employee Growth (`growth.json`)
This file tracks the individual experience levels of your agents.

### Evolution Rules:
- **Leveling Up**: After a project or critical task, agents who contributed significantly should have their `growth_level` incremented (Max 10).
- **Domain Mastery**: If an agent solves a specific niche problem (e.g., NOVA optimizing a transformer model), that mastery must be recorded as a `key_learning`.
- **Knowledge Injection**: During meetings, Antigravity must inject these `key_learnings` into the agent's simulated thoughts to ensure they act more "senior" over time.

## 3. Operational Logs (`/operational_logs/`)
- **Meeting Summaries**: Store a Markdown file for every major meeting.
- **Decision Log**: Record every Founder Approval with the timestamp and rationale. This allows for auditing why certain paths were taken.

## 4. Optimization & Cleanup
- **Compaction**: Once a month, Antigravity should summarize old, granular memories into broader "Organizational Wisdom" to keep file sizes manageable for portability.
- **Redundancy**: Remove duplicate lessons. If a pattern is proven across multiple projects, move it to "Standard Operating Procedures".
