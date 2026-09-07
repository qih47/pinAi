"""
CAKRA AI — Admin Dashboard Endpoints
====================================
Endpoints untuk administratior: memory consolidation trigger, audit logs, system config, dll.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.system.background_tasks import trigger_manual_memory_consolidation

router = APIRouter()
logger = logging.getLogger("CAKRA_ADMIN")


@router.post("/run-memory-consolidation")
async def manual_memory_consolidation_trigger(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Manual trigger untuk konsolidasi memori pegawai (Nightly Job).
    Hanya bisa diakses oleh admin yang sudah login.
    
    Usage: POST /api/admin/run-memory-consolidation
    """
    if not current_user_npp:
        logger.warning("⚠️ [ADMIN] Akses admin memory consolidation tanpa login ditolak")
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    logger.info(f"🔧 [ADMIN] User {current_user_npp} memicu manual memory consolidation...")
    
    try:
        result = await trigger_manual_memory_consolidation()
        logger.info(f"✅ [ADMIN] Manual consolidation selesai: {result}")
        return {
            "status": "success",
            "message": "Konsolidasi memori berhasil dijalankan secara manual",
            "details": result
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Manual consolidation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Manual consolidation failed: {str(e)}"
        )


@router.get("/system-status")
async def get_system_status(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Endpoint untuk melihat status sistem CAKRA AI (GPU, memory, scheduler jobs, dll).
    Hanya bisa diakses oleh admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        import torch
        from backend.app.services.system.background_tasks import scheduler
        
        gpu_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else "N/A"
        vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3 if gpu_available else 0.0
        
        scheduler_status = "RUNNING" if (scheduler and scheduler.running) else "STOPPED"
        
        logger.info(f"📊 [ADMIN] {current_user_npp} mengakses system status")
        
        return {
            "status": "success",
            "system": {
                "gpu": {
                    "available": gpu_available,
                    "name": gpu_name,
                    "vram_gb": f"{vram_total:.2f}" if vram_total > 0 else "0.00"
                },
                "scheduler": {
                    "status": scheduler_status,
                    "jobs": [
                        {
                            "id": job.id,
                            "name": job.name,
                            "next_run": str(job.next_run_time) if job.next_run_time else "N/A"
                        }
                        for job in (scheduler.get_jobs() if scheduler and scheduler.running else [])
                    ]
                }
            }
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] System status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")


@router.get("/cache-stats")
async def get_embedding_cache_stats(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Get embedding cache statistics (W13).
    Only accessible for logged-in admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        from backend.app.utils.embedding_cache import get_embedding_cache
        cache = get_embedding_cache()
        return {
            "status": "success",
            "stats": cache.stats()
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Cache stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.post("/clear-embedding-cache")
async def clear_embedding_cache_endpoint(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Clear all embedding cache entries (W13).
    Only accessible for logged-in admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        from backend.app.utils.embedding_cache import get_embedding_cache
        cache = get_embedding_cache()
        cache.clear()
        logger.info(f"🧹 [ADMIN] Embedding cache cleared by user {current_user_npp}")
        return {
            "status": "success",
            "message": "Embedding cache cleared successfully"
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Clear cache error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/vector-index-status")
async def get_vector_index_status_endpoint(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Get HNSW index status and DB size information (W15).
    Only accessible for logged-in admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        from backend.app.utils.vector_index import get_index_info
        from backend.app.core.database import get_db_pool
        
        indexes = await get_index_info()
        
        # Check if HNSW index is active
        hnsw_active = False
        parsed_indexes = []
        for idx in indexes:
            is_hnsw = "hnsw" in idx["indexdef"].lower()
            if is_hnsw:
                hnsw_active = True
            parsed_indexes.append({
                "name": idx["indexname"],
                "definition": idx["indexdef"],
                "scans": idx["scans"] or 0,
                "tuples_read": idx["tuples_read"] or 0,
                "tuples_fetched": idx["tuples_fetched"] or 0,
                "size": idx["size"] or "N/A"
            })
            
        # Get chunk stats
        pool = get_db_pool()
        total_chunks = 0
        table_size = "N/A"
        total_with_indexes = "N/A"
        
        try:
            async with pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT 
                        count(*) as total_chunks,
                        pg_size_pretty(pg_relation_size('dokumen_chunk'::regclass)) as table_size,
                        pg_size_pretty(pg_total_relation_size('dokumen_chunk'::regclass)) as total_with_indexes
                    FROM dokumen_chunk
                """)
                if stats:
                    total_chunks = stats["total_chunks"]
                    table_size = stats["table_size"]
                    total_with_indexes = stats["total_with_indexes"]
        except Exception as db_err:
            logger.warning(f"⚠️ Failed to query DB stats: {db_err}")
            
        return {
            "status": "success",
            "hnsw_active": hnsw_active,
            "indexes": parsed_indexes,
            "stats": {
                "total_chunks": total_chunks,
                "table_size": table_size,
                "total_with_indexes": total_with_indexes
            }
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Vector index status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get vector index status: {str(e)}")


@router.post("/optimize-vector-index")
async def optimize_vector_index_endpoint(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Run VACUUM ANALYZE to optimize vector search performance (W15).
    Only accessible for logged-in admin.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")
    
    try:
        from backend.app.utils.vector_index import optimize_vector_search
        
        logger.info(f"🔧 [ADMIN] User {current_user_npp} triggering vector index optimization...")
        stats = await optimize_vector_search()
        
        return {
            "status": "success",
            "message": "Vector index optimized and VACUUM ANALYZE completed successfully",
            "stats": {
                "total_chunks": stats["total_chunks"] if stats else 0,
                "table_size": stats["table_size"] if stats else "N/A",
                "total_with_indexes": stats["total_with_indexes"] if stats else "N/A"
            }
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Optimize index error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to optimize vector index: {str(e)}")

# =========================================================================================
# OPSI 4: GENERATED ARTIFACTS VAULT & AUDIT
# =========================================================================================

from backend.app.core.paths import ACCOUNTS_DIR
from fastapi.responses import PlainTextResponse, FileResponse
import os
from pathlib import Path
from datetime import datetime

@router.get("/artifacts")
async def admin_list_artifacts(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Mengambil seluruh daftar artifact yang pernah digenerate oleh AI.
    """
    artifacts_list = []
    base_dir = Path(ACCOUNTS_DIR)
    
    if not base_dir.exists():
        return {"status": "success", "artifacts": []}
        
    # Struktur direktori: accounts/{npp}/{session_id}/artifacts/{filename}
    try:
        for npp_dir in base_dir.iterdir():
            if not npp_dir.is_dir():
                continue
            npp = npp_dir.name
            
            for session_dir in npp_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                session_id = session_dir.name
                
                folders_to_check = [
                    session_dir / "brain" / "artifacts",
                    session_dir / "artifacts",
                ]
                seen_files = set()
                for artifact_folder in folders_to_check:
                    if not artifact_folder.exists() or not artifact_folder.is_dir():
                        continue
                    for file_path in artifact_folder.iterdir():
                        if file_path.is_file() and file_path.name not in seen_files:
                            seen_files.add(file_path.name)
                            stat = file_path.stat()
                            artifacts_list.append({
                                "npp": npp,
                                "session_id": session_id,
                                "filename": file_path.name,
                                "size": stat.st_size,
                                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                            })
                        
        # Urutkan berdasarkan waktu pembuatan terbaru
        artifacts_list.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "status": "success",
            "artifacts": artifacts_list
        }
    except Exception as e:
        logger.error(f"❌ [ADMIN] Failed to list artifacts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list artifacts: {str(e)}")


@router.get("/artifacts/read", response_class=PlainTextResponse)
async def admin_read_artifact(
    npp: str,
    session_id: str,
    filename: str,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Membaca konten file artifact (Admin Vault).
    """
    safe_name = Path(filename).name
    if not safe_name or safe_name.startswith(".") or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")
        
    target = Path(ACCOUNTS_DIR) / str(npp) / str(session_id) / "brain" / "artifacts" / safe_name
    if not target.exists() or not target.is_file():
        target = Path(ACCOUNTS_DIR) / str(npp) / str(session_id) / "artifacts" / safe_name
    
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact tidak ditemukan.")
        
    if target.stat().st_size > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File terlalu besar untuk dibaca langsung.")
        
    return PlainTextResponse(content=target.read_text(encoding="utf-8", errors="replace"), media_type="text/plain; charset=utf-8")


@router.get("/artifacts/download")
async def admin_download_artifact(
    npp: str,
    session_id: str,
    filename: str,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Mengunduh file artifact secara langsung.
    """
    safe_name = Path(filename).name
    if not safe_name or safe_name.startswith(".") or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")
        
    target = Path(ACCOUNTS_DIR) / str(npp) / str(session_id) / "brain" / "artifacts" / safe_name
    if not target.exists() or not target.is_file():
        target = Path(ACCOUNTS_DIR) / str(npp) / str(session_id) / "artifacts" / safe_name
    
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact tidak ditemukan.")
        
    return FileResponse(
        path=target,
        filename=safe_name,
        media_type="application/octet-stream"
    )

import zipfile
import io
from fastapi.responses import StreamingResponse

@router.get("/artifacts/download_all")
async def admin_download_all_artifacts(
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Mengunduh SEMUA artifact dari semua user dan sesi sebagai file ZIP.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")

    base_dir = Path(ACCOUNTS_DIR)
    if not base_dir.exists():
        raise HTTPException(status_code=404, detail="Tidak ada artifact di sistem.")

    zip_buffer = io.BytesIO()
    file_count = 0
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for npp_dir in base_dir.iterdir():
            if not npp_dir.is_dir(): continue
            for session_dir in npp_dir.iterdir():
                if not session_dir.is_dir(): continue
                folders_to_check = [
                    session_dir / "brain" / "artifacts",
                    session_dir / "artifacts",
                ]
                seen_session_files = set()
                for artifact_folder in folders_to_check:
                    if not artifact_folder.exists() or not artifact_folder.is_dir(): continue
                    for file_path in artifact_folder.iterdir():
                        if file_path.is_file() and file_path.name not in seen_session_files:
                            seen_session_files.add(file_path.name)
                            # Create an organized path in the zip: npp/session_id/filename
                            arcname = f"{npp_dir.name}/{session_dir.name}/{file_path.name}"
                            zip_file.write(file_path, arcname)
                            file_count += 1

                        
    if file_count == 0:
        raise HTTPException(status_code=404, detail="Tidak ada file yang bisa didownload.")

    zip_buffer.seek(0)
    logger.info(f"[ADMIN] Download All Artifacts by {current_user_npp} ({file_count} files)")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=all_cakra_artifacts.zip"}
    )


# =========================================================================================
# OPSI 5: USER MANAGEMENT & HRIS SYNCHRONIZATION
# =========================================================================================
from pydantic import BaseModel, Field
from backend.app.services.admin.user_management_service import UserManagementService


class CreateManualUserPayload(BaseModel):
    npp: str = Field(..., description="ID / NPP Unik untuk user non-resmi")
    fullname: str = Field(..., description="Nama lengkap user")
    divisi: Optional[str] = Field("Mitra / Non-Tetap", description="Divisi / Unit / Instansi")
    role: str = Field("USER", description="Role: USER, TRAINER, ADMIN, SUPERADMIN")
    password: str = Field(..., min_length=6, description="Password minimal 6 karakter")
    email: Optional[str] = Field(None, description="Email user (opsional)")


class ImportHrisUserPayload(BaseModel):
    npp: str = Field(..., description="NPP Karyawan dari HRIS DB")
    role: str = Field("USER", description="Role awal yang diberikan di CAKRA")


class UpdateUserRolePayload(BaseModel):
    role: str = Field(..., description="Role baru: USER, TRAINER, ADMIN, SUPERADMIN")


class ResetUserPasswordPayload(BaseModel):
    password: str = Field(..., min_length=6, description="Password baru minimal 6 karakter")


@router.get("/users")
async def get_users_endpoint(
    page: int = 1,
    page_size: int = 15,
    search: str = "",
    role: str = "",
    type: str = "",
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Mengambil daftar pengguna yang terdaftar di ragdb.users lengkap dengan statistik
    dan pagination.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")

    try:
        data = await UserManagementService.get_users_list(
            page=page,
            page_size=page_size,
            search=search,
            role_filter=role,
            type_filter=type,
        )
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"❌ [ADMIN] Error get_users_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/manual")
async def create_manual_user_endpoint(
    payload: CreateManualUserPayload,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Menambahkan user non-resmi/non-tetap langsung ke ragdb.users dengan password bcrypt.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")

    try:
        user = await UserManagementService.create_manual_user(
            npp=payload.npp,
            fullname=payload.fullname,
            divisi=payload.divisi or "Mitra / Non-Tetap",
            role=payload.role,
            password=payload.password,
            email=payload.email,
        )
        return {
            "status": "success",
            "message": f"Pengguna manual '{payload.fullname}' ({payload.npp}) berhasil ditambahkan ke CAKRA.",
            "data": user,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ [ADMIN] Error create_manual_user_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/hris-search")
async def search_hris_users_endpoint(
    q: str = "",
    limit: int = 25,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Pencarian personil resmi di hris_db (MURNI SELECT / Read-Only).
    Menampilkan apakah personil sudah di-import ke ragdb atau belum.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")

    try:
        results = await UserManagementService.search_hris_employees(
            search_query=q,
            limit=limit,
        )
        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"❌ [ADMIN] Error search_hris_users_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/import-hris")
async def import_hris_user_endpoint(
    payload: ImportHrisUserPayload,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Mengimpor / menyinkronkan data karyawan dari hris_db ke ragdb.users.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")

    try:
        user = await UserManagementService.import_hris_employee(
            npp=payload.npp,
            initial_role=payload.role,
        )
        return {
            "status": "success",
            "message": f"Karyawan HRIS '{user['fullname']}' ({payload.npp}) berhasil disinkronkan ke CAKRA.",
            "data": user,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ [ADMIN] Error import_hris_user_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{npp}/role")
async def update_user_role_endpoint(
    npp: str,
    payload: UpdateUserRolePayload,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Mengubah role pengguna di ragdb.users.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")

    try:
        result = await UserManagementService.update_user_role(
            npp=npp,
            new_role=payload.role,
            current_admin_npp=current_user_npp,
        )
        return {
            "status": "success",
            "message": f"Role pengguna {npp} berhasil diubah menjadi {payload.role.upper()}.",
            "data": result,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ [ADMIN] Error update_user_role_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{npp}/password")
async def reset_user_password_endpoint(
    npp: str,
    payload: ResetUserPasswordPayload,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Mereset password pengguna di ragdb.users dengan bcrypt hash baru.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")

    try:
        result = await UserManagementService.reset_user_password(
            npp=npp,
            new_password=payload.password,
        )
        return {
            "status": "success",
            "message": f"Password pengguna {npp} berhasil di-reset.",
            "data": result,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ [ADMIN] Error reset_user_password_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{npp}")
async def delete_user_endpoint(
    npp: str,
    current_user_npp: Optional[str] = Depends(get_current_user_npp),
):
    """
    Menghapus akun pengguna dari ragdb.users dan mencabut sesi aktifnya.
    TIDAK MENYENTUH HRIS DB.
    """
    if not current_user_npp:
        raise HTTPException(status_code=401, detail="Login required for admin functions")

    try:
        result = await UserManagementService.delete_user(
            npp=npp,
            current_admin_npp=current_user_npp,
        )
        return {
            "status": "success",
            "message": f"Pengguna {npp} berhasil dihapus dari CAKRA.",
            "data": result,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ [ADMIN] Error delete_user_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

