import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from faster_whisper import WhisperModel

logger = logging.getLogger("CAKRA_VOICE")

class WhisperService:
    _instance = None
    _model = None
    _executor = ThreadPoolExecutor(max_workers=2)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhisperService, cls).__new__(cls)
        return cls._instance

    def _init_model(self):
        if self._model is None:
            logger.info("⏳ [WHISPER] Loading Whisper model (small, cuda, float16)...")
            try:
                # Use small model for very fast inference with excellent accuracy
                self._model = WhisperModel("small", device="cuda", compute_type="float16")
                logger.info("✅ [WHISPER] Model loaded successfully to VRAM.")
            except Exception as e:
                logger.error(f"❌ [WHISPER] Failed to load model: {e}")
                # Fallback to CPU if CUDA fails
                logger.info("⏳ [WHISPER] Attempting fallback to CPU (int8)...")
                self._model = WhisperModel("small", device="cpu", compute_type="int8")
                logger.info("✅ [WHISPER] Fallback CPU model loaded.")

    def ensure_loaded(self):
        self._init_model()

    def transcribe_sync(self, audio_path: str) -> str:
        self.ensure_loaded()
        
        logger.info(f"🎙️ [WHISPER] Transcribing audio: {audio_path}")
        segments, info = self._model.transcribe(
            audio_path,
            beam_size=5,
            language="id", # Force Indonesian for accuracy
            vad_filter=True, # Voice Activity Detection to ignore silence
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        # Generator for segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())
            
        full_text = " ".join(text_parts).strip()
        logger.info(f"✅ [WHISPER] Transcribed {len(full_text)} characters.")
        return full_text

    async def transcribe(self, audio_path: str) -> str:
        """Run transcription in a separate thread so it doesn't block the FastAPI event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.transcribe_sync, audio_path)

whisper_service = WhisperService()
