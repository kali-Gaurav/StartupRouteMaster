"""
Agent Swarm API Router
========================
Exposes the complete agent swarm to the frontend via REST API.
Provides endpoints for agent management, execution, and telemetry.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from services.agents.orchestrator import swarm

logger = logging.getLogger("api.agents")

router = APIRouter(prefix="/agents", tags=["Agent Swarm"])


# ─── SWARM-LEVEL ───

@router.get("/swarm/status")
async def get_swarm_status():
    """Get aggregate status of the entire agent swarm."""
    return swarm.get_swarm_status()


@router.get("/swarm/agents")
async def list_all_agents(category: Optional[str] = Query(None)):
    """List all registered agents, optionally filtered by category."""
    if category:
        return swarm.get_agents_by_category(category)
    return swarm.get_all_agents()


@router.get("/swarm/categories")
async def list_categories():
    """List all agent categories with counts."""
    return swarm.get_categories()


@router.get("/swarm/history")
async def get_execution_history(limit: int = Query(50, le=200)):
    """Get recent execution history across all agents."""
    return swarm.get_execution_history(limit)


# ─── AGENT-LEVEL ───

@router.get("/agent/{agent_name}")
async def get_agent_details(agent_name: str):
    """Get detailed information about a specific agent."""
    agent = swarm.get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return agent


@router.get("/agent/{agent_name}/events")
async def get_agent_events(agent_name: str, limit: int = Query(20, le=100)):
    """Get recent event log for a specific agent."""
    events = swarm.get_agent_events(agent_name, limit)
    if events is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return events


@router.post("/agent/{agent_name}/run")
async def run_agent(agent_name: str):
    """Manually trigger execution of a specific agent."""
    agent = swarm.get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    result = await swarm.run_agent(agent_name)
    return result


@router.post("/agent/{agent_name}/pause")
async def pause_agent(agent_name: str):
    """Pause a specific agent (disables execution and scheduling)."""
    success = swarm.pause_agent(agent_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return {"status": "paused", "agent": agent_name}


@router.post("/agent/{agent_name}/resume")
async def resume_agent(agent_name: str):
    """Resume a paused agent."""
    success = swarm.resume_agent(agent_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return {"status": "resumed", "agent": agent_name}


@router.post("/agent/{agent_name}/reset")
async def reset_agent(agent_name: str):
    """Reset an agent's metrics and event log."""
    success = swarm.reset_agent(agent_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return {"status": "reset", "agent": agent_name}


# ─── CATEGORY-LEVEL ───

@router.post("/category/{category}/run")
async def run_category(category: str):
    """Execute all agents in a specific category."""
    result = await swarm.run_category(category)
    return result


# ─── BULK OPERATIONS ───

@router.post("/swarm/run-all")
async def run_all_agents():
    """Execute ALL enabled agents. Use with caution."""
    result = await swarm.run_all()
    return result


@router.post("/swarm/boot")
async def boot_swarm():
    """Initialize all agents (called during app startup, also can be manually triggered)."""
    result = await swarm.boot_all()
    return {"status": "booted", "results": result}
