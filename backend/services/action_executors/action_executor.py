import logging
from typing import Any, Dict, Callable

logger = logging.getLogger(__name__)

class ActionExecutor:
    """
    Executes business logic based on recognized intent and collected parameters.
    Acts as an orchestrator, calling appropriate RouteMaster services.
    """

    def __init__(self):
        self.actions: Dict[str, Callable[..., Any]] = {}

    def register_action(self, action_name: str, func: Callable[..., Any]):
        """Registers a function to be executed for a given action name."""
        self.actions[action_name] = func
        logger.info(f"Registered action: {action_name}")

    async def execute(self, action_name: str, **kwargs) -> Any:
        """
        Executes the registered action.
        Args:
            action_name: The name of the action to execute.
            **kwargs: Arguments to pass to the action function.
        Returns:
            The result of the action execution.
        Raises:
            ValueError: If the action is not registered.
            Exception: Any exception raised by the action function itself.
        """
        action_func = self.actions.get(action_name)
        if not action_func:
            logger.error(f"Attempted to execute unregistered action: {action_name}")
            raise ValueError(f"Action '{action_name}' is not registered.")
        
        logger.debug(f"Executing action: {action_name} with args: {kwargs}")
        return await action_func(**kwargs)

action_executor = ActionExecutor()
