from pydantic import BaseModel
from typing import List, Optional


class ChatRequest(BaseModel):
    message: str
    file_id: Optional[str] = None
    mode: str = "normal"
    session_uuid: Optional[str] = None
    attachments: List[dict] = []
    npp: Optional[str] = None
    role: Optional[str] = "GUEST"
    model: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_uuid: Optional[str] = None
    judul: Optional[str] = None
    pdf_info: Optional[dict] = None
    is_from_document: bool = False
    model_used: Optional[str] = None
    attachments: List[dict] = []


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    status: str
    query: str
    result: str


class Document(BaseModel):
    id: int
    judul: str
    nomor: str
    tanggal: Optional[str] = None
    tempat: Optional[str] = None
    filename: str
    status: str
    id_jenis: Optional[int] = None


class Chunk(BaseModel):
    id: int
    dokumen_id: int
    content: str
    chunk_id: int
    similarity: Optional[float] = None


class SearchDocumentsResponse(BaseModel):
    documents: List[Document]
    chunks: List[Chunk]


class AvailableModelsResponse(BaseModel):
    status: str
    data: List[dict]