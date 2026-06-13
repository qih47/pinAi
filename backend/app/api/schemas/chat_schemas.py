from pydantic import BaseModel, Field
from typing import List, Optional

class ChatMessageSchema(BaseModel):
    """Skema untuk memvalidasi setiap butir pesan dalam array chat history"""
    role: str = Field(..., description="Peran pengirim pesan: 'user' atau 'assistant'")
    content: str = Field(..., description="Isi teks mentah dari obrolan")

    class Config:
        from_attributes = True


class ChatStreamRequest(BaseModel):
    """Skema validasi payload utama yang dikirim Frontend saat menembak endpoint /stream"""
    session_uuid: Optional[str] = Field(None, description="UUID Sesi obrolan aktif dari database RAGDB")
    messages: List[ChatMessageSchema] = Field(..., description="Daftar riwayat percakapan dalam sesi ini")
    mode: Optional[str] = Field("normal", description="Mode operasi: normal, document, atau search")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Tingkat kreativitas inferensi model LLM")
    isolated_doc_id: Optional[int] = Field(None, description="ID dokumen RAG terisolasi")
    attachment_paths: Optional[List[str]] = Field(default=[], description="Daftar path file fisik lampiran chat untuk pemrosesan MiniCPM-V")

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
