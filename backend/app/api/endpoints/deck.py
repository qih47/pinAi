import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.api.dependencies.auth import get_current_user_npp
from backend.app.services.integrations.deck_service import DeckService
from backend.app.utils.security_firewall import check_rate_limit

router = APIRouter()
logger = logging.getLogger("CAKRA_DECK_ENDPOINT")

@router.get("/boards")
async def get_my_boards(
    request: Request,
    current_npp: Optional[str] = Depends(get_current_user_npp)
):
    """
    Mengambil daftar board Nextcloud Deck yang dapat diakses pengguna.
    """
    check_rate_limit(request, policy="chat")
    if not current_npp or current_npp.upper() == "GUEST":
        raise HTTPException(status_code=401, detail="Fitur Nextcloud Deck memerlukan login akun resmi.")

    creds = await DeckService.get_user_deck_credentials(current_npp)
    if not creds:
        raise HTTPException(
            status_code=403, 
            detail="Akun Pincloud belum terhubung. Silakan hubungkan akun Nextcloud di menu Settings."
        )

    username, password = creds
    boards = await DeckService.fetch_boards(username, password)
    return {
        "status": "success",
        "total": len(boards),
        "boards": [
            {
                "id": b.get("id"),
                "title": b.get("title"),
                "color": b.get("color"),
                "last_modified": b.get("lastModified"),
                "is_shared": b.get("isShared", False)
            }
            for b in boards
        ]
    }

@router.get("/boards/{board_id}/stacks")
async def get_board_stacks(
    board_id: int,
    request: Request,
    current_npp: Optional[str] = Depends(get_current_user_npp)
):
    """
    Mengambil kolom (stacks) beserta kartu dari board tertentu.
    """
    check_rate_limit(request, policy="chat")
    if not current_npp or current_npp.upper() == "GUEST":
        raise HTTPException(status_code=401, detail="Fitur Nextcloud Deck memerlukan login akun resmi.")

    creds = await DeckService.get_user_deck_credentials(current_npp)
    if not creds:
        raise HTTPException(
            status_code=403, 
            detail="Akun Pincloud belum terhubung. Silakan hubungkan akun Nextcloud di menu Settings."
        )

    username, password = creds
    stacks = await DeckService.fetch_board_stacks(board_id, username, password)
    return {
        "status": "success",
        "board_id": board_id,
        "stacks": stacks
    }

@router.get("/my-tasks")
async def get_my_assigned_tasks(
    request: Request,
    board_id: Optional[int] = Query(None, description="Filter kartu hanya dari board ID tertentu"),
    current_npp: Optional[str] = Depends(get_current_user_npp)
):
    """
    Mengambil seluruh kartu/tugas yang di-assign ke pengguna yang sedang login.
    """
    check_rate_limit(request, policy="chat")
    if not current_npp or current_npp.upper() == "GUEST":
        raise HTTPException(status_code=401, detail="Fitur Nextcloud Deck memerlukan login akun resmi.")

    result = await DeckService.get_user_assigned_cards(
        npp=current_npp, 
        board_id=board_id,
        include_all_boards_if_none=True
    )

    if result.get("code") == "NOT_CONNECTED":
        raise HTTPException(status_code=403, detail=result.get("message"))

    return result
