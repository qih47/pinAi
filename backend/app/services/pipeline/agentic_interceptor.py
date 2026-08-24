"""
Agentic Stream Interceptor for CAKRA AI (Call 2 ReAct Loop)
===========================================================
Mendeteksi dan menangani Autonomous Tool-Calling (seperti ```websearch) di tengah
stream Call 2 secara non-destruktif tanpa mengganggu alur teks reguler.
"""

import json
import re
import asyncio
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.web_tools.web_search import perform_web_search, format_search_results_for_llm
from backend.app.services.web_tools.url_reader import fetch_webpage_content

logger = logging.getLogger("CAKRA_AGENTIC_INTERCEPTOR")

_RE_WEBSEARCH_OPEN = re.compile(r"```websearch", re.IGNORECASE)
_RE_TRIPLE_BACKTICKS = re.compile(r"```")


async def execute_in_line_web_search(query: str) -> tuple[Dict[str, Any], str]:
    """
    Menjalankan pencarian web live + scraping paralel untuk in-line tool call.
    Mengembalikan (widget_payload, llm_context_text).
    """
    clean_query = query.strip()
    logger.info(f"[AGENTIC_TOOL] Executing in-line web search for query: '{clean_query}'")
    
    # 1. Search via SearXNG (5-8 hasil)
    raw_results = await perform_web_search(clean_query, num_results=6)
    
    if not raw_results:
        widget_payload = {
            "query": clean_query,
            "results": []
        }
        return widget_payload, f"Tidak ditemukan hasil pencarian web yang valid untuk query: '{clean_query}'."

    # 2. Rerank jika memungkinkan
    search_results = raw_results
    try:
        from backend.app.services.rag.reranker_service import reranker_service
        corpus_texts = [f"{r.get('title', '')} {r.get('content', '')}".strip() for r in raw_results]
        scores = await reranker_service.compute_scores(clean_query, corpus_texts)
        ranked = sorted(zip(scores, raw_results), key=lambda x: x[0], reverse=True)
        search_results = [r for _, r in ranked[:4]]
    except Exception as e:
        logger.warning(f"[AGENTIC_TOOL] Rerank fallback: {e}")
        search_results = raw_results[:4]

    # 3. Format payload widget untuk Frontend
    widget_payload = {
        "query": clean_query,
        "results": search_results
    }

    # 4. Format context teks untuk LLM
    web_context = format_search_results_for_llm(search_results)
    
    # 5. Quick scrape 2 top URLs jika memungkinkan untuk konteks mendalam
    top_urls = [r["url"] for r in search_results[:2] if r.get("url")]
    if top_urls:
        async def _scrape_one(u: str) -> str:
            try:
                c = await fetch_webpage_content(u)
                return c[:3000] if c else ""
            except Exception:
                return ""
        
        scraped_contents = await asyncio.gather(*[_scrape_one(u) for u in top_urls])
        extra_text = "\n\n".join([f"--- KONTEN SITUS ({top_urls[i]}) ---\n{scraped_contents[i]}" for i in range(len(top_urls)) if scraped_contents[i]])
        if extra_text:
            web_context += f"\n\n=== DETAIL KONTEN WEB TERBARU ===\n{extra_text}"

    return widget_payload, web_context


async def agentic_stream_wrapper(
    model_name: str,
    messages: List[Dict[str, str]],
    request: Optional[Request] = None,
    temperature: float = 0.6,
    num_ctx: int = 32768,
    is_thinking: bool = False,
    employee_name: str = "Pegawai",
    session_uuid: Optional[str] = None,
    max_tool_loops: int = 1
) -> AsyncGenerator[str, None]:
    """
    Membungkus stream_ollama_chat dengan ReAct interceptor.
    Jika tidak ada tool call, stream dialirkan langsung tanpa delay (zero overhead).
    Jika model mengeluarkan ```websearch, tool dieksekusi dan jawabannya dilanjutkan di bubble yang sama.
    """
    accumulated_full_text = ""
    current_messages = list(messages)
    loop_count = 0

    while loop_count <= max_tool_loops:
        stream_gen = stream_ollama_chat(
            model_name=model_name,
            messages=current_messages,
            request=request,
            temperature=temperature,
            keep_alive=-1,
            num_ctx=num_ctx,
            num_predict=-1,
            is_thinking=is_thinking,
        )

        buffer = ""
        is_capturing_tool = False
        tool_tag = None
        tool_buffer = ""
        tool_executed = False
        tool_query = None
        pre_tool_text = ""

        try:
            async for chunk_line in stream_gen:
                try:
                    chunk_data = json.loads(chunk_line.strip())
                    chunk_text = chunk_data.get("chunk", "")
                    native_thought = chunk_data.get("thinking", "")
                    eval_count = chunk_data.get("eval_count", 0)
                    eval_duration = chunk_data.get("eval_duration", 0)
                except (json.JSONDecodeError, AttributeError):
                    chunk_text = chunk_line if isinstance(chunk_line, str) else ""
                    native_thought = ""
                    eval_count = 0
                    eval_duration = 0

                # 1. Forward thinking chunks as usual
                if native_thought and is_thinking:
                    yield format_sse("", native_thought, False, event_type=SSEEventType.THINKING)

                if not chunk_text:
                    if eval_count > 0 and not is_capturing_tool:
                        yield format_sse("", "", False, event_type=SSEEventType.CHUNK, eval_count=eval_count, eval_duration=eval_duration)
                    continue

                # 2. Track text stream
                if not is_capturing_tool:
                    buffer += chunk_text
                    
                    # Deteksi pembuka blok ```websearch
                    open_match = _RE_WEBSEARCH_OPEN.search(buffer)
                    if open_match:
                        # Teks sebelum blok ```websearch dialirkan langsung ke user
                        preamble = buffer[:open_match.start()]
                        if preamble:
                            yield format_sse(preamble, "", False, event_type=SSEEventType.CHUNK)
                            accumulated_full_text += preamble
                            pre_tool_text += preamble

                        is_capturing_tool = True
                        tool_tag = "websearch"
                        # Sisakan karakter setelah ```websearch
                        tool_buffer = buffer[open_match.end():]
                        buffer = ""
                        logger.info("[AGENTIC_TOOL] 🎯 Intercepted ```websearch open tag during stream!")
                    else:
                        # Belum ada tanda tag tool, alirkan teks dengan aman (sisakan 12 karakter untuk potensi pembuka tag)
                        if len(buffer) > 15:
                            safe_to_flush = buffer[:-12]
                            buffer = buffer[-12:]
                            yield format_sse(safe_to_flush, "", False, event_type=SSEEventType.CHUNK)
                            accumulated_full_text += safe_to_flush
                            pre_tool_text += safe_to_flush
                else:
                    # Sedang menangkap isi JSON di dalam blok ```websearch
                    tool_buffer += chunk_text
                    close_match = _RE_TRIPLE_BACKTICKS.search(tool_buffer)
                    if close_match:
                        # Blok tool selesai ditutup!
                        raw_json_str = tool_buffer[:close_match.start()].strip()
                        remaining_text = tool_buffer[close_match.end():]
                        
                        logger.info(f"[AGENTIC_TOOL] Extracted tool JSON payload: {raw_json_str}")
                        try:
                            parsed_payload = json.loads(raw_json_str)
                            tool_query = parsed_payload.get("query") or parsed_payload.get("q")
                        except Exception as parse_err:
                            logger.warning(f"[AGENTIC_TOOL] JSON parse failed, trying regex: {parse_err}")
                            m_q = re.search(r'["\']query["\']\s*:\s*["\']([^"\']+)["\']', raw_json_str)
                            tool_query = m_q.group(1) if m_q else raw_json_str.replace("{", "").replace("}", "").strip()

                        if tool_query:
                            tool_executed = True
                            is_capturing_tool = False
                            
                            # Emit live status SSE
                            yield format_sse(status="🌐 Mencari di web", event_type=SSEEventType.STATUS)
                            await asyncio.sleep(0.01)

                            # Eksekusi Web Search
                            widget_payload, web_context = await execute_in_line_web_search(tool_query)
                            
                            # Kirim enriched websearch markdown block ke UI
                            enriched_block = f"\n```websearch\n{json.dumps(widget_payload)}\n```\n\n"
                            yield format_sse(enriched_block, "", False, event_type=SSEEventType.CHUNK)
                            accumulated_full_text += enriched_block

                            # Update status
                            yield format_sse(status="💡 Menyusun jawaban", event_type=SSEEventType.STATUS)
                            await asyncio.sleep(0.01)

                            # Siapkan Turn 2 Prompt untuk melanjutkan jawaban
                            continuation_instruction = (
                                f"\n\n[SISTEM: HASIL PENCARIAN WEB UNTUK '{tool_query}']:\n"
                                f"{web_context}\n\n"
                                f"[INSTRUKSI LANJUTAN]:\n"
                                f"Kamu telah mendapatkan data pencarian web di atas. Lanjutkan jawabanmu SEKARANG secara natural dari teks pembuka yang telah kamu katakan sebelumnya.\n"
                                f"Sajikan data cuaca/informasi tersebut secara detail, lengkap dengan tabel (```datagrid) atau grafik tren (```recharts) jika relevan. JANGAN ulangi sapaan awal."
                            )

                            current_messages.append({"role": "assistant", "content": pre_tool_text.strip()})
                            current_messages.append({"role": "user", "content": continuation_instruction})
                            
                            loop_count += 1
                            break # Break dari inner stream generator untuk memulai Turn 2
                        else:
                            # Jika tidak ada query valid, kembalikan buffer sebagai teks
                            fallback_text = f"```websearch\n{raw_json_str}\n```"
                            yield format_sse(fallback_text, "", False, event_type=SSEEventType.CHUNK)
                            accumulated_full_text += fallback_text
                            is_capturing_tool = False

            # Flush sisa buffer normal jika tool tidak dieksekusi
            if not tool_executed and buffer:
                yield format_sse(buffer, "", False, event_type=SSEEventType.CHUNK)
                accumulated_full_text += buffer
                buffer = ""

        except Exception as e:
            logger.error(f"[AGENTIC_TOOL] Error in agentic stream loop: {e}", exc_info=True)
            yield format_sse(f"\n\n[Terjadi kendala saat memproses: {str(e)}]", "", False, event_type=SSEEventType.CHUNK)
            return

        if not tool_executed:
            # Tidak ada tool yang dipanggil atau loop sudah selesai normal
            break
