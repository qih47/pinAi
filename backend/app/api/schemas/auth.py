from pydantic import BaseModel, Field
from typing import Optional

class LoginRequest(BaseModel):
    """Schema untuk memvalidasi payload data login dari Frontend"""
    npp: str = Field(..., description="Nomor Pokok Pegawai PT Pindad", min_length=3, max_length=20)

    class Config:
        json_schema_extra = {
            "example": {
                "npp": "06652"
            }
        }

class UserResponse(BaseModel):
    """Schema untuk standardisasi response sukses kembalian ke Frontend"""
    npp: str
    nama: str
    divisi: Optional[str] = "Umum"
    role: str = "pegawai"  # Default role setelah sukses validasi HRIS
    is_logged_in: bool = True

    class Config:
        from_attributes = True