from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional

from services.agents.kimi_swarm import kimi_swarm

router = APIRouter(prefix="/swarm", tags=["Kimi Swarm"])

class VibeRequest(BaseModel):
    vibe: str

class RefactorRequest(BaseModel):
    target_module: str

class AuditRequest(BaseModel):
    target_code: str

@router.get("/status")
async def get_swarm_status():
    """Returns the current status of the 300-agent Kimi Swarm."""
    try:
        return kimi_swarm.get_hive_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute-vibe")
async def execute_vibe(req: VibeRequest, background_tasks: BackgroundTasks):
    """
    Initiates the Autonomous Software Factory workflow.
    Executes the 'Vibe-to-Code' pipeline asynchronously.
    """
    try:
        # We run this in the background since it's a massive multi-agent process
        background_tasks.add_task(kimi_swarm.execute_vibe_pipeline, req.vibe)
        return {
            "status": "accepted",
            "message": f"Vibe-to-Code pipeline initiated for: '{req.vibe}'",
            "pipeline": "Architect -> Parallel Execution -> QA & Security Hive"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refactor-legacy")
async def refactor_legacy(req: RefactorRequest, background_tasks: BackgroundTasks):
    """
    Triggers the Legacy Refactor Module (LRM) for a specific target module.
    """
    try:
        background_tasks.add_task(kimi_swarm.run_legacy_refactor, req.target_module)
        return {
            "status": "accepted",
            "message": f"Legacy refactor initiated for module: '{req.target_module}'",
            "pipeline": "Legacy Refactor Module"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/safe-execution")
async def safe_execution_audit(req: AuditRequest, background_tasks: BackgroundTasks):
    """
    Triggers the SafeExecution Sandbox on the target code.
    """
    try:
        background_tasks.add_task(kimi_swarm.run_safe_execution_audit, req.target_code)
        return {
            "status": "accepted",
            "message": "Code submitted to SafeExecution Sandbox for security auditing.",
            "pipeline": "QA & Security Hive"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
