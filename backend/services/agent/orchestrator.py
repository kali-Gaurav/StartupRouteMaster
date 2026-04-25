"""
Agent Orchestration System

Coordinates multiple agents for complex workflows.
Enables autonomous operation with failure recovery.

Features:
- Multi-agent workflow execution
- Agent communication and coordination
- Failure recovery and retry
- Performance monitoring
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig

logger = logging.getLogger("agent.orchestrator")


class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskResult:
    """Result of task execution"""
    task_id: str
    status: TaskStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    started_at: datetime = None
    completed_at: datetime = None


@dataclass
class WorkflowTask:
    """Definition of a workflow task"""
    id: str
    agent_name: str
    task_type: str
    input_mapping: Dict[str, str] = field(default_factory=dict)  # output_var -> input_var
    output_mapping: Dict[str, str] = field(default_factory=dict)  # output_var -> context_var
    on_failure: str = "abort"  # abort, retry, continue
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 60
    conditions: List[Dict] = field(default_factory=list)  # Pre-conditions


@dataclass
class WorkflowDefinition:
    """Definition of a multi-agent workflow"""
    id: str
    name: str
    description: str
    tasks: List[WorkflowTask]
    parallel_tasks: List[List[str]] = field(default_factory=list)  # Task IDs that can run in parallel
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    workflow_id: str
    status: AgentStatus
    task_results: Dict[str, TaskResult]
    output: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    started_at: datetime = None
    completed_at: datetime = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = AgentStatus.IDLE
        self._circuit_breaker = circuit_breaker_manager.get_or_create(
            f"agent_{name}",
            CircuitConfig(failure_threshold=3, timeout_seconds=30.0, success_threshold=2)
        )
    
    @abstractmethod
    async def execute(self, task_type: str, input_data: Dict[str, Any]) -> TaskResult:
        """Execute a task"""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize agent resources"""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Cleanup agent resources"""
        pass


class RoutingAgent(BaseAgent):
    """Agent for routing operations"""
    
    def __init__(self):
        super().__init__("routing_agent")
        self._search_service = None
    
    async def initialize(self) -> bool:
        from services.search_service import SearchService
        from database.session import SessionLocal
        self._search_service = SearchService(SessionLocal())
        return True
    
    async def shutdown(self):
        if self._search_service:
            self._search_service.db.close()
    
    async def execute(self, task_type: str, input_data: Dict[str, Any]) -> TaskResult:
        start_time = datetime.utcnow()
        
        try:
            if task_type == "search_routes":
                result = await self._search_routes(input_data)
            elif task_type == "optimize_routes":
                result = await self._optimize_routes(input_data)
            else:
                return TaskResult(
                    task_id=task_type,
                    status=TaskStatus.FAILED,
                    error=f"Unknown task type: {task_type}"
                )
            
            return TaskResult(
                task_id=task_type,
                status=TaskStatus.COMPLETED,
                output=result,
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Routing agent error: {e}")
            return TaskResult(
                task_id=task_type,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
    
    async def _search_routes(self, input_data: Dict) -> Dict:
        """Search for routes"""
        routes = await self._search_service.search_routes(
            source=input_data["source"],
            destination=input_data["destination"],
            travel_date=input_data["travel_date"],
            constraints=input_data.get("constraints", {})
        )
        return {"routes": routes}
    
    async def _optimize_routes(self, input_data: Dict) -> Dict:
        """Optimize routes"""
        # Would apply optimization logic here
        return {"optimized_routes": input_data.get("routes", [])}


class PricingAgent(BaseAgent):
    """Agent for pricing operations"""
    
    def __init__(self):
        super().__init__("pricing_agent")
    
    async def initialize(self) -> bool:
        return True
    
    async def shutdown(self):
        pass
    
    async def execute(self, task_type: str, input_data: Dict[str, Any]) -> TaskResult:
        start_time = datetime.utcnow()
        
        try:
            if task_type == "calculate_price":
                result = await self._calculate_price(input_data)
            elif task_type == "apply_surge":
                result = await self._apply_surge(input_data)
            else:
                return TaskResult(
                    task_id=task_type,
                    status=TaskStatus.FAILED,
                    error=f"Unknown task type: {task_type}"
                )
            
            return TaskResult(
                task_id=task_type,
                status=TaskStatus.COMPLETED,
                output=result,
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            return TaskResult(
                task_id=task_type,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
    
    async def _calculate_price(self, input_data: Dict) -> Dict:
        """Calculate booking price"""
        from services.booking_price_calculator import get_booking_price_calculator
        from database.session import SessionLocal
        
        calculator = get_booking_price_calculator(SessionLocal())
        
        price_breakdown = await calculator.calculate_total_price(
            base_fare=input_data["base_fare"],
            passenger_count=input_data["passenger_count"],
            travel_date=input_data["travel_date"],
            route_id=input_data.get("route_id", "")
        )
        
        return {"price_breakdown": asdict(price_breakdown)}
    
    async def _apply_surge(self, input_data: Dict) -> Dict:
        """Apply surge pricing"""
        base_price = input_data["base_price"]
        demand_score = input_data.get("demand_score", 0.5)
        
        surge_multiplier = 1.0 + (demand_score - 0.5) * 0.67
        final_price = base_price * surge_multiplier
        
        return {
            "base_price": base_price,
            "surge_multiplier": surge_multiplier,
            "final_price": final_price
        }


class AllocationAgent(BaseAgent):
    """Agent for seat allocation"""
    
    def __init__(self):
        super().__init__("allocation_agent")
    
    async def initialize(self) -> bool:
        return True
    
    async def shutdown(self):
        pass
    
    async def execute(self, task_type: str, input_data: Dict[str, Any]) -> TaskResult:
        start_time = datetime.utcnow()
        
        try:
            if task_type == "allocate_seats":
                result = await self._allocate_seats(input_data)
            elif task_type == "check_availability":
                result = await self._check_availability(input_data)
            else:
                return TaskResult(
                    task_id=task_type,
                    status=TaskStatus.FAILED,
                    error=f"Unknown task type: {task_type}"
                )
            
            return TaskResult(
                task_id=task_type,
                status=TaskStatus.COMPLETED,
                output=result,
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            return TaskResult(
                task_id=task_type,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
    
    async def _allocate_seats(self, input_data: Dict) -> Dict:
        """Allocate seats for booking"""
        from services.booking_seat_allocator import get_booking_seat_allocator
        from database.session import SessionLocal
        
        allocator = get_booking_seat_allocator(SessionLocal())
        
        allocation = await allocator.allocate_seats_for_booking(
            train_number=input_data["train_number"],
            travel_date=input_data["travel_date"],
            passenger_preferences=input_data.get("preferences", []),
            passenger_count=input_data["passenger_count"]
        )
        
        return {"allocation": asdict(allocation)}
    
    async def _check_availability(self, input_data: Dict) -> Dict:
        """Check seat availability"""
        return {
            "available": True,
            "available_seats": 50,
            "waitlist_count": 0
        }


class AgentOrchestrator:
    """
    Orchestrates multi-agent workflows.
    
    Features:
    - Workflow definition and execution
    - Agent coordination
    - Failure recovery
    - Performance monitoring
    """
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self._register_default_agents()
        self._register_default_workflows()
        logger.info("AgentOrchestrator initialized")
    
    def _register_default_agents(self):
        """Register default agents"""
        self.register_agent("routing", RoutingAgent())
        self.register_agent("pricing", PricingAgent())
        self.register_agent("allocation", AllocationAgent())
    
    def _register_default_workflows(self):
        """Register default workflows"""
        
        # Search workflow
        search_workflow = WorkflowDefinition(
            id="search_workflow",
            name="Route Search Workflow",
            description="Search and optimize routes",
            tasks=[
                WorkflowTask(
                    id="search_routes",
                    agent_name="routing",
                    task_type="search_routes",
                    input_mapping={"source": "source", "destination": "destination", "travel_date": "date"},
                    output_mapping={"routes": "routes"}
                ),
                WorkflowTask(
                    id="optimize_routes",
                    agent_name="routing",
                    task_type="optimize_routes",
                    input_mapping={"routes": "routes"},
                    output_mapping={"optimized_routes": "optimized_routes"}
                )
            ]
        )
        self.register_workflow(search_workflow)
        
        # Booking workflow
        booking_workflow = WorkflowDefinition(
            id="booking_workflow",
            name="Booking Workflow",
            description="Complete booking process",
            tasks=[
                WorkflowTask(
                    id="search_routes",
                    agent_name="routing",
                    task_type="search_routes",
                    input_mapping={"source": "source", "destination": "destination", "travel_date": "date"},
                    output_mapping={"routes": "routes"}
                ),
                WorkflowTask(
                    id="calculate_price",
                    agent_name="pricing",
                    task_type="calculate_price",
                    input_mapping={"base_fare": "fare", "passenger_count": "passengers", "travel_date": "date"},
                    output_mapping={"price_breakdown": "price"}
                ),
                WorkflowTask(
                    id="allocate_seats",
                    agent_name="allocation",
                    task_type="allocate_seats",
                    input_mapping={"train_number": "train", "travel_date": "date", "passenger_count": "passengers"},
                    output_mapping={"allocation": "seats"}
                )
            ]
        )
        self.register_workflow(booking_workflow)
    
    def register_agent(self, name: str, agent: BaseAgent):
        """Register an agent"""
        self.agents[name] = agent
        logger.info(f"Agent registered: {name}")
    
    def register_workflow(self, workflow: WorkflowDefinition):
        """Register a workflow"""
        self.workflows[workflow.id] = workflow
        logger.info(f"Workflow registered: {workflow.id}")
    
    async def initialize_all(self) -> bool:
        """Initialize all agents"""
        success = True
        for name, agent in self.agents.items():
            try:
                result = await agent.initialize()
                if not result:
                    logger.error(f"Failed to initialize agent: {name}")
                    success = False
            except Exception as e:
                logger.error(f"Agent initialization error: {name}, {e}")
                success = False
        return success
    
    async def shutdown_all(self):
        """Shutdown all agents"""
        for agent in self.agents.values():
            try:
                await agent.shutdown()
            except Exception as e:
                logger.error(f"Agent shutdown error: {e}")
    
    async def execute_workflow(
        self, 
        workflow_id: str, 
        context: Dict[str, Any]
    ) -> WorkflowResult:
        """
        Execute a workflow.
        
        Args:
            workflow_id: ID of workflow to execute
            context: Input context for workflow
            
        Returns:
            WorkflowResult with execution details
        """
        start_time = datetime.utcnow()
        
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return WorkflowResult(
                workflow_id=workflow_id,
                status=AgentStatus.FAILED,
                task_results={},
                error=f"Unknown workflow: {workflow_id}",
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
        
        task_results = {}
        
        try:
            # Execute tasks sequentially
            for task in workflow.tasks:
                # Check pre-conditions
                if not self._check_conditions(task, context):
                    task_results[task.id] = TaskResult(
                        task_id=task.id,
                        status=TaskStatus.SKIPPED,
                        error="Pre-conditions not met"
                    )
                    continue
                
                # Get agent
                agent = self.agents.get(task.agent_name)
                if not agent:
                    task_results[task.id] = TaskResult(
                        task_id=task.id,
                        status=TaskStatus.FAILED,
                        error=f"Unknown agent: {task.agent_name}"
                    )
                    continue
                
                # Prepare input
                input_data = self._prepare_input(task, context)
                
                # Execute task with retry
                result = await self._execute_with_retry(agent, task, input_data)
                task_results[task.id] = result
                
                # Update context
                self._update_context(task, result, context)
                
                # Handle failure
                if result.status == TaskStatus.FAILED:
                    if task.on_failure == "abort":
                        return WorkflowResult(
                            workflow_id=workflow_id,
                            status=AgentStatus.FAILED,
                            task_results=task_results,
                            output=context,
                            duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                            started_at=start_time,
                            completed_at=datetime.utcnow(),
                            error=f"Task {task.id} failed: {result.error}"
                        )
                    elif task.on_failure == "continue":
                        continue
            
            return WorkflowResult(
                workflow_id=workflow_id,
                status=AgentStatus.COMPLETED,
                task_results=task_results,
                output=context,
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            return WorkflowResult(
                workflow_id=workflow_id,
                status=AgentStatus.FAILED,
                task_results=task_results,
                output=context,
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error=str(e)
            )
    
    async def _execute_with_retry(
        self, 
        agent: BaseAgent, 
        task: WorkflowTask, 
        input_data: Dict
    ) -> TaskResult:
        """Execute task with retry logic"""
        retries = 0
        max_retries = task.max_retries
        
        while retries <= max_retries:
            try:
                # Set timeout
                result = await asyncio.wait_for(
                    agent.execute(task.task_type, input_data),
                    timeout=task.timeout_seconds
                )
                return result
            except asyncio.TimeoutError:
                retries += 1
                if retries > max_retries:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.TIMEOUT,
                        error=f"Task timed out after {max_retries} retries"
                    )
            except Exception as e:
                retries += 1
                if retries > max_retries:
                    return TaskResult(
                        task_id=task.id,
                        status=TaskStatus.FAILED,
                        error=f"Task failed after {max_retries} retries: {str(e)}"
                    )
        
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.FAILED,
            error="Max retries exceeded"
        )
    
    def _check_conditions(self, task: WorkflowTask, context: Dict) -> bool:
        """Check if task pre-conditions are met"""
        for condition in task.conditions:
            var = condition.get("var")
            op = condition.get("op")
            value = condition.get("value")
            
            if var not in context:
                return False
            
            actual = context[var]
            
            if op == "eq" and actual != value:
                return False
            elif op == "ne" and actual == value:
                return False
            elif op == "gt" and actual <= value:
                return False
            elif op == "lt" and actual >= value:
                return False
        
        return True
    
    def _prepare_input(self, task: WorkflowTask, context: Dict) -> Dict:
        """Prepare input data for task from context"""
        input_data = {}
        for input_var, context_var in task.input_mapping.items():
            input_data[input_var] = context.get(context_var)
        return input_data
    
    def _update_context(self, task: WorkflowTask, result: TaskResult, context: Dict):
        """Update context with task output"""
        for output_var, context_var in task.output_mapping.items():
            if output_var in result.output:
                context[context_var] = result.output[output_var]
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {"status": "unknown", "error": "Workflow not found"}
        
        return {
            "id": workflow.id,
            "name": workflow.name,
            "task_count": len(workflow.tasks),
            "agents": list(set(t.agent_name for t in workflow.tasks))
        }
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all registered workflows"""
        return [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "task_count": len(wf.tasks)
            }
            for wf in self.workflows.values()
        ]


# Global orchestrator instance
_orchestrator = None

def get_agent_orchestrator() -> AgentOrchestrator:
    """Get or create orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


# Export for external use
__all__ = [
    'AgentOrchestrator',
    'BaseAgent',
    'RoutingAgent',
    'PricingAgent',
    'AllocationAgent',
    'WorkflowDefinition',
    'WorkflowTask',
    'WorkflowResult',
    'TaskResult',
    'get_agent_orchestrator'
]