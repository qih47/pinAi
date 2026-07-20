import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Response, Query
from pydantic import BaseModel
import httpx
from backend.app.core.database import get_db
from backend.app.api.endpoints.auth import verify_session

logger = logging.getLogger("CAKRA_NEXTCLOUD")
router = APIRouter()

NEXTCLOUD_BASE_URL = "https://cloud.pindad.com/remote.php/webdav"
TIMEOUT_SECS = 60.0

class NextcloudAuth(BaseModel):
    username: str
    password: str

async def get_nextcloud_credentials(token: str):
    """Ambil kredensial Nextcloud dari database berdasarkan token sesi."""
    if not token:
        raise HTTPException(status_code=401, detail="Token sesi tidak ditemukan")
        
    try:
        user_data = await verify_session(token=token)
        if not user_data or not hasattr(user_data, 'data'):
            raise HTTPException(status_code=401, detail="Sesi tidak valid")
        npp = user_data.data["npp"]
    except Exception:
        raise HTTPException(status_code=401, detail="Sesi tidak valid")
        
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT cloud_username, cloud_password FROM user_integrations WHERE npp = $1", npp)
        if not row or not row["cloud_username"] or not row["cloud_password"]:
            raise HTTPException(status_code=403, detail="NOT_CONNECTED")
        
        return NextcloudAuth(username=row["cloud_username"], password=row["cloud_password"])

class UploadFileRequest(BaseModel):
    token: str
    path: str
    content: str
    filename: str

class DownloadFileRequest(BaseModel):
    token: str
    path: str

@router.post("/list")
async def list_files(
    token: str = Body(...),
    path: str = Body("/")
):
    """
    List files in a specific Nextcloud directory using WebDAV PROPFIND.
    """
    auth = await get_nextcloud_credentials(token)
    
    url = f"{NEXTCLOUD_BASE_URL}{path}"
    headers = {"Depth": "1"}
    data = """<?xml version="1.0" encoding="utf-8" ?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:displayname/>
        <d:resourcetype/>
        <d:getcontentlength/>
        <d:getlastmodified/>
      </d:prop>
    </d:propfind>
    """
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
            response = await client.request(
                "PROPFIND", 
                url, 
                auth=(auth.username, auth.password),
                headers=headers,
                content=data
            )
            
            if response.status_code in [207, 200]:
                return {"status": "success", "message": "Successfully connected", "raw_xml": response.text}
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Nextcloud error: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"[NEXTCLOUD] Failed to connect: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect to Nextcloud server")

@router.post("/upload")
async def upload_file(
    req: UploadFileRequest
):
    """
    Upload a file to Nextcloud using WebDAV PUT.
    """
    auth = await get_nextcloud_credentials(req.token)
    
    folder_path = req.path if req.path.endswith("/") else f"{req.path}/"
    url = f"{NEXTCLOUD_BASE_URL}{folder_path}{req.filename}"
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
            response = await client.put(
                url,
                auth=(auth.username, auth.password),
                content=req.content.encode('utf-8')
            )
            
            if response.status_code in [200, 201, 204]:
                return {"status": "success", "message": f"File {req.filename} uploaded successfully"}
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Nextcloud upload error: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"[NEXTCLOUD] Failed to upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload file to Nextcloud")

@router.post("/download")
async def download_file(
    req: DownloadFileRequest
):
    """
    Download a file from Nextcloud using WebDAV GET.
    """
    auth = await get_nextcloud_credentials(req.token)
    url = f"{NEXTCLOUD_BASE_URL}{req.path}"
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
            response = await client.get(
                url,
                auth=(auth.username, auth.password)
            )
            
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "application/octet-stream")
                return Response(content=response.content, media_type=content_type)
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Nextcloud download error: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"[NEXTCLOUD] Failed to download: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download file from Nextcloud")
