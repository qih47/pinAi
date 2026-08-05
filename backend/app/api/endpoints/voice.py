import os
import shutil
import tempfile
import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Body
from fastapi.responses import StreamingResponse, FileResponse
import edge_tts
import re
import asyncio
import io
import soundfile as sf

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
    'ac': 'a se',
    # 'pt': 'pe te',
    'tbk': 'te be ka',
    'bumn': 'be u em en',
    'pic': 'pi ai si',
    'PKB': 'pe ka be',

    
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
    # 'cuy': 'cui',
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


# F5-TTS Global Instances (loaded once, lazily)
_f5_ema_model = None
_f5_vocoder = None
_ref_audio_cache = {}

# Arsitektur F5-TTS Base yang digunakan saat finetune
_F5_MODEL_CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)

def get_f5_tts():
    """Load & cache F5-TTS model + vocoder (thread-safe lazy init)."""
    global _f5_ema_model, _f5_vocoder
    if _f5_ema_model is not None:
        return _f5_ema_model, _f5_vocoder

    try:
        import torch
        import os
        from f5_tts.infer.utils_infer import load_model, load_vocoder
        from f5_tts.model import DiT

        # Ensure SDPA math mode (stable, no Flash/MemEfficient bugs on older GPUs)
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        torch.backends.cuda.enable_math_sdp(True)

        ckpt_file  = "/home/qisthi/pinAi/backend/models/f5_tts/f5_tts_indo_v2.pt"
        vocab_file = "/home/qisthi/pinAi/backend/models/f5_tts/vocab.txt"

        if not (os.path.exists(ckpt_file) and os.path.exists(vocab_file)):
            logger.warning("[VOICE] F5-TTS weights not found, skipping load.")
            return None, None

        logger.info("[VOICE] Loading F5-TTS EMA model to GPU...")
        _f5_ema_model = load_model(
            model_cls=DiT,
            model_cfg=_F5_MODEL_CFG,
            ckpt_path=ckpt_file,
            vocab_file=vocab_file,
            ode_method="euler",
            use_ema=True,
            device="cuda",
        )

        logger.info("[VOICE] Loading F5-TTS vocoder (vocos)...")
        vocos_local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "assets", "weights", "vocos")
        _f5_vocoder = load_vocoder(
            vocoder_name="vocos",
            is_local=True,
            local_path=vocos_local_path,
            device="cuda",
        )
        logger.info("[VOICE] F5-TTS Model loaded successfully.")

    except ImportError:
        logger.warning("[VOICE] f5_tts module not installed.")
    except Exception as e:
        import traceback
        logger.error(f"[VOICE] Failed to load F5-TTS: {e}")
        logger.error(traceback.format_exc())

    return _f5_ema_model, _f5_vocoder


def expand_numbers_id(text: str) -> str:
    """Konversi angka ke teks bahasa Indonesia."""
    satuan = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"]
    
    def to_words(n):
        if n < 12: return satuan[n]
        elif n < 20: return satuan[n-10] + " belas"
        elif n < 100: return satuan[n//10] + " puluh " + satuan[n%10]
        elif n < 200: return "seratus " + to_words(n-100)
        elif n < 1000: return satuan[n//100] + " ratus " + to_words(n%100)
        elif n < 2000: return "seribu " + to_words(n-1000)
        elif n < 10000: return satuan[n//1000] + " ribu " + to_words(n%1000)
        elif n < 1000000: return to_words(n//1000) + " ribu " + to_words(n%1000)
        elif n < 1000000000: return to_words(n//1000000) + " juta " + to_words(n%1000000)
        elif n < 1000000000000: return to_words(n//1000000000) + " miliar " + to_words(n%1000000000)
        else: return str(n)
        
    import re
    def replace_num(match):
        try:
            res = to_words(int(match.group(0))).strip()
            return re.sub(r'\s{2,}', ' ', res)
        except:
            return match.group(0)
            
    return re.sub(r'\d+', replace_num, text)

@router.post("/tts")
async def text_to_speech(
    text: str = Body(..., embed=True),
    voice: str = Body("id-ID-ArdiNeural", embed=True),
    speed: str = Body("normal", embed=True),
    current_user_npp: Optional[str] = Depends(get_current_user_npp)
):
    """
    Endpoint for Text-to-Speech using edge-tts or F5-TTS.
    Accepts text and returns a streaming audio response.
    """
    current_npp = current_user_npp or "GUEST"
    logger.info(f"[VOICE] TTS requested by {current_npp} with voice: {voice}")
    
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
        
        # Route to F5-TTS if voice is Indonesian and model is available
        is_indo_voice = voice.startswith("id-")
        ema_model, vocoder = None, None
        if is_indo_voice:
            ema_model, vocoder = await asyncio.to_thread(get_f5_tts)

        if is_indo_voice and ema_model is not None and vocoder is not None:
            logger.info(f"[VOICE] Routing to F5-TTS for voice: {voice}")

            if voice == "id-ID-Pria1":
                ref_file = "/home/qisthi/pinAi/backend/assets/voice_refs/male 1.mp3"
                ref_text = "Halo! Ada yang bisa saya bantu hari ini? Silakan sampaikan apa pun yang ingin kamu diskusikan atau tanyakan. Saya siap membantu.."
            elif voice == "id-ID-Pria2":
                ref_file = "/home/qisthi/pinAi/backend/assets/voice_refs/male 2.mp3"
                ref_text = "Halo! Ada yang bisa saya bantu hari ini? Silakan sampaikan apa pun yang ingin kamu diskusikan atau tanyakan. Saya siap membantu.."
            elif voice == "id-ID-Wanita1":
                ref_file = "/home/qisthi/pinAi/backend/assets/voice_refs/female 1.mp3"
                ref_text = "Halo! Ada yang bisa saya bantu hari ini? Silakan sampaikan apa pun yang ingin kamu diskusikan atau tanyakan. Saya siap membantu.."
            elif voice == "id-ID-Wanita2":
                ref_file = "/home/qisthi/pinAi/backend/assets/voice_refs/female 2.mp3"
                ref_text = "Halo! Ada yang bisa saya bantu hari ini? Silakan sampaikan apa pun yang ingin kamu diskusikan atau tanyakan. Saya siap membantu.."
            else:
                ref_file = "/home/qisthi/pinAi/backend/assets/voice_refs/male 1.mp3"
                ref_text = "Halo! Ada yang bisa saya bantu hari ini? Silakan sampaikan apa pun yang ingin kamu diskusikan atau tanyakan. Saya siap membantu.."

            def _run_f5():
                import torch
                import io
                from f5_tts.infer.utils_infer import preprocess_ref_audio_text, infer_process
                
                # Caching reference audio
                global _ref_audio_cache

                # Ensure SDPA math mode in this worker thread too
                torch.backends.cuda.enable_flash_sdp(False)
                torch.backends.cuda.enable_mem_efficient_sdp(False)
                torch.backends.cuda.enable_math_sdp(True)
                
                # Bersihkan teks sebelum dikirim ke F5-TTS:
                import re
                clean_gen = corrected_text

                # Hapus emoji (unicode ranges umum)
                clean_gen = re.sub(r'[\U0001F300-\U0001FFFF\U00002600-\U000027FF]', '', clean_gen)
                # Hapus tanda kutip (bikin model glitch/stuttering)
                clean_gen = re.sub(r'["\']', '', clean_gen)
                # Hapus markdown symbols (bintang, underscore, dll)
                clean_gen = re.sub(r'[*_#`~]', '', clean_gen)
                # Ganti standalone hyphens dengan koma (misal: kata - kata)
                clean_gen = re.sub(r'\s+[-—]\s+', ', ', clean_gen)
                
                # Hapus hyphen untuk suffix Indonesia (misal: coding-an -> codingan, update-nya -> updatenya)
                clean_gen = re.sub(r'(?<=[a-zA-Z])[-—](an|nya|ku|mu|lah|pun|kah)\b', r'\1', clean_gen, flags=re.IGNORECASE)
                # Sisa hyphen di dalam kata diganti spasi (untuk kata ulang, misal: kerjaan-kerjaan -> kerjaan kerjaan)
                clean_gen = re.sub(r'(?<=[a-zA-Z])[-—](?=[a-zA-Z])', ' ', clean_gen)
                
                # Sisa hyphen lainnya dibuang saja
                clean_gen = re.sub(r'[-—]', ' ', clean_gen)
                # Ganti tanda kurung dengan koma → natural pause
                clean_gen = re.sub(r'[(\[{]', ', ', clean_gen)
                clean_gen = re.sub(r'[)\]}]', ', ', clean_gen)
                # Ganti titik dua (colon) → titik agar F5-TTS beri jeda panjang
                clean_gen = re.sub(r':', '.', clean_gen)
                # Ganti & → dan
                clean_gen = re.sub(r'&', ' dan ', clean_gen)
                # Hapus list format angka (misal "1. ") di awal kalimat agar tidak kaku
                clean_gen = re.sub(r'(?m)^\s*\d+\.\s+', '', clean_gen)
                
                # BACA ANGKA: 
                # Hapus titik pemisah ribuan agar 1.000.000 dibaca satu juta bukan satu titik
                clean_gen = re.sub(r'(?<=\d)\.(?=\d)', '', clean_gen)
                # F5-TTS tidak bisa baca digit (tidak ada di vocab)
                # Jadi semua angka harus diexpand jadi teks ("1" -> "satu")
                clean_gen = expand_numbers_id(clean_gen)

                # Ganti tanda tanya & seru ganda menjadi tunggal (jangan diubah jadi titik)
                clean_gen = re.sub(r'\?{2,}', '?', clean_gen)
                clean_gen = re.sub(r'!{2,}', '!', clean_gen)
                # Bersihkan koma berurutan & spasi ganda
                clean_gen = re.sub(r',\s*,+', ',', clean_gen)
                
                # Hapus koma sebelum kata sapaan/partikel informal biar intonasinya nyambung (gak patah)
                clean_gen = re.sub(r',\s+(cuy|cui|bro|ya|dong|deh|nih|tuh|sih|yuk|kok)\b', r' \1', clean_gen, flags=re.IGNORECASE)

                # Sederhanakan elipsis (...) jadi satu titik dengan jeda
                clean_gen = re.sub(r'\.\s*\.+', '.', clean_gen)
                clean_gen = re.sub(r'\s{2,}', ' ', clean_gen).strip()
                
                # Mencegah terpotong di akhir dengan menambahkan titik secara eksplisit
                # Cek apakah kalimat sudah diakhiri dengan tanda baca pemutus (. ? !)
                if not re.search(r'[.?!]$', clean_gen):
                    clean_gen += '.'

                logger.debug(f"[VOICE] clean_gen: {clean_gen[:80]}...")

                # Gunakan cache untuk reference audio (menghemat ~1 detik TTFT)
                if ref_file not in _ref_audio_cache:
                    _ref_audio_cache[ref_file] = preprocess_ref_audio_text(
                        ref_audio_orig=ref_file,
                        ref_text=ref_text,
                    )
                ref_audio_proc, ref_text_proc = _ref_audio_cache[ref_file]

                # Inference — nfe_step=16 is kept as requested by user for quality
                wav, sr, _ = infer_process(
                    ref_audio=ref_audio_proc,
                    ref_text=ref_text_proc,
                    gen_text=clean_gen,
                    model_obj=ema_model,
                    vocoder=vocoder,
                    mel_spec_type="vocos",
                    cfg_strength=2.0,
                    nfe_step=16,
                    device="cuda",
                    show_info=logger.info,
                )

                logger.info(f"[VOICE] F5-TTS generated {len(wav)/sr:.1f}s audio (sr={sr})")

                # Tambah trailing silence 1.2 detik (dinaikkan dari 0.8) — cegah cutoff di akhir kalimat
                import numpy as np
                silence = np.zeros(int(1.2 * sr), dtype=wav.dtype)
                wav = np.concatenate([wav, silence])

                # Write ke in-memory WAV buffer
                buf = io.BytesIO()
                sf.write(buf, wav, sr, format='WAV', subtype='PCM_16')
                return buf.getvalue()

            audio_bytes = await asyncio.to_thread(_run_f5)
            
            # Use standard Response so FastAPI sends the Content-Length header.
            # Chrome fails to play WAV files without Content-Length.
            from fastapi import Response
            return Response(content=audio_bytes, media_type="audio/wav")
            
        else:
            if is_indo_voice:
                logger.warning("[VOICE] F5-TTS model not ready, falling back to edge-tts.")
                # Map custom voices back to standard edge-tts voices
                if voice in ["id-ID-Pria1", "id-ID-Pria2"]:
                    voice = "id-ID-ArdiNeural"
                elif voice in ["id-ID-Wanita1", "id-ID-Wanita2"]:
                    voice = "id-ID-GadisNeural"
                    
            logger.info(f"[VOICE] Routing to edge-tts for voice: {voice}")
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
        import traceback
        logger.error(f"[VOICE] TTS failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")

@router.get("/test/{voice_id}")
async def get_test_voice(voice_id: str):
    """
    Mengambil file contoh suara statis untuk menghindari generate berulang.
    Hanya untuk suara Indonesia.
    """
    from fastapi.responses import FileResponse
    # Map voice ID to file name
    voice_map = {
        "id-ID-Pria1": "male 1.mp3",
        "id-ID-Pria2": "male 2.mp3",
        "id-ID-Wanita1": "female 1.mp3",
        "id-ID-Wanita2": "female 2.mp3"
    }
    
    if voice_id not in voice_map:
        raise HTTPException(status_code=404, detail="File suara contoh tidak tersedia untuk voice ini")
        
    filename = voice_map[voice_id]
    
    # Path is relative to the backend root directory (assets/voice_refs)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    filepath = os.path.join(base_dir, "assets", "voice_refs", filename)
    
    if not os.path.exists(filepath):
        logger.error(f"Test voice file not found: {filepath}")
        raise HTTPException(status_code=404, detail="File suara contoh tidak ditemukan di server")
        
    return FileResponse(filepath, media_type="audio/mpeg")
