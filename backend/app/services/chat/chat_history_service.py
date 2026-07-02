import logging
from typing import List, Dict, Any, Optional
from .repositories.session_repository import SessionRepository
from .repositories.message_repository import MessageRepository
from .repositories.feedback_repository import FeedbackRepository

logger = logging.getLogger("CAKRA_CHAT_HISTORY")

class ChatHistoryService(SessionRepository, MessageRepository, FeedbackRepository):
    """
    Orchestrator class for Chat History that inherits from all specific repositories
    to maintain backward compatibility with existing codebase.
    """
    pass

chat_history_service = ChatHistoryService()
