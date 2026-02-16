"""
Agent State Manager - Manages RouteMaster Agent states for observability and control.

States:
- IDLE: Waiting for commands
- PLANNING: Analyzing task requirements
- NAVIGATING: Browsing and interacting with websites
- EXTRACTING: Pulling data from pages
- VALIDATING: Checking data quality and consistency
- STORING: Writing to database and data lake
- LEARNING: Updating memory and models
- ERROR_RECOVERY: Handling failures and retries
"""

from enum import Enum
from datetime import datetime
import json
import os
from typing import Dict, Any, Optional

from routemaster_agent.metrics import RMA_AGENT_STATE


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    NAVIGATING = "navigating"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    STORING = "storing"
    LEARNING = "learning"
    ERROR_RECOVERY = "error_recovery"


class AgentStateManager:
    def __init__(self):
        self.current_state = AgentState.IDLE
        self.state_history = []
        self.state_start_time = datetime.utcnow()
        self.task_id = None
        self.metadata = {}

    def transition_to(self, new_state: AgentState, task_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Transition to a new state, logging the change."""
        now = datetime.utcnow()
        duration = (now - self.state_start_time).total_seconds()

        # Log previous state
        self.state_history.append({
            'state': self.current_state.value,
            'start_time': self.state_start_time.isoformat(),
            'duration_seconds': duration,
            'task_id': self.task_id,
            'metadata': self.metadata
        })

        # Update to new state
        self.current_state = new_state
        self.state_start_time = now
        self.task_id = task_id or self.task_id
        self.metadata = metadata or {}

        # Update Prometheus metric
        try:
            RMA_AGENT_STATE.state(self.current_state.value)
        except Exception:
            pass

        print(f"[STATE] Transitioned to {self.current_state.value} for task {self.task_id}")

    def get_current_state(self) -> Dict[str, Any]:
        """Get current state info."""
        return {
            'state': self.current_state.value,
            'since': self.state_start_time.isoformat(),
            'task_id': self.task_id,
            'metadata': self.metadata
        }

    def get_state_history(self, limit: int = 10) -> list:
        """Get recent state transitions."""
        return self.state_history[-limit:]

    def is_in_error_recovery(self) -> bool:
        """Check if agent is in error recovery mode."""
        return self.current_state == AgentState.ERROR_RECOVERY

    def can_accept_commands(self) -> bool:
        """Check if agent can accept new commands (not in critical states)."""
        return self.current_state in [AgentState.IDLE, AgentState.LEARNING]

    def save_state_to_file(self, path: str = "memory/agent_state.json"):
        """Persist current state for recovery."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state_data = {
            'current_state': self.current_state.value,
            'state_start_time': self.state_start_time.isoformat(),
            'task_id': self.task_id,
            'metadata': self.metadata,
            'history': self.state_history[-50:]
        }
        with open(path, 'w') as f:
            json.dump(state_data, f, indent=2)

    def load_state_from_file(self, path: str = "memory/agent_state.json"):
        """Load state from file on startup."""
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    state_data = json.load(f)
                self.current_state = AgentState(state_data['current_state'])
                self.state_start_time = datetime.fromisoformat(state_data['state_start_time'])
                self.task_id = state_data.get('task_id')
                self.metadata = state_data.get('metadata', {})
                self.state_history = state_data.get('history', [])
            except Exception as e:
                print(f"Failed to load agent state: {e}")


# Global instance
agent_state_manager = AgentStateManager()
