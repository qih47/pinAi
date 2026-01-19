from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    status: str
    data: Optional[dict] = None


class LogoutRequest(BaseModel):
    token: str


class VerifySessionResponse(BaseModel):
    status: str
    data: Optional[dict] = None