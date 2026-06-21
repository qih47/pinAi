import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from fastapi import Request

from backend.app.core.config import settings
from backend.app.services.pipeline.token_continuation_layer import (
    build_raw_prompt_string,
    RawPromptBuilder,
    TokenStreamParser,
    stitch_raw_prompt_with_rag,
    parse_channel_marker
)
from backend.app.services.pipeline.ollama_raw_client import call_ollama_generate_raw
from backend.app.services.pipeline.system_prompts import (
    build_intent_analysis_prompt,
    build_response_prompt
)
from backend.app.services.rag.rag_pipeline import run_rag_pipeline
from backend.app.services.pipeline.sse_validation import format_sse, SSEEventType
from backend.app.services.pipeline.gemma_agentic_engine import _detect_precheck

logger = logging.getLogger(__name__)

@dataclass
class ContinuationState:
    session_uuid: str
    raw_prompt_history: List[str] = field(default_factory=list)
    accumulated_thinking: str = ""
    phase: Literal["analysis", "rag", "response"] = "analysis"
    rag_data_injected: bool = False
    interruption_count: int = 0
    total_thinking_tokens_estimate: int = 0
    final_response_text: str = ""
    
    def save_raw_prompt(self, prompt: str) -> None: 
        self.raw_prompt_history.append(prompt)
        
    def append_thinking(self, text: str) -> None: 
        self.accumulated_thinking += text
        self.total_thinking_tokens_estimate += len(text.split())
        
    def mark_rag_complete(self) -> None: 
        self.phase = "response"
        self.rag_data_injected = True

async def _save_audit_trail(
    session_uuid: str,
    state: ContinuationState,
    routing: Dict[str, Any],
    rag_sources: Optional[List[Dict]] = None
) -> None:
    from backend.app.core.database import get_db_pool
    if session_uuid == "temp" or not getattr(settings, "AUDIT_THINKING_CONTENT", True):
        return
        
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            rag_source_ids = [s.get("doc_id", "") for s in rag_sources] if rag_sources else []
            try:
                await conn.execute(
                    """
                    INSERT INTO llm_thinking_audit (
                        session_uuid, thinking_content, thinking_token_estimate,
                        routing_decision, rag_queries, rag_results_count, rag_source_ids,
                        response_text, continuation_attempts
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    session_uuid,
                    state.accumulated_thinking,
                    state.total_thinking_tokens_estimate,
                    json.dumps(routing),
                    routing.get("queries", []),
                    len(rag_sources) if rag_sources else 0,
                    rag_source_ids,
                    state.final_response_text,
                    state.interruption_count
                )
            except Exception as dberr:
                if "does not exist" in str(dberr):
                    pass # Ignore if table not created by admin yet
                else:
                    logger.warning(f"[AUDIT_TRAIL] Failed to insert: {dberr}")
    except Exception as e:
        logger.error(f"[AUDIT_TRAIL] Failed to save audit log: {e}")

async def _phase1_with_continuation(
    request: Request,
    messages: List[Dict[str, str]],
    precheck: Dict[str, Any],
    state: ContinuationState,
    ocr_text: Optional[str] = None,
    employee_name: str = "Pegawai"
) -> tuple[Dict[str, Any], List[str]]:
    user_message = messages[-1]["content"] if messages else ""
    context_history_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages[-5:-1]]) if len(messages) > 1 else ""

    system_prompt = build_intent_analysis_prompt(
        user_message=user_message,
        context_history_str=context_history_str,
        precheck=precheck,
        ocr_text=ocr_text,
    )
    
    # 3.7 Personalized Pre-fill Profiling
    prefill_text = f"[CONTEXT MEMORY: Pengguna bernama {employee_name}]\n"
    
    builder = RawPromptBuilder()
    builder.set_system(system_prompt)
    builder.add_message("user", user_message)
    builder.set_prefill_thinking(prefill_text)
    raw_prompt = builder.build()
    
    logger.info(f"\n{'='*50}\n🚀 [AGENTIC PHASE 1] STARTING\nSession UUID: {state.session_uuid}\nUser Message: {user_message}\n{'='*50}")
    
    state.save_raw_prompt(raw_prompt)
    state.append_thinking(prefill_text)

    thinking_events = []
    
    max_resumes = 2
    resumes = 0
    routing = {"need_rag": False, "queries": []}
    
    while resumes < max_resumes:
        parser = TokenStreamParser()
        parser.in_thinking_block = True 
        parser.accumulated_text = ""
        
        limit_hit = False
        
        logger.info(f"🔹 [PHASE 1 - CALL OLLAMA] Resume Hop: {resumes}\n[RAW PROMPT INPUT]:\n{raw_prompt}\n{'-'*50}")
        
        try:
            async for chunk_line in call_ollama_generate_raw(
                model_name=getattr(settings, "MODEL_PERSONA", "gemma4:12b"),
                raw_prompt=raw_prompt,
                temperature=0.1,
                num_predict=512,
                stop_sequences=["</s>", "<end_of_turn>"],
                request=request
            ):
                res = await parser.parse_chunk(chunk_line)
                token = res.get("token", "")
                
                if res.get("thinking_updated") and token:
                    evt = format_sse("", token, False, event_type=SSEEventType.THINKING)
                    if evt:
                        thinking_events.append(evt)
                        
                # 3.6 Adaptive Thinking Depth
                current_len = len(parser.accumulated_text.split())
                if parser.in_thinking_block and current_len > getattr(settings, "THINKING_DEPTH_THRESHOLD", 500):
                    limit_hit = True
                    break
                    
                if "</think>" in parser.accumulated_text:
                    break
                    
                if "<channel|>" in parser.accumulated_text:
                    marker_info = parse_channel_marker(parser.get_accumulated_text())
                    if marker_info["found"]:
                        break
                    
            state.append_thinking(parser.get_accumulated_thinking())
            logger.info(f"🔹 [PHASE 1 - RAW OUTPUT] Diterima dari Ollama:\n{parser.get_accumulated_text()}\n{'-'*50}")
            
            if limit_hit:
                forced_wrap = "\n\nKesimpulan analisis: "
                state.append_thinking(forced_wrap)
                evt = format_sse("", forced_wrap, False, event_type=SSEEventType.THINKING)
                if evt: thinking_events.append(evt)
                
                builder.set_prefill_thinking(state.accumulated_thinking)
                raw_prompt = builder.build()
                resumes += 1
                continue
                
            # Check context exhaustion
            if parser.in_thinking_block and not parser.marker_found and not limit_hit:
                forced_wrap = "\n\n[SISTEM: Token exhaustion terdeteksi. Tutup penalaran sekarang.]\n"
                state.append_thinking(forced_wrap)
                builder.set_prefill_thinking(state.accumulated_thinking)
                raw_prompt = builder.build()
                resumes += 1
                continue
                
            marker_info = parse_channel_marker(parser.get_accumulated_text())
            if marker_info["found"]:
                routing = {
                    "need_rag": True,
                    "queries": marker_info["queries"]
                }
            
            logger.info(f"✅ [PHASE 1 - ROUTING DECISION] Hasil Keputusan: {routing}")
            break

        except Exception as e:
            logger.error(f"[AGENTIC_PHASE1] Error in continuation: {e}")
            break

    if routing["need_rag"] and not routing["queries"]:
        from backend.app.services.pipeline.gemma_agentic_engine import _build_fallback_routing
        routing = _build_fallback_routing(precheck)

    return routing, thinking_events

async def _phase2_with_continuation(
    request: Request,
    messages: List[Dict[str, str]],
    state: ContinuationState,
    precheck: Dict[str, Any],
    rag_context: Optional[str] = None,
    rag_sources: Optional[List[Dict]] = None,
    is_chitchat: bool = False,
    ocr_text: Optional[str] = None,
    employee_name: str = "Pegawai"
) -> AsyncGenerator[str, None]:
    system_prompt = build_response_prompt(
        employee_name=employee_name,
        precheck=precheck,
        rag_context=rag_context,
        rag_sources=rag_sources,
        ocr_text=ocr_text,
        is_chitchat=is_chitchat,
    )

    trimmed_messages = messages[-3:] if len(messages) > 3 else messages

    # 3.9 Dynamic Persona Switching
    if "stres" in state.accumulated_thinking.lower() or "frustrasi" in state.accumulated_thinking.lower():
        system_prompt += "\n[SISTEM: User terdeteksi frustrasi/stres. Ganti persona menjadi sangat empatik dan menenangkan.]\n"

    builder = RawPromptBuilder()
    builder.set_system(system_prompt)
    for m in trimmed_messages:
        builder.add_message(m["role"], m["content"])

    # 3.2 Speed-Up Mode (Instant Response Chitchat)
    if is_chitchat:
        chitchat_prefill = "Analisis: Sapaan kasual. Mode respons cepat aktif.</think>"
        state.append_thinking(chitchat_prefill)
        
    builder.set_prefill_thinking(state.accumulated_thinking)

    raw_prompt = builder.build()
    state.save_raw_prompt(raw_prompt)
    
    logger.info(f"\n{'='*50}\n🚀 [AGENTIC PHASE 2] STARTING\nChitchat Mode: {is_chitchat}\nRAG Injected: {bool(rag_context)}\n{'='*50}")
    
    num_ctx = 16384 if rag_context else 4096
    temperature = 0.55 if not is_chitchat else 0.75

    max_resumes = 2
    resumes = 0
    
    while resumes < max_resumes:
        parser = TokenStreamParser()
        parser.in_thinking_block = False if ("</think>" in state.accumulated_thinking) else True
        parser.accumulated_text = ""
        
        limit_hit = False
        
        logger.info(f"🔹 [PHASE 2 - CALL OLLAMA] Resume Hop: {resumes}\n[RAW PROMPT INPUT]:\n{raw_prompt}\n{'-'*50}")
        
        try:
            async for chunk_line in call_ollama_generate_raw(
                model_name=getattr(settings, "MODEL_PERSONA", "gemma4:12b"),
                raw_prompt=raw_prompt,
                temperature=temperature,
                num_ctx=num_ctx,
                num_predict=8192,  # Diperbesar dari 4096 untuk menampung pemikiran RAG raksasa
                stop_sequences=["</s>", "<end_of_turn>"],
                request=request
            ):
                res = await parser.parse_chunk(chunk_line)
                token = res.get("token", "")
                
                if res.get("thinking_updated") and token:
                    evt = format_sse("", token, False, event_type=SSEEventType.THINKING)
                    if evt: yield evt
                elif not res.get("thinking_updated") and token:
                    evt = format_sse(token, "", False, event_type=SSEEventType.CHUNK)
                    if evt: yield evt
                    state.final_response_text += token

                if "<channel|>" in parser.accumulated_text:
                    marker_info = parse_channel_marker(parser.get_accumulated_text())
                    if marker_info["found"] and marker_info["queries"]:
                        break

            state.append_thinking(parser.get_accumulated_thinking())
            logger.info(f"🔹 [PHASE 2 - RAW OUTPUT] Diterima dari Ollama:\n{parser.get_accumulated_text()}\n{'-'*50}")
            
            # Multi-Hop RAG Check
            marker_info = parse_channel_marker(parser.get_accumulated_text())
            if marker_info["found"] and marker_info["queries"]:
                state.interruption_count += 1
                yield {"type": "MULTI_HOP", "queries": marker_info["queries"]}
                return

            # 3.8 Hedging handling for context exhaustion inside thinking
            if parser.in_thinking_block and not marker_info["found"]:
                hedge_injection = "\n\n[SISTEM: Token limit habis. Berikan jawaban dengan tambahan disclaimer bahwa data mungkin tidak lengkap.]\n</think>"
                state.append_thinking(hedge_injection)
                builder.set_prefill_thinking(state.accumulated_thinking)
                raw_prompt = builder.build()
                resumes += 1
                continue
                
            break
            
        except Exception as e:
            logger.error(f"[AGENTIC_PHASE2] Error: {e}")
            yield format_sse("Maaf, terjadi kendala teknis.", "", False, event_type=SSEEventType.CHUNK)
            break

async def execute_gemma_agentic_v2(
    request: Request,
    messages: List[Dict[str, str]],
    chat_mode: str = "auto",
    has_attachment: bool = False,
    ocr_text: Optional[str] = None,
    employee_name: str = "Pegawai",
    session_uuid: Optional[str] = None
) -> AsyncGenerator[str, None]:
    user_message = messages[-1]["content"] if messages else ""
    precheck = _detect_precheck(user_message, chat_mode, has_attachment)
    precheck["_user_message"] = user_message
    
    state = ContinuationState(session_uuid=session_uuid or "temp")
    is_chitchat = precheck["is_chitchat"]
    
    # 3.11 Proactive Clarification Loop Check
    clarification_state = None
    if state.session_uuid != "temp":
        from backend.app.core.database import get_continuation_state
        clarification_state = await get_continuation_state(state.session_uuid)

    routing = {"need_rag": False, "queries": []}
    phase1_thinking_events = []

    if clarification_state:
        # Bypass Phase 1, we are in Clarification mode!
        state.accumulated_thinking = clarification_state.get("accumulated_thinking", "")
        # Append clarification context from user
        state.append_thinking(f"\n[KLARIFIKASI USER: {user_message}]\n")
        # Menghapus hardcoded string "Melanjutkan analisis" agar UI hanya merender raw token
        await asyncio.sleep(0.01)
    else:
        if is_chitchat and not has_attachment and chat_mode not in ("documents",):
            # Menghapus hardcoded string "Menyiapkan balasan hangat"
            await asyncio.sleep(0.01)
            async for sse in _phase2_with_continuation(
                request=request, messages=messages, state=state, precheck=precheck,
                employee_name=employee_name, ocr_text=ocr_text, is_chitchat=True
            ):
                if isinstance(sse, str):
                    yield sse
            yield format_sse("", "", True, event_type=SSEEventType.DONE)
            await _save_audit_trail(state.session_uuid, state, {"need_rag": False}, None)
            
            # Clear clarification state on normal chitchat
            if state.session_uuid != "temp":
                from backend.app.core.database import save_continuation_state
                await save_continuation_state(state.session_uuid, None)
            return

        # Menghapus hardcoded string "Memahami konteks pesan"
        
        routing, phase1_thinking_events = await _phase1_with_continuation(
            request=request, messages=messages, precheck=precheck, state=state, ocr_text=ocr_text, employee_name=employee_name
        )
    
    for evt in phase1_thinking_events:
        yield evt
        await asyncio.sleep(0.005)

    max_hops = 3
    current_hop = 0
    
    rag_context = None
    rag_sources = []
    rag_queries = routing.get("queries", [])
    need_rag = routing.get("need_rag", False)
    
    while current_hop < max_hops:
        if need_rag and rag_queries:
            current_rag_context = ""
            current_rag_sources = []
            
            try:
                async for sse in run_rag_pipeline(rewritten_queries=rag_queries, limit_per_query=3):
                    raw = sse.strip()
                    if not raw: continue
                    try:
                        data = json.loads(raw)
                        event_type = data.get("event_type")
                        if event_type == SSEEventType.PIPELINE_DATA:
                            current_rag_context = data["payload"].get("context")
                            current_rag_sources = data["payload"].get("sources", [])
                        if event_type in (SSEEventType.SOURCES, SSEEventType.THINKING, SSEEventType.STATUS):
                            yield sse
                            await asyncio.sleep(0.005)
                    except:
                        yield sse
            except Exception as e:
                yield format_sse("", f"⚠️ Kegagalan koneksi RAG: {e}", False, event_type=SSEEventType.THINKING)
                state.append_thinking("\n[SISTEM: Koneksi ke database rujukan gagal/timeout. Gunakan basis pengetahuan internal dasar kamu dengan menyertakan catatan disclaimer bahwa sistem data sedang maintenance.]\n")

            if current_rag_context:
                rag_context = (rag_context or "") + "\n\n" + current_rag_context
                
                # 5.2 Formulasi Struktur Injeksi Data Konten RAG (Prompt Priming)
                docs_list = ""
                for idx, src in enumerate(current_rag_sources, 1):
                    title = src.get("title") or src.get("filename", "Dokumen")
                    docs_list += f"- {title}: {current_rag_context[:1000]}...\n"
                    
                priming_injection = (
                    f"\n[SISTEM INTERUPSI: Proses pencarian dokumen selesai. Ditemukan data referensi resmi berikut:\n"
                    f"{docs_list}]\n"
                    f"Melanjutkan analisis penalaran berdasarkan dokumen rujukan yang baru saja didapatkan: Berdasarkan data di atas, ketentuan menyatakan bahwa "
                )
                state.append_thinking(priming_injection)

            if current_rag_sources:
                rag_sources.extend(current_rag_sources)
                
            state.mark_rag_complete()

            if current_rag_sources:
                yield format_sse("", "", False, sources=current_rag_sources, event_type=SSEEventType.SOURCES)
                await asyncio.sleep(0.01)

        # Menghapus hardcoded string "Menyusun jawaban"
        await asyncio.sleep(0.01)

        # 3.8 Confidence-Based Hedging
        if any(word in state.accumulated_thinking.lower() for word in ["mungkin", "sepertinya", "kurang yakin"]):
            state.append_thinking("\n[SISTEM: Karena analisis menunjukkan ketidakpastian, tambahkan klausul mitigasi/disclaimer pada jawaban final.]\n")

        multi_hop_triggered = False
        async for sse in _phase2_with_continuation(
            request=request, messages=messages, state=state, precheck=precheck,
            employee_name=employee_name, rag_context=rag_context, rag_sources=rag_sources,
            ocr_text=ocr_text, is_chitchat=False
        ):
            if isinstance(sse, dict) and sse.get("type") == "MULTI_HOP":
                multi_hop_triggered = True
                rag_queries = sse.get("queries", [])
                need_rag = True
                current_hop += 1
                # Menghapus hardcoded string "Pencarian dokumen lanjutan..."
                break
            else:
                yield sse
                
        if not multi_hop_triggered:
            break

    yield format_sse("", "", True, event_type=SSEEventType.DONE)
    await _save_audit_trail(state.session_uuid, state, routing, rag_sources)

    # 3.11 Proactive Clarification Loop Saving
    if state.session_uuid != "temp":
        from backend.app.core.database import save_continuation_state
        last_chars = state.final_response_text.strip()[-20:].lower()
        if "?" in last_chars or "apakah" in last_chars or "bagaimana" in last_chars or "konfirmasi" in last_chars:
            await save_continuation_state(state.session_uuid, {
                "accumulated_thinking": state.accumulated_thinking
            })
        else:
            await save_continuation_state(state.session_uuid, None)
