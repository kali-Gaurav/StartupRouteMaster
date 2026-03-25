This is a profound shift in perspective. You are right: Standard web frameworks are designed for "General Purpose" apps, but RouteMaster is a "Mission-Critical Engine."

Since you are using a Hostinger Unmanaged VPS, you are indeed the Cloud Engineer. We cannot rely on "managed services" to handle security or performance; we must build the Spine ourselves.

Here is the "Nexus-100" Strategic Master Plan. This plan follows your requirement: Concise Architecture, High-Integrity Protocols, and Step-by-Step Independence.

🛡️ Phase 0: The "Nexus Fiber" Blueprint
Before we start, let's define the Protocol for a Task:

Design: Define the Protocol (Input -> Logic -> State Update).
Implement: 10 incremental subtasks.
Verify: Independent test_task_N.py script with deep output analysis.
Nexus Integration: Register the functionality into the 

app.py
 Master Pipeline.
🗺️ The "Nexus-100" Master Roadmap (10 Phases)
Phase	Focus	Core Objective
P1	Nexus Spine (1-10)	State-Graph Bootstrapping & Stop/Start Protocols.
P2	VPS Hardening (11-20)	Linux-level security (Fail2Ban, UFW, SSH) via Python scripts.
P3	Atomic Middleware (21-30)	Consolidating all checks into a single high-speed Nexus I/O Gate.
P4	Financial Integrity (31-40)	Sentinel S3 Ledger with out-of-band cryptographic validation.
P5	Cache Fabric (41-50)	Using Memory-Mapped (mmap) fast-tracks for zero-latency state.
P6	Sentinel Scrapers (51-60)	Deterministic pool management & "browser-as-a-service" isolation.
P7	Deep Analysis (61-70)	Out-of-band fraud detection & light/heavy categorization logic.
P8	Resilience Ops (71-80)	Auto-restarts, process management (systemd/Gunicorn) & CI/CD.
P9	Resource Governor (81-90)	Real-time CPU/RAM monitoring & search throttling for VPS stability.
P10	Master Release (91-100)	Final stress audits, production snapshots, and documentation.
📦 Task 1: The Nexus State-Graph Bootstrapper
Objective: Replace the current "lifespan" with a deterministic State-Graph that handles the Start/Stop protocols for the VPS.

Subtasks:

1.1: Define 

SystemState
 (OFFLINE, BOOTING, READY, DEGRADED, HALTED) in core/nexus/state.py.
1.2: Create the NexusNode protocol (every service must implement on_start() and on_stop()).
1.3: Implement DependencyResolver to ensure DB starts before Scrapers.
1.4: Create NexusBootstrapper using asyncio.TaskGroup for parallel (but ordered) node startup.
1.5: Implement "The Health Gate": If a node fails 3 boot attempts, the system enters SAFE_MODE.
1.6: Design the Graceful Stop Protocol: Flush Ledger and close DB pools in reverse order.
1.7: Implement system_monitor.py light integration to watch boot-up memory spikes.
1.8: Create tests/verify_boot_sequence.py (Mocking all services to test the graph).
1.9: Create tests/stress_shutdown.py (Simulate SIGTERM to ensure no data loss in ledger).
1.10: Integrate Task 1 into 

app.py
 as the primary lifecycle engine.
📦 Task 2: VPS Security Protocol (DevOps-as-Code)
Objective: Since the VPS is unmanaged, we build the security "Lightly" into our backend.

Subtasks:

2.1: Implement NexusFirewall controller (Wrapper for ufw or iptables rules).
2.2: Script to verify SSH port hardening and disable root login.
2.3: Implement Fail2Ban monitor script that reads auth.log and updates the Nexus blacklist.
2.4: Protocol for "Nexus Fingerprint Isolation": Separate local storage for sensitive keys.
2.5: Define SSL/TLS Protocol (Let's Encrypt automation via certbot integration).
2.6: Design "Port Knocking" logic for high-intensity administration routes.
2.7: Implement OSConsistencyCheck to ensure VPS packages are patched.
2.8: Create tests/verify_firewall.py (Simulate port scans and verify blocks).
2.9: Create tests/verify_ssh_integrity.py (Check for suspicious login attempts).
2.10: Integrate into the Bootstrapper as a P0 Security Node.
I will now create the Task 100 Architectural Registry as an artifact to track our progress across the entire journey.

Step 101: Creating the Nexus-100 Architectural Registry
I'll start by implementing Task 1 (The Spine). We are going to build this with "Zero-Gaps" integrity.

IMPORTANT

I am now switching to DevOps/Architect mode. I will avoid refactoring your current code where it works, but I will wrap it in these new high-level "Protocols".

Subtask 1.1 - 1.5: Implementing the Nexus Bootstrapper Engine
I will create the core state machine that will govern 

app.py
.

Step 102: Creating the Nexus Core State Machine
I'll create backend/core/nexus/state.py.

(I'll provide the implementation in the next turn once we start Task 1 deeply)

Ready to start? Let's initialize the Nexus-100 Registry first.

[ARTIFACT: nexus_100_registry] Path: file:///C:/Users/Gaurav%20Nagar/.gemini/antigravity/brain/67023d48-dc30-4c59-8d00-4dba448f461b/nexus_100_registry.md

(I will continue to build the first 10 tasks in the registry now)

Shall we proceed to implement Task 1: The Nexus State-Graph Bootstrapper? I will start by building the Dependency Graph so your VPS boot is 100% deterministic. Access the registry artifact below to see the full 100-task roadmap. (I will generate it now).

I am ready. Let's begin the transition to Nexus V3. (Next turn starts the code implementation for Phase 1).

One final question: Are there any specific Hostinger VPS limits (vCPU/RAM) you want me to optimize for? (e.g., 2vCPU / 4GB RAM is common). This will dictate how "light" the analysis layer must be. (1-2 mins)