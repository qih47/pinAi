"""
CAKRA AI — Document Writer & ONLYOFFICE Document Studio Service
==============================================================
Layanan backend terpadu untuk:
1. Dynamic Master Template System (SE, SKEP, IK, SOP, Nota Dinas, Blank).
2. Multi-tenant document storage di accounts/{npp}/{session_id}/brain/docwriter/
   dan accounts/{master_npp}/collab/{room_id}/brain/docwriter/
3. Integrasi ONLYOFFICE Document Server (DocsAPI) dengan autentikasi JWT.
4. Autosave Webhook Callback & Manipulasi AI via python-docx.
"""

import os
import re
import io
import json
import time
import uuid
import shutil
import logging
import base64
import hmac
import hashlib
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import jwt
except ImportError:
    jwt = None

def sign_jwt_token(payload: Dict[str, Any], secret: str) -> str:
    """
    Menghasilkan token JWT HS256 standar RFC 7519 untuk ONLYOFFICE.
    Menggunakan library standard jika PyJWT belum terinstal di environment.
    """
    if jwt:
        tok = jwt.encode(payload, secret, algorithm="HS256")
        return tok.decode("utf-8") if isinstance(tok, bytes) else tok

    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header, separators=(',', ':')).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    return f"{header_b64}.{payload_b64}.{sig_b64}"
from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from backend.app.core.paths import (
    DOCWRITER_TEMPLATES_DIR,
    get_docwriter_dir,
    ACCOUNTS_DIR
)

logger = logging.getLogger("DOC_WRITER_SERVICE")

ONLYOFFICE_JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET", "CAKRA_ONLYOFFICE_SECRET_2026")
ONLYOFFICE_PUBLIC_URL = os.getenv("ONLYOFFICE_PUBLIC_URL", "http://localhost:8085")

# Metadata katalog bawaan untuk template resmi PT Pindad
KNOWN_TEMPLATES_META = {
    "template_skep": {
        "name": "Surat Keputusan Direksi (SKEP)",
        "category": "Regulasi & Kebijakan",
        "description": "Format baku Surat Keputusan Direksi PT Pindad dengan bagian Menimbang, Mengingat, dan Diktum Putusan KESATU/KEDUA.",
        "icon": "FileCheck2",
        "default_title": "Surat Keputusan Direksi PT Pindad",
        "default_number": "SKEP/     /PINDAD/2026"
    },
    "template_se": {
        "name": "Surat Edaran (SE)",
        "category": "Pengumuman & Kebijakan",
        "description": "Format Surat Edaran PT Pindad untuk petunjuk pelaksanaan kebijakan atau instruksi operasional.",
        "icon": "ScrollText",
        "default_title": "Surat Edaran PT Pindad",
        "default_number": "SE/     /PINDAD/2026"
    },
    "template_ik": {
        "name": "Instruksi Kerja (IK)",
        "category": "Teknis & Operasional",
        "description": "Format teknis pelaksanaan kerja, langkah-langkah, peralatan keselamatan, dan parameter pengujian.",
        "icon": "Layers",
        "default_title": "Instruksi Kerja Teknis PT Pindad",
        "default_number": "IK/TI/     /2026"
    },
    "template_prosedur": {
        "name": "Standar Operasional Prosedur (SOP)",
        "category": "Proses Bisnis & SOP",
        "description": "Format SOP Pindad mencakup tujuan, ruang lingkup, pihak terkait, dan diagram alir prosedur kerja.",
        "icon": "CheckCircle2",
        "default_title": "Standar Operasional Prosedur PT Pindad",
        "default_number": "SOP/PROS/     /2026"
    },
    "template_nota_dinas": {
        "name": "Nota Dinas / Memo Internal",
        "category": "Korespondensi Internal",
        "description": "Format tabel naskah dinas antar divisi atau unit kerja di lingkungan PT Pindad.",
        "icon": "Mail",
        "default_title": "Nota Dinas Internal PT Pindad",
        "default_number": "ND/     /TI/2026"
    },
    "template_blank": {
        "name": "Kertas Kerja Standar PT Pindad (A4)",
        "category": "Umum",
        "description": "Kertas kerja kosong berformat margin A4 standar corporate PT Pindad dengan Kop Surat resmi.",
        "icon": "FileText",
        "default_title": "Dokumen Kerja PT Pindad",
        "default_number": ""
    }
}


class DocWriterService:
    """
    Service pengelola ONLYOFFICE Document Studio & Template Dinamis PT Pindad.
    """

    @classmethod
    def get_templates_dir(cls) -> Path:
        p = Path(DOCWRITER_TEMPLATES_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_available_templates(cls) -> List[Dict[str, Any]]:
        """
        Memindai direktori backend/assets/templates/docwriter/ secara dinamis.
        Mendeteksi otomatis berkas .docx baru yang ditambahkan user tanpa perlu restart.
        """
        templates_dir = cls.get_templates_dir()
        result: List[Dict[str, Any]] = []
        found_ids = set()

        # 1. Pindai berkas fisik .docx di templates_dir
        if templates_dir.exists():
            for f in sorted(templates_dir.glob("*.docx")):
                template_id = f.stem
                found_ids.add(template_id)

                if template_id in KNOWN_TEMPLATES_META:
                    meta = dict(KNOWN_TEMPLATES_META[template_id])
                    meta["id"] = template_id
                    meta["filename"] = f.name
                    meta["is_custom"] = False
                    meta["size_bytes"] = f.stat().st_size
                    result.append(meta)
                else:
                    # Template kustom baru yang baru saja ditaruh oleh user
                    clean_name = template_id.replace("template_", "").replace("_", " ").title()
                    meta = {
                        "id": template_id,
                        "name": clean_name,
                        "category": "Kustom / Tambahan",
                        "description": f"Template dokumen Word resmi: {clean_name}",
                        "icon": "FileText",
                        "default_title": clean_name,
                        "default_number": "",
                        "filename": f.name,
                        "is_custom": True,
                        "size_bytes": f.stat().st_size
                    }
                    result.append(meta)

        # 2. Urutkan agar template utama (SE, SKEP, IK, SOP, Nota Dinas, Blank) di posisi teratas
        priority_order = [
            "template_se",
            "template_skep",
            "template_ik",
            "template_prosedur",
            "template_nota_dinas",
            "template_blank"
        ]

        def sort_key(item):
            t_id = item["id"]
            if t_id in priority_order:
                return (0, priority_order.index(t_id))
            return (1, item["name"])

        result.sort(key=sort_key)
        return result

    @classmethod
    def find_template_file(cls, template_id: str) -> Optional[Path]:
        """
        Mencari file template fisik berdasarkan ID.
        """
        templates_dir = cls.get_templates_dir()
        # Coba exact match
        for ext in [".docx", ""]:
            cand = templates_dir / f"{template_id}{ext}"
            if cand.is_file():
                return cand

        # Coba dengan prefix template_
        if not template_id.startswith("template_"):
            cand = templates_dir / f"template_{template_id}.docx"
            if cand.is_file():
                return cand

        # Fallback ke template_blank.docx
        fallback = templates_dir / "template_blank.docx"
        if fallback.is_file():
            return fallback

        return None

    @classmethod
    def create_document(
        cls,
        template_id: str = "template_blank",
        npp: str = "guest",
        session_id: str = "",
        room_id: str = "",
        initial_title: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Membuat dokumen kerja baru berbasis template di folder accounts/{npp}/.../docwriter/.
        """
        tpl_path = cls.find_template_file(template_id)
        if not tpl_path or not tpl_path.exists():
            raise FileNotFoundError(f"Template '{template_id}' tidak ditemukan di {DOCWRITER_TEMPLATES_DIR}")

        master_npp = cls.find_room_master_npp(room_id) if room_id else ""
        storage_dir = Path(get_docwriter_dir(npp=npp, session_id=session_id, room_id=room_id, master_npp=master_npp))
        if room_id and master_npp and master_npp != npp:
            ensure_collab_symlink(master_npp, npp, room_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        now_ts = int(time.time())
        doc_uid = uuid.uuid4().hex[:8]
        doc_id = f"doc_{now_ts}_{doc_uid}"

        target_docx = storage_dir / f"{doc_id}.docx"
        shutil.copyfile(str(tpl_path), str(target_docx))

        # Tentukan judul dokumen
        resolved_title = title or initial_title
        tpl_meta = KNOWN_TEMPLATES_META.get(template_id, {})
        final_title = (resolved_title or tpl_meta.get("default_title") or tpl_path.stem.replace("template_", "").replace("_", " ").title()).strip()

        meta_data = {
            "doc_id": doc_id,
            "title": final_title,
            "template_id": template_id,
            "filename": f"{doc_id}.docx",
            "file_path": str(target_docx),
            "npp": npp,
            "session_id": session_id,
            "room_id": room_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": 1
        }

        meta_file = storage_dir / f"{doc_id}.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)

        # Catat di index registry global per folder
        cls._update_folder_index(storage_dir, meta_data)

        logger.info(f"[DOC_WRITER] Dokumen baru dibuat: {doc_id} ({title}) di {target_docx}")
        return meta_data

    @classmethod
    def _update_folder_index(cls, storage_dir: Path, meta_data: Dict[str, Any]):
        index_file = storage_dir / "index.json"
        index = {}
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                index = {}
        index[meta_data["doc_id"]] = {
            "title": meta_data.get("title"),
            "template_id": meta_data.get("template_id"),
            "updated_at": meta_data.get("updated_at")
        }
        try:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Gagal memperbarui index.json: {e}")

    @classmethod
    def find_room_master_npp(cls, room_id: str) -> str:
        """Mencari NPP pemilik asli (Room Master) berdasarkan direktori fisik accounts/*/collab/{room_id}/brain."""
        if not room_id:
            return ""
        safe_room = "".join(c if c.isalnum() or c == "-" else "_" for c in str(room_id)).strip("_")
        accounts_root = Path(ACCOUNTS_DIR)
        for match in accounts_root.glob(f"*/collab/{safe_room}/brain"):
            if not match.is_symlink():
                return match.parent.parent.parent.name
        return ""

    @classmethod
    def locate_document(
        cls,
        doc_id: str,
        npp: str = "",
        session_id: str = "",
        room_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Menemukan berkas dokumen dan metadatanya.
        Jika room_id atau session_id diberikan, isolasi ketat pada folder spesifik tersebut.
        Global scan hanya diizinkan jika konteks sesi/room sama sekali tidak disertakan.
        """
        master_npp = cls.find_room_master_npp(room_id) if room_id else ""

        # 1. Cek jalur spesifik jika session_id, room_id, atau npp diberikan
        if room_id or session_id:
            storage_dir = Path(get_docwriter_dir(npp=npp, session_id=session_id, room_id=room_id, master_npp=master_npp))
            docx_path = storage_dir / f"{doc_id}.docx"
            meta_path = storage_dir / f"{doc_id}.json"

            # Fallback jika di collab room tapi berkas ada di legacy path collab_shared atau folder collab akun lain
            if room_id and not docx_path.exists():
                safe_room = "".join(c if c.isalnum() or c == "-" else "_" for c in str(room_id)).strip("_")
                legacy_dir = Path(ACCOUNTS_DIR) / "collab_shared" / safe_room / "docwriter"
                if (legacy_dir / f"{doc_id}.docx").exists():
                    docx_path = legacy_dir / f"{doc_id}.docx"
                    meta_path = legacy_dir / f"{doc_id}.json"
                else:
                    room_matches = list(Path(ACCOUNTS_DIR).glob(f"*/collab/{safe_room}/**/{doc_id}.docx"))
                    if room_matches:
                        docx_path = room_matches[0]
                        meta_path = docx_path.parent / f"{doc_id}.json"

            if docx_path.exists():
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            return json.load(f)
                    except Exception:
                        pass
                return {
                    "doc_id": doc_id,
                    "title": doc_id,
                    "file_path": str(docx_path),
                    "updated_at": datetime.fromtimestamp(docx_path.stat().st_mtime).isoformat()
                }
            # Terisolasi: Jika diminta dari sesi/room spesifik namun tidak ada di foldernya, jangan ambil milik room lain
            return None

        # 2. Cek jika hanya npp akun global (fallback)
        if npp:
            storage_dir = Path(get_docwriter_dir(npp=npp))
            docx_path = storage_dir / f"{doc_id}.docx"
            meta_path = storage_dir / f"{doc_id}.json"
            if docx_path.exists():
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            return json.load(f)
                    except Exception:
                        pass
                return {
                    "doc_id": doc_id,
                    "title": doc_id,
                    "file_path": str(docx_path),
                    "updated_at": datetime.fromtimestamp(docx_path.stat().st_mtime).isoformat()
                }

        # 3. Pindai global HANYA jika request anonim (misal callback ONLYOFFICE murni dengan doc_id saja)
        accounts_root = Path(ACCOUNTS_DIR)
        matches = list(accounts_root.glob(f"**/docwriter/{doc_id}.docx"))
        if matches:
            docx_path = matches[0]
            meta_path = docx_path.parent / f"{doc_id}.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return {
                "doc_id": doc_id,
                "title": doc_id,
                "file_path": str(docx_path),
                "updated_at": datetime.fromtimestamp(docx_path.stat().st_mtime).isoformat()
            }

        return None

    @classmethod
    def get_active_document(
        cls,
        npp: str = "",
        session_id: str = "",
        room_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Mendapatkan dokumen aktif terakhir dari direktori kerja user/room/session.
        Membaca index.json atau berkas .json metadata terbaru berdasarkan mtime/updated_at.
        """
        master_npp = cls.find_room_master_npp(room_id) if room_id else ""
        storage_dir = Path(get_docwriter_dir(npp=npp, session_id=session_id, room_id=room_id, master_npp=master_npp))
        if not storage_dir.exists():
            return None

        # 1. Cek index.json
        index_file = storage_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                if isinstance(index_data, dict) and index_data:
                    sorted_docs = sorted(
                        index_data.items(),
                        key=lambda item: str(item[1].get("updated_at", "")),
                        reverse=True
                    )
                    for doc_id, _ in sorted_docs:
                        doc_meta = cls.locate_document(doc_id, npp=npp, session_id=session_id, room_id=room_id)
                        if doc_meta and Path(doc_meta.get("file_path", "")).exists():
                            return doc_meta
            except Exception as e:
                logger.warning(f"Error membaca index.json di {storage_dir}: {e}")

        # 2. Pindai berkas .json di folder docwriter
        json_files = [f for f in storage_dir.glob("doc_*.json") if f.is_file()]
        if json_files:
            json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            for jf in json_files:
                try:
                    with open(jf, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    doc_id = meta.get("doc_id")
                    if doc_id:
                        docx_p = storage_dir / f"{doc_id}.docx"
                        if docx_p.exists():
                            meta["file_path"] = str(docx_p)
                            return meta
                except Exception:
                    continue

        return None

    @classmethod
    def get_onlyoffice_config(
        cls,
        doc_id: str,
        user_info: Optional[Dict[str, Any]] = None,
        base_url: str = "http://localhost:8000"
    ) -> Dict[str, Any]:
        """
        Menghasilkan objek konfigurasi DocsAPI untuk ONLYOFFICE Document Server,
        lengkap dengan JWT token yang telah ditandatangani.
        """
        user_info = user_info or {}
        user_id = str(user_info.get("npp") or user_info.get("id") or "user_pindad")
        user_name = str(user_info.get("nama") or user_info.get("name") or "Pegawai PT Pindad")

        doc_meta = cls.locate_document(
            doc_id,
            npp=user_info.get("npp", ""),
            session_id=user_info.get("session_id", ""),
            room_id=user_info.get("room_id", "")
        )
        if not doc_meta:
            raise FileNotFoundError(f"Dokumen '{doc_id}' tidak ditemukan di sistem penyimpanan.")

        docx_path = Path(doc_meta["file_path"])
        if not docx_path.exists():
            raise FileNotFoundError(f"Berkas fisik .docx '{doc_meta['file_path']}' tidak ditemukan.")

        title = doc_meta.get("title", f"{doc_id}.docx")
        if not title.lower().endswith(".docx"):
            display_title = f"{title}.docx"
        else:
            display_title = title

        # Key unik untuk ONLYOFFICE caching: berubah saat file diperbarui
        file_mtime = int(docx_path.stat().st_mtime)
        doc_key = f"{doc_id}_{file_mtime}"

        # Tentukan internal URL agar container Docker ONLYOFFICE dapat mengunduh berkas & webhook
        internal_url = os.getenv("ONLYOFFICE_BACKEND_URL")
        if not internal_url:
            if "localhost" in base_url or "127.0.0.1" in base_url:
                internal_url = base_url.replace("localhost", "172.17.0.1").replace("127.0.0.1", "172.17.0.1")
            else:
                internal_url = base_url

        file_url = f"{internal_url}/api/doc-writer/file/{doc_id}"
        callback_url = f"{internal_url}/api/doc-writer/callback/{doc_id}"

        config = {
            "document": {
                "fileType": "docx",
                "key": doc_key,
                "title": display_title,
                "url": file_url,
                "permissions": {
                    "download": True,
                    "edit": True,
                    "print": True,
                    "review": True,
                    "comment": True
                }
            },
            "documentType": "word",
            "editorConfig": {
                "callbackUrl": callback_url,
                "user": {
                    "id": user_id,
                    "name": user_name
                },
                "lang": "id",
                "mode": "edit",
                "customization": {
                    "autosave": True,
                    "forcesave": True,
                    "chat": False,
                    "comments": True,
                    "zoom": 100,
                    "compactToolbar": False,
                    "toolbarNoTabs": False,
                    "help": False,
                    "feedback": False
                }
            }
        }

        # Tandatangani JWT Token ONLYOFFICE
        token = sign_jwt_token(config, ONLYOFFICE_JWT_SECRET)
        config["token"] = token

        return config

    @classmethod
    def save_callback_file(cls, doc_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Menangani webhook callback dari ONLYOFFICE saat dokumen diedit dan disimpan.
        ONLYOFFICE status:
        - 1: Dokumen sedang diedit
        - 2: Dokumen siap disimpan (user menutup tab atau autosave periodic)
        - 3: Terjadi error saat menyimpan dokumen
        - 4: Dokumen ditutup tanpa perubahan
        - 6: Dokumen dipaksa simpan (forcesave)
        - 7: Terjadi error pada forcesave
        """
        status = payload.get("status")
        logger.info(f"[DOC_WRITER_CALLBACK] Webhook doc_id={doc_id}, status={status}")

        # Status 2 (Ready for save) atau 6 (Forcesave)
        if status in [2, 6]:
            download_url = payload.get("url")
            if not download_url:
                logger.warning(f"[DOC_WRITER_CALLBACK] Status {status} namun tidak ada URL download")
                return {"error": 0}

            doc_meta = cls.locate_document(doc_id)
            if not doc_meta:
                logger.error(f"[DOC_WRITER_CALLBACK] Dokumen '{doc_id}' tidak ditemukan untuk disimpan.")
                return {"error": 1, "message": "Document not found"}

            target_path = Path(doc_meta["file_path"])
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Unduh berkas yang telah disunting dari server ONLYOFFICE
            try:
                req = urllib.request.Request(download_url, headers={"User-Agent": "CAKRA-AI/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with open(target_path, "wb") as out_file:
                        shutil.copyfileobj(resp, out_file)

                # Update metadata timestamp
                now_str = datetime.now().isoformat()
                meta_path = target_path.parent / f"{doc_id}.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        meta["updated_at"] = now_str
                        meta["version"] = meta.get("version", 1) + 1
                        with open(meta_path, "w", encoding="utf-8") as f:
                            json.dump(meta, f, ensure_ascii=False, indent=2)
                    except Exception as me:
                        logger.warning(f"Gagal memperbarui metadata file {meta_path}: {me}")

                logger.info(f"[DOC_WRITER_CALLBACK] Dokumen {doc_id} berhasil disimpan ke {target_path}")
            except Exception as e:
                logger.error(f"[DOC_WRITER_CALLBACK] Gagal mengunduh berkas dari ONLYOFFICE ({download_url}): {e}")
                return {"error": 1, "message": str(e)}

        return {"error": 0}

    @staticmethod
    def _is_placeholder_paragraph(p) -> bool:
        t = p.text.strip()
        if not t:
            return False
        cleaned = re.sub(r'[….\s_–-]', '', t)
        return len(cleaned) == 0 and len(t) >= 3

    @staticmethod
    def _set_paragraph_text_preserve_format(
        paragraph,
        new_text: str,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        alignment = None
    ):
        """
        Mengubah teks paragraf tanpa merusak Paragraph Properties (<w:pPr>):
        - Mempertahankan alignment (Justify, Left, Center)
        - Mempertahankan left_indent, first_line_indent (hanging indent a.)
        - Mempertahankan tab stops dan spacing
        - Menggunakan font & size dari run pertama (atau default Arial 11pt)
        """
        from docx.shared import Pt

        font_name = "Arial"
        font_size = Pt(11)
        r_bold = False
        r_italic = False

        if paragraph.runs:
            for r in paragraph.runs:
                if r.font.name:
                    font_name = r.font.name
                if r.font.size:
                    font_size = r.font.size
                if r.bold is not None:
                    r_bold = r.bold
                if r.italic is not None:
                    r_italic = r.italic
                break

        if bold is not None:
            r_bold = bold
        if italic is not None:
            r_italic = italic

        # Hapus run tambahan jika ada lebih dari 1 run lama, sisakan run pertama
        if len(paragraph.runs) > 1:
            for extra_r in list(paragraph.runs[1:]):
                try:
                    p_elem = paragraph._element
                    r_elem = extra_r._element
                    if r_elem in p_elem:
                        p_elem.remove(r_elem)
                except Exception:
                    extra_r.text = ""

        if paragraph.runs:
            target_run = paragraph.runs[0]
            target_run.text = new_text
            target_run.font.name = font_name
            target_run.font.size = font_size
            target_run.bold = r_bold
            target_run.italic = r_italic
        else:
            new_run = paragraph.add_run(new_text)
            new_run.font.name = font_name
            new_run.font.size = font_size
            new_run.bold = r_bold
            new_run.italic = r_italic

        if alignment is not None:
            paragraph.alignment = alignment

    @classmethod
    def apply_ai_edit(
        cls,
        doc_id: str,
        instruction: str,
        section_id: Optional[str] = None,
        content: Optional[str] = None,
        npp: str = "",
        session_id: str = "",
        room_id: str = ""
    ) -> Dict[str, Any]:
        """
        Menerapkan manipulasi/revisi teks secara presisi (surgical update) ke berkas .docx:
        1. Membaca node target (Tentang, Dasar poin a/b/c, Ketentuan, dll).
        2. Mempertahankan Paragraph Properties (<w:pPr>) agar Justify, hanging indent, dan margin tidak rusak.
        3. Memperbarui mtime berkas sehingga ONLYOFFICE otomatis memuat versi terbaru.
        """
        doc_meta = cls.locate_document(doc_id, npp=npp, session_id=session_id, room_id=room_id)
        if not doc_meta:
            raise FileNotFoundError(f"Dokumen '{doc_id}' tidak ditemukan.")

        docx_path = Path(doc_meta["file_path"])
        doc = Document(str(docx_path))

        content_str = (content or "").strip()
        instruction_str = (instruction or "").strip()
        combined_query = f"{instruction_str} {section_id or ''}".lower()

        # Parse HTML jika ada
        soup = None
        if "<" in content_str and ">" in content_str:
            try:
                soup = BeautifulSoup(content_str, "html.parser")
            except Exception:
                soup = None

        has_applied_smart_edit = False

        # 1. Ekstrak & Update Judul / Tentang
        tentang = ""
        if soup:
            for el in soup.find_all(["p", "div", "h3", "h4", "span"]):
                txt = el.get_text()
                if "tentang" in txt.lower():
                    parts = re.split(r"tentang\s*:?", txt, flags=re.IGNORECASE)
                    if len(parts) > 1 and parts[1].strip():
                        tentang = parts[1].strip()
                        break
        elif "tentang" in combined_query and any(k in combined_query for k in ["ganti", "ubah", "judul", "menjadi", "jadi"]):
            m = re.search(r'(?:tentang(?:nya)?|judul(?:nya)?)\s*(?:menjadi|jadi|:)\s*(.*)', instruction_str, re.IGNORECASE)
            if m and m.group(1).strip():
                tentang = m.group(1).strip().strip(" \"'.,")

        if tentang:
            for i, p in enumerate(doc.paragraphs):
                if p.text.lower().strip() in ["tentang", "t e n t a n g"]:
                    for j in range(i + 1, min(i + 4, len(doc.paragraphs))):
                        pj = doc.paragraphs[j]
                        if cls._is_placeholder_paragraph(pj) or (pj.text.strip() and not pj.text.strip().lower().startswith("1.")):
                            cls._set_paragraph_text_preserve_format(
                                pj,
                                tentang,
                                bold=True,
                                alignment=WD_ALIGN_PARAGRAPH.CENTER
                            )
                            has_applied_smart_edit = True
                            logger.info(f"[DOC_WRITER] Surgically updated Tentang at P[{j}]: {tentang}")
                            break
                    break

        # 2. Deteksi Target Item Spesifik pada Dasar (poin a, b, c, dll.)
        target_item_match = re.search(r'(?:poin|point|dasar|bagian|huruf|item)\s*([a-z])\b', combined_query)
        if not target_item_match and section_id and section_id.strip().lower() in list("abcdefghijkl"):
            target_item_letter = section_id.strip().lower()
        else:
            target_item_letter = target_item_match.group(1).lower() if target_item_match else None

        # Jika target item spesifik terdeteksi (misal: "edit bagian a jadi ...")
        if target_item_letter:
            new_item_text = ""
            # Coba ambil dari soup list
            if soup:
                lis = soup.find_all("li")
                if lis:
                    # Ambil index sesuai huruf: a=0, b=1, c=2
                    idx = ord(target_item_letter) - ord('a')
                    if 0 <= idx < len(lis):
                        new_item_text = lis[idx].get_text().strip()

            if not new_item_text and content_str:
                if not ("<ol" in content_str.lower() or "<ul" in content_str.lower()):
                    new_item_text = soup.get_text().strip() if soup else content_str.strip()

            if not new_item_text:
                m = re.search(r'(?:jadi|menjadi|adalah|yaitu|:)\s*(.*)', instruction_str, re.IGNORECASE)
                if m and m.group(1).strip():
                    new_item_text = m.group(1).strip().strip(" \"'")
                else:
                    new_item_text = instruction_str.strip()

            # Bersihkan prefix 'a.' jika sudah ada di teks agar tidak double 'a. a. teks'
            new_item_text = re.sub(rf"^{target_item_letter}[\.\)]\s*", "", new_item_text, flags=re.IGNORECASE).strip()
            if new_item_text:
                if not new_item_text.endswith("."):
                    new_item_text += "."
                formatted_item = f"{target_item_letter}.   {new_item_text}"

                for i, p in enumerate(doc.paragraphs):
                    if "dasar" in p.text.lower().strip() or "menimbang" in p.text.lower().strip():
                        target_updated = False
                        last_dasar_pj = None
                        # 1. Cari paragraf yang sudah ada huruf targetnya (misal sudah 'a.')
                        for j in range(i + 1, min(i + 12, len(doc.paragraphs))):
                            pj = doc.paragraphs[j]
                            p_clean = pj.text.strip().lower()
                            if re.match(r"^[a-z][\.\)]", p_clean):
                                last_dasar_pj = pj
                            if p_clean.startswith(f"{target_item_letter}.") or p_clean.startswith(f"{target_item_letter})"):
                                cls._set_paragraph_text_preserve_format(pj, formatted_item)
                                target_updated = True
                                has_applied_smart_edit = True
                                logger.info(f"[DOC_WRITER] Surgically updated existing item {target_item_letter} at P[{j}]: {formatted_item}")
                                break

                        # 2. Jika belum ada (misal masih placeholder ....), isi placeholder pertama yang cocok
                        if not target_updated:
                            for j in range(i + 1, min(i + 12, len(doc.paragraphs))):
                                pj = doc.paragraphs[j]
                                if cls._is_placeholder_paragraph(pj):
                                    cls._set_paragraph_text_preserve_format(pj, formatted_item)
                                    target_updated = True
                                    has_applied_smart_edit = True
                                    logger.info(f"[DOC_WRITER] Surgically filled placeholder item {target_item_letter} at P[{j}]: {formatted_item}")
                                    break

                        # 3. Jika belum ada placeholder dan item adalah item baru, tambahkan paragraf kloning
                        if not target_updated and last_dasar_pj is not None:
                            try:
                                import copy
                                from docx.oxml import OxmlElement
                                from docx.text.paragraph import Paragraph
                                new_p_elem = OxmlElement('w:p')
                                if last_dasar_pj._element.pPr is not None:
                                    new_p_elem.append(copy.deepcopy(last_dasar_pj._element.pPr))
                                last_dasar_pj._element.addnext(new_p_elem)
                                new_p_obj = Paragraph(new_p_elem, doc)
                                cls._set_paragraph_text_preserve_format(new_p_obj, formatted_item)
                                target_updated = True
                                has_applied_smart_edit = True
                                logger.info(f"[DOC_WRITER] Surgically appended new item {target_item_letter}: {formatted_item}")
                            except Exception as append_err:
                                logger.warning(f"[DOC_WRITER] Gagal append item baru: {append_err}")

                        if target_updated:
                            break

        # 3. Update Dasar secara Bulk jika ada beberapa poin dari AI
        elif soup:
            dasar_items = []
            dasar_header = soup.find(lambda e: e.name in ["p", "h4", "strong", "b", "span"] and "dasar" in e.get_text().lower())
            if dasar_header:
                ol = dasar_header.find_next(["ol", "ul"])
                if ol:
                    for li in ol.find_all("li", recursive=False):
                        dasar_items.append(li.get_text().strip())

            if dasar_items:
                for i, p in enumerate(doc.paragraphs):
                    if "dasar" in p.text.lower().strip() or "menimbang" in p.text.lower().strip():
                        item_idx = 0
                        to_delete = []
                        for j in range(i + 1, min(i + 12, len(doc.paragraphs))):
                            pj = doc.paragraphs[j]
                            if cls._is_placeholder_paragraph(pj) or re.match(r"^[a-z][\.\)]", pj.text.strip(), re.IGNORECASE):
                                if item_idx < len(dasar_items):
                                    cur_item_text = dasar_items[item_idx]
                                    cur_letter = chr(ord('a') + item_idx)
                                    cur_item_text = re.sub(rf"^{cur_letter}[\.\)]\s*", "", cur_item_text, flags=re.IGNORECASE).strip()
                                    formatted_line = f"{cur_letter}.   {cur_item_text}"
                                    cls._set_paragraph_text_preserve_format(pj, formatted_line)
                                    has_applied_smart_edit = True
                                    item_idx += 1
                                else:
                                    if cls._is_placeholder_paragraph(pj):
                                        to_delete.append(pj)
                        for dp in to_delete:
                            try:
                                dp._element.getparent().remove(dp._element)
                            except Exception:
                                pass
                        break

        # 4. Ekstrak Ketentuan / Isi Surat (Point 2 pada Surat Edaran)
        if soup and not has_applied_smart_edit:
            ketentuan_intro = ""
            for p in soup.find_all("p"):
                txt = p.get_text().strip()
                if "sehubungan dengan" in txt.lower() or "ditetapkan standar" in txt.lower() or "ketentuan" in txt.lower():
                    ketentuan_intro = txt
                    break

            if ketentuan_intro:
                for i, p in enumerate(doc.paragraphs):
                    if (cls._is_placeholder_paragraph(p) or p.text.strip().startswith("2.")) and i > 10:
                        formatted_ketentuan = f"2.   {ketentuan_intro}" if not ketentuan_intro.startswith("2.") else ketentuan_intro
                        cls._set_paragraph_text_preserve_format(p, formatted_ketentuan)
                        has_applied_smart_edit = True
                        logger.info(f"[DOC_WRITER] Surgically updated Ketentuan at P[{i}]")
                        break

        # 5. Fallback jika tidak ada pola khusus yang cocok
        if not has_applied_smart_edit:
            fallback_text = content_str or instruction_str
            if "<" in fallback_text and ">" in fallback_text:
                try:
                    fallback_text = BeautifulSoup(fallback_text, "html.parser").get_text(separator="\n").strip()
                except Exception:
                    pass

            replaced = False
            for p in doc.paragraphs:
                if cls._is_placeholder_paragraph(p):
                    cls._set_paragraph_text_preserve_format(p, fallback_text)
                    replaced = True
                    break

            if not replaced and fallback_text.strip():
                tembusan_idx = None
                for idx, p in enumerate(doc.paragraphs):
                    if "tembusan" in p.text.lower():
                        tembusan_idx = idx
                        break

                if tembusan_idx is not None:
                    p = doc.paragraphs[tembusan_idx].insert_paragraph_before(fallback_text)
                else:
                    p = doc.add_paragraph(fallback_text)
                p.paragraph_format.space_after = Pt(6)

        # Simpan kembali berkas .docx
        doc.save(str(docx_path))

        # Sentuh mtime agar DocsAPI key berbeda
        now_ts = time.time()
        os.utime(str(docx_path), (now_ts, now_ts))

        # Update metadata
        meta_path = docx_path.parent / f"{doc_id}.json"
        now_iso = datetime.now().isoformat()
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["updated_at"] = now_iso
                meta["version"] = meta.get("version", 1) + 1
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        logger.info(f"[DOC_WRITER] AI Edit berhasil diterapkan ke berkas .docx: {docx_path}")
        return {
            "success": True,
            "doc_id": doc_id,
            "updated_at": now_iso,
            "message": "Perubahan AI berhasil disimpan ke dokumen Word."
        }

    # =========================================================================
    # BACKWARD COMPATIBILITY: Legacy HTML to DOCX Compiler
    # =========================================================================
    @classmethod
    def compile_html_to_docx(
        cls,
        html_content: str,
        title: str = "Dokumen Resmi PT Pindad",
        template_id: str = "template_blank",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Mengonversi konten HTML dari editor menjadi berkas .docx in-memory.
        """
        metadata = metadata or {}
        doc = Document()

        section = doc.sections[0]
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

        style = doc.styles['Normal']
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)
        font.color.rgb = RGBColor(0, 0, 0)

        include_kop = metadata.get("include_kop", True)
        if include_kop:
            kop_p = doc.add_paragraph()
            kop_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            kop_p.paragraph_format.space_after = Pt(2)

            run_pt = kop_p.add_run("PT PINDAD (PERSERO)\n")
            run_pt.bold = True
            run_pt.font.size = Pt(14)

            run_sub = kop_p.add_run("DIVISI TEKNOLOGI INFORMASI & KOMUNIKASI\n")
            run_sub.bold = True
            run_sub.font.size = Pt(11)

            run_addr = kop_p.add_run("Jl. Gatot Subroto No. 517, Bandung 40284 | Telp: (022) 7321964 | www.pindad.com")
            run_addr.font.size = Pt(8.5)
            run_addr.font.italic = True
            run_addr.font.color.rgb = RGBColor(100, 100, 100)

            divider = doc.add_paragraph()
            divider.paragraph_format.space_after = Pt(18)
            pBdr = OxmlElement('w:pBdr')
            bottom_border = OxmlElement('w:bottom')
            bottom_border.set(qn('w:val'), 'single')
            bottom_border.set(qn('w:sz'), '18')
            bottom_border.set(qn('w:space'), '4')
            bottom_border.set(qn('w:color'), '000000')
            pBdr.append(bottom_border)
            divider._p.get_or_add_pPr().append(pBdr)

        soup = BeautifulSoup(html_content, "html.parser")
        for element in soup.children:
            if isinstance(element, NavigableString):
                text_clean = str(element).strip()
                if text_clean:
                    p = doc.add_paragraph(text_clean)
                    p.paragraph_format.space_after = Pt(6)
                continue

            if not isinstance(element, Tag):
                continue

            tag_name = element.name.lower()
            if tag_name in ['h1', 'h2', 'h3', 'h4']:
                level = int(tag_name[1])
                h_p = doc.add_paragraph()
                h_p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
                h_p.paragraph_format.space_after = Pt(4)
                h_run = h_p.add_run(element.get_text())
                h_run.bold = True
                h_run.font.name = 'Arial'
                h_run.font.size = Pt(13 if level == 1 else 11)
            elif tag_name == 'p':
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.line_spacing = 1.15
                cls._render_inline_elements(element, p)
            elif tag_name in ['ul', 'ol']:
                is_ordered = tag_name == 'ol'
                for li in element.find_all('li', recursive=False):
                    style_name = 'List Number' if is_ordered else 'List Bullet'
                    try:
                        p = doc.add_paragraph(style=style_name)
                    except Exception:
                        p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(3)
                    cls._render_inline_elements(li, p)

        output_stream = io.BytesIO()
        doc.save(output_stream)
        output_stream.seek(0)
        return output_stream.getvalue()

    @staticmethod
    def _render_inline_elements(parent_tag: Tag, paragraph):
        for child in parent_tag.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text:
                    paragraph.add_run(text)
            elif isinstance(child, Tag):
                tag = child.name.lower()
                run = paragraph.add_run(child.get_text())
                if tag in ['strong', 'b']:
                    run.bold = True
                elif tag in ['em', 'i']:
                    run.italic = True
                elif tag in ['u']:
                    run.underline = True


doc_writer_service = DocWriterService()
