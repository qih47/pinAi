# backend/app/api/dependencies/__init__.py
"""
FastAPI dependency injection module.

This package contains shared dependencies used across API endpoints:
- auth: Authentication and user validation
"""

from . import auth

__all__ = [
    "auth",
]
