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
    # Preprocessing query agar lebih aman untuk plainto_tsquery
    # Menghapus karakter khusus yang bisa mengacaukan lexer
    safe_query = "".join([c for c in query[:500] if c.isalnum() or c.isspace()])
    
    # Jika kueri terlalu pendek (misal cuma "hai" atau "halo"), jangan buang waktu mencari
    if len(safe_query.strip().split()) < 2:
        return ""
        
    try:
        async with get_db() as conn:
            if is_guest:
                npp_condition = "(cs.npp = 'GUEST' OR cs.npp IS NULL)"
            else:
                npp_condition = "(cs.npp != 'GUEST' AND cs.npp IS NOT NULL)"
                
            # Gunakan tsvector/tsquery 'simple' karena kamus bahasa Indonesia mungkin tidak terinstal di setiap server PG
            sql = f"""
                SELECT 
                    adc.user_text, 
                    adc.assistant_text,
                    ts_rank(to_tsvector('simple', COALESCE(adc.user_text, '') || ' ' || COALESCE(adc.assistant_text, '')), plainto_tsquery('simple', $1)) as rank
                FROM ai_dialogue_corpus adc
                JOIN chat_sessions cs ON adc.session_id = cs.id
                WHERE {npp_condition}
                  AND to_tsvector('simple', COALESCE(adc.user_text, '') || ' ' || COALESCE(adc.assistant_text, '')) @@ plainto_tsquery('simple', $1)
                ORDER BY rank DESC
                LIMIT $2
            """
            
            results = await conn.fetch(sql, safe_query, limit)
            
            if not results:
                return ""
            
            context_pieces = []
            for idx, r in enumerate(results, 1):
                # Filter manual: pastikan rank cukup relevan (mencegah teks acak masuk)
                if r['rank'] > 0.01:
                    user_text = r['user_text'] or ""
                    assistant_text = r['assistant_text'] or ""
                    
                    # Potong jika hasil masa lalu terlalu panjang
                    if len(assistant_text) > 1000:
                        assistant_text = assistant_text[:1000] + "... [dipotong]"
                        
                    context_pieces.append(f"Diskusi {idx}:\nUser Sebelumnya: {user_text}\nJawaban AI Sebelumnya: {assistant_text}")
            
            if not context_pieces:
                return ""
                
            final_context = "\n\n".join(context_pieces)
            
            # Format injeksi prompt
            return (
                "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 <COMMUNITY_CONTEXT>: INGATAN KOLEKTIF\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Berikut adalah riwayat percakapan sebelumnya yang berkaitan dengan pertanyaan saat ini:\n\n"
                f"{final_context}\n\n"
                "Instruksi: Gunakan informasi di atas sebagai acuan utama jawabanmu. "
                "DILARANG KERAS menggunakan pengetahuan umummu jika tidak ada jawaban relevan di atas. Jika kamu tidak menemukan jawabannya di context, katakan secara eksplisit bahwa kamu tidak tahu!\n"
            )
            
    except Exception as e:
        logger.error(f"[SEARCH_ERROR] Gagal mencari community knowledge: {e}", exc_info=True)
        return ""
