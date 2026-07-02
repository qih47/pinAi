"""
B12 — Auto-Generate Session Title via LLM
Generate informative session title menggunakan Qwen 0.5B secara async.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("cakra.services")


async def generate_session_title(
    user_message: str,
    first_response: str,
    max_length: int = 50
) -> str:
    """
    Generate informative session title menggunakan LLM Qwen secara cerdas.
    """
    from backend.app.core.llm_client import generate_json_response
    
    try:
        # 1. Bersihkan input & batasi biar Qwen gak pusing kebanyakan context
        clean_user = user_message.strip()[:80]
        
        if not clean_user and first_response:
            clean_user = f"Menjelaskan: {first_response.strip()[:80]}"
        elif not clean_user:
            clean_user = "Membahas gambar/dokumen"
        
        # 2. PROMPT HARDENING: Singkat, padat, ke intinya (Sangat ramah buat model kecil)
        # Buat prompt seminimalis mungkin tanpa menyertakan teks contoh yang bisa dicopas salah oleh Qwen
        title_prompt = f"""[TASK] Buat 1 judul Topik percakapan yang sesuai dengan pesan user berikut "{clean_user}" (2-4 kata saja) dalam Bahasa Indonesia.
[RULE] Output HARUS JSON murni dengan format wajib: {{"title": "isi judul disini"}}

JSON:"""

        # 3. Call Qwen dengan opsi pengunci stabilitas JSON
        messages = [
            {"role": "user", "content": title_prompt}
        ]
        
        result = await asyncio.wait_for(
            generate_json_response(
                model_name="gemma3:270m",
                messages=messages,
                request=None,
                timeout=5.0,  # Judul harusnya instan, 5 detik udah kepanjangan
                temperature=0.0,  # 🔥 WAJIB 0.0: Biar gak labil dan deterministic!
                # options={"think": False}  # ← Pasang ini jika fungsi llm_client lo dukung inject options root/sub
            ),
            timeout=6.0
        )
        
        title = result.get("title", "")
        
        # 4. Bersihkan karakter sampah & ubah ke format Title Case (Biar rapi di sidebar UI)
        title = title.strip().strip('"').strip("'").strip(".").title()
        
        # Fallback jika model gagal paham
        if not title or len(title) < 2 or "Title" in title:
            return _fallback_title(user_message)
        
        # Batasi panjang karakter
        if len(title) > max_length:
            title = title[:max_length].strip() + "..."
            
        logger.info(f"✅ [TITLE] Generated: '{title}'")
        return title
        
    except asyncio.TimeoutError:
        logger.warning("[TITLE] LLM generation timeout, using fallback")
        return _fallback_title(user_message)
    except Exception as e:
        logger.warning(f"[TITLE] LLM generation failed ({e}), using fallback")
        return _fallback_title(user_message)


def _fallback_title(text: str, word_count: int = 5) -> str:
    """
    Fallback title generation (simple word slicing).
    
    Args:
        text: Input text
        word_count: Number of words to extract
    
    Returns:
        str: Simple title
    """
    if not text.strip():
        return "Obrolan Gambar/File"

    words = text.split()[:word_count]
    title = " ".join(words)
    
    if len(title) > 50:
        title = title[:47] + "..."
    
    return title or "Chat Baru"


async def update_session_title_async(
    session_uuid: str,
    user_message: str,
    first_response: str,
    db_pool = None
) -> bool:
    """
    Background task untuk update session title dengan LLM-generated title.
    
    Args:
        session_uuid: Session UUID
        user_message: User's initial message
        first_response: AI's first response
        db_pool: Database connection pool
    
    Returns:
        bool: Success flag
    """
    try:
        from backend.app.core.database import get_db
        # Generate title
        new_title = await generate_session_title(user_message, first_response)
        
        # Update database
        async with get_db() as conn:
            await conn.execute(
                """
                UPDATE chat_sessions
                SET judul = $1
                WHERE session_uuid = $2
                """,
                new_title,
                session_uuid
            )
        
        logger.info(f"✅ [SESSION] Title updated for {session_uuid}: '{new_title}'")
        return True
    
    except Exception as e:
        logger.error(f"❌ [SESSION] Failed to update title for {session_uuid}: {e}")
        return False


async def enqueue_title_generation(
    session_uuid: str,
    user_message: str,
    first_response: str,
    db_pool = None
) -> None:
    """
    Enqueue title generation sebagai background task (non-blocking).
    
    Args:
        session_uuid: Session UUID
        user_message: User's message
        first_response: AI's response
        db_pool: Database connection pool
    """
    # Fire-and-forget async task
    asyncio.create_task(
        update_session_title_async(
            session_uuid,
            user_message,
            first_response,
            db_pool
        )
    )
