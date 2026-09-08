"""
CAKRA AI — Room Brain Service (Collab Space)
=============================================
Manajer folder `brain/` per ruang diskusi kolaborasi tim (Collab Room).
Menerapkan arsitektur Single Source of Truth (SSOT) di bawah Room Master
dengan sinkronisasi transparan ke seluruh anggota tim yang diundang.

Struktur folder:
  accounts/{master_npp}/collab/{room_id}/brain/
    ├── documents/        ← cache OCR & text_map per dokumen acuan (doc_{doc_id}.json)
    ├── images/           ← berkas fisik lampiran tim (PDF, Gambar, Word, Excel)
    ├── artifacts/        ← dokumen/draft kerja yang dihasilkan AI untuk tim
    └── manifest.json     ← katalog lampiran, cache, dan daftar anggota tersinkronisasi
"""

import os
import json
import logging
import re
import asyncio
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.paths import (
    get_collab_room_brain_dir,
    get_collab_member_dir,
    ensure_collab_symlink
)

logger = logging.getLogger("CAKRA_COLLAB_BRAIN")


class RoomBrainService:
    """
    Manajer folder brain/ untuk ruang diskusi kolaborasi tim.

    Usage:
        room_brain = RoomBrainService(master_npp="06652", room_id="1c735f12-...")
        room_brain.ensure_structure()
        room_brain.sync_member(member_npp="07781")
        await room_brain.record_attachment(metadata)
    """

    def __init__(self, master_npp: str, room_id: str):
        self.master_npp = re.sub(r"[^\w\-]", "_", str(master_npp))
        self.room_id = re.sub(r"[^\w\-]", "_", str(room_id))
        self._brain_dir: Optional[Path] = None

    @property
    def brain_dir(self) -> Path:
        if self._brain_dir is None:
            self._brain_dir = get_collab_room_brain_dir(self.master_npp, self.room_id)
        return self._brain_dir

    @property
    def images_dir(self) -> Path:
        p = self.brain_dir / "images"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def documents_dir(self) -> Path:
        p = self.brain_dir / "documents"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def artifacts_dir(self) -> Path:
        p = self.brain_dir / "artifacts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def manifest_path(self) -> Path:
        return self.brain_dir / "manifest.json"

    def ensure_structure(self) -> None:
        """Membuat struktur folder brain master ruangan jika belum ada."""
        try:
            self.images_dir
            self.documents_dir
            self.artifacts_dir
            if not self.manifest_path.exists():
                self._write_manifest_sync({
                    "room_id": self.room_id,
                    "master_npp": self.master_npp,
                    "created_at": datetime.datetime.now().isoformat(),
                    "members": [self.master_npp],
                    "attachments": [],
                    "documents": {}
                })
        except Exception as e:
            logger.error(f"[ROOM_BRAIN] Gagal membuat struktur folder room {self.room_id}: {e}")

    def sync_member(self, member_npp: str) -> bool:
        """
        Menghubungkan akun anggota tim yang di-invite ke Room Master Brain.
        Membuat symlink OS dan memperbarui manifest.json.
        """
        if not member_npp or member_npp == "GUEST":
            return False
        clean_member = re.sub(r"[^\w\-]", "_", str(member_npp))
        try:
            self.ensure_structure()
            # 1. Pastikan OS symlink terbentuk
            symlink_ok = ensure_collab_symlink(self.master_npp, clean_member, self.room_id)

            # 2. Catat anggota ke manifest.json
            manifest = self.get_manifest()
            members = set(manifest.get("members", []))
            members.add(clean_member)
            manifest["members"] = list(members)
            manifest["last_synced_at"] = datetime.datetime.now().isoformat()
            self._write_manifest_sync(manifest)

            logger.info(f"🔗 [ROOM_BRAIN] Member {clean_member} synced with room {self.room_id} (Symlink: {symlink_ok})")
            return True
        except Exception as e:
            logger.error(f"[ROOM_BRAIN] Gagal sync member {member_npp} untuk room {self.room_id}: {e}")
            return False

    def get_manifest(self) -> Dict[str, Any]:
        """Membaca isi manifest.json ruangan."""
        if not self.manifest_path.exists():
            return {
                "room_id": self.room_id,
                "master_npp": self.master_npp,
                "created_at": datetime.datetime.now().isoformat(),
                "members": [self.master_npp],
                "attachments": [],
                "documents": {}
            }
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[ROOM_BRAIN] Gagal membaca manifest {self.manifest_path}: {e}")
            return {}

    def _write_manifest_sync(self, data: Dict[str, Any]) -> None:
        """Menulis manifest.json secara atomik."""
        tmp_path = self.manifest_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp_path.replace(self.manifest_path)
        except Exception as e:
            logger.error(f"[ROOM_BRAIN] Gagal menulis manifest {self.manifest_path}: {e}")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    async def record_attachment(self, attachment_meta: Dict[str, Any]) -> None:
        """Mencatat lampiran baru ke dalam manifest ruangan."""
        manifest = self.get_manifest()
        attachments = manifest.get("attachments", [])
        attachments = [a for a in attachments if a.get("filename") != attachment_meta.get("filename")]
        attachments.append(attachment_meta)
        manifest["attachments"] = attachments
        manifest["updated_at"] = datetime.datetime.now().isoformat()
        await asyncio.to_thread(self._write_manifest_sync, manifest)

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Membaca cache ekstraksi dokumen (OCR/text map) bersama di ruangan."""
        safe_id = re.sub(r"[^\w\-]", "_", str(doc_id))
        doc_file = self.documents_dir / f"doc_{safe_id}.json"
        if not doc_file.exists():
            return None
        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[ROOM_BRAIN] Gagal membaca cache doc {doc_id}: {e}")
            return None

    async def save_document(self, doc_id: str, data: Dict[str, Any]) -> None:
        """Menyimpan cache ekstraksi dokumen agar dapat langsung dimanfaatkan seluruh tim."""
        safe_id = re.sub(r"[^\w\-]", "_", str(doc_id))
        doc_file = self.documents_dir / f"doc_{safe_id}.json"
        tmp_file = doc_file.with_suffix(".tmp")
        try:
            payload = {
                "doc_id": str(doc_id),
                "room_id": self.room_id,
                "cached_at": datetime.datetime.now().isoformat(),
                **data
            }
            def _write():
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                tmp_file.replace(doc_file)
            await asyncio.to_thread(_write)

            manifest = self.get_manifest()
            manifest.setdefault("documents", {})[str(doc_id)] = {
                "cached_at": datetime.datetime.now().isoformat(),
                "title": data.get("judul", "")
            }
            await asyncio.to_thread(self._write_manifest_sync, manifest)
        except Exception as e:
            logger.error(f"[ROOM_BRAIN] Gagal menyimpan cache doc {doc_id}: {e}")
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass
