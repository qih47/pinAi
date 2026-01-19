from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import logging
import uuid
import os
from pathlib import Path
from typing import Optional
from backend.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/files")
async def get_files():
    """
    Get list of uploaded files
    """
    try:
        upload_dir = Path(settings.UPLOAD_FOLDER)
        if not upload_dir.exists():
            upload_dir.mkdir(parents=True, exist_ok=True)
        
        files = []
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                files.append({
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "created_at": file_path.stat().st_ctime
                })
        
        return {"status": "success", "data": files}
    except Exception as e:
        logger.error(f"Error retrieving files: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"System Error: {str(e)}"}
        )


@router.get("/db_doc/{filename}")
async def get_db_doc(filename: str):
    """
    Get document from db_doc folder
    """
    try:
        db_doc_path = Path(settings.DB_DOC_FOLDER) / filename
        
        if not db_doc_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Return file content or path
        return {"status": "success", "data": {"filename": filename, "path": str(db_doc_path)}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving db_doc: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"System Error: {str(e)}"}
        )