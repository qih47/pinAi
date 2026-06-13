# backend/app/api/endpoints/__init__.py
"""
API Endpoints package.

This package contains all REST API endpoint definitions organized by domain:
- auth: Authentication and session management
- chat: Chat sessions and streaming
- health: System health checks
- documents: Document management and RAG
- admin: Administrative operations
- notifications: Real-time notifications and audit logs
"""

from . import auth
from . import chat
from . import health
from . import documents
from . import admin
from . import notifications

__all__ = [
    "auth",
    "chat",
    "health",
    "documents",
    "admin",
    "notifications",
]
