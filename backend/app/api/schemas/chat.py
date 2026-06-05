from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

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

    class Config:
        json_schema_extra = {
            "example": {
                "session_uuid": "a1b2c3d4-e5f6-7a8b-9c0d-e1f2a3b4c5d6",
                "messages": [
                    {"role": "user", "content": "Halo CAKRA, tolong cek status server database hris!"}
                ],
                "mode": "normal",
                "temperature": 0.5
            }
        }


class TitleUpdateSchema(BaseModel):
    """Skema untuk validasi payload saat admin/pegawai me-rename judul sesi di Sidebar"""
    judul: str = Field(..., min_length=1, max_length=255, description="Judul baru untuk sesi obrolan")


class TestRouterRequestSchema(BaseModel):
    """Skema validasi untuk hit testing kilat Slot 1 Router Engine"""
    text: str = Field(..., description="Kueri teks mentah yang akan diuji klasifikasi JSON-nya")