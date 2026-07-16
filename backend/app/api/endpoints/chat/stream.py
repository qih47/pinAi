import json
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, Request, HTTPException
from backend.app.services.pipeline.pipeline_orchestrator import _sequential_pipeline_generator
from fastapi.responses import StreamingResponse

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.chat.chat_history_service import chat_history_service
from backend.app.api.schemas.chat import ChatStreamRequest
from backend.app.utils.employee_cache import get_cached_employee_data
from backend.app.services.pipeline import (
    format_sse,
    SSEEventType,
)
from backend.app.services.pipeline.sse_validation import format_sse_pipeline_data
from backend.app.core.config import settings

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")


async def execute_vision_pipeline(
    request: Request,
    pdf_paths: List[str],
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Vision pipeline: PDF → convert ke image → MiniCPM OCR → return ocr_text.
    Hasilnya dikirim ke gemma_agentic_engine sebagai ocr_text.
    """
    raise NotImplementedError(
        "execute_vision_pipeline belum diimplementasi. "
        "Sambungkan ke vision_service (MiniCPM) di sini."
    )
    yield




@router.post("/stream")
async def chat_stream_endpoint(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    async def wrapped_generator():
        try:
            async for chunk in _sequential_pipeline_generator(request, payload, current_user_npp):
                yield chunk
        except asyncio.CancelledError:
            logger.info(
                f"⚠️ [STREAM] Client disconnect (NPP: {current_user_npp}) — "
                f"cleaning up gracefully"
            )
            raise
        except Exception as e:
            logger.error(f"❌ [STREAM] Error in generator: {e}")
            yield format_sse("", f"Error: {str(e)[:100]}", True)
            raise
        finally:
            logger.debug("[STREAM] Generator cleanup completed")

    return StreamingResponse(
        wrapped_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )