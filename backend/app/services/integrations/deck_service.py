import logging
from typing import Dict, Any, List, Optional, Tuple
import httpx
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_DECK_SERVICE")

DECK_API_BASE = "https://cloud.pindad.com/index.php/apps/deck/api/v1.0"
DECK_APP_BASE = "https://cloud.pindad.com/apps/deck/board"
TIMEOUT_SECS = 15.0

class DeckService:
    @staticmethod
    async def get_user_deck_credentials(npp: str) -> Optional[Tuple[str, str]]:
        """Mengambil kredensial cloud (Nextcloud Pincloud) user dari tabel user_integrations."""
        if not npp:
            return None
        async with get_db() as conn:
            row = await conn.fetchrow(
                "SELECT cloud_username, cloud_password FROM user_integrations WHERE npp = $1", 
                npp
            )
            if row and row["cloud_username"] and row["cloud_password"]:
                return (row["cloud_username"], row["cloud_password"])
        return None

    @staticmethod
    async def fetch_boards(username: str, password: str) -> List[Dict[str, Any]]:
        """Mengambil daftar board Nextcloud Deck yang dapat diakses pengguna."""
        headers = {"OCS-APIRequest": "true", "Accept": "application/json"}
        url = f"{DECK_API_BASE}/boards"
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
                resp = await client.get(url, auth=(username, password), headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"[DECK] Failed to fetch boards: HTTP {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"[DECK] Error fetching boards: {e}")
            return []

    @staticmethod
    async def fetch_board_stacks(board_id: int, username: str, password: str) -> List[Dict[str, Any]]:
        """Mengambil seluruh stack (kolom) dan kartu di dalam board tertentu."""
        headers = {"OCS-APIRequest": "true", "Accept": "application/json"}
        url = f"{DECK_API_BASE}/boards/{board_id}/stacks"
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
                resp = await client.get(url, auth=(username, password), headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"[DECK] Failed to fetch stacks for board {board_id}: HTTP {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"[DECK] Error fetching stacks for board {board_id}: {e}")
            return []

    @classmethod
    async def get_user_assigned_cards(
        cls, 
        npp: str, 
        board_id: Optional[int] = None,
        include_all_boards_if_none: bool = True
    ) -> Dict[str, Any]:
        """
        Mengambil semua kartu/tugas yang di-assign ke user berdasarkan NPP atau identitas terkait.
        Mencocokkan primaryKey, displayname, atau email prefix akun.
        """
        creds = await cls.get_user_deck_credentials(npp)
        if not creds:
            return {
                "status": "error",
                "code": "NOT_CONNECTED",
                "message": "Akun Pincloud belum terhubung atau kredensial belum tersimpan di Cakra AI.",
                "boards": [],
                "active_cards": [],
                "done_cards": [],
                "total_assigned": 0
            }

        username, password = creds
        raw_boards = await cls.fetch_boards(username, password)
        if not raw_boards:
            return {
                "status": "success",
                "message": "Tidak ada board Nextcloud Deck yang ditemukan.",
                "boards": [],
                "active_cards": [],
                "done_cards": [],
                "total_assigned": 0
            }

        target_boards = []
        if board_id is not None:
            target_boards = [b for b in raw_boards if b.get("id") == board_id]
        elif include_all_boards_if_none:
            # Default prioritize boards like PROYEK 2026, 2025, or all
            target_boards = raw_boards

        # Kunci pencocokan fleksibel
        username_clean = username.split("@")[0].lower()
        npp_clean = npp.strip().lower()

        def is_user_assigned(assigned_users: list) -> bool:
            for u in assigned_users:
                p = u.get("participant") or {}
                pk = str(p.get("primaryKey") or "").lower()
                uid = str(p.get("uid") or "").lower()
                display = str(p.get("displayname") or "").lower()
                
                if (npp_clean and npp_clean in display) or \
                   (username_clean and (username_clean == pk or username_clean == uid or username_clean in display)):
                    return True
            return False

        all_active_cards = []
        all_done_cards = []
        processed_boards = []

        for b in target_boards:
            b_id = b.get("id")
            b_title = b.get("title", f"Board {b_id}")
            b_color = b.get("color") or "#0284c7"
            
            stacks = await cls.fetch_board_stacks(b_id, username, password)
            board_cards = []

            for stack in stacks:
                stack_title = stack.get("title", "")
                is_done_stack = any(kw in stack_title.lower() for kw in ["done", "selesai", "finish", "closed"])

                for card in stack.get("cards", []):
                    assigned_users = card.get("assignedUsers", [])
                    if is_user_assigned(assigned_users):
                        # Ekstrak team members
                        team_members = []
                        for au in assigned_users:
                            part = au.get("participant") or {}
                            team_members.append({
                                "primary_key": part.get("primaryKey", ""),
                                "name": part.get("displayname", part.get("primaryKey", "")),
                            })

                        card_info = {
                            "card_id": card.get("id"),
                            "title": card.get("title"),
                            "description": card.get("description", ""),
                            "duedate": card.get("duedate"),
                            "stack_id": stack.get("id"),
                            "stack_title": stack_title,
                            "is_done": is_done_stack,
                            "board_id": b_id,
                            "board_title": b_title,
                            "board_url": f"{DECK_APP_BASE}/{b_id}",
                            "team": team_members,
                            "labels": [lbl.get("title") for lbl in card.get("labels", []) if lbl.get("title")]
                        }
                        board_cards.append(card_info)
                        if is_done_stack:
                            all_done_cards.append(card_info)
                        else:
                            all_active_cards.append(card_info)

            if board_cards:
                processed_boards.append({
                    "board_id": b_id,
                    "title": b_title,
                    "color": b_color,
                    "url": f"{DECK_APP_BASE}/{b_id}",
                    "total_cards": len(board_cards),
                    "cards": board_cards
                })

        return {
            "status": "success",
            "user_npp": npp,
            "cloud_username": username,
            "total_assigned": len(all_active_cards) + len(all_done_cards),
            "active_count": len(all_active_cards),
            "done_count": len(all_done_cards),
            "boards": processed_boards,
            "active_cards": all_active_cards,
            "done_cards": all_done_cards
        }
