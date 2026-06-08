"""
Telegram Flow Handler
=====================
Manages multi-step conversational flows (e.g., booking, profile update).
"""

import logging
from typing import Optional, Dict, Any, List, Callable, Awaitable
from .schemas import UserContext, UserState, IntentType, BotResponse
from .command_router import HandlerResult, HandlerResultStatus
from .keyboards import keyboard_builder

logger = logging.getLogger(__name__)

class FlowStep:
    def __init__(
        self,
        id: str,
        prompt: str,
        keyboard_factory: Optional[Callable[[], Dict[str, Any]]] = None,
        validator: Optional[Callable[[str], bool]] = None,
        processor: Optional[Callable[[str, UserContext], Awaitable[None]]] = None
    ):
        self.id = id
        self.prompt = prompt
        self.keyboard_factory = keyboard_factory
        self.validator = validator
        self.processor = processor

class Flow:
    def __init__(self, name: str, state: UserState, steps: List[FlowStep], on_complete: Optional[Callable[[UserContext, int], Awaitable[HandlerResult]]] = None):
        self.name = name
        self.state = state
        self.steps = steps
        self.on_complete = on_complete

class FlowHandler:
    """Manages multi-turn flows by tracking current step in UserContext."""
    
    def __init__(self):
        self._flows: Dict[UserState, Flow] = {}
    
    def register_flow(self, flow: Flow):
        self._flows[flow.state] = flow
    
    async def handle_flow(
        self, 
        text: str, 
        context: UserContext, 
        chat_id: int
    ) -> HandlerResult:
        """Process current step in the active flow."""
        flow = self._flows.get(context.state)
        if not flow:
            return HandlerResult(status=HandlerResultStatus.FAILED, error="No active flow")
        
        current_step_idx = context.data.get("flow_step_idx", 0)
        if current_step_idx >= len(flow.steps):
            return HandlerResult(status=HandlerResultStatus.SUCCESS, next_state="idle")
        
        current_step = flow.steps[current_step_idx]
        
        # 1. Validate & Process input for CURRENT step (unless it's the first time entering)
        if context.data.get("flow_waiting_input"):
            if current_step.validator and not current_step.validator(text):
                return HandlerResult(
                    status=HandlerResultStatus.NEEDS_INPUT,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=f"⚠️ Invalid input. {current_step.prompt}",
                        keyboard=current_step.keyboard_factory() if current_step.keyboard_factory else None
                    )
                )
            
            if current_step.processor:
                await current_step.processor(text, context)
            
            current_step_idx += 1
            context.data["flow_step_idx"] = current_step_idx
        
        # 2. Prepare NEXT step
        if current_step_idx < len(flow.steps):
            next_step = flow.steps[current_step_idx]
            context.data["flow_waiting_input"] = True
            
            return HandlerResult(
                status=HandlerResultStatus.NEEDS_INPUT,
                response=BotResponse(
                    chat_id=chat_id,
                    text=next_step.prompt,
                    keyboard=next_step.keyboard_factory() if next_step.keyboard_factory else None
                ),
                next_state=flow.state
            )
        else:
            # Flow complete
            context.data.pop("flow_step_idx", None)
            context.data.pop("flow_waiting_input", None)
            
            if hasattr(flow, 'on_complete') and flow.on_complete:
                return await flow.on_complete(context, chat_id)
                
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"✅ {flow.name} completed!",
                    keyboard=keyboard_builder.main_menu()
                ),
                next_state="idle"
            )

# Global instance
flow_handler = FlowHandler()
