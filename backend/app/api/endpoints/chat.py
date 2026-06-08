from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from fastapi.responses import StreamingResponse
import logging
from typing import Optional
from backend.app.core.database import get_db
# 🔌 IMPORT DEPENDENCIES & CORE SERVICES CAKRA AI
from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.core.llm_client import stream_ollama_chat
from backend.app.core.config import settings
from backend.app.services.chat_history_service import chat_history_service
from backend.app.services.memory_service import memory_service
from backend.app.services.rag_service import rag_service

# 🧠 MENGHUBUNGKAN STRUKTUR KOGNITIF: Slot 1 Router & Slot 2 Reasoning Engine
from backend.app.services.agent.router_engine import router_engine
from backend.app.services.agent.cognitive_loop import cognitive_orchestrator

# 📦 SUNTIKAN VALIDASI: Menarik Skema Pydantic V2 dari foldernya yang sah
from backend.app.api.schemas.chat import (
    ChatStreamRequest,
    TitleUpdateSchema,
    TestRouterRequestSchema,
)

router = APIRouter()
logger = logging.getLogger("CAKRA_CHAT_API")


# ==============================================================================
# 📂 SECTION 1: ENDPOINTS MANAJEMEN SESI (SIDEBAR FRONTEND JALUR COMPATIBLE)
# ==============================================================================


@router.get("/sessions", summary="Ambil Daftar Sesi Aktif Pegawai untuk Sidebar")
async def get_history_sessions(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Menarik semua history chat milik user aktif untuk dipasang di Sidebar Frontend.
    Jika masuk dalam Guest Mode, otomatis mengembalikan array kosong secara aman.
    """
    if not current_user_npp:
        return {"status": "success", "data": []}

    sessions = await chat_history_service.get_user_sessions(current_user_npp)
    return {"status": "success", "data": sessions}


@router.post("/sessions/create", summary="Membuat Sesi Obrolan Baru (New Chat)")
async def create_new_chat_session(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
    judul: Optional[str] = Query("Obrolan Baru"),
):
    """Triggered otomatis dari state Zustand saat user klik tombol '+ New Chat' di Sidebar"""
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
    """Triggered saat user selesai melakukan editing nama sesi di komponen Sidebar.jsx"""
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
    """Menaikkan atau menurunkan prioritas sematan sesi obrolan di list Sidebar"""
    # 🔥 FIX SAKTI: Bersihkan double assignment biar syntax-nya valid
    success = await chat_history_service.toggle_pin_session(session_uuid, is_pinned)
    if not success:
        raise HTTPException(
            status_code=500, detail="Gagal merubah status sematan sesi."
        )
    return {"status": "success", "message": "Status sematan sesi berhasil diperbarui!"}


@router.delete("/sessions/{session_uuid}", summary="Soft Delete Sesi Chat")
async def delete_chat_session(session_uuid: str):
    """Menghapus sesi dari tampilan user menggunakan metode soft-delete (is_deleted = TRUE)"""
    success = await chat_history_service.soft_delete_session(session_uuid)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal menghapus sesi obrolan.")
    return {"status": "success", "message": "Sesi obrolan berhasil dihapus, bolo!"}


@router.get("/sessions/{session_uuid}/messages", summary="Ambil Pesan dalam Sesi Chat")
async def get_session_messages(session_uuid: str):
    """Mengambil riwayat pesan untuk sesi tertentu (dipakai saat user klik item di Sidebar)."""
    messages = await chat_history_service.get_session_messages(session_uuid)
    return {"status": "success", "data": messages}


# ==============================================================================
# 🚀 SECTION 2: ENDPOINT UTAMA CORE THREE-ENGINE AGENTIC CHAT (CALIBRATED)
# ==============================================================================

@router.post("/stream", summary="Streaming Engine Obrolan CAKRA AI + Auto-Save")
async def chat_stream_endpoint(
    request: Request,
    payload: ChatStreamRequest,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    user_label = (
        f"Pegawai (NPP: {current_user_npp})"
        if current_user_npp
        else "GUEST (Mode Tamu)"
    )
    print(f"\n💬 [CHAT API] Request obrolan masuk dari {user_label} | Mode: {payload.mode}")

    if not payload.messages:
        raise HTTPException(
            status_code=400, detail="Daftar urutan pesan tidak boleh kosong, cuy!"
        )

    last_user_message = payload.messages[-1].content
    print("\n" + "═" * 50)
    print(f'👤 [USER MSG] Pertanyaan Utuh:\n"{last_user_message}"')
    print("═" * 50)

    # 🧠 EXECUTING SLOT 1: Jalankan Analisis Kognitif Otomatis via Qwen 2.5
    print("🧠 [CHAT API] Menjalankan Analisis Slot 1 Router Engine...")
    cognitive_analysis = await router_engine.analyze_user_query(last_user_message)

    detected_intent = cognitive_analysis.get("intent", "NORMAL")
    detected_sentiment = cognitive_analysis.get("sentiment", "NEUTRAL")

    # 1. AUTO-SAVE pesan user (termasuk sesi guest dengan npp=GUEST di DB)
    if payload.session_uuid:
        await chat_history_service.save_chat_message(
            session_id=payload.session_uuid,
            role="user",
            text=last_user_message,
            thought=f"Intent: {detected_intent} | Sentiment: {detected_sentiment}",
        )

    # Rekonstruksi array payload pesan untuk LLM target
    formatted_messages = [
        {"role": msg.role, "content": msg.content} for msg in payload.messages
    ]

    # 🔀 ORKESTRASI THREE-ENGINE SELECTOR ROUTING (PERSIMPANGAN JALUR COGNITIVE)

    # 🟢 JALUR A: Jika Kueri Butuh Penalaran Berat / Analisis Dokumen / SQL (SLOT 2 - DEEPSEEK R1)
    if detected_intent in ["RAG", "ANALYTICS"]:
        print(f"🔀 [ROUTER DECISION] Intent Kritis '{detected_intent}' Terdeteksi! Menarik Dokumen RAG...")

        # 🚀 Cukup panggil SATU KALI saja biar hemat resources server lo, bolo!
        rag_context = await rag_service.assemble_powerful_context(
            query=last_user_message, limit=4
        )

        if payload.session_uuid:
            try:
                async with get_db() as conn:
                    check_title = await conn.fetchrow(
                        "SELECT judul FROM chat_sessions WHERE session_uuid = $1", payload.session_uuid
                    )
                    if check_title and check_title["judul"] == "Obrolan Baru":
                        auto_title = " ".join(last_user_message.split()[:4]) + "..."
                        await conn.execute(
                            "UPDATE chat_sessions SET judul = $1 WHERE session_uuid = $2", auto_title, payload.session_uuid
                        )
                        print(f"📝 [AUTO TITLE] Berhasil merubah judul sesi RAG: {auto_title}")

                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=last_user_message,
                    context_document=rag_context if rag_context else "Tidak ada dokumen relevan yang lolos threshold",
                )
                print(f"📝 [CORPUS SUCCESS] Kueri User & Knowledge Base Sesi {payload.session_uuid[:8]} dikunci!")
            except Exception as e:
                print(f"⚠️ [CORPUS WARNING] Gagal mengunci data awal korpus RAG: {str(e)}")

        print(f"🔀 [ROUTER DECISION] Membelokkan Traffic ke Slot 2 Reasoning Engine ({settings.MODEL_REASONING})...")

        system_content = (
            "Anda adalah CAKRA AI, asisten analitik tingkat tinggi PT Pindad. "
            "Gunakan kemampuan berpikir mendalam Anda untuk memecahkan masalah teknis, "
            "regulasi dokumen, atau skrip database yang diajukan oleh karyawan.\n\n"
        )

        if rag_context:
            print("📎 [CONTEXT INJECTED] Dokumen Pindad sukses disuntikkan ke dalam ingatan DeepSeek R1!")
            system_content += (
                "Berikut adalah dokumen rahasia korporat valid yang berhasil ditarik dari database internal sebagai dasar analisis Anda. "
                "Wajib gunakan data ini untuk merumuskan jawaban, dan sebutkan judul/nomor regulasi dokumen saat memberikan solusi:\n"
                f"{rag_context}\n"
                "PENTING: Jika dokumen di atas tidak cukup kuat untuk menjawab, sampaikan batas informasinya tanpa berasumsi liar."
            )
        else:
            print("ℹ️  [CONTEXT EMPTY] Zero match context. DeepSeek beroperasi dengan mode penalaran murni.")
            system_content += "Gunakan pengetahuan bawaan Anda untuk menyajikan analisis terstructured beserta solusi mitigasi risikonya secara berwibawa."

        system_prompt_reasoning = {"role": "system", "content": system_content}
        formatted_messages.insert(0, system_prompt_reasoning)

        return StreamingResponse(
            cognitive_orchestrator.stream_reasoning_engine(
                messages=formatted_messages, request=request, temperature=0.6,
                session_uuid=payload.session_uuid
            ),
            media_type="text/event-stream",
        )

    # 🔵 JALUR B: Kueri Bersifat Chit-Chat / Operasional Umum Ringan (SLOT 3 - GEMMA 4)
    else:
        print(f"🤖 [ROUTER DECISION] Intent '{detected_intent}'. Menetap di Slot 3 Persona Engine ({settings.MODEL_PERSONA})...")

        if payload.session_uuid:
            try:
                async with get_db() as conn:
                    check_title = await conn.fetchrow(
                        "SELECT judul FROM chat_sessions WHERE session_uuid = $1", payload.session_uuid
                    )
                    if check_title and check_title["judul"] == "Obrolan Baru":
                        auto_title = " ".join(last_user_message.split()[:4]) + "..."
                        await conn.execute(
                            "UPDATE chat_sessions SET judul = $1 WHERE session_uuid = $2", auto_title, payload.session_uuid
                        )
                        print(f"📝 [AUTO TITLE] Berhasil merubah judul sesi Chit-Chat: {auto_title}")

                await chat_history_service.save_dialogue_corpus(
                    session_uuid=payload.session_uuid,
                    user_text=last_user_message,
                )
                print(f"📝 [CORPUS SUCCESS] Kueri Chit-Chat Sesi {payload.session_uuid[:8]} dikunci!")
            except Exception as e:
                print(f"⚠️ [CORPUS WARNING] Gagal mengunci data awal korpus Chit-Chat: {str(e)}")

        # 🧠 SUNTIKAN MEMORI: Tarik memori masa lalu pegawai dari RAGDB
        npp_query = current_user_npp if current_user_npp else "GUEST"
        past_memory_context = await memory_service.get_employee_long_term_memory(npp_query)

        base_prompt = (
            "Anda adalah CAKRA AI, asisten virtual inteligen terintegrasi milik PT Pindad. "
            "Tugas Anda adalah membantu karyawan dalam analisis data, modernisasi sistem, "
            "dan otomatisasi taktis pekerjaan. Jawablah dengan lugas, profesional, "
            "dan berwibawa khas lingkungan pertahanan, namun tetap suportif."
        )

        if past_memory_context:
            base_prompt += past_memory_context

        if detected_sentiment == "FRUSTRATED":
            base_prompt += " NOTE: Karyawan sedang mengalami kendala/frustrasi teknis. Redam situasi dengan empati taktis yang menenangkan di awal kalimat, lalu berikan solusi instruksi perbaikan yang sangat konkret."

        system_prompt_persona = {"role": "system", "content": base_prompt}
        formatted_messages.insert(0, system_prompt_persona)

        return StreamingResponse(
            stream_ollama_chat(
                model_name=settings.MODEL_PERSONA,
                messages=formatted_messages,
                request=request,
                temperature=payload.temperature,
                session_uuid=payload.session_uuid
            ),
            media_type="text/event-stream",
        )