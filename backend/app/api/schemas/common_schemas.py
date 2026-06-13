from pydantic import BaseModel, Field
from typing import Optional, Any

class PaginationSchema(BaseModel):
    """Schema standar untuk pagination metadata"""
    total: int = Field(..., description="Total records")
    offset: int = Field(..., description="Current offset")
    limit: int = Field(..., description="Limit of records per page")

    class Config:
        from_attributes = True

class ErrorSchema(BaseModel):
    """Schema standar untuk error responses"""
    detail: str = Field(..., description="Pesan error detail")
    status: str = Field("error", description="Status string")

    class Config:
        from_attributes = True
