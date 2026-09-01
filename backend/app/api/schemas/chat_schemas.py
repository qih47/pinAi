from pydantic import BaseModel, Field
from typing import List, Optional, Union
from enum import Enum

class ChatMessageSchema(BaseModel):
    """Skema untuk memvalidasi setiap butir pesan dalam array chat history"""
    role: str = Field(..., description="Peran pengirim pesan: 'user' atau 'assistant'")
    content: str = Field(..., description="Isi teks mentah dari obrolan")

    class Config:
        from_attributes = True


class ChatMode(str, Enum):
    global_chat = "global_chat" # Slot 1: Mode Documents (Global)
    focus = "focus"             # Slot 2: Mode Focus (Satu Dokumen)
    compliance = "compliance"   # Slot 3: Mode Compliance
    redteam = "redteam"         # Slot 4: Mode Red-Team (Bedah Celah)


class ChatStreamRequest(BaseModel):
    """Skema validasi payload utama yang dikirim Frontend saat menembak endpoint /stream"""
    session_uuid: Optional[str] = Field(None, description="UUID Sesi obrolan aktif dari database RAGDB")
    messages: List[ChatMessageSchema] = Field(..., description="Daftar riwayat percakapan dalam sesi ini")
    mode: Optional[str] = Field("normal", description="Mode operasi: normal, document, search, focus, atau compliance")
    thinking: Optional[bool] = Field(True, description="Enable or disable LLM thinking")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Tingkat kreativitas inferensi model LLM")
    isolated_doc_id: Optional[Union[int, str]] = Field(None, description="ID dokumen RAG terisolasi atau nama file PDF")
    attachment_paths: Optional[List[str]] = Field(default=[], description="Daftar path file fisik lampiran chat untuk pemrosesan MiniCPM-V")
    edit_index: Optional[int] = Field(None, description="Indeks array dari chat user yang ingin diedit di DB (In-Place Update)")
    active_topic: Optional[str] = Field(None, description="Topik percakapan aktif sebelumnya di sesi ini")
    key_subject: Optional[str] = Field(None, description="Entitas / subjek inti spesifik yang sedang dibahas")
    client_context: Optional[dict] = Field(None, description="Metadata lingkungan klien (lat, lon, timezone, waktu klien)")
    forced_mode: Optional[str] = Field(None, description="Mode paksa dari FE pill: websearch, documents, code, focus")
    bypass_router: Optional[bool] = Field(False, description="Flag untuk bypass Call 1 router langsung ke executor mode")

    class Config:
        from_attributes = True



class TitleUpdateSchema(BaseModel):
    """Skema untuk validasi payload saat admin/pegawai me-rename judul sesi di Sidebar"""
    judul: str = Field(..., min_length=1, max_length=255, description="Judul baru untuk sesi obrolan")


class FeedbackSchema(BaseModel):
    """Skema untuk validasi feedback/rating terhadap respon AI"""
    message_id: int = Field(..., description="ID pesan yang di-feedback")
    rating: int = Field(..., ge=1, le=5, description="Rating kualitas respons (1-5 bintang)")
    comment: Optional[str] = Field(None, max_length=500, description="Komentar opsional untuk feedback")

    class Config:
        from_attributes = True


class TestRouterRequestSchema(BaseModel):
    """Skema validasi untuk hit testing kilat Slot 1 Router Engine"""
    text: str = Field(..., description="Kueri teks mentah yang akan diuji klasifikasi JSON-nya")
