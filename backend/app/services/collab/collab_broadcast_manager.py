"""
CAKRA AI — Collab Broadcast Manager
===================================
Manajer event streaming Server-Sent Events (SSE) untuk broadcast pesan,
indikator mengetik (typing), dan pembaruan dokumen real-time di Collab Space.
"""

import asyncio
import json
import logging
from typing import Dict, Set, AsyncGenerator, Any

logger = logging.getLogger("COLLAB_BROADCAST")


class CollabBroadcastManager:
    """
    Menyimpan subscriber queue per room_id dan melakukan fan-out broadcast.
    """

    def __init__(self):
        # room_id -> set of asyncio.Queue
        self._rooms: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, room_id: str) -> AsyncGenerator[str, None]:
        """
        Mendaftarkan client ke event stream room_id dan mengalirkan event SSE.
        """
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = set()
            self._rooms[room_id].add(queue)

        logger.info(f"📡 [COLLAB_SSE] Client connected to room {room_id}. Total listeners: {len(self._rooms[room_id])}")

        try:
            # Kirim initial ping / handshake
            init_payload = {"type": "connected", "room_id": room_id}
            yield f"data: {json.dumps(init_payload)}\n\n"

            while True:
                # Menunggu event masuk ke antrean
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat / Keep-alive setiap 30 detik
                    yield f": heartbeat\n\n"

        except asyncio.CancelledError:
            logger.info(f"📡 [COLLAB_SSE] Client disconnected from room {room_id}")
        finally:
            async with self._lock:
                if room_id in self._rooms and queue in self._rooms[room_id]:
                    self._rooms[room_id].remove(queue)
                    if not self._rooms[room_id]:
                        del self._rooms[room_id]

    async def broadcast(self, room_id: str, event_data: Dict[str, Any]):
        """
        Mengirimkan event_data ke seluruh client yang sedang aktif di room_id.
        """
        async with self._lock:
            listeners = list(self._rooms.get(room_id, []))

        if not listeners:
            return

        for q in listeners:
            try:
                if not q.full():
                    q.put_nowait(event_data)
            except Exception as e:
                logger.warning(f"⚠️ [COLLAB_SSE] Failed to enqueue event to listener: {e}")

    async def send_typing(self, room_id: str, sender: str, is_typing: bool, sender_npp: str = "", photo_url: Optional[str] = None):
        """
        Broadcast indikator mengetik.
        """
        await self.broadcast(room_id, {
            "type": "typing",
            "sender": sender,
            "sender_npp": sender_npp,
            "photo_url": photo_url,
            "profile_photo_url": photo_url,
            "is_typing": is_typing
        })


collab_broadcast_manager = CollabBroadcastManager()
