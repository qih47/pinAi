import os
import shutil
import tempfile
import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Body
from fastapi.responses import StreamingResponse
import edge_tts
import re

# Comprehensive phonetic map for common tech jargon, English loanwords, and Indonesian abbreviations
# Comprehensive dictionary for root words
PHONETIC_ROOTS = {
    # Tech / English Loanwords
    'file': 'fail',
    'files': 'fails',
    'download': 'daunlod',
    'chat': 'cet',
    'web': 'wep',
    'website': 'wepsait',
    'app': 'ep',
    'apps': 'eps',
    'update': 'apdet',
    'upgrade': 'apgred',
    'user': 'yuser',
    'users': 'yusers',
    'error': 'eror',
    'dashboard': 'desbord',
    'database': 'databes',
    'online': 'onlain',
    'offline': 'oflain',
    'wifi': 'waifai',
    'password': 'paswot',
    'email': 'imel',
    'detail': 'ditel',
    'project': 'projek',
    'task': 'tesk',
    'bug': 'bag',
    'fix': 'fiks',
    'feature': 'ficer',
    'upload': 'aplod',
    'share': 'syer',
    'software': 'sofwer',
    'hardware': 'hardwer',
    'server': 'server',
    'cloud': 'klaud',
    'link': 'ling',
    'click': 'klik',
    
    # Acronyms
    'ai': 'e ai',
    'api': 'e pi ai',
    'ui': 'yu ai',
    'ux': 'yu eks',
    'it': 'ai ti',
    'url': 'yu er el',
    'pdf': 'pe de ef',
    'cv': 'si fi',
    'hr': 'eic ar',
    
    # Indonesian specific quirks
    'sip': 'siip',
    'oke': 'okey',
    'yg': 'yang',
    'dg': 'dengan',
    'dgn': 'dengan',
    'tsb': 'tersebut',
    'dll': 'dan lain lain',
    'ybs': 'yang bersangkutan',
    'tgl': 'tanggal',
    'bln': 'bulan',
    'thn': 'tahun',
    'rp': 'rupiah',
    'jgn': 'jangan',
    'bgt': 'banget',
}

def phonetic_correction(text: str) -> str:
    """
    Applies phonetic substitution while respecting Indonesian morphology (prefixes & suffixes).
    """
    prefixes = ['di', 'ke', 'ter']
    suffixes = ['nya', 'ku', 'mu', 'kan', 'lah', 'pun']
    
    def replace_word(match):
        word = match.group(0)
        word_lower = word.lower()
        
        # 1. Exact match
        if word_lower in PHONETIC_ROOTS:
            return PHONETIC_ROOTS[word_lower]
            
        # 2. Check Suffix only (e.g., filenya)
        for suf in suffixes:
            if word_lower.endswith(suf):
                root = word_lower[:-len(suf)]
                if root in PHONETIC_ROOTS:
                    return PHONETIC_ROOTS[root] + suf
                    
        # 3. Check Prefix only (e.g., diupdate)
        for pref in prefixes:
            if word_lower.startswith(pref):
                root = word_lower[len(pref):]
                if root in PHONETIC_ROOTS:
                    return pref + PHONETIC_ROOTS[root]
                    
        # 4. Check Prefix + Suffix (e.g., diupdatenya)
        for pref in prefixes:
            for suf in suffixes:
                if word_lower.startswith(pref) and word_lower.endswith(suf):
                    root = word_lower[len(pref):-len(suf)]
                    if root in PHONETIC_ROOTS:
                        return pref + PHONETIC_ROOTS[root] + suf
                        
        return word

    # Match any word sequence (letters only)
    return re.sub(r'\b[a-zA-Z]+\b', replace_word, text)

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


@router.post("/tts")
async def text_to_speech(
    text: str = Body(..., embed=True),
    voice: str = Body("id-ID-ArdiNeural", embed=True),
    speed: str = Body("normal", embed=True),
    current_user_npp: Optional[str] = Depends(get_current_user_npp)
):
    """
    Endpoint for Text-to-Speech using edge-tts.
    Accepts text and returns a streaming audio response (MP3).
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    logger.info(f"[VOICE] TTS requested by {current_user_npp} with voice: {voice}")
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
        
    try:
        # Terapkan koreksi fonetik sebelum memproses TTS
        corrected_text = phonetic_correction(text)
        
        rate_map = {
            "slow": "+0%",
            "normal": "+25%",
            "fast": "+50%"
        }
        rate = rate_map.get(speed, "+0%")
        
        communicate = edge_tts.Communicate(corrected_text, voice, rate=rate)
        
        async def audio_stream():
            try:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        yield chunk["data"]
            except Exception as e:
                logger.error(f"[VOICE] Error generating audio stream: {e}")
                
        return StreamingResponse(audio_stream(), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"[VOICE] TTS failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")
