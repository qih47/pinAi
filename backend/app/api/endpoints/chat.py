import os
import time
import json
import shutil
import logging
from typing import List, Optional, AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.core.paths import UPLOAD_DIR
from backend.app.services.chat_history_service import chat_history_service
from backend.app.services.memory_service import memory_service
from backend.app.services.rag_service import rag_service
from backend.app.services.pipeline_layer_executor import (
    execute_layer_0_vision,
    execute_layer_1_analyzer,
    execute_layer_2_planner,
    execute_layer_3_executor,
)
from backend.app.api.schemas.chat import (
    ChatStreamRequest,
    TitleUpdateSchema,
    TestRouterRequestSchema,
)

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")


# ==============================================================================
# 📂 SECTION 1: ENDPOINTS MANAJEMEN SESI (SIDEBAR FRONTEND)
# ==============================================================================

@router.get("/sessions", summary="Ambil Daftar Sesi Aktif Pegawai untuk Sidebar")
async def get_history_sessions(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    if not current_user_npp:
        return {"status": "success", "data": []}

    sessions = await chat_history_service.get_user_sessions(current_user_npp)
    return {"status": "success", "data": sessions}


@router.post("/sessions/create", summary="Membuat Sesi Obrolan Baru (New Chat)")
async def create_new_chat_session(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
    judul: Optional[str] = Query("Obrolan Baru"),
):
    npp_target = current_user_npp if current_user_npp else "GUEST"
    name_target = "Pegawai Pindad" if current_user_npp else "Guest User"

    new_session = await chat_history_service.create_new_session(
        npp=npp_target,
        username=name_target,
        model_name=settings.MODEL_PERSONA,
        judul=judul,
    )
    return {"status": "success", "data": new_session}


@router.put("/sessions/{session_uuid}/title", summary="Rename Judul Sesi Chat")
async def rename_chat_title(session_uuid: str, payload: TitleUpdateSchema):
    success = await chat_history_service.update_session_title(
        session_uuid, payload.judul
    )
    if not success:
        raise HTTPException(
            status_code=500, detail="Gagal memperbarui judul sesi di RAGDB."
        )
    return {"status": "success", "message": "Judul sesi berhasil diperbarui, bolo!"}


@router.put("/sessions/{session_uuid}/pin", summary="Pin atau Unpin Sesi Obrolan")
async def pin_chat_session(session_uuid: str, is_pinned: bool = Query(...)):
    success = await chat_history_service.toggle_pin_session(session_uuid, is_pinned)
    if not success:
        raise HTTPException(
            status_code=500, detail="Gagal merubah status sematan sesi."
        )
    return {"status": "success", "message": "Status sematan sesi berhasil diperbarui!"}


@router.delete("/sessions/{session_uuid}", summary="Soft Delete Sesi Chat")
async def delete_chat_session(session_uuid: str):
    success = await chat_history_service.soft_delete_session(session_uuid)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal menghapus sesi obrolan.")
    return {"status": "success", "message": "Sesi obrolan berhasil dihapus, bolo!"}


@router.get("/sessions/{session_uuid}/messages", summary="Ambil Pesan dalam Sesi Chat beserta Attachment")
async def get_session_messages_endpoint(session_uuid: str):
    messages = await chat_history_service.get_session_messages(session_uuid)
    return {"status": "success", "data": messages}


# ==============================================================================
# 🚀 SECTION 2: ENDPOINT UTAMA SEQUENTIAL PIPELINE (LAYER 0→1→2→3)
# ==============================================================================

def _format_sse(chunk: str, thinking: str = "", done: bool = False) -> str:
    """Format SSE response dengan thinking signal dan done flag"""
    return json.dumps({
        "chunk": chunk,
        "thinking": thinking,
        "done": done
    }) + "\n"


async def _sequential_pipeline_generator(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str],
) -> AsyncGenerator[str, None]:
    """
    Sequential Cognitive Pipeline Generator Berbasis Inteligensia Tingkat Tinggi CAKRA AI
    Mengorkestrasikan 34 Parameter Kognitif Lintas Layer Tanpa Degradasi Informasi.
    """
    user_label = (
        f"Pegawai (NPP: {current_user_npp})"
        if current_user_npp
        else "GUEST (Mode Tamu)"
    )
    print(f"\n💬 [PIPELINE] Sequential pipeline starting dari {user_label}")
    
    if not payload.messages:
        raise HTTPException(
            status_code=400, detail="Daftar urutan pesan tidak boleh kosong!"
        )
    
    user_message = payload.messages[-1].content
    print("\n" + "═" * 50)
    print(f'👤 [USER MSG] "{user_message}"')
    print("═" * 50)
    
    # Convert messages to dict format
    messages_for_pipeline = [
        {"role": msg.role, "content": msg.content} for msg in payload.messages
    ]
    
    # ========== LAYER 0: Vision Preprocessor (OPTIONAL) ==========
    ocr_text = None
    if payload.attachment_paths and len(payload.attachment_paths) > 0:
        logger.info(f"[LAYER 0] Vision preprocessing starting for {len(payload.attachment_paths)} files...")
        # 🔥 UI FIX: Kirim sinyal pendek membaca berkas lampiran
        yield _format_sse("", "📄 Membaca lampiran berkas...", False)
        
        try:
            vision_result = await execute_layer_0_vision(request, payload.attachment_paths)
            ocr_text = vision_result.get("extracted_text", "")
            
            if payload.session_uuid:
                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=f"{user_message} [Lampiran: {len(payload.attachment_paths)} file(s)]"
                )
            
            logger.info(f"[LAYER 0] Complete | Pages: {vision_result.get('page_count', 0)}")
        except Exception as e:
            logger.error(f"[LAYER 0] Error: {str(e)}")
            ocr_text = "[File processing failed]"
    
    # Save user message ke chat_messages
    if payload.session_uuid:
        await chat_history_service.save_chat_message(
            session_id=payload.session_uuid,
            role="user",
            text=user_message,
            thought="Submitted to advanced socio-cognitive pipeline [34 parameters active]",
        )
    
    # ========== LAYER 1: Cognitive Analyzer (MANDATORY) ==========
    logger.info("[LAYER 1] Cognitive analysis starting...")
    # 🔥 UI FIX: Kirim sinyal pendek analisis konteks kueri
    yield _format_sse("", "🧠 Menganalisis konteks kueri...", False)
    
    try:
        cognitive_params = await execute_layer_1_analyzer(
            request=request,
            messages=messages_for_pipeline,
            chat_history=[],
            employee_npp=current_user_npp,
            ocr_text=ocr_text
        )
        logger.info(f"[LAYER 1] Complete | Intent: {cognitive_params.get('detected_intent')}")
    except Exception as e:
        logger.error(f"[LAYER 1] Error: {str(e)}")
        from backend.app.services.pipeline_layer_executor import _get_fallback_cognitive_params
        cognitive_params = _get_fallback_cognitive_params()
    
    # 📑 LOG DUMP TERMINAL: Tetap cetak log parameter komplit di sisi console backend buat analitik lo
    print("\n" + "🧠 " * 20)
    print("[LAYER 1 LOG DUMP] Runtunan 34 Parameter Kognitif yang Dihasilkan Gerbang Utama (CAKRA AI):")
    print(json.dumps(cognitive_params, indent=2, ensure_ascii=False))
    print("🧠 " * 20 + "\n")
    
    # Note: Blok string 'thinking_dump' lama yang panjang ke Accordion sengaja KITA HAPUS di sini biar UI bersih!
    
    # ========== INTERSEPTOR BYPASS & KENDALI ALIRAN PIPA ==========
    detected_intent_flag = str(cognitive_params.get("detected_intent", "NORMAL")).upper()
    vram_urgency = str(cognitive_params.get("estimated_vram_urgency", "low_bypass_safe")).lower()
    
    # Jika terdeteksi CHITCHAT atau orkestrator menandai aman di-bypass demi efisiensi hardware
    if "CHITCHAT" in detected_intent_flag or "CHIT_CHAT" in detected_intent_flag or vram_urgency == "low_bypass_safe":
        print("⚡ [PIPELINE BYPASS] Terdeteksi sapaan santai / diskusi ringan. Melakukan bypass Layer 2 (DeepSeek-R1) untuk optimalisasi VRAM!")
        # 🔥 UI FIX: Kirim sinyal pendek penyelarasan respon sosial
        yield _format_sse("", "⚡ Menyelaraskan respon...", False)
        
        strategy_params = {
            "action_plan": [
                "Tanggapi sapaan atau obrolan ringan user dengan ramah dan penuh kehangatan sosial",
                "Pastikan mendeklarasikan diri murni sebagai CAKRA AI, bukan sub-model bahasa dasar mana pun"
            ],
            "response_structure": {
                "open_with": "greeting",
                "middle": "narrative",
                "close_with": "offer_help"
            },
            "key_points_to_cover": ["Sapaan ramah", "Tanggapan kasual", "Identitas Cakra AI"],
            "tone": "suportif",
            "estimated_response_length": "brief",
            "should_ask_followup": True,
            "rag_context": None,
            "rag_utilized": False
        }
    else:
        # ========== LAYER 2: Strategic Planner (MANDATORY UNTUK NON-CHITCHAT / LOGIKA BERAT) ==========
        logger.info("[LAYER 2] Strategic planning starting...")
        
        # 🔥 UI FIX: Bedakan status dinamis pendek berdasarkan deteksi kebutuhan RAG internal Pindad
        if cognitive_params.get("need_rag"):
            yield _format_sse("", "📚 Menyelami basis data RAG Pindad...", False)
        else:
            yield _format_sse("", "📋 Menyusun rencana tindakan...", False)
        
        try:
            strategy_params = await execute_layer_2_planner(
                request=request,
                messages=messages_for_pipeline,
                cognitive_params=cognitive_params,
                employee_npp=current_user_npp
            )
            logger.info(f"[LAYER 2] Complete | Tone: {strategy_params.get('tone')}")
        except Exception as e:
            logger.error(f"[LAYER 2] Error: {str(e)}")
            from backend.app.services.pipeline_layer_executor import _get_fallback_strategy_params
            strategy_params = _get_fallback_strategy_params()
            
        print("\n" + "📋 " * 20)
        print("[LAYER 2 LOG DUMP] Cetak Biru Taktis Tindakan Hasil Perumusan Logika:")
        print(json.dumps(strategy_params, indent=2, ensure_ascii=False))
        print("📋 " * 20 + "\n")
        
    # ========== LAYER 3: Social Executor (MANDATORY) ==========
    logger.info("[LAYER 3] Response generation starting...")
    # 🔥 UI FIX: Kirim sinyal pendek tahap akhir perajutan narasi teks utama
    yield _format_sse("", "✍️ Sedang menggenerate narasi...", False)
    
    full_response_text = ""
    start_time = datetime.now()
    
    try:
        async for layer3_chunk in execute_layer_3_executor(
            request=request,
            messages=messages_for_pipeline,
            cognitive_params=cognitive_params,
            strategy_params=strategy_params,
        ):
            try:
                chunk_data = json.loads(layer3_chunk.strip())
                chunk_text = chunk_data.get("chunk", "")
                
                if chunk_text:
                    full_response_text += chunk_text
                yield _format_sse(chunk_text, "", False)
            except json.JSONDecodeError:
                if layer3_chunk:
                    full_response_text += layer3_chunk
                yield _format_sse(layer3_chunk, "", False)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[LAYER 3] Complete | Generated {len(full_response_text)} chars in {elapsed:.2f}s")
        
    except Exception as e:
        logger.error(f"[LAYER 3] Error: {str(e)}")
        error_msg = f"Gagal mengeksekusi tanggapan sosial: {str(e)}"
        yield _format_sse(error_msg, "", False)
        full_response_text = error_msg
    
    # ========== DATABASE PERSISTENCE & ANALYTICS DATA BINDING ==========
    if payload.session_uuid:
        logger.info("[DATABASE] Saving chat messages & auto-titling...")
        
        # Pemicu judul otomatis jika sesi masih default
        await chat_history_service.auto_update_session_title(
            payload.session_uuid, user_message
        )
        
        # Menyimpan respon asisten AI beserta penanda thought terpadu
        await chat_history_service.save_chat_message(
            session_id=payload.session_uuid,
            role="assistant",
            text=full_response_text,
            thought="Processed via Layer 3 [Social Executor with Mirroring Strategy]",
        )
        
        # Penyimpanan massal korpus analitik internal (jika kasus no-attachments)
        if not (payload.attachment_paths and len(payload.attachment_paths) > 0):
            try:
                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=user_message,
                    assistant_text=full_response_text,
                    context_document=strategy_params.get("rag_context") or "No RAG context utilized"
                )
            except Exception as e:
                logger.warning(f"[DATABASE] Failed to save dialogue analytic corpus: {str(e)}")
    
    logger.info("[PIPELINE] Sequential pipeline complete ✅")
    # Sinyal done bernilai true untuk memutuskan sasis koneksi SSE di FE
    yield _format_sse("", "", True)


@router.post("/stream", summary="Streaming Engine Sequential Pipeline CAKRA AI")
async def chat_stream_endpoint(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Endpoint Utama Penghubung UI Frontend dengan Sasis Aliran Kognitif CAKRA AI.
    """
    return StreamingResponse(
        _sequential_pipeline_generator(request, payload, current_user_npp),
        media_type="text/event-stream",
    )


# ==============================================================================
# 📎 SECTION 3: UPLOAD ATTACHMENT (SEMUA QUERY DI SERVICE)
# ==============================================================================

@router.post("/documents/upload", summary="Mengunggah Lampiran Chat (Gambar/PDF) ke RAGDB")
async def upload_chat_attachments(
    files: List[UploadFile] = File(...),
    session_uuid: Optional[str] = Form(None),
):
    """
    Endpoint upload lampiran. Semua operasi database didelegasikan ke chat_history_service.
    """
    uploaded_meta_list = []

    for file in files:
        if not (file.content_type.startswith("image/") or file.content_type == "application/pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Format berkas '{file.filename}' salah! Cakra hanya menerima Gambar atau PDF, bolo!",
            )

        unique_filename = f"{int(time.time())}_{file.filename}"
        absolute_write_path = os.path.join(UPLOAD_DIR, unique_filename)

        try:
            with open(absolute_write_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_size = os.path.getsize(absolute_write_path)
            extracted_text_placeholder = f"[OCR Korpus Berkas {file.filename}]: Ekstraksi taktis siap."

            inserted_meta = await chat_history_service.save_chat_attachment(
                session_uuid=session_uuid,
                original_filename=file.filename,
                unique_filename=unique_filename,
                file_size=file_size,
                mime_type=file.content_type,
                extracted_text=extracted_text_placeholder,
            )

            if inserted_meta:
                uploaded_meta_list.append(inserted_meta)
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Gagal menyimpan metadata lampiran {file.filename} ke database.",
                )

        except HTTPException:
            raise
        except Exception as err:
            logger.error(f"❌ [UPLOAD ERROR] Gagal memproses berkas {file.filename}: {str(err)}")
            if os.path.exists(absolute_write_path):
                os.remove(absolute_write_path)
            raise HTTPException(
                status_code=500,
                detail=f"Gagal memproses lampiran berkas {file.filename}.",
            )

    print(f"📦 [UPLOAD SUCCESS] {len(uploaded_meta_list)} Berkas sukses mengunci record 'chat_attachments'!")
    return {"status": "success", "data": uploaded_meta_list}