"""
CAKRA AI — Document Writer Endpoints
====================================
Endpoint API untuk template dokumen resmi dan kompilasi ekspor berkas DOCX.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Dict, Any, Optional
import urllib.parse
from backend.app.services.document_writer.doc_writer_service import doc_writer_service

router = APIRouter(prefix="/doc-writer", tags=["Document Writer"])


class ExportDocxRequest(BaseModel):
    html_content: str
    title: Optional[str] = "Dokumen Resmi PT Pindad"
    template_id: Optional[str] = "template_blank"
    metadata: Optional[Dict[str, Any]] = None


@router.get("/templates")
async def get_templates():
    """
    Mengambil katalog daftar template resmi (SE, SKEP, Memo Dinas, Blank).
    """
    templates = doc_writer_service.get_available_templates()
    return {
        "success": True,
        "templates": templates
    }


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
