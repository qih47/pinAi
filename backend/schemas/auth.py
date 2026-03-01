from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    status: str
    data: Optional[dict] = None
    message: Optional[str] = None


class LogoutRequest(BaseModel):
    token: str


class VerifySessionRequest(BaseModel):
    token: str


class VerifySessionResponse(BaseModel):
    status: str
    data: Optional[dict] = None
    message: Optional[str] = None