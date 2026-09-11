"""
CAKRA AI — Document Writer & ONLYOFFICE Endpoints
=================================================
Endpoint API untuk template dokumen resmi, pembuatan berkas dinamis,
konfigurasi editor ONLYOFFICE (DocsAPI), callback autosave, dan manipulasi AI.
"""

import os
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.services.document_writer.doc_writer_service import doc_writer_service

router = APIRouter(prefix="/doc-writer", tags=["Document Writer"])


# =============================================================================
# Request Models
# =============================================================================

class CreateDocRequest(BaseModel):
    template_id: str = "template_blank"
    title: Optional[str] = None
    npp: Optional[str] = "guest"
    session_id: Optional[str] = ""
    room_id: Optional[str] = ""


class AiEditRequest(BaseModel):
    doc_id: str
    instruction: str
    section_id: Optional[str] = None
    content: Optional[str] = None
    npp: Optional[str] = ""
    session_id: Optional[str] = ""
    room_id: Optional[str] = ""


class ExportDocxRequest(BaseModel):
    html_content: str
    title: Optional[str] = "Dokumen Resmi PT Pindad"
    template_id: Optional[str] = "template_blank"
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/templates")
async def get_templates():
    """
    Mengambil katalog daftar template resmi (SE, SKEP, IK, SOP, Nota Dinas, Blank).
    Mendeteksi otomatis berkas .docx baru yang ditambahkan di direktori master template.
    """
    try:
        templates = doc_writer_service.get_available_templates()
        return {
            "success": True,
            "templates": templates
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memuat template: {str(e)}")


@router.post("/create")
async def create_document(req: CreateDocRequest):
    """
    Membuat dokumen baru berbasis template di folder user accounts/{npp}/.../docwriter/.
    """
    try:
        meta = doc_writer_service.create_document(
            template_id=req.template_id,
            npp=req.npp or "guest",
            session_id=req.session_id or "",
            room_id=req.room_id or "",
            initial_title=req.title
        )
        return {
            "success": True,
            "document": meta
        }
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuat dokumen baru: {str(e)}")


@router.get("/active")
async def get_active_document(
    npp: str = Query("", description="NPP pemilik"),
    session_id: str = Query("", description="ID sesi chat"),
    room_id: str = Query("", description="ID collab room")
):
    """
    Mengambil dokumen aktif terakhir dari sesi chat atau ruang kolaborasi.
    """
    try:
        meta = doc_writer_service.get_active_document(
            npp=npp,
            session_id=session_id,
            room_id=room_id
        )
        if meta:
            return {
                "success": True,
                "document": meta
            }
        return {
            "success": False,
            "document": None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil dokumen aktif: {str(e)}")


@router.get("/config/{doc_id}")
async def get_editor_config(
    doc_id: str,
    request: Request,
    npp: str = Query("", description="NPP pemilik"),
    session_id: str = Query("", description="ID sesi chat"),
    room_id: str = Query("", description="ID collab room"),
    user_name: str = Query("Pegawai PT Pindad", description="Nama tampilan user")
):
    """
    Mengambil konfigurasi DocsAPI ONLYOFFICE lengkap dengan token JWT.
    """
    try:
        # Tentukan base_url backend yang dapat diakses oleh server ONLYOFFICE
        # Jika request melalui gateway localhost:8000, gunakan itu
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
        scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
        base_url = f"{scheme}://{host}"

        user_info = {
            "npp": npp,
            "name": user_name,
            "session_id": session_id,
            "room_id": room_id
        }

        config = doc_writer_service.get_onlyoffice_config(
            doc_id=doc_id,
            user_info=user_info,
            base_url=base_url
        )
        return {
            "success": True,
            "config": config
        }
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menghasilkan konfigurasi ONLYOFFICE: {str(e)}")


@router.get("/file/{doc_id}")
async def get_document_file(
    doc_id: str,
    npp: str = Query("", description="NPP"),
    session_id: str = Query("", description="Sesi"),
    room_id: str = Query("", description="Room")
):
    """
    Menyajikan berkas fisik .docx untuk diakses oleh ONLYOFFICE Document Server
    atau dipratinjau oleh browser.
    """
    doc_meta = doc_writer_service.locate_document(doc_id, npp=npp, session_id=session_id, room_id=room_id)
    if not doc_meta or not Path(doc_meta["file_path"]).exists():
        raise HTTPException(status_code=404, detail=f"Berkas dokumen '{doc_id}' tidak ditemukan.")

    file_path = Path(doc_meta["file_path"])
    safe_title = (doc_meta.get("title") or doc_id).strip().replace(" ", "_")
    if not safe_title.lower().endswith(".docx"):
        filename = f"{safe_title}.docx"
    else:
        filename = safe_title

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )


@router.post("/callback/{doc_id}")
async def onlyoffice_callback(doc_id: str, request: Request):
    """
    Webhook callback dari ONLYOFFICE Document Server saat dokumen disimpan (autosave).
    ONLYOFFICE mengharuskan response JSON: {"error": 0}.
    """
    try:
        body = await request.json()
        result = doc_writer_service.save_callback_file(doc_id, body)
        return result
    except Exception as e:
        # ONLYOFFICE tetap mengharapkan format error
        return {"error": 1, "message": str(e)}


@router.post("/ai-edit")
async def apply_ai_edit(req: AiEditRequest):
    """
    Menerapkan perubahan teks/instruksi dari AI langsung ke berkas .docx dan me-reload editor.
    """
    try:
        result = doc_writer_service.apply_ai_edit(
            doc_id=req.doc_id,
            instruction=req.instruction,
            section_id=req.section_id,
            content=req.content,
            npp=req.npp or "",
            session_id=req.session_id or "",
            room_id=req.room_id or ""
        )
        return result
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menerapkan edit AI: {str(e)}")


@router.get("/download/{doc_id}")
async def download_document(
    doc_id: str,
    npp: str = Query("", description="NPP"),
    session_id: str = Query("", description="Sesi"),
    room_id: str = Query("", description="Room")
):
    """
    Mengunduh berkas Word (.docx) secara langsung ke komputer pengguna.
    """
    doc_meta = doc_writer_service.locate_document(doc_id, npp=npp, session_id=session_id, room_id=room_id)
    if not doc_meta or not Path(doc_meta["file_path"]).exists():
        raise HTTPException(status_code=404, detail=f"Dokumen '{doc_id}' tidak ditemukan.")

    file_path = Path(doc_meta["file_path"])
    safe_title = (doc_meta.get("title") or "Dokumen_Pindad").strip().replace(" ", "_")
    if not safe_title.lower().endswith(".docx"):
        filename = f"{safe_title}.docx"
    else:
        filename = safe_title
    encoded_filename = urllib.parse.quote(filename)

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


# =============================================================================
# Backward Compatibility Endpoint
# =============================================================================

@router.post("/export-docx")
async def export_docx(req: ExportDocxRequest):
    """
    Mengompilasi konten Tiptap menjadi file .docx asli berformat resmi PT Pindad.
    """
    try:
        docx_bytes = doc_writer_service.compile_html_to_docx(
            html_content=req.html_content,
            title=req.title or "Dokumen Resmi PT Pindad",
            template_id=req.template_id or "template_blank",
            metadata=req.metadata or {}
        )

        safe_title = (req.title or "Dokumen_Pindad").strip().replace(" ", "_")
        safe_filename = f"{safe_title}.docx"
        encoded_filename = urllib.parse.quote(safe_filename)

        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengompilasi berkas DOCX: {str(e)}")
