from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    message: str
    file_id: Optional[str] = None
    mode: str = "normal"
    session_uuid: Optional[str] = None
    attachments: List[Dict[str, Any]] = []
    npp: Optional[str] = None
    role: Optional[str] = "GUEST"
    fullname: Optional[str] = "Guest"
    model: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_uuid: str
    judul: Optional[str] = None
    pdf_info: Optional[Dict[str, Any]] = None
    is_from_document: bool = False
    model_used: str
    attachments: List[Dict[str, Any]] = []


class SearchRequest(BaseModel):
    query: str


class UploadFileResponse(BaseModel):
    success: bool
    file_id: str
    filename: str
    file_type: str
    text_length: int
    summary: str
    message: str


class AnalyzeRequest(BaseModel):
    file_id: str
    question: str = "Apa isi file ini?"


class ListFilesResponse(BaseModel):
    files: List[Dict[str, Any]]
    count: int


class ModeSwitchRequest(BaseModel):
    mode: str


class AvailableModelsResponse(BaseModel):
    status: str
    data: List[Dict[str, str]]