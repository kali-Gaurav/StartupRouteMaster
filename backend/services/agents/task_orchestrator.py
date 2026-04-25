"""
Task Orchestrator Agent
=======================
Receives high-level tasks and delegates to appropriate agents.
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from services.agents.base_agent import BaseAgent

logger = logging.getLogger("agent.task_orchestrator")

class TaskOrchestrator(BaseAgent):
    """Orchestrates tasks across all agents"""
    
    name = "TaskOrchestrator"
    description = "Delegates tasks to appropriate specialized agents"
    category = "orchestration"
    icon = "🎯"
    color = "#9B59B6"
    
    def __init__(self):
        super().__init__()
        self.agent_registry = {}
    
    async def on_start(self):
        """Initialize task orchestrator"""
        logger.info("🤖 TaskOrchestrator starting...")
        # Will be populated by register_agent
        return True
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the orchestrator"""
        self.agent_registry[agent.name] = agent
        logger.debug(f"Registered agent: {agent.name} ({agent.category})")
    
    def find_agent_for_task(self, task_description: str) -> Optional[BaseAgent]:
        """Find the best agent for a given task"""
        task_lower = task_description.lower()
        
        # Task to agent mapping
        task_mapping = {
            # Database tasks
            "database": ["DatabaseAgent", "SystemHealthAgent"],
            "migration": ["DatabaseAgent"],
            "cleanup": ["DatabaseAgent"],
            "backup": ["DatabaseAgent"],
            
            # Monitoring tasks
            "monitor": ["SystemHealthAgent", "CacheAgent"],
            "health": ["SystemHealthAgent"],
            "performance": ["SystemHealthAgent", "CacheAgent"],
            
            # Deployment tasks
            "deploy": ["DeploymentAgent"],
            "production": ["DeploymentAgent", "SecurityAgent"],
            "vps": ["DeploymentAgent"],
            
            # Security tasks
            "security": ["SecurityAgent", "GuardianAgent"],
            "auth": ["SecurityAgent"],
            "permission": ["SecurityAgent"],
            
            # Financial tasks
            "payment": ["RevenueAgent", "SettlementAgent"],
            "revenue": ["RevenueAgent"],
            "fraud": ["FraudDetectionAgent"],
            "reconciliation": ["ReconciliationAgent"],
            
            # Booking tasks
            "booking": ["BookingOpsAgent", "InventoryAgent"],
            "inventory": ["InventoryAgent"],
            "seat": ["SeatOptimizationAgent", "InventoryAgent"],
            
            # Support tasks
            "support": ["SupportTriageAgent"],
            "notification": ["NotificationAgent"],
            "feedback": ["FeedbackAnalyzerAgent"],
            
            # Analytics tasks
            "analytics": ["PredictiveAnalyticsAgent", "ReportGeneratorAgent"],
            "report": ["ReportGeneratorAgent"],
            "predict": ["PredictiveAnalyticsAgent"],
            
            # Growth tasks
            "growth": ["UserGrowthAgent", "EngagementAgent"],
            "user": ["UserGrowthAgent"],
            "campaign": ["CampaignAgent"],
            
            # Compliance tasks
            "compliance": ["ComplianceAgent"],
            "tax": ["TaxEngineAgent"],
        }
        
        # Find matching agents
        matching_agents = []
        for keyword, agent_names in task_mapping.items():
            if keyword in task_lower:
                for agent_name in agent_names:
                    if agent_name in self.agent_registry:
                        matching_agents.append(self.agent_registry[agent_name])
        
        # Return the first matching agent
        return matching_agents[0] if matching_agents else None
    
    async def execute_task(self, task_description: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a task by delegating to the appropriate agent
        
        Args:
            task_description: Description of the task to perform
            **kwargs: Additional parameters for the task
            
        Returns:
            Dictionary with task execution results
        """
        logger.info(f"🎯 Task received: {task_description}")
        
        # Find appropriate agent
        agent = self.find_agent_for_task(task_description)
        
        if not agent:
            logger.warning(f"⚠️ No agent found for task: {task_description}")
            return {
                "success": False,
                "error": f"No agent found for task: {task_description}",
                "task": task_description
            }
        
        logger.info(f"🤖 Delegating to {agent.name}...")
        
        try:
            # Execute task through the agent
            result = await agent.execute(task_description, **kwargs)
            
            return {
                "success": True,
                "agent": agent.name,
                "task": task_description,
                "result": result,
                "timestamp": "2026-04-20T19:30:00Z"
            }
            
        except Exception as e:
            logger.error(f"❌ Task execution failed: {e}")
            return {
                "success": False,
                "agent": agent.name,
                "task": task_description,
                "error": str(e),
                "timestamp": "2026-04-20T19:30:00Z"
            }
    
    async def execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """Base agent execute method"""
        return await self.execute_task(task, **kwargs)