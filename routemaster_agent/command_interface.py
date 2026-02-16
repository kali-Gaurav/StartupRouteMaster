"""
Command Interface - REST API and WebSocket for Grafana/dashboard commands.

Allows external systems to send commands to the agent.
"""

from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import json
from datetime import datetime

from .ai.reasoning_controller import ReasoningController
from .ai.planner import TaskPlanner
from .ai.agent_state_manager import agent_state_manager
from routemaster_agent.metrics import RMA_COMMAND_REQUESTS_TOTAL, RMA_COMMAND_SUCCESS_TOTAL


class CommandRequest(BaseModel):
    command: str
    parameters: Dict[str, Any] = {}
    priority: Optional[str] = "medium"
    timeout_seconds: Optional[int] = 300
    callback_url: Optional[str] = None


class CommandResponse(BaseModel):
    command_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None


class CommandInterface:
    def __init__(self, app: FastAPI):
        self.app = app
        self.controller = ReasoningController()
        self.planner = TaskPlanner()
        self.active_commands = {}
        self.command_history = []
        self.websocket_clients = set()

        self._setup_routes()

    def _setup_routes(self):
        @self.app.post("/api/agent/execute-command")
        async def execute_command(request: CommandRequest, background_tasks: BackgroundTasks):
            """Execute a command asynchronously."""
            RMA_COMMAND_REQUESTS_TOTAL.inc()

            try:
                if request.command not in self.planner.get_available_task_types():
                    raise HTTPException(status_code=400, detail=f"Unknown command: {request.command}")

                task_def = {
                    'id': f"cmd_{request.command}_{datetime.utcnow().timestamp()}",
                    'type': request.command,
                    'parameters': request.parameters,
                    'priority': request.priority,
                    'timeout': request.timeout_seconds
                }

                plan = await self.planner.plan_task(task_def)

                background_tasks.add_task(self._execute_command_async, task_def, plan, request.callback_url)

                return JSONResponse({
                    'command_id': task_def['id'],
                    'status': 'accepted',
                    'estimated_duration': plan.get('estimated_duration', 60),
                    'message': f'Command {request.command} accepted for execution'
                })

            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={'error': str(e), 'status': 'failed'}
                )

        @self.app.get("/api/agent/command-status/{command_id}")
        async def get_command_status(command_id: str):
            """Get status of a running/completed command."""
            if command_id in self.active_commands:
                return JSONResponse({
                    'command_id': command_id,
                    'status': 'running',
                    'progress': agent_state_manager.get_current_state()
                })

            for cmd in self.command_history[-50:]:
                if cmd['id'] == command_id:
                    return JSONResponse(cmd)

            raise HTTPException(status_code=404, detail="Command not found")

        @self.app.get("/api/agent/available-commands")
        async def get_available_commands():
            """List available commands."""
            commands = self.planner.get_available_task_types()
            return JSONResponse({
                'commands': commands,
                'examples': {
                    'update_train_schedule': {'train_number': '12951', 'date': 'today'},
                    'collect_live_status': {'train_number': '12951'},
                    'check_seat_availability': {'train_number': '12951', 'date': '2024-01-15', 'source': 'NDLS', 'destination': 'BCT'},
                    'update_all_trains': {},
                    'monthly_maintenance': {}
                }
            })

        @self.app.get("/api/agent/status")
        async def get_agent_status():
            """Get current agent status."""
            return JSONResponse({
                'state': agent_state_manager.get_current_state(),
                'active_commands': list(self.active_commands.keys()),
                'can_accept_commands': agent_state_manager.can_accept_commands()
            })

        @self.app.websocket("/ws/agent")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket for real-time agent updates."""
            await websocket.accept()
            self.websocket_clients.add(websocket)

            try:
                while True:
                    status = {
                        'type': 'status_update',
                        'data': agent_state_manager.get_current_state(),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    await websocket.send_json(status)
                    await asyncio.sleep(5)
            except Exception:
                pass
            finally:
                self.websocket_clients.remove(websocket)

    async def _execute_command_async(self, task_def: Dict[str, Any], plan: Dict[str, Any], callback_url: Optional[str]):
        """Execute command in background."""
        command_id = task_def['id']
        self.active_commands[command_id] = task_def

        try:
            result = await self.controller.execute_task(task_def)

            completed_command = {
                'id': command_id,
                'status': 'completed',
                'result': result,
                'completed_at': datetime.utcnow().isoformat(),
                'plan': plan
            }

            RMA_COMMAND_SUCCESS_TOTAL.inc()

        except Exception as e:
            completed_command = {
                'id': command_id,
                'status': 'failed',
                'error': str(e),
                'failed_at': datetime.utcnow().isoformat()
            }

        self.command_history.append(completed_command)
        if command_id in self.active_commands:
            del self.active_commands[command_id]

        if callback_url:
            await self._send_callback(callback_url, completed_command)

        await self._broadcast_to_websockets(completed_command)

    async def _send_callback(self, url: str, data: Dict[str, Any]):
        """Send result to callback URL."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=data)
        except Exception as e:
            print(f"Callback failed: {e}")

    async def _broadcast_to_websockets(self, data: Dict[str, Any]):
        """Broadcast message to all WebSocket clients."""
        message = {
            'type': 'command_complete',
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }

        disconnected = set()
        for client in self.websocket_clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.add(client)

        self.websocket_clients -= disconnected

    async def initialize(self):
        """Initialize the command interface."""
        await self.controller.initialize()

    async def shutdown(self):
        """Shutdown the command interface."""
        await self.controller.cleanup()
