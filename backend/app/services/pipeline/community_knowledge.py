import logging
from typing import Optional

from backend.app.core.database import get_db

logger = logging.getLogger("COMMUNITY_KNOWLEDGE")

async def search_community_knowledge(query: str, is_guest: bool, limit: int = 3) -> str:
    """
    Melakukan pencarian riwayat obrolan masa lalu berdasarkan query user.
    Menggunakan Full-Text Search (FTS) Postgres sederhana untuk menghindari overload memory.
    
    Args:
        query: Pertanyaan pengguna.
        is_guest: Jika True, cari sesi GUEST. Jika False, cari sesi User Login.
        limit: Batas jumlah diskusi masa lalu.
    """
    # Preprocessing query agar lebih aman untuk to_tsquery
    safe_query = "".join([c for c in query[:500] if c.isalnum() or c.isspace()])
    
    words = [w for w in safe_query.strip().split() if len(w) > 2]
    # Jika kueri terlalu pendek, jangan buang waktu mencari
    if len(words) == 0:
        return ""
        
    # Ganti AND logic dengan OR logic supaya tidak terlalu strict
    or_tsquery = " | ".join(words)
        
    try:
        async with get_db() as conn:
            if is_guest:
                npp_condition = "(cs.npp = 'GUEST' OR cs.npp IS NULL)"
            else:
                npp_condition = "(cs.npp != 'GUEST' AND cs.npp IS NOT NULL)"
                
            # Gunakan tsvector/tsquery 'simple' dengan OR logic
            sql = f"""
                SELECT 
                    adc.user_text, 
                    adc.assistant_text,
                    ts_rank(to_tsvector('simple', COALESCE(adc.user_text, '') || ' ' || COALESCE(adc.assistant_text, '')), to_tsquery('simple', $1)) as rank
                FROM ai_dialogue_corpus adc
                JOIN chat_sessions cs ON adc.session_id = cs.id
                WHERE {npp_condition}
                  AND to_tsvector('simple', COALESCE(adc.user_text, '') || ' ' || COALESCE(adc.assistant_text, '')) @@ to_tsquery('simple', $1)
                ORDER BY rank DESC
                LIMIT $2
            """
            
            results = await conn.fetch(sql, or_tsquery, limit)
            
            if not results:
                return ""
            
            context_pieces = []
            for idx, r in enumerate(results, 1):
                # Filter manual: pastikan rank cukup relevan (mencegah teks acak masuk)
                if r['rank'] > 0.02:
                    user_text = r['user_text'] or ""
                    assistant_text = r['assistant_text'] or ""
                    
                    # 🧹 Sanitasi residu tag <think>...</think> dari riwayat masa lalu
                    import re
                    assistant_text = re.sub(r'<think>.*?</think>', '', assistant_text, flags=re.DOTALL).strip()
                    user_text = re.sub(r'<think>.*?</think>', '', user_text, flags=re.DOTALL).strip()

                    # Potong riwayat agar prompt tetap ramping & responsif
                    if len(user_text) > 300:
                        user_text = user_text[:300] + "... [dipotong]"
                    if len(assistant_text) > 500:
                        assistant_text = assistant_text[:500] + "... [dipotong]"
                        
                    if assistant_text:
                        context_pieces.append(f"Diskusi {idx}:\nUser Sebelumnya: {user_text}\nJawaban AI Sebelumnya: {assistant_text}")
            
            if not context_pieces:
                return ""
                
            final_context = "\n\n".join(context_pieces)
            
            # Format injeksi prompt
            return (
                "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 <COMMUNITY_CONTEXT>: INGATAN KOLEKTIF\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Berikut adalah referensi riwayat percakapan sebelumnya yang relevan:\n\n"
                f"{final_context}\n\n"
                "Gunakan informasi di atas sebagai referensi pendukung jika relevan dengan pertanyaan saat ini.\n"
            )
            
    except Exception as e:
        logger.error(f"[SEARCH_ERROR] Gagal mencari community knowledge: {e}", exc_info=True)
        return ""
