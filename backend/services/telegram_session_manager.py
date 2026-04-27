from sqlalchemy.orm import Session
from database.models import TelegramSession
from datetime import datetime
import uuid
import logging

logger = logging.getLogger("telegram.session_manager")

class TelegramSessionManager:
    """
    Manages Telegram conversation sessions, scoped by chat_id (group or private).
    """
    
    @staticmethod
    def get_or_create_session(db: Session, chat_id: str, telegram_id: str) -> TelegramSession:
        composite_key = f"{chat_id}:{telegram_id}"
        session = db.query(TelegramSession).filter(
            TelegramSession.telegram_id == composite_key,
            TelegramSession.is_active == True
        ).first()
        
        if not session:
            session = TelegramSession(
                telegram_id=composite_key,
                current_intent="",
                current_step="",
                context_data={}
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"Created new Telegram session for {composite_key}")
            
        return session

    @staticmethod
    def update_session(
        db: Session, 
        chat_id: str, 
        telegram_id: str,
        intent: str = "", 
        step: str = "", 
        context: dict = {},
        clear_context: bool = False
    ) -> TelegramSession:
        session = TelegramSessionManager.get_or_create_session(db, chat_id, telegram_id)
        
        if intent is not None:
            session.current_intent = intent or ""
        if step is not None:
            session.current_step = step or ""
        if context is not None:
            if clear_context:
                session.context_data = context or {}
            else:
                updated_context = dict(session.context_data)
                updated_context.update(context or {})
                session.context_data = updated_context
                
        session.last_active_at = datetime.utcnow()
        db.commit()
        return session
        # ... (rest of update logic remains same)
        
        if intent is not None:
            session.current_intent = intent
        if step is not None:
            session.current_step = step
        if context is not None:
            if clear_context:
                session.context_data = context
            else:
                updated_context = dict(session.context_data)
                updated_context.update(context)
                session.context_data = updated_context
                
        session.last_active_at = datetime.utcnow()
        db.commit()
        return session

    @staticmethod
    def clear_session(db: Session, telegram_id: str):
        session = db.query(TelegramSession).filter(
            TelegramSession.telegram_id == str(telegram_id)
        ).first()
        if session:
            session.current_intent = None
            session.current_step = None
            session.context_data = {}
            db.commit()
            logger.info(f"Cleared Telegram session for {telegram_id}")

    @staticmethod
    def deactivate_session(db: Session, telegram_id: str):
        session = db.query(TelegramSession).filter(
            TelegramSession.telegram_id == str(telegram_id)
        ).first()
        if session:
            session.is_active = False
            db.commit()
            logger.info(f"Deactivated Telegram session for {telegram_id}")

session_manager = TelegramSessionManager()
