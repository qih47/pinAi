import os
import shutil
import tempfile
import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.voice.whisper_service import whisper_service

logger = logging.getLogger("CAKRA_VOICE_API")
router = APIRouter()

@router.post("/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...),
    current_user_npp: Optional[str] = Depends(get_current_user_npp)
):
    """
    Endpoint for Voice-to-Text transcription.
    Accepts audio (WEBM, WAV, etc.) and returns transcribed text.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    logger.info(f"[VOICE] Received audio file: {audio.filename} from NPP: {current_user_npp}")
    
    # Save uploaded file to a temporary location
    try:
        suffix = os.path.splitext(audio.filename)[1] if audio.filename else ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            shutil.copyfileobj(audio.file, tmp_file)
            tmp_path = tmp_file.name
    except Exception as e:
        logger.error(f"[VOICE] Failed to save temporary audio file: {e}")
        raise HTTPException(status_code=500, detail="Failed to process audio file.")
        
    try:
        # Perform transcription using the Whisper Service (background execution)
        transcribed_text = await whisper_service.transcribe(tmp_path)
        
        logger.info(f"[VOICE] Transcription completed for {current_user_npp}")
        return {
            "status": "success",
            "text": transcribed_text
        }
    except Exception as e:
        logger.error(f"[VOICE] Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
