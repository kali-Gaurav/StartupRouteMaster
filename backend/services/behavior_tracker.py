import time
import asyncio
import logging
from typing import Dict, List, Optional
from collections import deque

logger = logging.getLogger("behavior-tracker")

class UserBehaviorState:
    """Tracks a sliding window of a single user's actions."""
    def __init__(self, window_size: int = 5):
        self.history = deque(maxlen=window_size)
        self.last_action_time = time.time()

    def add_action(self, path: str):
        self.history.append(path)
        self.last_action_time = time.time()

class HeuristicIntentTrigger:
    """
    Subtask 1.9: Advanced Behavioral Heuristics.
    Identifies high-confidence intent based on action sequences.
    """
    def __init__(self):
        self.user_states: Dict[str, UserBehaviorState] = {}
        self.lock = asyncio.Lock()

    async def analyze_sequence(self, client_id: str, current_path: str) -> Optional[str]:
        """
        Analyzes the last few actions to detect complex intent.
        Returns upgraded intent if a heuristic is triggered.
        """
        async with self.lock:
            if client_id not in self.user_states:
                self.user_states[client_id] = UserBehaviorState()
            
            state = self.user_states[client_id]
            state.add_action(current_path)
            
            history = list(state.history)
            
            # Heuristic 1: "Deep Station Explorer" -> SEARCH Intent
            # If 3+ different station paths seen in last 5 actions
            station_hits = [p for p in history if "/stations/" in p or "/search/" in p]
            if len(set(station_hits)) >= 3:
                logger.debug(f"🔥 Heuristic Triggered: Deep Station Explorer ({client_id})")
                return "SEARCH_DEEP"

            # Heuristic 2: "Ready to Book" -> BOOKING Intent
            # If search -> pricing -> seat_availability sequence seen
            # Simplified check for specific keywords in sequence
            if any("search" in p for p in history) and any("availability" in p or "fare" in p for p in history):
                logger.debug(f"🔥 Heuristic Triggered: Ready to Book ({client_id})")
                return "BOOKING_PREP"

            # Heuristic 3: "Active Traveler" -> STATUS Intent
            # If user hits live status multiple times rapidly
            live_hits = [p for p in history if "live" in p or "track" in p]
            if len(live_hits) >= 2:
                logger.debug(f"🔥 Heuristic Triggered: Active Traveler ({client_id})")
                return "STATUS_ACTIVE"

        return None

    async def cleanup_idle_states(self):
        """Reclaim memory for inactive users."""
        while True:
            await asyncio.sleep(60)
            async with self.lock:
                now = time.time()
                idle_ids = [cid for cid, s in self.user_states.items() if (now - s.last_action_time) > 300]
                for cid in idle_ids:
                    del self.user_states[cid]

behavior_tracker = HeuristicIntentTrigger()
