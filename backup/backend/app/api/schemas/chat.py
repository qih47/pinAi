from typing import Dict, List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: Optional[str] = None
    file_id: Optional[str] = None
    mode: str = "normal"
    session_uuid: Optional[str] = None
    attachments: List[Dict] = []
    model: Optional[str] = None
    npp: Optional[str] = None
    role: Optional[str] = "GUEST"
    fullname: Optional[str] = "Guest"
