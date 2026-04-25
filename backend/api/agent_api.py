"""
Agent Orchestration API Endpoints

Provides REST API for:
- Executing multi-agent workflows
- Managing workflows
- Monitoring agent performance
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
from datetime import datetime
from pydantic import BaseModel

from database.session import get_db
from services.agent.orchestrator import get_agent_orchestrator, WorkflowDefinition

router = APIRouter(prefix="/api/agents", tags=["Agents"])


class WorkflowExecuteRequest(BaseModel):
    """Request to execute a workflow"""
    workflow_id: str
    context: Dict[str, Any]


class WorkflowResponse(BaseModel):
    """Workflow execution response"""
    workflow_id: str
    status: str
    output: Dict[str, Any] = {}
    duration_ms: float = 0.0
    error: str = None


class WorkflowListResponse(BaseModel):
    """List of available workflows"""
    workflows: List[Dict[str, Any]]


class WorkflowStatusResponse(BaseModel):
    """Workflow status response"""
    id: str
    name: str
    description: str
    task_count: int
    agents: List[str]


@router.post("/execute", response_model=WorkflowResponse)
async def execute_workflow(
    request: WorkflowExecuteRequest,
    db=Depends(get_db)
):
    """
    Execute a multi-agent workflow.
    
    The workflow will:
    1. Initialize required agents
    2. Execute tasks in sequence/parallel
    3. Handle failures and retries
    4. Return results
    
    Example:
    ```json
    {
        "workflow_id": "booking_workflow",
        "context": {
            "source": "NDLS",
            "destination": "BCT",
            "date": "2024-12-01",
            "passengers": 2,
            "fare": 500
        }
    }
    ```
    """
    try:
        orchestrator = get_agent_orchestrator()
        
        # Initialize agents if needed
        await orchestrator.initialize_all()
        
        # Execute workflow
        result = await orchestrator.execute_workflow(
            workflow_id=request.workflow_id,
            context=request.context
        )
        
        return WorkflowResponse(
            workflow_id=result.workflow_id,
            status=result.status.value,
            output=result.output,
            duration_ms=result.duration_ms,
            error=result.error
        )
        
    except Exception as e:
        logger.error(f"Workflow execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows():
    """
    List all available workflows.
    
    Returns:
    - Workflow ID and name
    - Description
    - Number of tasks
    """
    try:
        orchestrator = get_agent_orchestrator()
        workflows = orchestrator.list_workflows()
        
        return WorkflowListResponse(workflows=workflows)
        
    except Exception as e:
        logger.error(f"List workflows error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/workflows/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str
):
    """
    Get status of a specific workflow.
    
    Returns:
    - Workflow definition
    - Required agents
    - Task count
    """
    try:
        orchestrator = get_agent_orchestrator()
        status = orchestrator.get_workflow_status(workflow_id)
        
        if "error" in status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=status["error"]
            )
        
        return WorkflowStatusResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get workflow status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/agents")
async def list_agents():
    """
    List all registered agents.
    
    Returns:
    - Agent names and types
    - Current status
    """
    try:
        orchestrator = get_agent_orchestrator()
        
        agents = []
        for name, agent in orchestrator.agents.items():
            agents.append({
                "name": name,
                "type": type(agent).__name__,
                "status": agent.status.value
            })
        
        return {
            "agents": agents,
            "total_count": len(agents)
        }
        
    except Exception as e:
        logger.error(f"List agents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agents/{agent_name}/initialize")
async def initialize_agent(
    agent_name: str
):
    """
    Initialize a specific agent.
    
    Useful for pre-warming agents before workflow execution.
    """
    try:
        orchestrator = get_agent_orchestrator()
        
        agent = orchestrator.agents.get(agent_name)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent not found: {agent_name}"
            )
        
        result = await agent.initialize()
        
        return {
            "agent": agent_name,
            "initialized": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Initialize agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agents/{agent_name}/shutdown")
async def shutdown_agent(
    agent_name: str
):
    """
    Shutdown a specific agent.
    
    Releases resources held by the agent.
    """
    try:
        orchestrator = get_agent_orchestrator()
        
        agent = orchestrator.agents.get(agent_name)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent not found: {agent_name}"
            )
        
        await agent.shutdown()
        
        return {
            "agent": agent_name,
            "status": "shutdown"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Shutdown agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/shutdown-all")
async def shutdown_all_agents():
    """
    Shutdown all agents.
    
    Cleanup all agent resources.
    """
    try:
        orchestrator = get_agent_orchestrator()
        await orchestrator.shutdown_all()
        
        return {
            "status": "all agents shutdown"
        }
        
    except Exception as e:
        logger.error(f"Shutdown all error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Import logger at module level
import logging
logger = logging.getLogger(__name__)