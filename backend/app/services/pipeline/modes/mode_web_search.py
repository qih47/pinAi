import json
import logging
from typing import Dict, Any, List
import asyncio

from backend.app.core.config import settings
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.web_tools.web_search import (
    execute_web_search_pipeline_stream,
    sanitize_web_query,
)
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.pipeline.prompts.core_prompts import build_web_search_prompt

logger = logging.getLogger("cakra.pipeline.mode_web_search")


async def handle_web_search(
    query: str,
    messages: List[Dict[str, str]],
    request: Any,
    db: Any = None,
    employee_name: str = "Pegawai",
    precheck: Dict[str, Any] = None,
    is_thinking: bool = False
):
    """
    Menangani pencarian web dan sintesis jawaban LLM.
    """
    if precheck is None:
        precheck = {}
    
    # Ambil semua query dari Call 1 (mendukung multi-query paralel untuk komparasi / multi-topik)
    queries_from_call1 = precheck.get("queries", [])
    if isinstance(queries_from_call1, list) and queries_from_call1:
        target_queries = [sanitize_web_query(q.strip(), user_message=query) for q in queries_from_call1 if isinstance(q, str) and q.strip()]
    else:
        target_queries = [sanitize_web_query(query.strip(), user_message=query)] if query.strip() else []

    target_queries = [q for q in target_queries if q]
    if not target_queries:
        target_queries = [query.strip()]

    # Bersihkan duplikat
    seen_q = set()
    clean_target_queries = []
    for q in target_queries:
        if q.lower() not in seen_q:
            seen_q.add(q.lower())
            clean_target_queries.append(q)

    display_query = " & ".join(clean_target_queries)
    logger.info(f"[Web Search] queries: {clean_target_queries} | display: '{display_query}'")
    yield format_sse(status="🌐 Mencari di web", status_key="WEB_SEARCH_INIT", event_type=SSEEventType.STATUS)
    
    # 1. Ambil URL-read content yang sudah di-fetch oleh url_reader di mode_hub (jika ada)
    # Ini terjadi saat user mengetik domain seperti "pindad.com" di pesannya
    pre_fetched_content = precheck.get("_session_chunks_text", "")
    pre_fetched_url_entries = []
    if precheck.get("has_url_context"):
        from backend.app.services.web_tools.url_reader import extract_urls_from_text
        detected_urls = extract_urls_from_text(display_query)
        for url in detected_urls:
            # Bersihkan spasi dari url (misal "pindad. com")
            url = url.replace(" ", "")
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc or parsed.path
                pre_fetched_url_entries.append({
                    "title": f"Halaman resmi: {domain}",
                    "url": url,
                    "content": f"Konten halaman {domain} telah dibaca langsung oleh sistem.",
                    "engine": "url_reader"
                })
            except Exception:
                pass
        logger.info(f"[Web Search] Injecting {len(pre_fetched_url_entries)} pre-fetched URL(s) into widget: {detected_urls}")

    # 2. ⚡ Eksekusi Web Search Pipeline terpusat (Single Source of Truth)
    web_search_result = None
    async for event in execute_web_search_pipeline_stream(
        queries=clean_target_queries,
        user_message=query,
        pre_fetched_urls=pre_fetched_url_entries,
        pre_fetched_content=pre_fetched_content,
        num_raw_results=12,
        scrape_top_k=3,
    ):
        if event.event_type == "SEARCHING":
            yield format_sse(status="🌐 Mencari di web", status_key="WEB_SEARCH_INIT", event_type=SSEEventType.STATUS)
        elif event.event_type == "RERANKING":
            yield format_sse(status="Menyaring rujukan web", status_key="TOOL_WEBSEARCH_RERANKING", event_type=SSEEventType.STATUS)
        elif event.event_type == "RANKED":
            search_payload = {
                "query": event.data.get("display_query", display_query),
                "results": event.data.get("search_results", [])
            }
            widget_markdown = f"```websearch\n{json.dumps(search_payload)}\n```\n\n"
            yield format_sse(chunk=widget_markdown, event_type=SSEEventType.CHUNK)
        elif event.event_type == "SCRAPING":
            top_urls = event.data.get("top_urls", [])
            yield format_sse(status=f"📖 Membaca {len(top_urls)} tautan", status_key="READING_URLS", event_type=SSEEventType.STATUS)
        elif event.event_type == "FILTERING_FACTS":
            yield format_sse(status="🎯 Menyaring fakta penting", status_key="FILTERING_FACTS", event_type=SSEEventType.STATUS)
        elif event.event_type == "RESULT":
            web_search_result = event.data

    web_context = web_search_result.llm_context if web_search_result else "Tidak ada hasil pencarian."

    
    # 4. Bangun system prompt
    system_prompt = build_web_search_prompt(
        employee_name=employee_name,
        web_context=web_context,
        precheck=precheck
    )

    # Inject Employee Long-Term Memory (ai_memory)
    current_user_npp = getattr(request.state, "user", {}).get("npp") if request and hasattr(request, "state") and hasattr(request.state, "user") else None
    if current_user_npp and current_user_npp != "GUEST":
        from backend.app.services.memory.memory_service import memory_service
        employee_memory = await memory_service.get_employee_long_term_memory(current_user_npp)
        if employee_memory:
            system_prompt += employee_memory

    # Trim riwayat chat (ambil 10 pesan terakhir) agar context budget tetap optimal
    trimmed_history = messages[-10:] if len(messages) > 10 else messages
    modified_messages = [m for m in trimmed_history if m["role"] != "system"]
    modified_messages.insert(0, {"role": "system", "content": system_prompt})
    
    yield format_sse(status="💡 Menyusun ringkasan", status_key="DRAFTING_SUMMARY", event_type=SSEEventType.STATUS)

    # 5. Mulai streaming jawaban dari LLM via Agentic Interceptor (num_ctx=16384, num_predict=-1)
    try:
        from backend.app.services.pipeline.agentic_interceptor import agentic_stream_wrapper
        async for chunk in agentic_stream_wrapper(
            model_name=getattr(settings, "MODEL_PERSONA", "gemma4:31b"),
            messages=modified_messages,
            request=request,
            is_thinking=is_thinking,
            employee_name=employee_name,
            session_uuid=precheck.get("session_uuid") if precheck else None,
            temperature=0.4,
            num_ctx=16384,
            num_predict=-1,
            max_tool_loops=2,
        ):
            yield chunk
    except Exception as e:
        logger.error(f"[MODE_WEB_SEARCH] Stream error: {e}", exc_info=True)
        yield format_sse(f"Maaf, terjadi kendala teknis saat menyusun ringkasan: {str(e)}", "", False, event_type=SSEEventType.CHUNK)

    logger.info(f"[CALL2_WEB_SEARCH] ✅ Finished generation | needs_history={precheck.get('needs_history', False)} | turns_sent={len(modified_messages)-1}")
    yield format_sse(status="Selesai", event_type=SSEEventType.STATUS)
