"""
Real-time Notification System — SSE-based Pub/Sub for Live Events
==================================================================
Mengirim notifikasi real-time ke connected clients tentang:
- New sessions dari device lain (multi-device awareness)
- Memory consolidation completed
- Document indexing status updates
- Admin events
"""

import logging
import asyncio
import json
from typing import Dict, Set, Optional, Callable, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger("CAKRA_NOTIFICATIONS")


class NotificationType(str, Enum):
    """Tipe-tipe notifikasi yang bisa dikirim"""
    SESSION_CREATED = "session_created"
    SESSION_DELETED = "session_deleted"
    SESSION_UPDATED = "session_updated"
    MEMORY_CONSOLIDATED = "memory_consolidated"
    DOCUMENT_INDEXED = "document_indexed"
    DOCUMENT_FAILED = "document_failed"
    LOGIN_FROM_DEVICE = "login_from_device"  # Login dari device lain
    ADMIN_ALERT = "admin_alert"
    SYSTEM_NOTICE = "system_notice"


@dataclass
class Notification:
    """Model notifikasi dengan metadata"""
    type: NotificationType
    title: str
    message: str
    recipient_npp: str  # Target: NPP yang akan menerima notifikasi
    data: Optional[Dict[str, Any]] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_json(self) -> str:
        """Convert ke JSON untuk SSE"""
        payload = {
            "type": self.type.value,
            "title": self.title,
            "message": self.message,
            "data": self.data or {},
            "timestamp": self.created_at.isoformat(),
        }
        return json.dumps(payload, ensure_ascii=False)


class NotificationBroker:
    """
    Pub/Sub broker untuk real-time notifications.
    Mengelola connections dan distribute events.
    """

    def __init__(self):
        # Dict[npp] -> Set[asyncio.Queue] untuk setiap NPP
        self.subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        logger.info("🚀 [NOTIFICATION BROKER] Initialized")

    async def subscribe(self, npp: str) -> asyncio.Queue:
        """
        Client subscribe untuk menerima notifikasi.
        
        Returns:
            asyncio.Queue yang akan menerima notification events
        """
        async with self._lock:
            if npp not in self.subscribers:
                self.subscribers[npp] = set()
            
            queue = asyncio.Queue()
            self.subscribers[npp].add(queue)
            
            logger.info(f"✅ [SUBSCRIBE] NPP {npp} subscribed (total subscribers: {len(self.subscribers[npp])})")
            return queue

    async def unsubscribe(self, npp: str, queue: asyncio.Queue):
        """
        Client unsubscribe.
        """
        async with self._lock:
            if npp in self.subscribers and queue in self.subscribers[npp]:
                self.subscribers[npp].remove(queue)
                logger.info(f"👋 [UNSUBSCRIBE] NPP {npp} unsubscribed")

    async def publish(self, notification: Notification):
        """
        Publish notifikasi ke semua subscriber dari target NPP.
        Non-blocking, menggunakan queue.
        """
        async with self._lock:
            recipient_npp = notification.recipient_npp
            
            if recipient_npp not in self.subscribers:
                logger.debug(f"⚠️ [PUBLISH] No subscribers for NPP {recipient_npp}")
                return
            
            queues = list(self.subscribers[recipient_npp])
            logger.info(
                f"📢 [PUBLISH] Sending {notification.type.value} to {len(queues)} subscribers (NPP: {recipient_npp})"
            )
        
        # Send asynchronously to avoid blocking
        for queue in queues:
            try:
                # Put notification ke queue, max 100 items per subscriber
                queue.put_nowait(notification.to_json())
            except asyncio.QueueFull:
                logger.warning(f"⚠️ [PUBLISH] Queue full for subscriber (NPP: {recipient_npp})")

    async def publish_to_all(self, notification: Notification):
        """
        Broadcast notifikasi ke SEMUA subscriber (admin alerts, system notices).
        """
        async with self._lock:
            all_queues: Set[asyncio.Queue] = set()
            for queues in self.subscribers.values():
                all_queues.update(queues)
            
            logger.info(f"📢 [BROADCAST] Sending {notification.type.value} to {len(all_queues)} total subscribers")
        
        for queue in all_queues:
            try:
                queue.put_nowait(notification.to_json())
            except asyncio.QueueFull:
                logger.warning("⚠️ [BROADCAST] Queue full for some subscriber")

    async def get_stats(self) -> dict:
        """Get broker statistics"""
        async with self._lock:
            total_subscribers = sum(len(queues) for queues in self.subscribers.values())
            return {
                "total_npps": len(self.subscribers),
                "total_subscribers": total_subscribers,
                "npp_breakdown": {npp: len(queues) for npp, queues in self.subscribers.items()},
            }


# Singleton instance
_notification_broker: Optional[NotificationBroker] = None


def get_notification_broker() -> NotificationBroker:
    """Get atau create singleton NotificationBroker"""
    global _notification_broker
    if _notification_broker is None:
        _notification_broker = NotificationBroker()
    return _notification_broker


# Convenience functions untuk publish common events

async def notify_new_session(npp: str, session_uuid: str, session_title: str):
    """Notify ketika sesi baru dibuat dari device lain"""
    broker = get_notification_broker()
    notification = Notification(
        type=NotificationType.SESSION_CREATED,
        title="Sesi Baru Dimulai",
        message=f"Sesi '{session_title}' dibuat dari device lain",
        recipient_npp=npp,
        data={"session_uuid": session_uuid, "session_title": session_title},
    )
    await broker.publish(notification)


async def notify_memory_consolidated(npp: str):
    """Notify setelah memory consolidation selesai"""
    broker = get_notification_broker()
    notification = Notification(
        type=NotificationType.MEMORY_CONSOLIDATED,
        title="✅ Memori Terkonsolidasi",
        message="Memori jangka panjang Anda telah diperbarui",
        recipient_npp=npp,
        data={"consolidated_at": datetime.now().isoformat()},
    )
    await broker.publish(notification)


async def notify_document_indexed(npp: str, doc_id: int, doc_title: str):
    """Notify setelah dokumen selesai di-index"""
    broker = get_notification_broker()
    notification = Notification(
        type=NotificationType.DOCUMENT_INDEXED,
        title="📚 Dokumen Terindeks",
        message=f"Dokumen '{doc_title}' siap untuk RAG",
        recipient_npp=npp,
        data={"doc_id": doc_id, "doc_title": doc_title},
    )
    await broker.publish(notification)


async def notify_login_from_device(npp: str, device_name: str, ip_address: str):
    """Notify login dari device baru/berbeda"""
    broker = get_notification_broker()
    notification = Notification(
        type=NotificationType.LOGIN_FROM_DEVICE,
        title="🔐 Login Baru Terdeteksi",
        message=f"Login dari {device_name} ({ip_address})",
        recipient_npp=npp,
        data={"device": device_name, "ip": ip_address},
    )
    await broker.publish(notification)


async def notify_admin_alert(title: str, message: str, severity: str = "info"):
    """Broadcast admin alert ke semua admin users"""
    broker = get_notification_broker()
    notification = Notification(
        type=NotificationType.ADMIN_ALERT,
        title=title,
        message=message,
        recipient_npp="ADMIN",  # Special target untuk broadcast
        data={"severity": severity},
    )
    await broker.publish_to_all(notification)
