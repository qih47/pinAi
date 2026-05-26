# app/services/background_tasks.py
import logging
from ..database import get_db
from ..utils.embeddings import get_embedding

logger = logging.getLogger(__name__)


async def update_dialogue_embeddings(
    session_id: int, user_text: str, assistant_text: str
):
    """Hitung embedding & update DB di background"""
    try:
        v_user = await get_embedding(user_text) or [0.0] * 1024
        v_assistant = await get_embedding(assistant_text) or [0.0] * 1024

        async with get_db() as conn:
            await conn.execute(
                """
                UPDATE ai_dialogue_corpus
                SET embedding_user = $1, embedding_assistant = $2
                WHERE session_id = $3 AND user_text = $4 AND assistant_text = $5
                """,
                str(v_user),
                str(v_assistant),
                session_id,
                user_text,
                assistant_text,
            )
    except Exception as e:
        logger.error(f"Background embedding failed: {e}")

async def upsert_ai_memory_background(mem_key: str, mem_value: str, npp: str = None):
    """Simpan memori AI di background"""
    try:
        category = "private" if (npp and str(npp).strip()) else "public"
        content_to_embed = f"Informasi {category} untuk {mem_key}: {mem_value}"
        
        embedding = await get_embedding(content_to_embed)
        if embedding is None:
            embedding = [0.0] * 1024
        
        formatted_embedding = "[" + ",".join(map(str, embedding)) + "]"
        
        async with get_db() as conn:
            await conn.execute(
                """
                INSERT INTO ai_memory (mem_key, mem_value, npp, category, embedding, updated_at)
                VALUES ($1, $2, $3, $4, $5::vector, NOW())
                ON CONFLICT (mem_key, npp) 
                DO UPDATE SET 
                    mem_value = EXCLUDED.mem_value,
                    embedding = EXCLUDED.embedding,
                    category = EXCLUDED.category,
                    updated_at = NOW();
                """,
                str(mem_key),
                str(mem_value),
                npp,
                category,
                formatted_embedding,
            )
        logger.info(f"✅ [BG] Memori tersimpan: {mem_key} (NPP: {npp})")
    except Exception as e:
        logger.error(f"❌ [BG] Gagal simpan memori: {e}")