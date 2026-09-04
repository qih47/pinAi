"""
Call 1.1 CRAG Verifier — Fast-Path Document Retrieval Quality Control
======================================================================
Model: gemma4:e4b (Single Model Architecture, Router Engine)
Tugas: Memverifikasi secara instan (~200ms-400ms, non-thinking, non-stream)
       apakah dokumen/snippet hasil retrieval MySQL/pgvector benar-benar
       relevan dengan apa yang diminta user.

Fitur:
- Logging presisi milidetik: ⚡ [TIMING_BENCHMARK] [CALL1.1_CRAG]
- Feature Toggle: ENABLE_CALL1_1_CRAG (bisa diaktifkan/dinonaktifkan tanpa merusak pipeline)
- Sugesti query alternatif jika dokumen meleset untuk 1x re-search.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import generate_json_response

logger = logging.getLogger("CAKRA_CRAG_VERIFIER")

# 🎛️ Feature Toggle: Set False jika ingin menonaktifkan Call 1.1 secara instan
ENABLE_CALL1_1_CRAG = True


CRAG_VERIFIER_SYSTEM_PROMPT = """Kamu adalah Quality Control (QC) verifikator dokumen instan CAKRA AI PT Pindad.

TUGAS:
Evaluasi apakah dokumen/snippet kandidat yang ditemukan dari database RELEVAN dan MEMUAT substansi yang dicari user.

TARGET PENCARIAN USER:
- Pesan User: {{ user_query }}
- Target Judul: {{ target_judul }}
- Target Tags: {{ target_tags }}

KANDIDAT DOKUMEN YANG DITEMUKAN DARI DATABASE:
{{ candidates_summary }}

ATURAN EVALUASI:
1. Jika judul dokumen atau cuplikan kandidat COCOK / MEMBAHAS topik yang dicari user:
   "is_relevant": true, "reason": "cocok", field suggested dikosongkan ([]).
2. Jika dokumen SALAH / TIDAK RELEVAN (contoh: user cari PKB/Cuti tapi yang ditemukan Audit Internal / Helpdesk / Kontrak KPI):
   "is_relevant": false, "reason": "penjelasan 1 kalimat singkat mengapa tidak cocok",
   "suggested_query_judul": ["nama dokumen alternatif spesifik"],
   "suggested_queries": ["frasa pencarian alternatif"],
   "suggested_tags": ["tag relevan"]

OUTPUT JSON FORMAT (WAJIB JSON MURNI TANPA MARKDOWN):
{
  "is_relevant": true,
  "reason": "...",
  "suggested_query_judul": [],
  "suggested_queries": [],
  "suggested_tags": []
}
"""


async def verify_retrieved_documents_crag(
    user_query: str,
    target_judul_list: List[str],
    target_tags: List[str],
    candidate_docs: List[Dict[str, Any]],
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    """
    Verifikasi instan dokumen hasil retrieval menggunakan gemma4:e4b.
    Mengembalikan dict hasil evaluasi beserta timing_ms.
    """
    if not ENABLE_CALL1_1_CRAG:
        return {
            "is_relevant": True,
            "reason": "CRAG Verifier disabled via feature flag",
            "suggested_query_judul": [],
            "suggested_queries": [],
            "suggested_tags": [],
            "timing_ms": 0.0,
        }

    if not candidate_docs or not user_query:
        return {
            "is_relevant": False,
            "reason": "Tidak ada kandidat dokumen yang ditemukan dari database",
            "suggested_query_judul": target_judul_list,
            "suggested_queries": [user_query],
            "suggested_tags": target_tags,
            "timing_ms": 0.0,
        }

    # Buat ringkasan super ringkas kandidat dokumen (maksimal 3 dokumen teratas, ~300 token)
    cand_lines = []
    for idx, doc in enumerate(candidate_docs[:3]):
        judul = doc.get("judul") or doc.get("noper") or "Tanpa Judul"
        tag = doc.get("tag") or ""
        snippet = doc.get("isi_snippet") or doc.get("snippet") or ""
        snippet_clean = " ".join(snippet[:180].split()) if snippet else ""
        cand_lines.append(f"[{idx+1}] Judul: {judul} | Tag: {tag} | Cuplikan: {snippet_clean}")

    candidates_summary = "\n".join(cand_lines)

    prompt = (
        CRAG_VERIFIER_SYSTEM_PROMPT
        .replace("{{ user_query }}", user_query.strip())
        .replace("{{ target_judul }}", json.dumps(target_judul_list, ensure_ascii=False))
        .replace("{{ target_tags }}", json.dumps(target_tags, ensure_ascii=False))
        .replace("{{ candidates_summary }}", candidates_summary)
    )

    model = getattr(settings, "MODEL_ROUTER", "gemma4:e4b")
    router_ctx = getattr(settings, "NUM_CTX_ROUTER", 4096)

    t0 = datetime.now()
    try:
        res_json = await generate_json_response(
            model_name=model,
            messages=[{"role": "user", "content": prompt}],
            request=request,
            temperature=0.0,
            top_p=0.1,
            top_k=1,
            keep_alive=-1,
            num_ctx=router_ctx,
            num_predict=220,
            timeout=5.0,
        )
        duration_ms = (datetime.now() - t0).total_seconds() * 1000

        if not isinstance(res_json, dict):
            logger.warning(f"[CALL1.1_CRAG] Non-dict response from model: {res_json}")
            return {"is_relevant": True, "reason": "Fallback: non-dict model response", "timing_ms": duration_ms}

        is_relevant = bool(res_json.get("is_relevant", True))
        reason = str(res_json.get("reason", ""))
        suggested_qj = [str(q).strip() for q in res_json.get("suggested_query_judul", []) if str(q).strip()]
        suggested_queries = [str(q).strip() for q in res_json.get("suggested_queries", []) if str(q).strip()]
        suggested_tags = [str(t).strip() for t in res_json.get("suggested_tags", []) if str(t).strip()]

        logger.info(
            f"⚡ [TIMING_BENCHMARK] [CALL1.1_CRAG] Evaluasi selesai dalam {duration_ms:.1f}ms ({duration_ms/1000:.2f}s) | "
            f"is_relevant={is_relevant} | reason: {reason}"
        )

        return {
            "is_relevant": is_relevant,
            "reason": reason,
            "suggested_query_judul": suggested_qj,
            "suggested_queries": suggested_queries,
            "suggested_tags": suggested_tags,
            "timing_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = (datetime.now() - t0).total_seconds() * 1000
        logger.warning(f"[CALL1.1_CRAG] Error saat evaluasi ({duration_ms:.1f}ms): {e} -> Graceful fallback is_relevant=True")
        return {
            "is_relevant": True,
            "reason": f"Fallback error: {e}",
            "suggested_query_judul": [],
            "suggested_queries": [],
            "suggested_tags": [],
            "timing_ms": duration_ms,
        }
