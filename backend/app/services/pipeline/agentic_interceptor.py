"""
Agentic Stream Interceptor for CAKRA AI (Call 2 ReAct Loop)
===========================================================
Mendeteksi dan menangani Autonomous Tool-Calling (seperti ```websearch) di tengah
stream Call 2 secara non-destruktif tanpa mengganggu alur teks reguler.
"""

import os
import json
import re
import asyncio
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from datetime import datetime
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.pipeline.tool_dispatcher import dispatch_agentic_tool, dispatch_agentic_tool_stream, ToolResult

logger = logging.getLogger("CAKRA_AGENTIC_INTERCEPTOR")

_RE_TOOL_OPEN = re.compile(r"```(websearch|docsearch|python_calc|web_search|doc_search|calc|urlfetch|url_fetch|read_url|fetch_url|map_search|map|geocode)", re.IGNORECASE)
_RE_TRIPLE_BACKTICKS = re.compile(r"```")
_RE_SOURCES_OPEN = re.compile(r"<\s*sources_json\s*>", re.IGNORECASE)
_RE_SOURCES_CLOSE = re.compile(r"<\s*/\s*sources_json\s*>", re.IGNORECASE)



async def execute_in_line_web_search(query: str) -> tuple[Dict[str, Any], str]:
    """
    Menjalankan pencarian web live + scraping paralel untuk in-line tool call via Unified Pipeline.
    Mengembalikan (widget_payload, llm_context_text).
    """
    from backend.app.services.web_tools.web_search import execute_web_search_pipeline

    result = await execute_web_search_pipeline(queries=query, num_raw_results=12, scrape_top_k=2)
    widget_payload = {
        "query": result.display_query,
        "results": result.results,
    }
    return widget_payload, result.llm_context


FILE_PERATURAN_DIR = getattr(settings, "FILE_PERATURAN_DIR", "/home/qisthi/pinAi/file_peraturan")


async def resolve_and_enrich_sources(json_str: str, rag_sources: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Memvalidasi dan merekonsiliasi dokumen referensi dari tag <sources_json>
    dengan candidate sources di memori atau database MySQL secara non-destruktif.
    """
    clean_sources = list(rag_sources or [])
    filtered_sources = []
    
    try:
        clean_json_str = re.sub(r'```json|```', '', json_str).strip()
        if not clean_json_str:
            return []
        
        used_docs = json.loads(clean_json_str)
        if not isinstance(used_docs, list):
            return []

        # Filter out dokumen dengan alasan negatif
        valid_used_docs = []
        for doc in used_docs:
            if not isinstance(doc, dict):
                continue
            alasan = str(doc.get("alasan", "")).lower()
            if any(neg in alasan for neg in ["tidak digunakan", "tidak relevan", "tidak dipakai", "tidak merujuk"]):
                continue
            valid_used_docs.append(doc)

        missing_docs = []
        for doc in valid_used_docs:
            doc_id = str(doc.get("id", "")).strip()
            doc_judul = str(doc.get("judul", "")).strip().lower()
            found = False

            # 1. Match di memory (clean_sources) via ID, Nomor, atau Judul
            for src in clean_sources:
                src_id = str(src.get("id", "")).strip()
                src_nomor = str(src.get("nomor") or src.get("noper") or "").strip().lower()
                src_title = str(src.get("title") or src.get("judul") or src.get("raw_judul") or "").strip().lower()

                if doc_id and (doc_id == src_id):
                    if src not in filtered_sources:
                        filtered_sources.append(src)
                    found = True
                    break

                if doc_id and src_nomor and (doc_id.lower() in src_nomor or src_nomor in doc_id.lower()):
                    if src not in filtered_sources:
                        filtered_sources.append(src)
                    found = True
                    break

                if doc_judul and src_title and len(doc_judul) > 5 and (doc_judul in src_title or src_title in doc_judul):
                    if src not in filtered_sources:
                        filtered_sources.append(src)
                    found = True
                    break

            if not found and (doc_id or doc_judul):
                missing_docs.append(doc)

        # 2. Database lookup fallback jika dokumen tidak ada di memory RAG awal
        if missing_docs:
            try:
                from backend.app.core.database import get_peraturan_db
                from backend.app.services.peraturan_service import _find_valid_pdf_file

                async with get_peraturan_db() as conn_my:
                    async with conn_my.cursor() as cur:
                        for mdoc in missing_docs:
                            m_id = str(mdoc.get("id", "")).strip()
                            m_judul = str(mdoc.get("judul", "")).strip()
                            row = None

                            if m_id.isdigit():
                                sql = """
                                    SELECT b.id_berita, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.noper
                                    FROM berita b
                                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                                    WHERE b.id_berita = %s
                                """
                                await cur.execute(sql, (int(m_id),))
                                row = await cur.fetchone()

                            if not row and m_id:
                                sql = """
                                    SELECT b.id_berita, b.judul, b.gambar, b.gambar2, b.gambar3, k.nama_kategori, b.noper
                                    FROM berita b
                                    LEFT JOIN kategori k ON b.id_kategori = k.id_kategori
                                    WHERE b.noper LIKE %s OR b.judul LIKE %s
                                    ORDER BY b.id_berita DESC
                                    LIMIT 1
                                """
                                noper_like = f"%{m_id}%"
                                judul_like = f"%{m_judul}%" if m_judul else noper_like
                                await cur.execute(sql, (noper_like, judul_like))
                                row = await cur.fetchone()

                            if row:
                                id_berita, db_judul, gambar, gambar2, gambar3, nama_kategori, noper = row
                                valid_file = _find_valid_pdf_file(gambar, gambar2, gambar3)
                                filename = os.path.basename(valid_file) if valid_file else None
                                filtered_sources.append({
                                    "id": str(id_berita),
                                    "title": db_judul,
                                    "document_title": db_judul,
                                    "filename": filename,
                                    "file_path": f"file_peraturan/{filename}" if filename else None,
                                    "jenis": nama_kategori or "Regulasi",
                                    "nomor": noper or "N/A",
                                    "score_label": "AI_MEMORY_RECOVERED",
                                    "score": 1.0,
                                })
            except Exception as e_db:
                logger.warning(f"[AGENTIC_INTERCEPTOR] DB lookup fallback error: {e_db}")

        # 3. Deduplikasi final_sources
        seen_final = set()
        unique_final = []
        for f_src in filtered_sources:
            f_key = str(f_src.get("id") or f_src.get("filename") or f_src.get("title") or "")
            if f_key and f_key not in seen_final:
                seen_final.add(f_key)
                unique_final.append(f_src)
        final_sources = unique_final

        # 4. Hitung total_pages untuk dokumen yang terpilih
        if final_sources:
            def _count_pages_sync(abs_path: str) -> int:
                try:
                    import fitz
                    doc = fitz.open(abs_path)
                    n = len(doc)
                    doc.close()
                    return n
                except Exception:
                    return 0

            _loop = asyncio.get_running_loop()
            _tasks = []
            for _src in final_sources:
                _filename = os.path.basename(_src.get("file_path", "") or "")
                _abs = os.path.join(FILE_PERATURAN_DIR, _filename) if _filename else ""
                if _abs and os.path.exists(_abs):
                    _tasks.append(_loop.run_in_executor(None, _count_pages_sync, _abs))
                else:
                    async def _zero(): return 0
                    _tasks.append(_zero())

            _page_results = await asyncio.gather(*_tasks, return_exceptions=True)
            for _src, _n in zip(final_sources, _page_results):
                n_pages = _n if isinstance(_n, int) else 0
                if n_pages > 0:
                    if not _src.get("total_pages"):
                        _src["total_pages"] = str(n_pages)
                    if not _src.get("page_number"):
                        _src["page_number"] = ""
                elif not _src.get("total_pages"):
                    _src["total_pages"] = ""

        return final_sources

    except Exception as e:
        logger.warning(f"[AGENTIC_INTERCEPTOR] Error resolving sources_json: {e}")
        return []


async def agentic_stream_wrapper(
    model_name: str,
    messages: List[Dict[str, str]],
    request: Optional[Request] = None,
    temperature: float = 0.6,
    num_ctx: int = 16384,
    is_thinking: bool = False,
    employee_name: str = "Pegawai",
    session_uuid: Optional[str] = None,
    rag_sources: Optional[List[Dict[str, Any]]] = None,
    max_tool_loops: int = 2,
    current_user_npp: Optional[str] = None,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """
    Membungkus stream_ollama_chat dengan ReAct interceptor universal (MCP-Ready).
    Mendukung in-stream tool execution (websearch, docsearch, python_calc) dan
    sources_json filtering secara terpadu dan non-destruktif.
    """
    accumulated_full_text = ""
    current_messages = list(messages)
    current_rag_sources = list(rag_sources) if rag_sources is not None else None
    sources_emitted = False
    loop_count = 0
    was_truncated = False
    user_message = str(kwargs.get("user_message") or (messages[-1]["content"] if messages and messages[-1].get("role") == "user" else ""))

    while loop_count <= max_tool_loops:
        stream_gen = stream_ollama_chat(
            model_name=model_name,
            messages=current_messages,
            request=request,
            temperature=temperature,
            keep_alive=-1,
            num_ctx=num_ctx,
            is_thinking=is_thinking,
            **kwargs,
        )

        buffer = ""
        is_capturing_tool = False
        tool_tag = None
        tool_buffer = ""
        tool_executed = False
        pre_tool_text = ""

        is_capturing_sources = False
        sources_buffer = ""

        try:
            async for chunk_line in stream_gen:
                try:
                    chunk_data = json.loads(chunk_line.strip())
                    chunk_text = chunk_data.get("chunk", "")
                    native_thought = chunk_data.get("thinking", "")
                    eval_count = chunk_data.get("eval_count", 0)
                    eval_duration = chunk_data.get("eval_duration", 0)
                    prompt_eval_count = chunk_data.get("prompt_eval_count", 0)
                    is_truncated = bool(chunk_data.get("is_truncated", False) or chunk_data.get("done_reason") == "length")
                    if is_truncated:
                        was_truncated = True
                except (json.JSONDecodeError, AttributeError):
                    chunk_text = chunk_line if isinstance(chunk_line, str) else ""
                    native_thought = ""
                    eval_count = 0
                    eval_duration = 0
                    prompt_eval_count = 0
                    is_truncated = False

                # 1. Forward thinking chunks as usual
                if native_thought and is_thinking:
                    yield format_sse("", native_thought, False, event_type=SSEEventType.THINKING)

                if not chunk_text:
                    if (eval_count > 0 or prompt_eval_count > 0 or is_truncated) and not is_capturing_tool and not is_capturing_sources:
                        yield format_sse("", "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_duration, prompt_eval_count=prompt_eval_count, is_truncated=is_truncated)
                    continue

                # 2. Tangkap tag <sources_json> jika belum pernah diproses
                if not sources_emitted:
                    if not is_capturing_sources:
                        combined = buffer + chunk_text
                        open_m = _RE_SOURCES_OPEN.search(combined)
                        if open_m:
                            s_start = open_m.start()
                            s_end = open_m.end()
                            # Flush teks sebelum <sources_json> jika ada
                            if s_start > 0:
                                pre_sources = combined[:s_start]
                                yield format_sse(pre_sources, "", False, event_type=SSEEventType.CHUNK)
                                accumulated_full_text += pre_sources
                                pre_tool_text += pre_sources
                            
                            is_capturing_sources = True
                            sources_buffer = combined[s_end:]
                            buffer = ""
                            
                            # Cek langsung apakah closing tag juga sudah ada dalam sources_buffer
                            close_m = _RE_SOURCES_CLOSE.search(sources_buffer)
                            if close_m:
                                sources_json_str = sources_buffer[:close_m.start()].strip()
                                remainder = sources_buffer[close_m.end():]
                                
                                is_capturing_sources = False
                                sources_emitted = True
                                sources_buffer = ""
                                
                                final_sources = await resolve_and_enrich_sources(sources_json_str, current_rag_sources)
                                logger.info(f"[AGENTIC_INTERCEPTOR] 📚 Emitting {len(final_sources)} resolved sources to client")
                                yield format_sse("", "", False, sources=final_sources, event_type=SSEEventType.SOURCES)
                                
                                chunk_text = remainder
                                if not chunk_text:
                                    continue
                            else:
                                continue
                    else:
                        sources_buffer += chunk_text
                        close_m = _RE_SOURCES_CLOSE.search(sources_buffer)
                        if close_m:
                            sources_json_str = sources_buffer[:close_m.start()].strip()
                            remainder = sources_buffer[close_m.end():]
                            
                            is_capturing_sources = False
                            sources_emitted = True
                            sources_buffer = ""
                            
                            # Parse dan emit SSEEventType.SOURCES
                            final_sources = await resolve_and_enrich_sources(sources_json_str, current_rag_sources)
                            logger.info(f"[AGENTIC_INTERCEPTOR] 📚 Emitting {len(final_sources)} resolved sources to client")
                            yield format_sse("", "", False, sources=final_sources, event_type=SSEEventType.SOURCES)
                            
                            # Lanjutkan pemrosesan sisa teks setelah tag penutup
                            chunk_text = remainder
                            if not chunk_text:
                                continue
                        else:
                            continue

                # 3. Track text stream & deteksi tool calling
                if not is_capturing_tool:
                    buffer += chunk_text
                    
                    # 🛡️ BUFFER HOLDING: Tahan potongan tag <sources_json> agar token pembuka tidak bocor ke klien
                    if not sources_emitted:
                        last_lt = buffer.rfind('<')
                        if last_lt != -1:
                            tail_candidate = buffer[last_lt:].lower()
                            # Jika tail_candidate merupakan awalan dari "<sources_json>" dan belum selesai ditutup '>'
                            if "<sources_json>".startswith(tail_candidate) and ">" not in tail_candidate:
                                if last_lt > 0:
                                    safe_to_flush = buffer[:last_lt]
                                    buffer = buffer[last_lt:]
                                    yield format_sse(safe_to_flush, "", False, event_type=SSEEventType.CHUNK)
                                    accumulated_full_text += safe_to_flush
                                    pre_tool_text += safe_to_flush
                                continue

                    bt_idx = buffer.find("```")
                    if bt_idx != -1:
                        tail = buffer[bt_idx:]
                        open_match = _RE_TOOL_OPEN.search(tail)
                        if open_match:
                            preamble = buffer[:bt_idx + open_match.start()]
                            if preamble:
                                yield format_sse(preamble, "", False, event_type=SSEEventType.CHUNK)
                                accumulated_full_text += preamble
                                pre_tool_text += preamble

                            is_capturing_tool = True
                            tool_tag = open_match.group(1).lower()
                            tool_buffer = tail[open_match.end():]
                            buffer = ""
                            logger.info(f"[AGENTIC_TOOL] 🎯 Intercepted ```{tool_tag} open tag during stream!")

                            _norm_tag = tool_tag
                            if _norm_tag in ("web_search", "websearch"):
                                _norm_tag = "websearch"
                            elif _norm_tag in ("doc_search", "docsearch"):
                                _norm_tag = "docsearch"
                            elif _norm_tag in ("url_fetch", "read_url", "fetch_url", "urlfetch"):
                                _norm_tag = "urlfetch"
                            elif _norm_tag in ("calc", "python_calc"):
                                _norm_tag = "python_calc"
                            elif _norm_tag in ("map", "geocode", "map_search"):
                                _norm_tag = "map_search"

                            tool_initial_statuses = {
                                "websearch": ("Mencari di mesin pencari", "TOOL_WEBSEARCH_SEARCHING"),
                                "docsearch": ("Membuka arsip regulasi", "TOOL_DOCSEARCH_OPENING"),
                                "urlfetch": ("Mengunduh konten tautan", "TOOL_URLFETCH_DOWNLOADING"),
                                "python_calc": ("Menjalankan komputasi", "TOOL_CALC_RUNNING"),
                                "map_search": ("Menelusuri koordinat peta", "TOOL_MAP_SEARCHING"),
                            }
                            init_status = tool_initial_statuses.get(_norm_tag, (f"Menyiapkan alat {_norm_tag}", f"TOOL_{_norm_tag.upper()}_PREPARING"))
                            yield format_sse(status=init_status[0], status_key=init_status[1], event_type=SSEEventType.STATUS)
                        elif len(tail) < 30 and "\n" not in tail[3:]:
                            # Masih mungkin bagian dari tag tool (misal: ```doc...), tahan tail di buffer
                            if bt_idx > 0:
                                safe_to_flush = buffer[:bt_idx]
                                buffer = tail
                                yield format_sse(safe_to_flush, "", False, event_type=SSEEventType.CHUNK)
                                accumulated_full_text += safe_to_flush
                                pre_tool_text += safe_to_flush
                            continue
                        else:
                            # Bukan tool agentic kita (misal: ```sql atau ```html umum), flush normal
                            yield format_sse(buffer, "", False, event_type=SSEEventType.CHUNK)
                            accumulated_full_text += buffer
                            pre_tool_text += buffer
                            buffer = ""
                    else:
                        # Tidak ada ```. Cek apakah ada 1 atau 2 backtick menggantung di ujung akhir buffer
                        if buffer.endswith("``"):
                            safe_to_flush = buffer[:-2]
                            buffer = "``"
                            if safe_to_flush:
                                yield format_sse(safe_to_flush, "", False, event_type=SSEEventType.CHUNK)
                                accumulated_full_text += safe_to_flush
                                pre_tool_text += safe_to_flush
                        elif buffer.endswith("`"):
                            safe_to_flush = buffer[:-1]
                            buffer = "`"
                            if safe_to_flush:
                                yield format_sse(safe_to_flush, "", False, event_type=SSEEventType.CHUNK)
                                accumulated_full_text += safe_to_flush
                                pre_tool_text += safe_to_flush
                        else:
                            yield format_sse(buffer, "", False, event_type=SSEEventType.CHUNK)
                            accumulated_full_text += buffer
                            pre_tool_text += buffer
                            buffer = ""

                else:
                    # Sedang menangkap payload di dalam blok tool
                    tool_buffer += chunk_text
                    close_match = _RE_TRIPLE_BACKTICKS.search(tool_buffer)
                    if close_match:
                        raw_payload_str = tool_buffer[:close_match.start()].strip()
                        tool_executed = True
                        is_capturing_tool = False
                        
                        logger.info(f"[AGENTIC_TOOL] Executing tool '{tool_tag}' with payload: {raw_payload_str[:120]}...")
                        
                        # Eksekusi via Universal Tool Dispatcher Stream (menghasilkan SSE status progresif)
                        tool_result = None
                        preview_emitted = False
                        async for item in dispatch_agentic_tool_stream(
                            tool_tag,
                            raw_payload_str,
                            session_uuid=session_uuid,
                            current_user_npp=current_user_npp,
                            request=request,
                            user_message=user_message,
                        ):
                            if isinstance(item, tuple):
                                status_msg, status_k = item
                                if status_msg in ("TOOL_PREVIEW", "DOCUMENTS_PREVIEW"):
                                    if not preview_emitted:
                                        # Kirim enriched JSON block preview awal agar UI langsung menampilkan widget secara realtime
                                        preview_block = f"\n```{tool_tag}\n{json.dumps(status_k)}\n```\n\n"
                                        yield format_sse(preview_block, "", False, event_type=SSEEventType.CHUNK)
                                        accumulated_full_text += preview_block
                                        preview_emitted = True
                                else:
                                    yield format_sse(status=status_msg, status_key=status_k, event_type=SSEEventType.STATUS)
                            else:
                                tool_result = item

                        if tool_result is None:
                            tool_result = ToolResult(
                                tool_name=tool_tag,
                                status="error",
                                display_data={"error": "Tool execution returned no result"},
                                llm_context="[Gagal menjalankan alat]"
                            )
                        
                        # Jika tool docsearch menghasilkan dokumen baru, catat ke current_rag_sources dengan metadata lengkap
                        if tool_result.tool_name == "docsearch" and current_rag_sources is not None:
                            for d in tool_result.display_data.get("documents", []):
                                d_id = str(d.get("doc_id") or d.get("id") or "")
                                if d_id and not any(str(s.get("id", "")) == d_id for s in current_rag_sources):
                                    current_rag_sources.append({
                                        "id": d_id,
                                        "title": d.get("title", ""),
                                        "document_title": d.get("title", ""),
                                        "nomor": d.get("nomor") or d.get("noper") or "",
                                        "noper": d.get("nomor") or d.get("noper") or "",
                                        "tanggal": d.get("tanggal", ""),
                                        "total_pages": str(d.get("total_pages", "")),
                                        "page": str(d.get("page") or d.get("page_number") or ""),
                                        "page_number": str(d.get("page") or d.get("page_number") or ""),
                                        "jenis": d.get("jenis") or "Regulasi",
                                        "stataktif": d.get("stataktif") or "Berlaku",
                                        "status_berlaku": d.get("stataktif") or "Berlaku",
                                        "filename": d.get("filename") or "",
                                        "file_path": d.get("file_path") or "",
                                        "content": d.get("snippet", ""),
                                        "score": d.get("score", 1.0)
                                    })

                        # Jika tool urlfetch sukses dan ada session_uuid, simpan ke session memory agar multi-turn aware
                        if tool_result.tool_name == "urlfetch" and session_uuid and tool_result.status == "success":
                            try:
                                from backend.app.services.chat.chat_history_service import chat_history_service
                                clean_sample = " ".join(tool_result.llm_context.replace("=== KONTEN DARI TAUTAN WEB ===", "").split())[:180]
                                u_nodes = tool_result.display_data.get("nodes", [])
                                u_list = [n.get("url") for n in u_nodes if n.get("url")]
                                tgt_title = u_list[0] if u_list else "Tautan Web"
                                asyncio.create_task(chat_history_service.save_document_chunk(
                                    session_uuid=session_uuid,
                                    npp=current_user_npp or "Pegawai",
                                    content=tool_result.llm_context[:30000],
                                    file_id=None,
                                    chunk_metadata={
                                        "type": "web",
                                        "source": "url_read",
                                        "title": tgt_title,
                                        "urls": u_list,
                                        "summary": f"Konten web {tgt_title}: {clean_sample}...",
                                        "fetched_at": datetime.now().isoformat()
                                    }
                                ))
                            except Exception as e_mem:
                                logger.warning(f"[AGENTIC_INTERCEPTOR] Gagal menyimpan chunk urlfetch ke memori sesi: {e_mem}")

                        # Kirim enriched JSON block ke UI (akan dirender oleh Frontend jika belum dipancarkan saat preview)
                        if not preview_emitted:
                            enriched_block = f"\n```{tool_result.tool_name}\n{json.dumps(tool_result.display_data)}\n```\n\n"
                            yield format_sse(enriched_block, "", False, event_type=SSEEventType.CHUNK)
                            accumulated_full_text += enriched_block

                        yield format_sse(status="Menyusun jawaban", status_key="DRAFTING_RESPONSE", event_type=SSEEventType.STATUS)

                        # Batas kuota konteks LLM aman (~11.000 - 11.500 token dalam 32K context)
                        safe_context = tool_result.llm_context[:45000] if len(tool_result.llm_context) > 45000 else tool_result.llm_context
                        if tool_result.tool_name == "docsearch":
                            continuation_instruction = (
                                f"\n\n[SISTEM: HASIL EKSEKUSI ALAT 'DOCSEARCH']:\n"
                                f"{safe_context}\n\n"
                                f"[INSTRUKSI LANJUTAN]:\n"
                                f"Kamu telah menerima hasil pembacaan dokumen regulasi di atas. Evaluasi apakah dokumen di atas RELEVAN dan MEMUAT klausul yang dibutuhkan pengguna:\n"
                                f"- JIKA INFORMASI SUDAH LENGKAP & RELEVAN:\n"
                                f"  1. AWALI respon lanjutanmu dengan tag <sources_json>[{{\"id\": \"ID_DOKUMEN\", \"judul\": \"JUDUL_DOKUMEN\", \"alasan\": \"alasan penggunaan\"}}]</sources_json> HANYA untuk dokumen yang kamu jadikan referensi (gunakan ID dan Judul dokumen dari data di atas). Tag ini otomatis diproses sistem menjadi kartu sitasi resmi dan tidak akan ditampilkan sebagai teks mentah.\n"
                                f"  2. Setelah tag </sources_json>, lanjutkan jawabanmu secara tuntas, akurat, dan terstruktur menyambung respons sebelumnya. Patuhi gaya bahasa & kata ganti aktifmu.\n"
                                f"- JIKA HASIL TIDAK RELEVAN, SALAH DOKUMEN, ATAU KURANG LENGKAP: Kamu WAJIB LANGSUNG MEMANGGIL ALAT LAGI (misal ```docsearch dengan kata kunci substansi yang lebih spesifik, atau ```websearch jika topik tidak ada di arsip internal) DI BAWAH KALIMATMU SEKARANG JUGA! DILARANG KERAS hanya berjanji dalam bentuk teks tanpa menyertakan blok pemanggilan alatnya!\n"
                                f"Tetap konsisten menjaga gaya bahasa aktifmu. JANGAN mengulangi sapaan awal."
                            )
                        else:
                            continuation_instruction = (
                                f"\n\n[SISTEM: HASIL EKSEKUSI ALAT '{tool_result.tool_name.upper()}']:\n"
                                f"{safe_context}\n\n"
                                f"[INSTRUKSI LANJUTAN]:\n"
                                f"Kamu telah menerima hasil eksekusi alat di atas. Evaluasi apakah dokumen/data di atas RELEVAN dan MEMUAT informasi yang dibutuhkan pengguna:\n"
                                f"- JIKA INFORMASI SUDAH LENGKAP & RELEVAN: Lanjutkan jawabanmu secara tuntas, akurat, dan terstruktur menyambung respons sebelumnya. Patuhi gaya bahasa & kata ganti aktifmu.\n"
                                f"- JIKA HASIL TIDAK RELEVAN, SALAH DOKUMEN, ATAU KURANG LENGKAP: Kamu WAJIB LANGSUNG MEMANGGIL ALAT LAGI (misal ```docsearch dengan kata kunci substansi yang lebih spesifik, atau ```websearch jika topik tidak ada di arsip internal) DI BAWAH KALIMATMU SEKARANG JUGA! DILARANG KERAS hanya berjanji dalam bentuk teks tanpa menyertakan blok pemanggilan alatnya!\n"
                                f"Tetap konsisten menjaga gaya bahasa aktifmu. JANGAN mengulangi sapaan awal."
                            )
                        if loop_count + 1 >= max_tool_loops:
                            continuation_instruction += "\n(Batas panggilan alat tercapai: Berikan simpulan akhir tuntas sekarang tanpa memanggil alat lagi)."

                        current_messages.append({"role": "assistant", "content": pre_tool_text.strip()})
                        current_messages.append({"role": "user", "content": continuation_instruction})
                        
                        loop_count += 1
                        break # Break dari inner stream untuk memulai loop berikutnya

            if is_capturing_sources and sources_buffer:
                is_capturing_sources = False
                sources_emitted = True
                try:
                    final_sources = await resolve_and_enrich_sources(sources_buffer.strip(), current_rag_sources)
                    if final_sources:
                        logger.info(f"[AGENTIC_INTERCEPTOR] 📚 Emitting {len(final_sources)} sources at stream end")
                        yield format_sse("", "", False, sources=final_sources, event_type=SSEEventType.SOURCES)
                except Exception as e:
                    logger.warning(f"[AGENTIC_INTERCEPTOR] Incomplete sources_buffer parse at stream end: {e}")

            if not tool_executed and buffer:
                # Bersihkan jika buffer menyisakan potongan tag <sources_json>
                if not sources_emitted and buffer.strip().startswith("<") and "<sources_json>".startswith(buffer.strip().lower()):
                    buffer = ""
                if buffer:
                    yield format_sse(buffer, "", False, event_type=SSEEventType.CHUNK, is_truncated=was_truncated)
                    accumulated_full_text += buffer
                    buffer = ""
            elif not tool_executed and was_truncated:
                yield format_sse("", "", False, event_type=SSEEventType.CHUNK, is_truncated=True)

        except Exception as e:
            logger.error(f"[AGENTIC_TOOL] Error in agentic stream loop: {e}", exc_info=True)
            yield format_sse(f"\n\n[Terjadi kendala saat memproses: {str(e)}]", "", False, event_type=SSEEventType.CHUNK)
            return

        if not tool_executed:
            break
