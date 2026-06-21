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
    Generate informative session title menggunakan LLM.
    
    Args:
        user_message: User's initial message
        first_response: AI's first response (untuk context)
        max_length: Maximum title length (default: 50 chars)
    
    Returns:
        str: Generated title (atau fallback ke first 30 chars jika gagal)
    """
    from backend.app.core.llm_client import generate_json_response
    
    try:
        # Prepare prompt untuk Qwen 0.5B (ringan, cepat)
        title_prompt = f"""Buat judul ringkas 3-7 kata untuk topik percakapan ini.
Format output harus berupa JSON valid dengan key "title".

Percakapan:
User: {user_message[:100]}
Assistant: {first_response[:100]}

Format output wajib:
{{"title": "Judul Singkat"}}"""

        # Call Qwen 0.5B dengan timeout 5s
        messages = [
            {"role": "user", "content": title_prompt}
        ]
        result = await asyncio.wait_for(
            generate_json_response(
                model_name="qwen2.5:0.5b",
                messages=messages,
                request=None,
                timeout=5.0,
                temperature=0.3  # Deterministic output
            ),
            timeout=6.0
        )
        title = result.get("title", "")
        
        # Sanitize title
        title = title.strip().strip('"').strip("'").strip()
        
        # Validate length
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0] + "..."
        
        # Fallback jika hasil kosong
        if not title or len(title) < 3:
            return _fallback_title(user_message)
        
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
        # Generate title
        new_title = await generate_session_title(user_message, first_response)
        
        # Update database
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE chat_sessions
                    SET judul = $1, updated_at = NOW()
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
