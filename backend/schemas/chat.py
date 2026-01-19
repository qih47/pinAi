from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    session_uuid: Optional[str] = None
    mode: Optional[str] = "normal"
    selected_model: Optional[str] = None

class ChatResponse(BaseModel):
    status: str
    data: dict

class ChatHistoryResponse(BaseModel):
    status: str
    data: List[dict]

class ChatMessagesResponse(BaseModel):
    status: str
    data: List[dict]

class AvailableModelsResponse(BaseModel):
    status: str
    data: List[dict]