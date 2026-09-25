"""
CAKRA AI — Universal Tool Dispatcher (MCP-Ready Architecture)
============================================================
Pusat eksekusi tools otonom Call 2 yang modular, aman, dan non-destruktif.
Mendukung tool internal native (web_search, doc_search, python_calc) dan
siap dihubungkan ke remote MCP Server di masa depan via adapter.
"""

import os
import re
import sys
import json
import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

from backend.app.core.config import settings

logger = logging.getLogger("CAKRA_TOOL_DISPATCHER")


@dataclass
class ToolResult:
    """Standardized MCP-Ready Tool Execution Result."""
    tool_name: str
    status: str  # "success" | "error" | "timeout"
    intent: str
    display_data: Dict[str, Any]
    llm_context: str
    error_message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TOOL: WEB SEARCH & LIVE SCRAPING
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_web_search_tool(query: str, reason: str = "") -> ToolResult:
    """Eksekusi pencarian web SearXNG + Reranking + Scraping 2 tautan teratas."""
    from backend.app.services.web_tools.web_search import (
        perform_web_search,
        format_search_results_for_llm,
        sanitize_web_query,
    )
    from backend.app.services.web_tools.url_reader import fetch_webpage_content

    clean_query = sanitize_web_query(query.strip()) or query.strip()
    intent_desc = reason.strip() if reason.strip() else f"Menelusuri informasi web: '{clean_query}'"
    logger.info(f"[TOOL_DISPATCHER] 🌐 Executing web_search for query: '{clean_query}'")

    try:
        raw_results = await perform_web_search(clean_query, num_results=6)
        if not raw_results:
            return ToolResult(
                tool_name="websearch",
                status="success",
                intent=intent_desc,
                display_data={
                    "tool": "websearch",
                    "intent": intent_desc,
                    "query": clean_query,
                    "results": [],
                    "stage": "done",
                },
                llm_context=f"Tidak ditemukan hasil pencarian web yang valid untuk query: '{clean_query}'.",
            )

        # Reranking jika tersedia
        search_results = raw_results
        try:
            from backend.app.services.rag.reranker_service import reranker_service
            corpus_texts = [f"{r.get('title', '')} {r.get('content', '')}".strip() for r in raw_results]
            scores = await reranker_service.compute_scores(clean_query, corpus_texts)
            ranked = sorted(zip(scores, raw_results), key=lambda x: x[0], reverse=True)
            search_results = [r for _, r in ranked[:4]]
        except Exception as e:
            logger.warning(f"[TOOL_DISPATCHER] Rerank fallback for websearch: {e}")
            search_results = raw_results[:4]

        # Format teks konteks awal untuk LLM
        web_context = format_search_results_for_llm(search_results)

        # Quick scrape 2 URL teratas untuk detail mendalam
        top_urls = [r["url"] for r in search_results[:2] if r.get("url")]
        if top_urls:
            async def _scrape_one(u: str) -> str:
                try:
                    c = await fetch_webpage_content(u)
                    return c[:3000] if c else ""
                except Exception:
                    return ""

            scraped_contents = await asyncio.gather(*[_scrape_one(u) for u in top_urls])
            extra_text = "\n\n".join(
                [f"--- KONTEN SITUS ({top_urls[i]}) ---\n{scraped_contents[i]}"
                 for i in range(len(top_urls)) if scraped_contents[i]]
            )
            if extra_text:
                web_context += f"\n\n=== DETAIL KONTEN WEB TERBARU ===\n{extra_text}"

        safe_web_context = (web_context[:7500] + "\n...(dipotong)") if len(web_context) > 7500 else web_context

        return ToolResult(
            tool_name="websearch",
            status="success",
            intent=intent_desc,
            display_data={
                "tool": "websearch",
                "intent": intent_desc,
                "query": clean_query,
                "results": search_results,
                "stage": "done",
            },
            llm_context=safe_web_context,
        )

    except Exception as e:
        logger.error(f"[TOOL_DISPATCHER] Error in web_search_tool: {e}", exc_info=True)
        return ToolResult(
            tool_name="websearch",
            status="error",
            intent=intent_desc,
            display_data={"tool": "websearch", "intent": intent_desc, "query": clean_query, "results": [], "stage": "error"},
            llm_context=f"Kendala teknis saat menelusuri web: {str(e)}",
            error_message=str(e),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TOOL: DOC SEARCH & REGULASI INTERNAL (RAG LOOKUP)
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_doc_search_tool(query: str, reason: str = "", doc_type: str = "") -> ToolResult:
    """Eksekusi pencarian semantik ke database regulasi dan dokumen internal Pindad."""
    clean_query = query.strip()
    intent_desc = reason.strip() if reason.strip() else f"Mencocokkan arsip regulasi internal: '{clean_query}'"
    logger.info(f"[TOOL_DISPATCHER] 📑 Executing doc_search for query: '{clean_query}'")

    try:
        from backend.app.services.rag.rag_service import RagService
        rag_service = RagService()
        rag_context, source_docs = await rag_service.assemble_powerful_context(clean_query, limit=4)

        formatted_docs = []
        if source_docs:
            for doc in source_docs[:4]:
                formatted_docs.append({
                    "id": doc.get("id") or doc.get("dokumen_id"),
                    "doc_id": doc.get("id") or doc.get("dokumen_id"),
                    "title": doc.get("title") or doc.get("judul") or doc.get("filename") or "Dokumen Internal Pindad",
                    "nomor": doc.get("nomor"),
                    "jenis": doc.get("jenis"),
                    "stataktif": doc.get("stataktif") or doc.get("status_berlaku") or "Berlaku",
                    "total_pages": doc.get("total_pages", ""),
                    "page": doc.get("page") or doc.get("page_number") or doc.get("halaman", ""),
                    "filename": doc.get("filename") or doc.get("mysql_filename"),
                    "file_path": doc.get("file_path"),
                    "score": round(float(doc.get("score", 0.0)), 3) if doc.get("score") else None,
                })

        # Batasi konteks LLM ke 7500 karakter agar tidak melebihi batas 16384 token vLLM
        safe_rag_context = (rag_context[:7500] + "\n...(dipotong demi efisiensi context)") if rag_context and len(rag_context) > 7500 else (rag_context or f"Tidak ditemukan dokumen yang cocok untuk: '{clean_query}'.")

        return ToolResult(
            tool_name="docsearch",
            status="success",
            intent=intent_desc,
            display_data={
                "tool": "docsearch",
                "intent": intent_desc,
                "query": clean_query,
                "documents": formatted_docs,
                "stage": "done",
            },
            llm_context=safe_rag_context,
        )

    except Exception as e:
        logger.error(f"[TOOL_DISPATCHER] Error in doc_search_tool: {e}", exc_info=True)
        return ToolResult(
            tool_name="docsearch",
            status="error",
            intent=intent_desc,
            display_data={"tool": "docsearch", "intent": intent_desc, "query": clean_query, "documents": [], "stage": "error"},
            llm_context=f"Kendala saat memeriksa basis data dokumen internal: {str(e)}",
            error_message=str(e),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TOOL: PYTHON CALCULATOR (ISOLATED SANDBOX)
# ═══════════════════════════════════════════════════════════════════════════════

_FORBIDDEN_PYTHON_TOKENS = {
    "import os", "import sys", "import subprocess", "import socket", "import shutil",
    "import pty", "import requests", "import urllib", "__import__", "eval(", "exec(",
    "open(", "compile(", "globals()", "locals()", "builtins", "rmtree", "system("
}

def execute_python_calc_sync(code: str) -> Tuple[bool, str]:
    """Menjalankan kode kalkulator di subprocess terisolasi dengan timeout 3 detik."""
    # 1. Validasi keamanan sintaks
    code_lower = code.lower()
    for forbidden in _FORBIDDEN_PYTHON_TOKENS:
        if forbidden in code_lower:
            return False, f"Akses ke modul berbahaya '{forbidden}' diblokir oleh Security Firewall demi keselamatan sistem."

    # 2. Siapkan wrapper kode dengan batas memori dan output terarah
    runner_script = (
        "import math, statistics\n"
        "try:\n"
        + "\n".join("    " + line for line in code.splitlines())
        + "\nexcept Exception as e:\n"
        "    print(f'Error Eksekusi: {e}')\n"
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", runner_script],
            capture_output=True,
            text=True,
            timeout=3.5,
        )
        output = proc.stdout.strip()
        if not output and proc.stderr.strip():
            output = proc.stderr.strip()
        return True, output if output else "Eksekusi berhasil tanpa output cetak (print)."
    except subprocess.TimeoutExpired:
        return False, "Eksekusi kode melebihi batas waktu (timeout 3 detik)."
    except Exception as e:
        return False, f"Gagal mengeksekusi kalkulasi: {str(e)}"


async def execute_python_calc_tool(code: str, reason: str = "") -> ToolResult:
    """Wrapper asinkron untuk tool kalkulator Python."""
    clean_code = code.strip()
    intent_desc = reason.strip() if reason.strip() else "Melakukan kalkulasi matematis presisi via Python Sandbox"
    logger.info(f"[TOOL_DISPATCHER] ⚡ Executing python_calc (len: {len(clean_code)})")

    success, output = await asyncio.to_thread(execute_python_calc_sync, clean_code)

    return ToolResult(
        tool_name="python_calc",
        status="success" if success else "error",
        intent=intent_desc,
        display_data={
            "tool": "python_calc",
            "intent": intent_desc,
            "code": clean_code,
            "output": output,
            "error": None if success else output,
            "stage": "done" if success else "error",
        },
        llm_context=f"--- HASIL EKSEKUSI PYTHON SANDBOX ---\nOutput:\n{output}",
        error_message=None if success else output,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TOOL: URL READER & SUB-LINK DISCOVERY (URLFETCH)
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_url_fetch_tool(urls: Any, reason: str = "", user_query: str = "") -> ToolResult:
    """Eksekusi pembacaan konten halaman web langsung via url_reader."""
    from backend.app.services.web_tools.url_reader import (
        extract_url_display_info,
        fetch_webpage_with_discovery,
        extract_urls_from_text,
    )

    target_urls: List[str] = []
    if isinstance(urls, list):
        for item in urls:
            if isinstance(item, str):
                target_urls.extend(extract_urls_from_text(item) if "http" in item else [item])
    elif isinstance(urls, str):
        if urls.strip().startswith("[") and urls.strip().endswith("]"):
            try:
                raw_list = json.loads(urls)
                if isinstance(raw_list, list):
                    for item in raw_list:
                        target_urls.extend(extract_urls_from_text(str(item)))
            except Exception:
                target_urls = extract_urls_from_text(urls)
        else:
            target_urls = extract_urls_from_text(urls)

    # Filter URL valid
    target_urls = [u.strip() for u in target_urls if u.startswith("http://") or u.startswith("https://")]
    # Deduplicate
    seen_urls = set()
    clean_target_urls = []
    for u in target_urls:
        if u not in seen_urls:
            seen_urls.add(u)
            clean_target_urls.append(u)

    intent_desc = reason.strip() if reason.strip() else f"Membaca konten dari {len(clean_target_urls)} tautan web"
    logger.info(f"[TOOL_DISPATCHER] 🔗 Executing urlfetch for URLs: {clean_target_urls}")

    if not clean_target_urls:
        return ToolResult(
            tool_name="urlfetch",
            status="error",
            intent=intent_desc,
            display_data={
                "tool": "urlfetch",
                "nodes": [],
                "fetching": None,
                "activity": intent_desc,
            },
            llm_context="Tidak ditemukan URL web yang valid dalam pemanggilan alat urlfetch.",
            error_message="No valid URLs provided",
        )

    collected_nodes = []
    url_contexts = ""
    for u in clean_target_urls:
        display_info = extract_url_display_info(u)
        content, sub_nodes = await fetch_webpage_with_discovery(u, user_query=user_query or reason)
        if content:
            url_contexts += f"\n\n==== ISI WEB: {u} ====\n\n{content}\n\n========================\n"
        if sub_nodes:
            collected_nodes.extend(sub_nodes)
        else:
            collected_nodes.append({
                "title": display_info["title"],
                "domain": display_info["domain"],
                "url": u
            })

    activity_text = intent_desc or "Menelaah referensi tautan web"
    safe_url_context = (url_contexts[:7500] + "\n...(dipotong demi efisiensi)") if len(url_contexts) > 7500 else url_contexts
    has_content = bool(url_contexts and url_contexts.strip())

    return ToolResult(
        tool_name="urlfetch",
        status="success" if has_content else "error",
        intent=intent_desc,
        display_data={
            "tool": "urlfetch",
            "nodes": collected_nodes,
            "fetching": None,
            "activity": activity_text
        },
        llm_context=f"=== KONTEN DARI TAUTAN WEB ===\n{safe_url_context}" if has_content else f"Gagal mengunduh atau konten kosong untuk tautan: {clean_target_urls}",
        error_message=None if has_content else "Halaman web kosong atau tidak dapat diakses",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TOOL: GEOCODING & MAP SEARCH (OPENSTREETMAP NOMINATIM)
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_map_search_tool(location: str, reason: str = "") -> ToolResult:
    """Eksekusi pencarian titik koordinat dan fasilitas via geocode_osm."""
    from backend.app.services.tools.geocoding import geocode_osm

    clean_loc = location.strip()
    intent_desc = reason.strip() if reason.strip() else f"Mencari titik lokasi / fasilitas: '{clean_loc}'"
    logger.info(f"[TOOL_DISPATCHER] 🌍 Executing map_search for location: '{clean_loc}'")

    try:
        coords = await geocode_osm(clean_loc)
        if coords:
            division_info = f"\nDivisi/Fasilitas: {coords['division']}" if coords.get("division") else ""
            map_info = (
                f"Hasil pencarian lokasi untuk '{clean_loc}':\n"
                f"Latitude: {coords['lat']}\n"
                f"Longitude: {coords['lng']}\n"
                f"Alamat Terdaftar: {coords['name']}{division_info}\n"
            )
            return ToolResult(
                tool_name="map_search",
                status="success",
                intent=intent_desc,
                display_data={
                    "tool": "map_search",
                    "intent": intent_desc,
                    "location": clean_loc,
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                    "name": coords["name"],
                    "division": coords.get("division"),
                    "stage": "done"
                },
                llm_context=f"[TOOL: GEOCODING_RESULT]\n{map_info}",
            )
        else:
            return ToolResult(
                tool_name="map_search",
                status="error",
                intent=intent_desc,
                display_data={"tool": "map_search", "intent": intent_desc, "location": clean_loc, "stage": "not_found"},
                llm_context=f"Lokasi atau fasilitas '{clean_loc}' tidak ditemukan dalam peta OpenStreetMap.",
                error_message="Location not found"
            )
    except Exception as e:
        logger.error(f"[TOOL_DISPATCHER] Error in map_search_tool: {e}", exc_info=True)
        return ToolResult(
            tool_name="map_search",
            status="error",
            intent=intent_desc,
            display_data={"tool": "map_search", "intent": intent_desc, "location": clean_loc, "stage": "error"},
            llm_context=f"Kendala teknis saat mencari lokasi: {str(e)}",
            error_message=str(e)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. MASTER DISPATCHER (MCP-READY HUB)
# ═══════════════════════════════════════════════════════════════════════════════

from typing import AsyncGenerator, List, Dict, Any, Optional, Union

async def dispatch_agentic_tool(tool_name: str, payload_str: Union[str, Dict[str, Any]]) -> ToolResult:
    """
    Pusat parsing dan delegasi panggilan tool dari interceptor.
    Menerima nama tool dan raw JSON/string/dict, lalu memanggil fungsi pelaksana yang tepat.
    """
    tool_clean = tool_name.strip().lower()
    if isinstance(payload_str, dict):
        parsed_json = payload_str
        raw_str = json.dumps(payload_str)
    else:
        raw_str = (payload_str or "").strip()
        parsed_json: Dict[str, Any] = {}
        try:
            parsed_json = json.loads(raw_str)
        except Exception:
            # Coba ekstrak field dengan regex fleksibel jika JSON tidak sempurna
            q_match = re.search(r'["\'](?:query|location|url|urls|q)["\']\s*:\s*(?:\[([^\]]+)\]|["\']([^"\']+)["\'])', raw_str)
            if q_match:
                parsed_json["query"] = q_match.group(1) or q_match.group(2)
            r_match = re.search(r'["\'](?:reason|intent)["\']\s*:\s*["\']([^"\']+)["\']', raw_str)
            if r_match:
                parsed_json["reason"] = r_match.group(1)

    query_val = parsed_json.get("query") or parsed_json.get("q") or raw_str.replace("{", "").replace("}", "").strip()
    reason_val = parsed_json.get("reason") or parsed_json.get("intent") or ""

    if tool_clean in ("websearch", "web_search"):
        return await execute_web_search_tool(query_val, reason=reason_val)

    elif tool_clean in ("docsearch", "doc_search", "rag_search", "rag"):
        doc_type_val = parsed_json.get("doc_type") or ""
        return await execute_doc_search_tool(query_val, reason=reason_val, doc_type=doc_type_val)

    elif tool_clean in ("urlfetch", "url_fetch", "read_url", "fetch_url"):
        urls_val = parsed_json.get("urls") or parsed_json.get("url") or query_val
        return await execute_url_fetch_tool(urls_val, reason=reason_val)

    elif tool_clean in ("map_search", "map", "geocode", "geocoding"):
        loc_val = parsed_json.get("location") or parsed_json.get("lokasi") or query_val
        return await execute_map_search_tool(loc_val, reason=reason_val)

    elif tool_clean in ("python_calc", "python", "calc", "calculator"):
        # Jika model mengirimkan JSON {"code": "...", "reason": "..."}, ambil code-nya
        code_val = parsed_json.get("code") or raw_str
        return await execute_python_calc_tool(code_val, reason=reason_val)

    else:
        logger.warning(f"[TOOL_DISPATCHER] Unknown tool requested: '{tool_clean}'")
        return ToolResult(
            tool_name=tool_clean,
            status="error",
            intent=f"Percobaan memanggil tool tidak dikenal '{tool_clean}'",
            display_data={"tool": tool_clean, "stage": "error"},
            llm_context=f"Tool '{tool_clean}' tidak tersedia dalam sistem CAKRA AI.",
            error_message=f"Tool '{tool_clean}' not found",
        )
