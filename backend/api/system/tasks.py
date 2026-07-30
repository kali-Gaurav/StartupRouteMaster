"""
Task API endpoints
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

logger = logging.getLogger("routemaster.tasks")

router = APIRouter(prefix="/tasks", tags=["tasks"])

class TaskRequest(BaseModel):
    description: str
    parameters: Optional[Dict[str, Any]] = None

class TaskResponse(BaseModel):
    success: bool
    agent: Optional[str] = None
    task: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str

# Global task orchestrator instance
task_orchestrator = None

def get_task_orchestrator():
    """Get or create task orchestrator instance"""
    global task_orchestrator
    if task_orchestrator is None:
        try:
            from services.agents.task_orchestrator import TaskOrchestrator
            task_orchestrator = TaskOrchestrator()
            
            # Register infrastructure agents
            try:
                from services.agents.database_agent import DatabaseAgent
                task_orchestrator.register_agent(DatabaseAgent())
                logger.info("✅ Registered DatabaseAgent")
            except ImportError as e:
                logger.warning(f"⚠️ DatabaseAgent not available: {e}")
            
            try:
                from services.agents.monitoring_agent import MonitoringAgent
                task_orchestrator.register_agent(MonitoringAgent())
                logger.info("✅ Registered MonitoringAgent")
            except ImportError as e:
                logger.warning(f"⚠️ MonitoringAgent not available: {e}")
            
            try:
                from services.agents.deployment_agent import DeploymentAgent
                task_orchestrator.register_agent(DeploymentAgent())
                logger.info("✅ Registered DeploymentAgent")
            except ImportError as e:
                logger.warning(f"⚠️ DeploymentAgent not available: {e}")
            
            # Register safety agents (NEW)
            try:
                from services.agents.women_safety_agent import WomenSafetyAgent
                task_orchestrator.register_agent(WomenSafetyAgent())
                logger.info("✅ Registered WomenSafetyAgent")
            except ImportError as e:
                logger.warning(f"⚠️ WomenSafetyAgent not available: {e}")
            
            try:
                from services.agents.family_safety_agent import FamilySafetyAgent
                task_orchestrator.register_agent(FamilySafetyAgent())
                logger.info("✅ Registered FamilySafetyAgent")
            except ImportError as e:
                logger.warning(f"⚠️ FamilySafetyAgent not available: {e}")
            
            logger.info(f"✅ Task orchestrator initialized with {len(task_orchestrator.agent_registry)} agents")
        except Exception as e:
            logger.warning(f"⚠️ Task orchestrator initialization failed: {e}")
            task_orchestrator = None
    
    return task_orchestrator

@router.post("/execute", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    """Execute a task through the orchestrator"""
    orchestrator = get_task_orchestrator()
    
    if not orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Task orchestrator not available"
        )
    
    try:
        result = await orchestrator.execute_task(
            request.description,
            **(request.parameters or {})
        )
        
        return TaskResponse(**result)
        
    except Exception as e:
        logger.error(f"❌ Task execution error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Task execution failed: {str(e)}"
        )

@router.get("/agents")
async def list_agents():
    """List available agents"""
    orchestrator = get_task_orchestrator()
    
    if not orchestrator:
        return {"agents": [], "count": 0}
    
    agents = list(orchestrator.agent_registry.keys())
    return {
        "agents": agents,
        "count": len(agents)
    }

@router.get("/health")
async def task_service_health():
    """Check task service health"""
    orchestrator = get_task_orchestrator()
    
    return {
        "status": "operational" if orchestrator else "degraded",
        "orchestrator_available": orchestrator is not None,
        "agent_count": len(orchestrator.agent_registry) if orchestrator else 0
    }
