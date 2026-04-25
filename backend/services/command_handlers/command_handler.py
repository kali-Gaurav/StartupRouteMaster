import logging
from typing import Callable, Dict, List, Any, Optional
from services.telegram_dispatcher import telegram_dispatcher # Moved import to module level

logger = logging.getLogger(__name__)

class CommandHandler:
    """
    Manages and dispatches commands received from Telegram.
    Supports both explicit commands (e.g., /start) and implicit intent-based actions.
    """
    def __init__(self, telegram_dispatcher_instance=telegram_dispatcher): # Inject dependency
        self.commands: Dict[str, Callable[[int, str, Any], None]] = {}
        self.default_handler: Optional[Callable[[int, str, Any], None]] = None
        self.telegram_dispatcher = telegram_dispatcher_instance # Store as instance attribute

    def register_command(self, command: str, handler: Callable[[int, str, Any], None]):
        """Registers a command with its corresponding handler function."""
        if not command.startswith('/'):
            command = '/' + command
        self.commands[command] = handler
        logger.info(f"Registered command: {command}")

    def register_default_handler(self, handler: Callable[[int, str, Any], None]):
        """Registers a default handler for unrecognized commands or general text messages."""
        self.default_handler = handler
        logger.info("Registered default command handler.")

    async def handle_message(self, chat_id: int, text: str, **kwargs):
        """
        Processes an incoming message, identifies the command, and dispatches it to the appropriate handler.
        """
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in self.commands:
            logger.debug(f"Dispatching command: {command} for chat_id: {chat_id}")
            await self.commands[command](chat_id, args, **kwargs)
        elif self.default_handler:
            logger.debug(f"Dispatching to default handler for chat_id: {chat_id}")
            await self.default_handler(chat_id, text, **kwargs)
        else:
            logger.warning(f"No handler found for command or text: '{text}' for chat_id: {chat_id}")
            # Use the instance's telegram_dispatcher
            await self.telegram_dispatcher._api_request("sendMessage", {
                "chat_id": chat_id,
                "text": "I'm sorry, I don't understand that command. Please try /help."
            })

command_handler = CommandHandler() # Initialize with default telegram_dispatcher

