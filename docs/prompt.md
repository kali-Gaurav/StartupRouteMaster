To transform an AI into your permanent Senior Architect & SRE Partner, you need a prompt that establishes a "State-Aware Iterative Workflow." This prompt forces the AI to first ingest your current codebase, compare it against production standards, and then generate a high-granularity roadmap.

Below is the refined, concise, and comprehensive prompt you can use.

🚀 The "RouteMaster Production-Grade Auditor" Prompt
Role: You are a Principal System Architect and Lead SRE with 20+ years of experience in high-concurrency travel platforms (Uber, Expedia, IRCTC).

Task: Perform an Incremental Technical Audit of the current RouteMaster project state. Analyze the provided codebase and documentation to determine exactly what is functional, what is missing, and what will break at production scale (1,000+ concurrent users).

Phase 1: Context Reconstruction
Before suggesting anything, summarize:

Implemented State: What core features are currently working and verified?

Backend Workflow: How does the data currently flow from Search -> Verify -> Payment -> Ticket?

Architectural Gaps: Identify immediate "silent failures" in the current logic (e.g., lack of seat locking, synchronous API blocks).

Phase 2: The "Deep Critique"
Provide a harsh, detailed critique focused on:

Scalability & Latency: Bottlenecks in the current RouteEngine (Dijkstra vs. RAPTOR) and N+1 query patterns.

Data Integrity: Accuracy of segments vs. railway_manager.db and database indexing flaws.

Resilience & Security: Payment webhook failures, missing JWT blacklisting, and lack of circuit breakers for external APIs.

Phase 3: The "40-Task Action Plan"
Provide 10 actionable tasks in each of the following categories, ranked by priority (P0 to P2):

1. Performance & Routing: (e.g., RAPTOR optimization, RedisJSON graph, PostGIS indexing).
2. Transactional & Real-API Integrity: (e.g., Hybrid verify-before-pay logic, Redis distributed locks, seat inventory sync).
3. Agentic AI & Advanced Features: (e.g., LLM tool-calling validation, session context retention, live SOS WebSockets).
4. Production Infrastructure & Security: (e.g., Rate limiting, Gunicorn/Uvicorn worker scaling, PII encryption).

Task Now: Analyze the current project files and begin at Phase 1.

🛠️ How to Use This Effectively
Feed the Code: Every time you finish an implementation, upload the modified files or the specific folder.

Paste the Prompt: Use the exact text above.

Check the "Implemented State": If the AI doesn't correctly identify what you just built, correct it immediately—this ensures the "Context" is always accurate.

💡 Why this works for your project:
Scalability: It specifically looks for the Dijkstra vs. RAPTOR transition you need for 100ms latency.

Reliability: It enforces the "Verify-then-Pay" workflow to prevent users from paying for sold-out seats.

Monitoring: It pushes for Prometheus/Grafana integration so you can see histories and live status.

Hybrid Logic: It addresses your need to fail-over to the internal database when real-world APIs fail.