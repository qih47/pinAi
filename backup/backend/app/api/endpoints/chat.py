import uuid
from app.api.schemas.chat import ChatRequest
from app.api.dependencies.database import get_db_conn
import json
import traceback
import logging
import inspect
import httpx  # Tambahan untuk fetch API Ollama
from fastapi.responses import StreamingResponse
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict

# Relative imports
from app.core.database import get_db
from app.core.config import settings
from app.services.vector_service import get_embedding
from app.services.chat_history_service import generate_judul_ai
from app.services.rag_service import smart_chat_with_context
from app.services.vision_service.gateway import process_pdf_attachment_to_ocr


router = APIRouter()
logger = logging.getLogger(__name__)


# --- DATABASE DEPENDENCY ---
