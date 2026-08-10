import json
import logging
from typing import Dict, Any, List
import asyncio

from backend.app.core.config import settings
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.web_tools.web_search import perform_web_search, format_search_results_for_llm
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.pipeline.prompts.core_prompts import build_web_search_prompt

logger = logging.getLogger("cakra.pipeline.mode_web_search")


def _clean_query(query: str) -> str:
    """Wrapper ringan yang memanggil mode_utils.build_clean_web_search_query."""
    try:
        from backend.app.services.pipeline.modes.mode_utils import build_clean_web_search_query
        return build_clean_web_search_query(query)
    except Exception:
        return query

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
    
    # Bersihkan query dari kata instruksi / basa-basi sebelum ke Google
    clean_query = _clean_query(query)
    logger.info(f"Entered Web Search Mode for query: {query} → cleaned: {clean_query}")
    yield format_sse(status="🌐 Melakukan penelusuran web...", event_type=SSEEventType.STATUS)
    await asyncio.sleep(0.01)
    
    # 1. Ambil URL-read content yang sudah di-fetch oleh url_reader di mode_hub (jika ada)
    # Ini terjadi saat user mengetik domain seperti "pindad.com" di pesannya
    pre_fetched_content = precheck.get("_session_chunks_text", "")
    pre_fetched_url_entries = []
    if precheck.get("has_url_context"):
        from backend.app.services.web_tools.url_reader import extract_urls_from_text
        detected_urls = extract_urls_from_text(query)
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

    # 2. Lakukan pencarian web menggunakan clean_query (limit ditambah menjadi 10)
    search_results = await perform_web_search(clean_query, num_results=10)
    
    # 3. Gabungkan: URL yg sudah di-read masuk sebagai result PERTAMA di widget
    combined_results = pre_fetched_url_entries + search_results
    
    # 4. Kirim Markdown blok custom untuk dirender widget web search di Frontend
    search_payload = {
        "query": clean_query,
        "results": combined_results[:12]  # cap 12 hasil di UI
    }
    search_json = json.dumps(search_payload)
    widget_markdown = f"```websearch\n{search_json}\n```\n\n"
    yield format_sse(chunk=widget_markdown, event_type=SSEEventType.CHUNK)
    await asyncio.sleep(0.01)
    
    # 5. Format hasil pencarian untuk dimasukkan ke konteks LLM
    web_context = format_search_results_for_llm(search_results)
    
    # 5.1. Tambahkan konten URL yang sudah di-fetch sebelumnya ke konteks LLM
    if pre_fetched_content and "[KONTEN WEB DARI URL DI CHAT]" in pre_fetched_content:
        # Ekstrak hanya bagian konten web (bukan knowledge dari file lain)
        url_section = pre_fetched_content.split("[KONTEN WEB DARI URL DI CHAT]")[-1].strip()
        if url_section:
            web_context += f"\n\n=== KONTEN LANGSUNG DARI URL YANG DISEBUTKAN USER ===\n{url_section[:20000]}"
            logger.info(f"[Web Search] Injected pre-fetched URL content ({len(url_section)} chars) into LLM context")
    
    # 5.2. ⚡ PARALLEL Deep scraping: semua top URL di-crawl bersamaan
    top_urls = [r["url"] for r in search_results[:3] if r.get("engine") != "url_reader"]
    if top_urls:
        yield format_sse(status=f"📖 Membaca mendalam dari {len(top_urls)} tautan secara paralel...", event_type=SSEEventType.STATUS)
        await asyncio.sleep(0.01)
        
        from backend.app.services.web_tools.url_reader import fetch_webpage_content
        
        async def _scrape_one(url: str) -> str:
            try:
                content = await fetch_webpage_content(url)
                return content or ""
            except Exception as e:
                logger.warning(f"[Web Search] Deep scrape failed for {url}: {e}")
                return ""
        
        # Semua URL di-crawl secara paralel
        scrape_results = await asyncio.gather(*[_scrape_one(url) for url in top_urls])
        
        combined_deep = "\n\n---\n\n".join(
            f"[Sumber: {url}]\n{content[:8000]}"
            for url, content in zip(top_urls, scrape_results)
            if content.strip()
        )
        if combined_deep:
            if len(combined_deep) > 16000:
                combined_deep = combined_deep[:16000] + "\n\n...[TRUNCATED UNTUK MENGHEMAT TOKENS]..."
            web_context += "\n\n=== KONTEN MENDALAM DARI TAUTAN TERATAS ===\n"
            web_context += combined_deep


    
    # 4. Bangun system prompt
    system_prompt = build_web_search_prompt(
        employee_name=employee_name,
        web_context=web_context,
        precheck=precheck
    )

    modified_messages = [m for m in messages if m["role"] != "system"]
    modified_messages.insert(0, {"role": "system", "content": system_prompt})
    
    yield format_sse(status="💡 Menyusun jawaban dari berbagai sumber web...", event_type=SSEEventType.STATUS)
    await asyncio.sleep(0.01)

    # 5. Mulai streaming jawaban dari LLM
    response_stream = stream_ollama_chat(
        messages=modified_messages,
        model_name=getattr(settings, "MODEL_PERSONA", "gemma4:12b"),
        is_thinking=is_thinking,
        temperature=0.4,
        num_ctx=16384,
        request=request
    )
    
    async for chunk_line in response_stream:
        try:
            chunk = json.loads(chunk_line.strip())
        except json.JSONDecodeError:
            continue

        event_type = chunk.get("event_type", "chunk")
        if event_type == "chunk":
            char = chunk.get("chunk", "")
            thought = chunk.get("thinking", "")
            
            if thought:
                yield format_sse(thinking=thought, event_type=SSEEventType.THINKING)
            elif char:
                yield format_sse(chunk=char, event_type=SSEEventType.CHUNK)
        elif event_type == "status":
            yield format_sse(status=chunk.get("status", ""), event_type=SSEEventType.STATUS)
    
    yield format_sse(status="Selesai", event_type=SSEEventType.STATUS)
