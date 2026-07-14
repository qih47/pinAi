import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("CAKRA_NEXTCLOUD")
router = APIRouter()

NEXTCLOUD_BASE_URL = "https://cloud.pindad.com/remote.php/webdav"

class NextcloudAuth(BaseModel):
    username: str
    password: str
    
class UploadFileRequest(BaseModel):
    auth: NextcloudAuth
    path: str
    content: str
    filename: str

class DownloadFileRequest(BaseModel):
    auth: NextcloudAuth
    path: str

@router.post("/list")
async def list_files(
    auth: NextcloudAuth = Body(...),
    path: str = Body("/")
):
    """
    List files in a specific Nextcloud directory using WebDAV PROPFIND.
    """
    url = f"{NEXTCLOUD_BASE_URL}{path}"
    headers = {"Depth": "1"}
    # Simplified XML for PROPFIND
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
        response = requests.request(
            "PROPFIND", 
            url, 
            auth=HTTPBasicAuth(auth.username, auth.password),
            headers=headers,
            data=data,
            timeout=10
        )
        if response.status_code in [207, 200]:
            # For simplicity, returning raw XML string to be parsed or just status success
            # In a full implementation, we'd parse the XML. 
            # For this MVP, we return a success status to verify auth.
            return {"status": "success", "message": "Successfully connected", "raw_xml": response.text}
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Nextcloud error: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"[NEXTCLOUD] Failed to connect: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect to Nextcloud server")

@router.post("/upload")
async def upload_file(
    req: UploadFileRequest
):
    """
    Upload a file to Nextcloud using WebDAV PUT.
    """
    # Ensure path ends with /
    folder_path = req.path if req.path.endswith("/") else f"{req.path}/"
    url = f"{NEXTCLOUD_BASE_URL}{folder_path}{req.filename}"
    
    try:
        response = requests.put(
            url,
            auth=HTTPBasicAuth(req.auth.username, req.auth.password),
            data=req.content.encode('utf-8'),
            timeout=15
        )
        if response.status_code in [200, 201, 204]:
            return {"status": "success", "message": f"File {req.filename} uploaded successfully"}
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Nextcloud upload error: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"[NEXTCLOUD] Failed to upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload file to Nextcloud")

@router.post("/download")
async def download_file(
    req: DownloadFileRequest
):
    """
    Download a file from Nextcloud using WebDAV GET.
    """
    url = f"{NEXTCLOUD_BASE_URL}{req.path}"
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(req.auth.username, req.auth.password),
            timeout=15
        )
        if response.status_code == 200:
            return {"status": "success", "content": response.text}
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Nextcloud download error: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"[NEXTCLOUD] Failed to download: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download file from Nextcloud")
