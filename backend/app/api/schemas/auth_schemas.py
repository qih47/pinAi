from pydantic import BaseModel, Field
from typing import Optional

class LoginRequest(BaseModel):
    """Schema untuk memvalidasi payload data login dari Frontend"""
    username: str = Field(..., description="Username / Nomor Pokok Pegawai PT Pindad")
    password: str = Field(..., description="Plain password dari Frontend")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "06652",
                "password": "secret_password"
            }
        }

class LoginResponse(BaseModel):
    """Schema untuk standardisasi response sukses kembalian ke Frontend"""
    status: str
    message: Optional[str] = None
    data: Optional[dict] = None

    class Config:
        from_attributes = True

class ExtendSessionRequest(BaseModel):
    """Schema untuk validasi perpanjangan sesi"""
    hours_to_add: int = Field(8, description="Jumlah jam tambahan untuk perpanjangan sesi")

class UserResponse(BaseModel):
    """Schema untuk standardisasi response data user dari database"""
    npp: str
    nama: str
    divisi: Optional[str] = "Umum"
    role: str = "pegawai"
    is_logged_in: bool = True

    class Config:
        from_attributes = True
