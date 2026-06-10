import os
import time
import json
import shutil
import logging
from typing import List, Optional, AsyncGenerator
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    Request,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
)
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


@router.get(
    "/sessions/{session_uuid}/messages",
    summary="Ambil Pesan dalam Sesi Chat beserta Attachment",
)
async def get_session_messages_endpoint(session_uuid: str):
    messages = await chat_history_service.get_session_messages(session_uuid)
    return {"status": "success", "data": messages}


# ==============================================================================
# 🚀 SECTION 2: ENDPOINT UTAMA SEQUENTIAL PIPELINE (LAYER 0→1→2→3)
# ==============================================================================


def _format_sse(chunk: str, thinking: str = "", done: bool = False) -> str:
    """Format SSE response dengan thinking signal dan done flag"""
    return json.dumps({"chunk": chunk, "thinking": thinking, "done": done}) + "\n"


async def _sequential_pipeline_generator(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str],
) -> AsyncGenerator[str, None]:
    """
    Sequential Cognitive Pipeline Generator Berbasis Inteligensia Tingkat Tinggi CAKRA AI
    Mengorkestrasikan 35 Parameter Kognitif Lintas Layer Sesuai Tipe Lampiran (Image/PDF).
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

    # AMBIL PARAMETER CHAT MODE DARI FRONTEND (auto | documents)
    chat_mode = getattr(payload, "mode", "auto")
    print(f"⚙️  [CHAT MODE] Mode Aktif FE: {chat_mode}")
    print("═" * 50)

    # Convert messages to dict format
    messages_for_pipeline = [
        {"role": msg.role, "content": msg.content} for msg in payload.messages
    ]

    # Klasifikasi Tipe Attachment Secara Taktis
    ocr_text = None
    has_images = False
    has_pdf = False
    pdf_paths = []

    if payload.attachment_paths and len(payload.attachment_paths) > 0:
        for path in payload.attachment_paths:
            path_lower = path.lower()
            if path_lower.endswith(".pdf"):
                has_pdf = True
                pdf_paths.append(path)
            if any(
                path_lower.endswith(ext)
                for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]
            ):
                has_images = True

    # ==========================================================================
    # 🔥 STRATEGI PRE-PROCESSING LAYER 0 BERDASARKAN KONSEP BERKAS
    # ==========================================================================
    if has_pdf:
        # Jika ada PDF: Konversi ke image internal, jalankan OCR MiniCPM-V, suapkan teksnya ke Qwen
        logger.info(
            f"[LAYER 0] PDF detected. Triggering MiniCPM OCR conversion for {len(pdf_paths)} file(s)..."
        )
        yield _format_sse("", "📄 Membaca lampiran berkas PDF...", False)

        try:
            # Menggunakan array pdf_paths saja agar MiniCPM fokus meng-OCR PDF
            vision_result = await execute_layer_0_vision(request, pdf_paths)
            ocr_text = vision_result.get("extracted_text", "")

            if payload.session_uuid:
                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=f"{user_message} [PDF OCR Berhasil Dibuat]",
                )
            logger.info(
                f"[LAYER 0] PDF OCR Complete | Pages: {vision_result.get('page_count', 0)}"
            )
        except Exception as e:
            logger.error(f"[LAYER 0] PDF OCR Failed: {str(e)}")
            ocr_text = "[File processing failed]"

    elif has_images:
        # Jika murni GAMBAR (tanpa PDF): Jangan panggil MiniCPM, biarkan gambar murni diantre untuk Gemma 4 Vision
        logger.info(
            "📸 [IMAGE QUEUED] Lampiran berupa gambar murni. Menahan file untuk native Gemma 4 Vision."
        )
        yield _format_sse("", "🖼️ Mengantre analisis visual gambar...", False)

    # Save user message ke chat_messages history database
    if payload.session_uuid:
        attachment_info = (
            f" [Lampiran: {len(payload.attachment_paths)} file(s)]"
            if payload.attachment_paths
            else ""
        )
        await chat_history_service.save_chat_message(
            session_id=payload.session_uuid,
            role="user",
            text=f"{user_message}{attachment_info}",
            thought=f"Submitted to advanced socio-cognitive pipeline [Mode: {chat_mode}]",
        )

    # ==========================================================================
    # 🧠 LAYER 1: COGNITIVE ANALYZER (MANDATORY - ORKESTRATOR PARAMETER)
    # ==========================================================================
    logger.info("[LAYER 1] Cognitive analysis starting...")
    yield _format_sse("", "🧠 Menganalisis konteks kueri...", False)

    try:
        # Pipa mengalirkan ocr_text (hanya terisi jika berkasnya PDF) demi keakuratan kognitif Qwen
        cognitive_params = await execute_layer_1_analyzer(
            request=request,
            messages=messages_for_pipeline,
            chat_history=[],
            employee_npp=current_user_npp,
            ocr_text=ocr_text,
        )
        logger.info(
            f"[LAYER 1] Complete | Intent: {cognitive_params.get('detected_intent')}"
        )
    except Exception as e:
        logger.error(f"[LAYER 1] Error: {str(e)}")
        from backend.app.services.pipeline_layer_executor import (
            _get_fallback_cognitive_params,
        )

        cognitive_params = _get_fallback_cognitive_params()

    # HARD HARDENING VALIDATION JIKA MODE BUKAN DOCUMENTS ATAU BUKAN RAG
    coding_tokens = [
        "import ",
        "export ",
        "const ",
        "async ",
        "await ",
        "function",
        "def ",
        "return ",
        "create(",
    ]
    user_msg_lower = user_message.lower()

    if any(token in user_msg_lower or token in user_message for token in coding_tokens):
        cognitive_params["is_coding"] = True
        logger.info("⚡ [HARDENING DETECTION] Token kodingan terdeteksi secara fisik.")

    # KUNCI UTAMA CHAT MODE BE: Jika dari FE mengirimkan 'documents', paksa need_rag bernilai True!
    if chat_mode == "documents":
        cognitive_params["need_rag"] = True
        logger.info(
            "🔒 [MODE ENFORCEMENT] ChatMode dikunci ke 'documents'. Memaksa status need_rag = True!"
        )

    # 🔥 REGULASI ANTI-BENTROK: Jika mode document atau need_rag True, paksa is_coding MENJADI False (Mentalin!)
    if chat_mode == "documents" or cognitive_params.get("need_rag") is True:
        cognitive_params["is_coding"] = False
        logger.info(
            "🛡️  [ANTI-BENTROK LOCK] Zona RAG Aktif. Memaksa status is_coding = False secara mutlak!"
        )

    # 📑 LOG DUMP TERMINAL
    print("\n" + "🧠 " * 20)
    print(
        "[LAYER 1 LOG DUMP] Runtunan 35 Parameter Kognitif yang Dihasilkan Gerbang Utama (CAKRA AI):"
    )
    print(json.dumps(cognitive_params, indent=2, ensure_ascii=False))
    print("🧠 " * 20 + "\n")

    # READ FINAL PARAMETERS DETERMINATION
    need_rag_final = bool(cognitive_params.get("need_rag", False))
    is_coding_task = bool(cognitive_params.get("is_coding", False))
    # ========== INTERSEPTOR BYPASS & KENDALI ALIRAN PIPA ==========
    detected_intent_flag = str(cognitive_params.get("detected_intent", "NORMAL")).upper()
    vram_urgency = str(cognitive_params.get("estimated_vram_urgency", "low_bypass_safe")).lower()
    is_coding_task = bool(cognitive_params.get("is_coding", False))

    # 🔥 FIX MUTLAK: Jika terdeteksi CHITCHAT, langsung bypass ke Gemma4, tidak peduli mode documents atau auto!
    is_chitchat = "CHITCHAT" in detected_intent_flag or "CHIT_CHAT" in detected_intent_flag

    if is_chitchat or (not is_coding_task and chat_mode != "documents" and vram_urgency == "low_bypass_safe"):
        print("⚡ [PIPELINE BYPASS] Aliran dialihkan langsung ke Gemma4 (Bypass Layer 2 DeepSeek-R1)!")
        yield _format_sse("", "⚡ Menyelaraskan respon...", False)

        strategy_params = {
            "action_plan": [
                "Tanggapi sapaan atau obrolan ringan user dengan ramah dan penuh kehangatan sosial",
                "Pastikan mendeklarasikan diri murni sebagai CAKRA AI, bukan sub-model bahasa dasar mana pun",
            ],
            "response_structure": {
                "open_with": "greeting",
                "middle": "narrative",
                "close_with": "offer_help",
            },
            "key_points_to_cover": [
                "Sapaan ramah",
                "Tanggapan kasual",
                "Identitas Cakra AI",
            ],
            "tone": "suportif",
            "estimated_response_length": "brief",
            "should_ask_followup": True,
            "rag_context": None,
            "rag_utilized": False,
        }
    else:
        # KONDISI 2 & 3: Mode AUTO need_rag TRUE atau Mode DOCUMENTS -> Wajib Olah via DeepSeek-R1
        logger.info("[LAYER 2] Strategic planning starting (KONDISI 2/3 Active)...")

        if need_rag_final:
            yield _format_sse("", "📚 Menyelami basis data RAG Pindad...", False)
        else:
            yield _format_sse("", "📋 Menyusun rencana tindakan...", False)

        try:
            strategy_params = await execute_layer_2_planner(
                request=request,
                messages=messages_for_pipeline,
                cognitive_params=cognitive_params,
                employee_npp=current_user_npp,
            )
            logger.info(f"[LAYER 2] Complete | Tone: {strategy_params.get('tone')}")
        except Exception as e:
            logger.error(f"[LAYER 2] Error: {str(e)}")
            from backend.app.services.pipeline_layer_executor import (
                _get_fallback_strategy_params,
            )

            strategy_params = _get_fallback_strategy_params()

        print("\n" + "📋 " * 20)
        print("[LAYER 2 LOG DUMP] Cetak Biru Taktis Tindakan Hasil Perumusan Logika:")
        print(json.dumps(strategy_params, indent=2, ensure_ascii=False))
        print("📋 " * 20 + "\n")

    # ==========================================================================
    # ✍️ LAYER 3: SOCIAL EXECUTOR (MANDATORY - GEMMA 4 FUSION ENGINE)
    # ==========================================================================
    logger.info("[LAYER 3] Response generation starting...")
    yield _format_sse("", "✍️ Sedang menggenerate narasi...", False)

    full_response_text = ""
    start_time = datetime.now()

    try:
        # Jika murni lampiran gambar, execute_layer_3_executor akan otomatis menyuplai path fisik ke Gemma Vision secara native
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
        logger.info(
            f"[LAYER 3] Complete | Generated {len(full_response_text)} chars in {elapsed:.2f}s"
        )

    except Exception as e:
        logger.error(f"[LAYER 3] Error: {str(e)}")
        error_msg = f"Gagal mengeksekusi tanggapan sosial: {str(e)}"
        yield _format_sse(error_msg, "", False)
        full_response_text = error_msg

    # ========== DATABASE PERSISTENCE & ANALYTICS DATA BINDING ==========
    if payload.session_uuid:
        logger.info("[DATABASE] Saving chat messages & auto-titling...")

        await chat_history_service.auto_update_session_title(
            payload.session_uuid, user_message
        )

        await chat_history_service.save_chat_message(
            session_id=payload.session_uuid,
            role="assistant",
            text=full_response_text,
            thought="Processed via Layer 3 [Social Executor with Mirroring Strategy]",
        )

        if not (payload.attachment_paths and len(payload.attachment_paths) > 0):
            try:
                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=user_message,
                    assistant_text=full_response_text,
                    context_document=strategy_params.get("rag_context")
                    or "No RAG context utilized",
                )
            except Exception as e:
                logger.warning(
                    f"[DATABASE] Failed to save dialogue analytic corpus: {str(e)}"
                )

    logger.info("[PIPELINE] Sequential pipeline complete ✅")
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


@router.post(
    "/documents/upload", summary="Mengunggah Lampiran Chat (Gambar/PDF) ke RAGDB"
)
async def upload_chat_attachments(
    files: List[UploadFile] = File(...),
    session_uuid: Optional[str] = Form(None),
):
    """
    Endpoint upload lampiran. Semua operasi database didelegasikan ke chat_history_service.
    """
    uploaded_meta_list = []

    for file in files:
        if not (
            file.content_type.startswith("image/")
            or file.content_type == "application/pdf"
        ):
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
            extracted_text_placeholder = (
                f"[OCR Korpus Berkas {file.filename}]: Ekstraksi taktis siap."
            )

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
            logger.error(
                f"❌ [UPLOAD ERROR] Gagal memproses berkas {file.filename}: {str(err)}"
            )
            if os.path.exists(absolute_write_path):
                os.remove(absolute_write_path)
            raise HTTPException(
                status_code=500,
                detail=f"Gagal memproses lampiran berkas {file.filename}.",
            )

    print(
        f"📦 [UPLOAD SUCCESS] {len(uploaded_meta_list)} Berkas sukses mengunci record 'chat_attachments'!"
    )
    return {"status": "success", "data": uploaded_meta_list}
