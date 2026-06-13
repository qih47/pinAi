from fastapi import APIRouter, HTTPException
from backend.app.core.database import get_db

router = APIRouter()

@router.get("")
async def list_documents():
    """
    Mengambil daftar dokumen regulasi untuk pilihan fokus isolasi context (W7).
    """
    async with get_db() as conn:
        try:
            # Query untuk mengambil ID, judul, nomor, dan nama jenis dokumen
            rows = await conn.fetch("""
                SELECT d.id, d.judul, d.nomor, j.nama AS tipe
                FROM dokumen d
                LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                ORDER BY d.judul ASC;
            """)
            return {
                "status": "success",
                "data": [
                    {
                        "id": r["id"],
                        "judul": r["judul"],
                        "nomor": r["nomor"],
                        "tipe": r["tipe"] or "Regulasi Resmi"
                    }
                    for r in rows
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gagal mengambil daftar dokumen: {str(e)}")
