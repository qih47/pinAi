"""
CAKRA AI — Dual-Layer Memory Engine (Short-Term Journal & Long-Term Manifest)
=============================================================================
Menyediakan penyimpanan dan penarikan memori percakapan terstruktur:
1. Short-Term Memory (Intra-Session Journal):
   - accounts/{npp}/{session_id}/brain/session_journal.json
   - Menyimpan active_topics, listed_items, dan key_decisions sesi berjalan.
   - Diinjeksi saat routing["history_scope"] == "full_session" (misal: "apa saja yang tadi udah kita list").
2. Long-Term Memory (Cross-Session Manifest):
   - accounts/{npp}/brain/sessions_manifest.json
   - Menyimpan rangkuman sesi-sesi lampau per pengguna.
   - Diinjeksi saat routing["history_scope"] == "cross_session" (misal: "kemarin kita bahas apa soal X").

Non-blocking background updates, zero streaming latency impact.
"""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.app.core.paths import ACCOUNTS_DIR

logger = logging.getLogger("CAKRA_MEMORY")


def _get_safe_id(val: str, default: str = "guest") -> str:
    """Membersihkan ID (NPP atau session_uuid) agar aman di filesystem."""
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(val)).strip("_")
    return safe or default


def get_session_journal_path(npp: str, session_id: str) -> Path:
    """Mengembalikan path file session_journal.json."""
    safe_npp = _get_safe_id(npp, "guest")
    safe_session = _get_safe_id(session_id, "default_session")
    target_dir = Path(ACCOUNTS_DIR) / safe_npp / safe_session / "brain"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "session_journal.json"


def get_sessions_manifest_path(npp: str) -> Path:
    """Mengembalikan path file sessions_manifest.json."""
    safe_npp = _get_safe_id(npp, "guest")
    target_dir = Path(ACCOUNTS_DIR) / safe_npp / "brain"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "sessions_manifest.json"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SHORT-TERM INTRA-SESSION JOURNAL
# ═══════════════════════════════════════════════════════════════════════════════

def get_session_journal(npp: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Membaca session_journal.json jika ada."""
    if not npp or not session_id:
        return None
    try:
        path = get_session_journal_path(npp, session_id)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"[MEMORY] Gagal membaca session journal ({session_id}): {e}")
    return None


def format_session_journal_for_prompt(journal: Dict[str, Any]) -> str:
    """Memformat journal menjadi blok teks siap injeksi ke prompt Call 2."""
    if not journal:
        return ""

    topics = ", ".join(journal.get("active_topics", [])) or "Diskusi Berjalan"
    items = journal.get("listed_items", [])
    decisions = journal.get("key_decisions", [])

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "📋 <SESSION_JOURNAL>: RINGKASAN RESMI SESI BERJALAN",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Topik Aktif: {topics}"
    ]

    if items:
        lines.append("\nDaftar Item / Rencana / Artefak yang Telah Dibahas:")
        for it in items[:15]:  # Batas 15 item agar prompt tetap ramping
            lines.append(f"• {it}")

    if decisions:
        lines.append("\nKeputusan & Kesepakatan Teknis:")
        for d in decisions[:8]:
            lines.append(f"• {d}")

    lines.append(
        "\nInstruksi: Gunakan rangkuman resmi di atas untuk menjawab permintaan rekapitulasi, "
        "daftar item, atau keputusan tanpa perlu menebak dari teks percakapan mentah."
    )
    return "\n".join(lines)


async def update_session_journal_background(
    npp: str,
    session_id: str,
    user_message: str,
    assistant_reply: str,
    routing: Optional[Dict[str, Any]] = None
) -> None:
    """
    Memperbarui session_journal.json secara asinkron di latar belakang.
    Mengekstrak topik, daftar berkas (<create_file>), dan bullet points dari respons.
    """
    if not npp or not session_id or npp == "guest":
        return

    try:
        path = get_session_journal_path(npp, session_id)
        current = get_session_journal(npp, session_id) or {
            "session_id": session_id,
            "active_topics": [],
            "listed_items": [],
            "key_decisions": [],
            "turn_count": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # 1. Update Turn Count
        current["turn_count"] = current.get("turn_count", 0) + 1
        current["updated_at"] = datetime.now().isoformat()

        # 2. Ekstrak Topik dari Routing
        if routing and isinstance(routing, dict):
            topic = routing.get("active_topic") or routing.get("key_subject")
            if topic and isinstance(topic, str):
                topic_clean = topic.strip()
                if topic_clean and topic_clean not in current["active_topics"]:
                    current["active_topics"].append(topic_clean)
                    if len(current["active_topics"]) > 6:
                        current["active_topics"] = current["active_topics"][-6:]

        # 3. Ekstrak Berkas Fisik yang Dibuat (<create_file filename="...">)
        created_files = re.findall(r'<create_file\s+filename=["\']([^"\']+)["\']', assistant_reply)
        for f in created_files:
            item_desc = f"Berkas Dibuat: {f}"
            if item_desc not in current["listed_items"]:
                current["listed_items"].append(item_desc)

        # 4. Ekstrak Daftar Angka / Bullet Penting jika User Meminta Rencana / List
        if any(w in user_message.lower() for w in ["buatkan list", "daftar", "langkah", "rencana", "fitur"]):
            # Ambil baris bertipe 1. ..., 2. ... atau - ...
            raw_bullets = re.findall(r'(?:^\s*(?:\d+\.|\-|\*)\s+([^\n]{5,120}))', assistant_reply, flags=re.MULTILINE)
            for b in raw_bullets[:8]:
                b_clean = b.strip()
                if b_clean and b_clean not in current["listed_items"]:
                    current["listed_items"].append(b_clean)

        # Batas ceiling listed_items
        if len(current["listed_items"]) > 25:
            current["listed_items"] = current["listed_items"][-25:]

        # 5. Tulis secara atomik ke disk
        path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug(f"[MEMORY] Journal updated for session {session_id} (turn {current['turn_count']})")

    except Exception as e:
        logger.warning(f"[MEMORY] Gagal update session journal ({session_id}): {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LONG-TERM CROSS-SESSION MANIFEST
# ═══════════════════════════════════════════════════════════════════════════════

def get_sessions_manifest(npp: str) -> Optional[Dict[str, Any]]:
    """Membaca sessions_manifest.json per pengguna."""
    if not npp or npp == "guest":
        return None
    try:
        path = get_sessions_manifest_path(npp)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"[MEMORY] Gagal membaca sessions manifest ({npp}): {e}")
    return None


def get_matching_past_sessions(npp: str, query: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Mencari sesi-sesi lampau yang relevan berdasarkan kecocokan kata kunci pada query."""
    manifest = get_sessions_manifest(npp)
    if not manifest or not query:
        return []

    sessions = manifest.get("sessions", [])
    if not sessions:
        return []

    query_words = set(re.findall(r'\w{3,}', query.lower()))
    scored_sessions = []

    for s in sessions:
        title = (s.get("title") or "").lower()
        summary = (s.get("summary") or "").lower()
        topics = " ".join(s.get("topics", [])).lower()
        combined = f"{title} {summary} {topics}"

        # Hitung overlap kata kunci
        score = sum(1 for w in query_words if w in combined)
        if score > 0:
            scored_sessions.append((score, s))

    # Urutkan berdasarkan score tertinggi lalu waktu terbaru
    scored_sessions.sort(key=lambda x: (x[0], x[1].get("updated_at", "")), reverse=True)
    return [s for _, s in scored_sessions[:limit]]


def format_past_sessions_for_prompt(past_sessions: List[Dict[str, Any]]) -> str:
    """Memformat rangkuman sesi masa lalu menjadi blok siap injeksi."""
    if not past_sessions:
        return ""

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🧠 <CROSS_SESSION_MEMORY>: RINGKASAN SESI PERCAKAPAN LAMPAU",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    for idx, s in enumerate(past_sessions, 1):
        title = s.get("title") or f"Sesi #{idx}"
        summary = s.get("summary") or "Diskusi sebelumnya"
        topics = ", ".join(s.get("topics", []))
        lines.append(f"Diskusi Lampau {idx} ({title}):")
        if topics:
            lines.append(f"Topik: {topics}")
        lines.append(f"Rangkuman: {summary}\n")

    lines.append(
        "Instruksi: Gunakan ingatan masa lalu di atas sebagai referensi pendukung "
        "jika pengguna merujuk ke percakapan terdahulu / proyek sebelumnya."
    )
    return "\n".join(lines)


async def register_session_to_manifest(
    npp: str,
    session_id: str,
    title: str,
    summary: str,
    topics: Optional[List[str]] = None
) -> None:
    """Mendaftarkan atau memperbarui entri sesi ke dalam sessions_manifest.json pengguna."""
    if not npp or npp == "guest" or not session_id:
        return

    try:
        path = get_sessions_manifest_path(npp)
        manifest = get_sessions_manifest(npp) or {
            "npp": npp,
            "sessions": [],
            "updated_at": datetime.now().isoformat()
        }

        sessions = manifest.get("sessions", [])
        existing = next((s for s in sessions if s.get("session_id") == session_id), None)

        now_str = datetime.now().isoformat()
        if existing:
            existing["title"] = title or existing.get("title", "Sesi Diskusi")
            existing["summary"] = summary or existing.get("summary", "")
            if topics:
                existing["topics"] = list(set(existing.get("topics", []) + topics))
            existing["updated_at"] = now_str
        else:
            sessions.append({
                "session_id": session_id,
                "title": title or "Sesi Diskusi",
                "summary": summary or "",
                "topics": topics or [],
                "updated_at": now_str
            })

        # Batasi maksimal 50 sesi tersimpan dalam manifest
        if len(sessions) > 50:
            sessions = sessions[-50:]

        manifest["sessions"] = sessions
        manifest["updated_at"] = now_str
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug(f"[MEMORY] Manifest updated for user {npp} with session {session_id}")

    except Exception as e:
        logger.warning(f"[MEMORY] Gagal update sessions manifest ({npp}): {e}")
