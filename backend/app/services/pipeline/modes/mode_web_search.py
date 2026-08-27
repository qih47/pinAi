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
        target_queries = [q.strip() for q in queries_from_call1 if isinstance(q, str) and q.strip()]
    else:
        target_queries = [query.strip()] if query.strip() else []

    if not target_queries:
        target_queries = [query]

    # Bersihkan duplikat
    seen_q = set()
    clean_target_queries = []
    for q in target_queries:
        if q.lower() not in seen_q:
            seen_q.add(q.lower())
            clean_target_queries.append(q)

    display_query = " & ".join(clean_target_queries)
    logger.info(f"[Web Search] queries: {clean_target_queries} | display: '{display_query}'")
    yield format_sse(status="🌐 Mencari di web", event_type=SSEEventType.STATUS)
    await asyncio.sleep(0.01)
    
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

    # 2. ⚡ Lakukan pencarian web paralel untuk SEMUA target queries
    search_tasks = [perform_web_search(q, num_results=12) for q in clean_target_queries]
    search_results_lists = await asyncio.gather(*search_tasks)

    # Gabung dan deduplikasi URL
    seen_urls = set()
    raw_search_results = []
    for r_list in search_results_lists:
        for r in r_list:
            u = r.get("url")
            if u and u not in seen_urls:
                seen_urls.add(u)
                raw_search_results.append(r)
    
    # 2.1 Rerank hasil search berdasarkan relevansi query gabungan
    search_results = raw_search_results
    if search_results:
        try:
            from backend.app.services.rag.reranker_service import reranker_service
            corpus_texts = [
                f"{r.get('title', '')} {r.get('content', '')}".strip()
                for r in search_results
            ]
            rerank_query = " ".join(clean_target_queries)
            scores = await reranker_service.compute_scores(rerank_query, corpus_texts)
            
            # Urutkan search_results berdasarkan skor reranker
            ranked = sorted(
                zip(scores, search_results),
                key=lambda x: x[0],
                reverse=True
            )
            
            # Dynamic Filter: Ambil hanya yang relevan (skor >= 0.40), batasi dinamis antara 2 sampai 10 hasil
            relevant_results = [r for s, r in ranked if s >= 0.40]
            if len(relevant_results) < 2:
                search_results = [r for _, r in ranked[:2]] # Fallback minimal 2 terbaik
            else:
                max_res = 10 if len(clean_target_queries) > 1 else 7
                search_results = relevant_results[:max_res]
                
            logger.info(f"[Web Search] Dynamically filtered {len(search_results)} relevant search results (from {len(ranked)} raw). Top: '{search_results[0]['title']}'")
        except Exception as e:
            logger.warning(f"[Web Search] Reranker gagal (fallback top 5): {e}")
            search_results = search_results[:5]

    # 3. Gabungkan: URL yg sudah di-read masuk sebagai result PERTAMA di widget
    combined_results = pre_fetched_url_entries + search_results
    
    # 4. Kirim Markdown blok custom untuk dirender widget web search di Frontend
    search_payload = {
        "query": display_query,
        "results": combined_results  # Dinamis sesuai jumlah hasil relevan
    }
    widget_markdown = f"```websearch\n{json.dumps(search_payload)}\n```\n\n"
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
        yield format_sse(status=f"📖 Membaca {len(top_urls)} tautan", event_type=SSEEventType.STATUS)
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
        
        # CHUNKING & RERANKING
        from backend.app.services.rag.reranker_service import reranker_service
        
        def chunk_text(text: str, source: str, chunk_size: int = 1500, overlap: int = 200) -> List[Dict[str, str]]:
            chunks = []
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunks.append({
                    "text": text[start:end],
                    "source": source
                })
                start += chunk_size - overlap
            return chunks

        all_chunks = []
        for url, content in zip(top_urls, scrape_results):
            if content.strip():
                all_chunks.extend(chunk_text(content.strip(), url))
                
        if all_chunks:
            yield format_sse(status="🎯 Menyaring fakta penting", event_type=SSEEventType.STATUS)
            await asyncio.sleep(0.01)
            
            chunk_texts = [c["text"] for c in all_chunks]
            scores = await reranker_service.compute_scores(display_query, chunk_texts)
            
            scored_chunks = []
            for i, score in enumerate(scores):
                scored_chunks.append({
                    "text": chunk_texts[i],
                    "source": all_chunks[i]["source"],
                    "score": score
                })
                
            # Ambil Top potongan terbaik (maksimal 15 chunks, relevan dari hasil BGE)
            scored_chunks.sort(key=lambda x: x["score"], reverse=True)
            top_chunks = scored_chunks[:15]
            
            combined_deep = "\n\n---\n\n".join(
                f"[Sumber: {c['source']}]\n{c['text']}"
                for c in top_chunks
            )
            
            web_context += "\n\n=== KONTEN MENDALAM DARI TAUTAN TERATAS (FILTERED & RERANKED) ===\n"
            web_context += combined_deep
            logger.info(f"[Web Search] Reranking complete. Selected {len(top_chunks)} top chunks from {len(all_chunks)}.")

    
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
    
    yield format_sse(status="💡 Menyusun ringkasan", event_type=SSEEventType.STATUS)
    await asyncio.sleep(0.01)

    # 5. Mulai streaming jawaban dari LLM dengan num_ctx=16384 dan num_predict=-1 (tak terbatas)
    response_stream = stream_ollama_chat(
        messages=modified_messages,
        model_name=getattr(settings, "MODEL_PERSONA", "gemma4:12b"),
        is_thinking=is_thinking,
        temperature=0.4,
        num_ctx=16384,
        num_predict=-1,
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
