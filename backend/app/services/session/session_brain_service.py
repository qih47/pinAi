"""
CAKRA AI — Session Brain Service
==================================
Manajer folder `brain/` per sesi pengguna.

Struktur folder brain:
  accounts/{npp}/{session_id}/brain/
    ├── documents/        ← cache dokumen yang sudah diekstrak (JSON per doc)
    ├── images/           ← (future: foto/scan yang diupload)
    ├── artifacts/        ← (future: file yang digenerate AI)
    └── manifest.json     ← daftar semua item di brain ini

Catatan Step 1:
  Brain di sini masih paralel dengan struktur lama (images/ dan artifacts/ di luar brain/).
  Migrasi path akan terjadi di Step 2.
"""

import json
import logging
import re
import asyncio
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("CAKRA_BRAIN")

ACCOUNTS_BASE = Path("/home/qisthi/pinAi/accounts")


class SessionBrainService:
    """
    Manajer folder brain/ untuk satu sesi pengguna.

    Usage:
        brain = SessionBrainService(npp="06652", session_id="abc123-...")
        doc = brain.get_document("12345")   # None jika belum ada
        await brain.save_document("12345", extracted_doc)
    """

    def __init__(self, npp: str, session_id: str):
        self.npp = re.sub(r"[^\w\-]", "_", str(npp))
        self.session_id = re.sub(r"[^\w\-]", "_", str(session_id))
        self._brain_dir: Optional[Path] = None

    # ─── Path Properties ──────────────────────────────────────────────────────
    @property
    def brain_dir(self) -> Path:
        if self._brain_dir is None:
            self._brain_dir = ACCOUNTS_BASE / self.npp / self.session_id / "brain"
        return self._brain_dir

    @property
    def documents_dir(self) -> Path:
        return self.brain_dir / "documents"

    @property
    def artifacts_dir(self) -> Path:
        return self.brain_dir / "artifacts"

    @property
    def manifest_path(self) -> Path:
        return self.brain_dir / "manifest.json"

    def _ensure_dirs(self) -> None:
        """Buat semua folder brain jika belum ada."""
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def save_artifact_manifest(self, filename: str, relative_path: str, size_bytes: int = 0) -> None:
        """Catat artefak baru ke dalam manifest.json."""
        manifest = self.get_manifest()
        if not manifest.get("created_at"):
            manifest["created_at"] = datetime.datetime.now().isoformat()
        manifest.setdefault("artifacts", {})[filename] = {
            "path": relative_path,
            "saved_at": datetime.datetime.now().isoformat(),
            "size": size_bytes
        }
        self._save_manifest(manifest)

    # ─── Manifest ─────────────────────────────────────────────────────────────
    def get_manifest(self) -> Dict[str, Any]:
        """Baca manifest.json. Return dict kosong jika belum ada."""
        if not self.manifest_path.exists():
            return {"documents": {}, "artifacts": {}, "created_at": None}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[BRAIN] Manifest baca gagal: {e}")
            return {"documents": {}, "artifacts": {}, "created_at": None}

    def _save_manifest(self, manifest: Dict[str, Any]) -> None:
        """Tulis manifest.json ke disk."""
        try:
            self.manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"[BRAIN] Manifest tulis gagal: {e}")

    # ─── Document Cache ────────────────────────────────────────────────────────
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Ambil dokumen dari brain cache.

        Args:
            doc_id: ID unik dokumen (bisa ID DB atau path hash).

        Returns:
            Dict berisi data dokumen (full_text, pages, metadata), atau None jika tidak ada.
        """
        self._ensure_dirs()
        safe_id = re.sub(r"[^\w\-]", "_", str(doc_id))
        doc_file = self.documents_dir / f"doc_{safe_id}.json"

        if not doc_file.exists():
            logger.debug(f"[BRAIN] MISS dokumen: {doc_id}")
            return None

        try:
            data = json.loads(doc_file.read_text(encoding="utf-8"))
            logger.info(f"[BRAIN] 🧠 HIT dokumen: {doc_id}")
            return data
        except Exception as e:
            logger.warning(f"[BRAIN] Gagal baca cache dokumen {doc_id}: {e}")
            return None

    async def save_document(self, doc_id: str, data: Dict[str, Any]) -> None:
        """
        Simpan dokumen ke brain cache secara async.

        Args:
            doc_id: ID unik dokumen.
            data: Data dokumen yang akan disimpan (full_text, pages, metadata, dst).
        """
        self._ensure_dirs()
        safe_id = re.sub(r"[^\w\-]", "_", str(doc_id))
        doc_file = self.documents_dir / f"doc_{safe_id}.json"

        data["_brain_saved_at"] = datetime.datetime.now().isoformat()

        def _write():
            doc_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)
        logger.info(f"[BRAIN] 💾 Disimpan dokumen: {doc_id}")

        # Update manifest
        manifest = self.get_manifest()
        if not manifest.get("created_at"):
            manifest["created_at"] = datetime.datetime.now().isoformat()
        manifest.setdefault("documents", {})[doc_id] = {
            "file": doc_file.name,
            "saved_at": data["_brain_saved_at"],
            "total_pages": data.get("total_pages", 0),
            "title": data.get("title", ""),
            "nomor": data.get("nomor", ""),
            "jenis": data.get("jenis", ""),
            "tanggal": data.get("tanggal", ""),
        }
        self._save_manifest(manifest)

    def has_document(self, doc_id: str) -> bool:
        """Cek apakah dokumen ada di brain tanpa membacanya."""
        safe_id = re.sub(r"[^\w\-]", "_", str(doc_id))
        return (self.documents_dir / f"doc_{safe_id}.json").exists()

    # ─── List & Stats ──────────────────────────────────────────────────────────
    def list_documents(self) -> List[str]:
        """Daftar semua doc_id yang ada di brain."""
        if not self.documents_dir.exists():
            return []
        return [
            f.stem.replace("doc_", "", 1)
            for f in self.documents_dir.glob("doc_*.json")
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Info ringkas tentang brain sesi ini."""
        manifest = self.get_manifest()
        doc_count = len(manifest.get("documents", {}))
        artifact_count = len(manifest.get("artifacts", {}))
        brain_exists = self.brain_dir.exists()

        return {
            "npp": self.npp,
            "session_id": self.session_id,
            "brain_dir": str(self.brain_dir),
            "brain_exists": brain_exists,
            "document_count": doc_count,
            "artifact_count": artifact_count,
            "created_at": manifest.get("created_at"),
        }

    # ─── Cleanup ──────────────────────────────────────────────────────────────
    def clear_documents(self) -> int:
        """Hapus semua cache dokumen. Return jumlah file yang dihapus."""
        if not self.documents_dir.exists():
            return 0
        deleted = 0
        for f in self.documents_dir.glob("doc_*.json"):
            try:
                f.unlink()
                deleted += 1
            except Exception:
                pass
        # Reset manifest documents
        manifest = self.get_manifest()
        manifest["documents"] = {}
        self._save_manifest(manifest)
        logger.info(f"[BRAIN] 🗑️ Dihapus {deleted} cache dokumen sesi {self.session_id}")
        return deleted
