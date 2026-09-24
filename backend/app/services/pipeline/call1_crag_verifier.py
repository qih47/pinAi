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
Evaluasi apakah dokumen kandidat yang ditemukan RELEVAN dan MEMUAT topik/dokumen yang dicari user (Turn {{ turn }} QC).
Pilihlah TEPAT 1 DOKUMEN PRIMER (primary_doc_id) yang menjadi subjek acuan utama untuk dibaca secara mendalam, serta dokumen lainnya sebagai referensi (reference_doc_ids).

TARGET PENCARIAN USER:
- Pesan User: {{ user_query }}
- Target Judul: {{ target_judul }}
- Target Tags: {{ target_tags }}

KANDIDAT DOKUMEN:
{{ candidates_summary }}

ATURAN EVALUASI:
1. TARGET & SUBSTANSI:
   a. Jika user mencari dokumen spesifik (contoh: PKB, nomor SK tertentu, SOP tertentu), prioritaskan dokumen tersebut sebagai "primary_doc_id".
   b. Jika user menanyakan topik umum (contoh: cuti, jam kerja, lembur), pilih 1 dokumen yang berstatus "Berlaku" dan paling berwenang/komprehensif sebagai "primary_doc_id".
   c. Dokumen lainnya yang relevan atau versi terdahulu masukkan ke "reference_doc_ids".
2. JIKA RELEVAN:
   "is_relevant": true,
   "primary_doc_id": "<ID dokumen utama>",
   "reference_doc_ids": ["<ID dokumen referensi>", ...],
   "reason": "alasan singkat kecocokan",
   "suggested_query_judul": [], "suggested_queries": [], "suggested_tags": []
3. JIKA SALAH / TIDAK RELEVAN (dokumen yang ditemukan tidak memuat atau berbeda topik):
   "is_relevant": false,
   "primary_doc_id": null,
   "reference_doc_ids": [],
   "reason": "alasan singkat mengapa tidak cocok",
   "suggested_query_judul": ["nama dokumen yang lebih tepat"],
   "suggested_queries": ["query alternatif"],
   "suggested_tags": ["tag yang relevan"]

OUTPUT JSON FORMAT (WAJIB JSON MURNI TANPA MARKDOWN):
{
  "is_relevant": true,
  "primary_doc_id": "123",
  "reference_doc_ids": ["124"],
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
    turn: int = 1,
) -> Dict[str, Any]:
    """
    Verifikasi instan dokumen hasil retrieval menggunakan gemma4:e4b.
    Mendukung Turn 1 (validasi awal Brain/MySQL) dan Turn 2 (validasi hasil retry).
    Menghasilkan primary_doc_id (dokumen inti) dan reference_doc_ids (dokumen pendukung).
    """
    if not ENABLE_CALL1_1_CRAG:
        default_primary = str(candidate_docs[0].get("id")) if candidate_docs else None
        default_refs = [str(d.get("id")) for d in candidate_docs[1:]] if len(candidate_docs) > 1 else []
        return {
            "is_relevant": True,
            "primary_doc_id": default_primary,
            "reference_doc_ids": default_refs,
            "reason": "CRAG Verifier disabled via feature flag",
            "suggested_query_judul": [],
            "suggested_queries": [],
            "suggested_tags": [],
            "timing_ms": 0.0,
        }

    if not candidate_docs or not user_query:
        return {
            "is_relevant": False,
            "primary_doc_id": None,
            "reference_doc_ids": [],
            "reason": "Tidak ada kandidat dokumen yang ditemukan",
            "suggested_query_judul": target_judul_list,
            "suggested_queries": [user_query],
            "suggested_tags": target_tags,
            "timing_ms": 0.0,
        }

    # Ringkas hingga 5 kandidat dokumen teratas (~400 token)
    cand_lines = []
    for idx, doc in enumerate(candidate_docs[:5]):
        doc_id = str(doc.get("id") or doc.get("doc_id") or "?")
        judul = doc.get("judul") or doc.get("noper") or "Tanpa Judul"
        nomor = doc.get("noper") or doc.get("nomor") or "-"
        status = doc.get("status_berlaku") or "Berlaku"
        tag = doc.get("tag") or doc.get("jenis") or ""
        origin = "Memori Sesi (Brain)" if doc.get("_from_session_brain") else "Database MySQL"
        snippet = doc.get("isi_snippet") or doc.get("snippet") or doc.get("raw_isi") or ""
        snippet_clean = " ".join(snippet[:180].split()) if snippet else ""
        cand_lines.append(
            f"[{idx+1}] ID:{doc_id} | Status:{status} | Asal:{origin} | Judul: {judul} (No: {nomor}) | Tag: {tag} | Cuplikan: {snippet_clean}"
        )

    candidates_summary = "\n".join(cand_lines)

    prompt = (
        CRAG_VERIFIER_SYSTEM_PROMPT
        .replace("{{ turn }}", str(turn))
        .replace("{{ user_query }}", user_query.strip())
        .replace("{{ target_judul }}", json.dumps(target_judul_list, ensure_ascii=False))
        .replace("{{ target_tags }}", json.dumps(target_tags, ensure_ascii=False))
        .replace("{{ candidates_summary }}", candidates_summary)
    )

    model = getattr(settings, "MODEL_ROUTER", "/home/qisthi/models/gemma-4-31B-it-AWQ")
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
            num_predict=260,
            timeout=15.0,
        )
        duration_ms = (datetime.now() - t0).total_seconds() * 1000

        if not isinstance(res_json, dict):
            logger.warning(f"[CALL1.1_CRAG] Non-dict response from model: {res_json}")
            default_primary = str(candidate_docs[0].get("id")) if candidate_docs else None
            default_refs = [str(d.get("id")) for d in candidate_docs[1:]] if len(candidate_docs) > 1 else []
            return {
                "is_relevant": True,
                "primary_doc_id": default_primary,
                "reference_doc_ids": default_refs,
                "reason": "Fallback: non-dict model response",
                "timing_ms": duration_ms
            }

        is_relevant = bool(res_json.get("is_relevant", True))
        reason = str(res_json.get("reason", ""))
        
        # Ekstrak primary_doc_id dan sanitasi
        raw_primary = res_json.get("primary_doc_id")
        primary_doc_id = str(raw_primary).strip() if raw_primary is not None and str(raw_primary).strip() not in ("", "null", "None") else None
        
        # Ekstrak reference_doc_ids
        raw_refs = res_json.get("reference_doc_ids", [])
        reference_doc_ids = []
        if isinstance(raw_refs, list):
            for r_id in raw_refs:
                c_id = str(r_id).strip()
                if c_id and c_id not in ("", "null", "None") and c_id != primary_doc_id:
                    reference_doc_ids.append(c_id)

        # Fallback jika model menyatakan is_relevant=True tapi primary_doc_id kosong:
        if is_relevant and not primary_doc_id and candidate_docs:
            primary_doc_id = str(candidate_docs[0].get("id"))
            reference_doc_ids = [str(d.get("id")) for d in candidate_docs[1:] if str(d.get("id")) != primary_doc_id]

        suggested_qj = [str(q).strip() for q in res_json.get("suggested_query_judul", []) if str(q).strip()]
        suggested_queries = [str(q).strip() for q in res_json.get("suggested_queries", []) if str(q).strip()]
        suggested_tags = [str(t).strip() for t in res_json.get("suggested_tags", []) if str(t).strip()]

        logger.info(
            f"⚡ [TIMING_BENCHMARK] [CALL1.1_CRAG] Evaluasi selesai dalam {duration_ms:.1f}ms ({duration_ms/1000:.2f}s) | "
            f"is_relevant={is_relevant} | primary_doc_id={primary_doc_id} | refs={reference_doc_ids} | reason: {reason}"
        )

        return {
            "is_relevant": is_relevant,
            "primary_doc_id": primary_doc_id,
            "reference_doc_ids": reference_doc_ids,
            "reason": reason,
            "suggested_query_judul": suggested_qj,
            "suggested_queries": suggested_queries,
            "suggested_tags": suggested_tags,
            "timing_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = (datetime.now() - t0).total_seconds() * 1000
        logger.warning(f"[CALL1.1_CRAG] Error saat evaluasi ({duration_ms:.1f}ms): {e} -> Graceful fallback is_relevant=True")
        default_primary = str(candidate_docs[0].get("id")) if candidate_docs else None
        default_refs = [str(d.get("id")) for d in candidate_docs[1:]] if len(candidate_docs) > 1 else []
        return {
            "is_relevant": True,
            "primary_doc_id": default_primary,
            "reference_doc_ids": default_refs,
            "reason": f"Fallback error: {e}",
            "suggested_query_judul": [],
            "suggested_queries": [],
            "suggested_tags": [],
            "timing_ms": duration_ms,
        }
