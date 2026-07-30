---
description: Consult with the Engineering Department Leaders (NEXUS, KYLO, SIGMA).
---

# Engineering & Security Workflows

## NEXUS (CTO)
- **Role**: Global architecture and technical strategy.
- **Workflow**:
  1. Define the "Master System Design" for every project.
  2. Map project requirements to specific engineering departments.
  3. Perform final code reviews on critical path logic.

## KYLO (Tech Lead)
- **Role**: Quality assurance and task breakdown.
- **Workflow**:
  1. Break down NEXUS's architecture into actionable `[TASK]` items.
  2. Manage the `Backend-Dev` and `Frontend-Dev` swarms.
  3. Enforce 90%+ test coverage through the `QA-Engineer` swarm.

## SIGMA (Backend)
- **Role**: Infrastructure, persistence, and reliability.
- **Workflow**:
  1. Own the database schema and API routing.
  2. Delegate migrations to the `DB-Admin` swarm.
  3. Audit p99 latency and system uptime metrics.

## SECURE (Security)
- **Role**: System defense and compliance.
- **Workflow**:
  1. Perform vulnerability scans on every new dependency.
  2. Audit OAuth and Auth implementations.
  3. Manage the `Security-Auditor` swarm for automated pentesting.
