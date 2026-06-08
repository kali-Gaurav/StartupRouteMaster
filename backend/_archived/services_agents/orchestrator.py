"""
Agent Orchestrator — The Swarm Commander
==========================================
Central registry and execution coordinator for all business agents.
Handles scheduling, priority queuing, concurrent execution, and
provides the unified API for the frontend dashboard.
"""
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from services.agents.base_agent import BaseAgent, AgentStatus

logger = logging.getLogger("agent.orchestrator")


class AgentOrchestrator:
    """
    Master control plane for the RouteMaster Agent Swarm.
    
    Responsibilities:
    - Register/deregister agents
    - Execute agents individually or in coordinated workflows
    - Schedule recurring agent tasks
    - Provide aggregate telemetry
    - Manage agent lifecycle (pause, resume, reset)
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._categories: Dict[str, List[str]] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}
        self._boot_time = datetime.now(timezone.utc)
        self._is_running = False

    # --- Registration ---

    def register(self, agent: BaseAgent) -> None:
        """Register an agent with the swarm."""
        agent_name = getattr(agent, "name", agent.__class__.__name__)
        agent_category = getattr(agent, "category", "general")
        
        if not hasattr(agent, "name"):
            agent.name = agent_name
        if not hasattr(agent, "category"):
            agent.category = agent_category
            
        self._agents[agent_name] = agent
        if agent_category not in self._categories:
            self._categories[agent_category] = []
        if agent_name not in self._categories[agent_category]:
            self._categories[agent_category].append(agent_name)
        logger.info(f"[Orchestrator] Registered: {agent_name} ({agent_category})")

    def deregister(self, agent_name: str) -> bool:
        if agent_name in self._agents:
            agent = self._agents.pop(agent_name)
            cat = agent.category
            if cat in self._categories and agent_name in self._categories[cat]:
                self._categories[cat].remove(agent_name)
            return True
        return False

    # --- Boot ---

    async def boot_all(self) -> Dict[str, str]:
        """Initialize all registered agents."""
        results = {}
        for name, agent in self._agents.items():
            try:
                if hasattr(agent, "initialize"):
                    await agent.initialize()
                results[name] = "initialized"
            except Exception as e:
                results[name] = f"init_failed: {e}"
                logger.error(f"[Orchestrator] Failed to init {name}: {e}")
        
        # Start auto-scheduled agents
        for name, agent in self._agents.items():
            interval = getattr(agent, "auto_schedule_interval", None)
            enabled = getattr(agent, "_is_enabled", True)
            if interval and enabled:
                self._start_scheduled(name, interval)
        
        self._is_running = True
        
        # Start Watchdog
        asyncio.create_task(self._run_watchdog())
        
        logger.info(f"[Orchestrator] Swarm booted: {len(self._agents)} agents online")
        return results

    async def _run_watchdog(self):
        """[Self-Healing] Periodically verifies that all scheduled agents are actually running."""
        while self._is_running:
            await asyncio.sleep(60)
            for name, agent in self._agents.items():
                interval = getattr(agent, "auto_schedule_interval", None)
                enabled = getattr(agent, "_is_enabled", True)
                if interval and enabled:
                    task = self._scheduled_tasks.get(name)
                    if not task or task.done():
                        # [Task 19.3] Detected Dead Agent Task: Recovery Pulse
                        logger.warning(f"🚨 [WATCHDOG] Agent {name} task found DEAD. Restarting...")
                        self._start_scheduled(name, interval)

    async def shutdown_all(self) -> None:
        """Graceful shutdown of all agents."""
        # Cancel scheduled tasks
        for task_name, task in self._scheduled_tasks.items():
            task.cancel()
        self._scheduled_tasks.clear()

        for name, agent in self._agents.items():
            try:
                await agent.shutdown()
            except Exception as e:
                logger.error(f"[Orchestrator] Shutdown error for {name}: {e}")
        
        self._is_running = False
        logger.info("[Orchestrator] All agents shut down")

    # --- Execution ---

    async def run_agent(self, agent_name: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a single agent by name."""
        agent = self._agents.get(agent_name)
        if not agent:
            return {"status": "error", "summary": f"Agent '{agent_name}' not found"}
        
        if not agent._is_enabled:
            return {"status": "error", "summary": f"Agent '{agent_name}' is disabled"}

        result = await agent.run(context)
        
        # Record execution
        record = {
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": result.get("status", "unknown"),
            "duration_ms": result.get("duration_ms", 0),
            "summary": result.get("summary", "")
        }
        self._execution_history.append(record)
        if len(self._execution_history) > 500:
            self._execution_history = self._execution_history[-500:]

        return result

    async def run_category(self, category: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute all agents in a category concurrently."""
        agent_names = self._categories.get(category, [])
        if not agent_names:
            return {"status": "error", "summary": f"No agents in category '{category}'"}

        tasks = [self.run_agent(name, context) for name in agent_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "status": "success",
            "category": category,
            "results": {
                name: (r if isinstance(r, dict) else {"status": "error", "summary": str(r)})
                for name, r in zip(agent_names, results)
            }
        }

    async def run_all(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute every enabled agent. Use with caution."""
        enabled = [n for n, a in self._agents.items() if a._is_enabled]
        tasks = [self.run_agent(name, context) for name in enabled]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            "status": "success",
            "total": len(enabled),
            "results": {
                name: (r if isinstance(r, dict) else {"status": "error", "summary": str(r)})
                for name, r in zip(enabled, results)
            }
        }

    async def execute_all(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Alias for run_all for backwards compatibility."""
        return await self.run_all(context)

    # --- Scheduling ---

    def _start_scheduled(self, agent_name: str, interval: float):
        """Create a recurring background task for an agent."""
        async def _loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    await self.run_agent(agent_name)
                except Exception as e:
                    logger.error(f"[Scheduler] {agent_name} failed: {e}")
        
        task = asyncio.create_task(_loop())
        self._scheduled_tasks[agent_name] = task

    # --- Agent Control ---

    def pause_agent(self, agent_name: str) -> bool:
        agent = self._agents.get(agent_name)
        if agent:
            agent._is_enabled = False
            agent.status = AgentStatus.PAUSED
            if agent_name in self._scheduled_tasks:
                self._scheduled_tasks[agent_name].cancel()
                del self._scheduled_tasks[agent_name]
            return True
        return False

    def resume_agent(self, agent_name: str) -> bool:
        agent = self._agents.get(agent_name)
        if agent:
            agent._is_enabled = True
            agent.status = AgentStatus.IDLE
            if agent.auto_schedule_interval:
                self._start_scheduled(agent_name, agent.auto_schedule_interval)
            return True
        return False

    def reset_agent(self, agent_name: str) -> bool:
        agent = self._agents.get(agent_name)
        if agent:
            from services.agents.base_agent import AgentMetrics
            agent.metrics = AgentMetrics()
            agent._event_log.clear()
            agent.status = AgentStatus.IDLE
            return True
        return False

    # --- Telemetry ---

    def get_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        agent = self._agents.get(agent_name)
        if not agent:
            return None
        if hasattr(agent, "to_dict"):
            return agent.to_dict()
        return {
            "name": getattr(agent, "name", agent.__class__.__name__),
            "category": getattr(agent, "category", "unknown"),
            "status": getattr(agent, "status", "active"),
            "is_enabled": getattr(agent, "is_enabled", True),
            "last_run": getattr(agent, "last_run", None),
            "auto_schedule_interval": getattr(agent, "auto_schedule_interval", None)
        }

    def get_all_agents(self) -> List[Dict[str, Any]]:
        results = []
        for agent in self._agents.values():
            if hasattr(agent, "to_dict"):
                results.append(agent.to_dict())
            else:
                results.append({
                    "name": getattr(agent, "name", agent.__class__.__name__),
                    "category": getattr(agent, "category", "unknown"),
                    "status": getattr(agent, "status", "active"),
                })
        return results

    def get_agents_by_category(self, category: str) -> List[Dict[str, Any]]:
        names = self._categories.get(category, [])
        results = []
        for n in names:
            if n in self._agents:
                agent = self._agents[n]
                if hasattr(agent, "to_dict"):
                    results.append(agent.to_dict())
                else:
                    results.append({"name": n, "category": category})
        return results

    def get_categories(self) -> Dict[str, int]:
        return {cat: len(names) for cat, names in self._categories.items()}

    def get_agent_events(self, agent_name: str, limit: int = 20) -> List[Dict]:
        agent = self._agents.get(agent_name)
        return agent.get_recent_events(limit) if agent else []

    def get_execution_history(self, limit: int = 50) -> List[Dict]:
        return list(reversed(self._execution_history[-limit:]))

    def get_swarm_status(self) -> Dict[str, Any]:
        total = len(self._agents)
        enabled_agents = [a for a in self._agents.values() if a._is_enabled]
        running = sum(1 for a in enabled_agents if a.status == AgentStatus.RUNNING)
        failed = sum(1 for a in enabled_agents if a.status == AgentStatus.FAILED)
        idle = sum(1 for a in enabled_agents if a.status in (AgentStatus.IDLE, AgentStatus.SUCCESS))
        
        total_execs = sum(a.metrics.total_executions for a in self._agents.values())
        total_success = sum(a.metrics.successful_executions for a in self._agents.values())

        return {
            "total_agents": total,
            "enabled": len(enabled_agents),
            "running": running,
            "idle": idle,
            "failed": failed,
            "paused": total - len(enabled_agents),
            "categories": self.get_categories(),
            "total_executions": total_execs,
            "success_rate": round((total_success / total_execs * 100) if total_execs else 100, 1),
            "uptime_seconds": (datetime.now(timezone.utc) - self._boot_time).total_seconds(),
            "is_running": self._is_running,
        }


# --- Singleton ---
swarm = AgentOrchestrator()
