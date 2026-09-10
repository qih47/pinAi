"""
CAKRA AI — Cross-Page Document Parser & Continuous Accumulator
==============================================================
Membaca dokumen PDF halaman demi halaman layaknya manusia membaca buku.
Mampu mendeteksi pembahasan/pasal yang terpotong di akhir suatu halaman
dan menyambungkannya (stitching) secara utuh melintasi halaman 4, 5, bahkan 6
sehingga tidak ada kalimat atau pasal buntung yang kehilangan subjek/sanksi.
"""

import re
import os
import base64
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("CAKRA_PAGE_PARSER")

# Regex pattern hierarki regulasi formal Indonesia & PT Pindad
BAB_PATTERN = re.compile(r'^\s*(BAB\s+[IVXLCDM]+(?:[\.\:\-\s]+.*)?)$', re.IGNORECASE | re.MULTILINE)
BAGIAN_PATTERN = re.compile(r'^\s*(Bagian\s+(?:Kesatu|Kedua|Ketiga|Keempat|Kelima|Keenam|Ketujuh|Kedelapan|Kesembilan|Kesepuluh|[A-Z]+).*)$', re.IGNORECASE | re.MULTILINE)
PASAL_PATTERN = re.compile(r'^\s*(Pasal\s+\d+.*)$', re.IGNORECASE | re.MULTILINE)
AYAT_PATTERN = re.compile(r'^\s*(\(\d+\)|[a-z]\.|\d+\.)\s+', re.MULTILINE)

@dataclass
class StitchedSection:
    dokumen_id: int
    bab: str
    pasal: str
    page_start: int
    page_end: int
    page_range: str
    content: str
    is_cross_page: bool = False
    section_type: str = "PASAL"  # 'BAB', 'PASAL', 'UMUM'

@dataclass
class PendingSectionBuffer:
    """Menampung state pasal/pembahasan yang belum tuntas di akhir halaman"""
    active_bab: str = ""
    active_pasal: str = ""
    page_start: int = 0
    current_page: int = 0
    accumulated_text: str = ""
    is_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "PendingSectionBuffer":
        if not data:
            return cls()
        if isinstance(data, str):
            try:
                import json
                data = json.loads(data)
            except Exception:
                return cls()
        if not isinstance(data, dict):
            return cls()
        return cls(
            active_bab=data.get("active_bab", ""),
            active_pasal=data.get("active_pasal", ""),
            page_start=data.get("page_start", 0),
            current_page=data.get("current_page", 0),
            accumulated_text=data.get("accumulated_text", ""),
            is_active=data.get("is_active", False)
        )

class BookPageReader:
    """
    Ekstraktor halaman per halaman dengan memori lintas halaman (Cross-Page Stitcher).
    """

    def __init__(self, pdf_path: str, dokumen_id: int, initial_buffer: Optional[Dict[str, Any]] = None):
        self.pdf_path = pdf_path
        self.dokumen_id = dokumen_id
        self.buffer = PendingSectionBuffer.from_dict(initial_buffer)
        self.total_pages = 0
        self._doc = None

        if os.path.exists(pdf_path):
            try:
                import fitz  # PyMuPDF
                self._doc = fitz.open(pdf_path)
                self.total_pages = len(self._doc)
            except Exception as e:
                logger.warning(f"[PAGE_PARSER] PyMuPDF gagal memuat {pdf_path}: {e}")
                self._doc = None

    def get_total_pages(self) -> int:
        return self.total_pages

    def extract_page_raw_text(self, page_num_1based: Optional[int]) -> str:
        """Mengambil teks murni dari 1 halaman (1-indexed)"""
        if page_num_1based is None or not self._doc:
            return ""
        if page_num_1based < 1 or page_num_1based > self.total_pages:
            return ""
        try:
            page = self._doc[page_num_1based - 1]
            return page.get_text("text") or ""
        except Exception as e:
            logger.error(f"[PAGE_PARSER] Error baca halaman {page_num_1based}: {e}")
            return ""

    def render_page_image(self, page_num_1based: Optional[int], dpi: int = 150) -> Optional[bytes]:
        """Merender halaman menjadi PNG bytes (untuk Worker 4 Vision RAG)"""
        if page_num_1based is None or not self._doc or page_num_1based < 1 or page_num_1based > self.total_pages:
            return None
        try:
            import fitz
            page = self._doc[page_num_1based - 1]
            pix = page.get_pixmap(dpi=dpi)
            return pix.tobytes("png")
        except Exception as e:
            logger.error(f"[PAGE_PARSER] Gagal render gambar halaman {page_num_1based}: {e}")
            return None

    def is_sentence_incomplete(self, text: str) -> bool:
        """
        Mengecek apakah kalimat di akhir teks belum tuntas.
        Indikator: tidak diakhiri titik (.), berakhir dengan koma (,), titik koma (;),
        tanda hubung (-), atau kata hubung terbuka.
        """
        stripped = text.strip()
        if not stripped:
            return False

        # Tanda baca penutup final
        if stripped[-1] in [".", "!", "?"]:
            return False

        # Tanda baca yang jelas menunjukkan kelanjutan
        if stripped[-1] in [",", ";", ":", "-", "(", "/", "&"]:
            return True

        # Kata penghubung di ujung teks
        open_words = ["dan", "atau", "serta", "yaitu", "sebagaimana", "berupa", "antara lain", "seperti", "pada", "dalam"]
        last_word = stripped.split()[-1].lower()
        if last_word in open_words:
            return True

        # Jika berakhiran huruf kecil atau angka biasa tanpa titik
        return True

    def process_page(self, page_num_1based: int) -> Dict[str, Any]:
        """
        Memproses 1 halaman dengan logika penyambungan lintas halaman (Cross-Page Stitching).
        
        Returns:
            {
                "page_number": page_num_1based,
                "raw_text": str,
                "completed_sections": List[StitchedSection],
                "pending_buffer": Dict[str, Any], # state buffer jika ada pasal yg masih nyambung
                "has_continuation": bool
            }
        """
        raw_text = self.extract_page_raw_text(page_num_1based)
        if not raw_text.strip():
            return {
                "page_number": page_num_1based,
                "raw_text": "",
                "completed_sections": [],
                "pending_buffer": self.buffer.to_dict(),
                "has_continuation": self.buffer.is_active
            }

        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        completed_sections: List[StitchedSection] = []

        # Pisahkan halaman menjadi blok-blok pasal/bab
        current_chunk_lines = []
        
        # Jika dari halaman sebelumnya ada pasal yang masih menggantung:
        if self.buffer.is_active:
            logger.info(f"🔗 [CROSS_PAGE] Menyambung pembahasan '{self.buffer.active_pasal or 'Lanjutan'}' dari Halaman {self.buffer.page_start} ke Halaman {page_num_1based}")
            self.buffer.current_page = page_num_1based

        idx = 0
        while idx < len(lines):
            line = lines[idx]

            # Cek apakah baris ini pembuka BAB baru
            is_bab = bool(BAB_PATTERN.match(line))
            is_pasal = bool(PASAL_PATTERN.match(line))

            if is_bab or is_pasal:
                # Jika ada buffer sebelumnya yang sedang terbuka, kita tutup dan selesaikan!
                if self.buffer.is_active and self.buffer.accumulated_text.strip():
                    page_start = self.buffer.page_start
                    page_end = page_num_1based
                    is_cross = (page_start != page_end)
                    prange = f"{page_start}-{page_end}" if is_cross else str(page_start)

                    completed_sections.append(StitchedSection(
                        dokumen_id=self.dokumen_id,
                        bab=self.buffer.active_bab,
                        pasal=self.buffer.active_pasal,
                        page_start=page_start,
                        page_end=page_end,
                        page_range=prange,
                        content=self.buffer.accumulated_text.strip(),
                        is_cross_page=is_cross,
                        section_type="PASAL" if self.buffer.active_pasal else "BAB"
                    ))
                    # Reset buffer
                    self.buffer.accumulated_text = ""
                    self.buffer.is_active = False

                if is_bab:
                    self.buffer.active_bab = line
                    # BAB biasanya punya judul di baris berikutnya
                    if idx + 1 < len(lines) and not PASAL_PATTERN.match(lines[idx+1]) and not BAB_PATTERN.match(lines[idx+1]):
                        self.buffer.active_bab += f" - {lines[idx+1]}"
                        idx += 1
                elif is_pasal:
                    self.buffer.active_pasal = line

                self.buffer.page_start = page_num_1based
                self.buffer.current_page = page_num_1based
                self.buffer.accumulated_text = line + "\n"
                self.buffer.is_active = True
            else:
                # Baris isi / ayat
                if not self.buffer.is_active:
                    # Teks umum pembuka sebelum pasal pertama
                    self.buffer.page_start = page_num_1based
                    self.buffer.current_page = page_num_1based
                    self.buffer.accumulated_text = ""
                    self.buffer.is_active = True

                self.buffer.accumulated_text += line + "\n"

            idx += 1

        # Di ujung akhir halaman, cek apakah teks terpotong atau tuntas
        if self.buffer.is_active and self.buffer.accumulated_text.strip():
            ends_incomplete = self.is_sentence_incomplete(self.buffer.accumulated_text)
            is_last_page = (page_num_1based >= self.total_pages)

            if ends_incomplete and not is_last_page:
                # Pembahasan BELUM SELESAI -> simpan di buffer untuk disambung di halaman berikutnya!
                logger.info(f"⏳ [CROSS_PAGE] Teks '{self.buffer.active_pasal or 'Pasal'}' di ujung Halaman {page_num_1based} terpotong, menahan buffer untuk Halaman {page_num_1based + 1}...")
            else:
                # Pembahasan selesai atau ini halaman terakhir dokumen
                page_start = self.buffer.page_start
                page_end = page_num_1based
                is_cross = (page_start != page_end)
                prange = f"{page_start}-{page_end}" if is_cross else str(page_start)

                completed_sections.append(StitchedSection(
                    dokumen_id=self.dokumen_id,
                    bab=self.buffer.active_bab,
                    pasal=self.buffer.active_pasal,
                    page_start=page_start,
                    page_end=page_end,
                    page_range=prange,
                    content=self.buffer.accumulated_text.strip(),
                    is_cross_page=is_cross,
                    section_type="PASAL" if self.buffer.active_pasal else "UMUM"
                ))
                self.buffer.accumulated_text = ""
                self.buffer.is_active = False

        return {
            "page_number": page_num_1based,
            "raw_text": raw_text,
            "completed_sections": completed_sections,
            "pending_buffer": self.buffer.to_dict(),
            "has_continuation": self.buffer.is_active
        }

    def process_multimodal_spread(self, page_left: int, page_right: Optional[int] = None) -> Dict[str, Any]:
        """
        Memproses bentangan 2 halaman (Two-Page Spread: Kiri & Kanan) secara Vision-First.
        
        Merender kedua halaman menjadi gambar PNG 150 DPI dan mengonversinya ke base64
        untuk diserahkan langsung ke mata multimodal Gemma 31B.
        Juga mengekstrak layer teks pendukung dan menerapkan state-machine penyambung lintas batch.
        """
        effective_end_page = page_right if page_right is not None else page_left
        prange_display = f"{page_left}-{page_right}" if (page_right is not None and page_left != page_right) else str(page_left)

        # 1. Render gambar untuk kedua halaman (Vision Engine)
        img_left_bytes = self.render_page_image(page_left, dpi=150)
        img_right_bytes = self.render_page_image(page_right, dpi=150) if (page_right is not None and page_right != page_left) else None

        images_b64 = []
        if img_left_bytes:
            images_b64.append(base64.b64encode(img_left_bytes).decode('utf-8'))
        if img_right_bytes:
            images_b64.append(base64.b64encode(img_right_bytes).decode('utf-8'))

        # 2. Ekstraksi teks gabungan dari kedua halaman
        text_left = self.extract_page_raw_text(page_left)
        text_right = self.extract_page_raw_text(page_right) if (page_right is not None and page_right != page_left) else ""
        raw_text = f"{text_left}\n{text_right}".strip()

        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        completed_sections: List[StitchedSection] = []

        if self.buffer.is_active:
            logger.info(f"🔗 [CROSS_BATCH] Menyambung pembahasan '{self.buffer.active_pasal or 'Lanjutan'}' dari Halaman {self.buffer.page_start} ke Spread Halaman {prange_display}")
            self.buffer.current_page = effective_end_page

        idx = 0
        while idx < len(lines):
            line = lines[idx]
            is_bab = bool(BAB_PATTERN.match(line))
            is_pasal = bool(PASAL_PATTERN.match(line))

            if is_bab or is_pasal:
                if self.buffer.is_active and self.buffer.accumulated_text.strip():
                    page_start = self.buffer.page_start
                    page_end = effective_end_page
                    is_cross = (page_start != page_end)
                    prange = f"{page_start}-{page_end}" if is_cross else str(page_start)

                    completed_sections.append(StitchedSection(
                        dokumen_id=self.dokumen_id,
                        bab=self.buffer.active_bab,
                        pasal=self.buffer.active_pasal,
                        page_start=page_start,
                        page_end=page_end,
                        page_range=prange,
                        content=self.buffer.accumulated_text.strip(),
                        is_cross_page=is_cross,
                        section_type="PASAL" if self.buffer.active_pasal else "BAB"
                    ))
                    self.buffer.accumulated_text = ""
                    self.buffer.is_active = False

                if is_bab:
                    self.buffer.active_bab = line
                    if idx + 1 < len(lines) and not PASAL_PATTERN.match(lines[idx+1]) and not BAB_PATTERN.match(lines[idx+1]):
                        self.buffer.active_bab += f" - {lines[idx+1]}"
                        idx += 1
                elif is_pasal:
                    self.buffer.active_pasal = line

                self.buffer.page_start = page_left
                self.buffer.current_page = effective_end_page
                self.buffer.is_active = True
                self.buffer.accumulated_text = line + "\n"
            else:
                if self.buffer.is_active:
                    self.buffer.accumulated_text += line + "\n"
                else:
                    self.buffer.active_bab = "UMUM"
                    self.buffer.active_pasal = "Ketentuan Umum"
                    self.buffer.page_start = page_left
                    self.buffer.current_page = effective_end_page
                    self.buffer.is_active = True
                    self.buffer.accumulated_text = line + "\n"

            idx += 1

        # Cek apakah di ujung spread kalimat/pasal terpotong
        if self.buffer.is_active and self.buffer.accumulated_text.strip():
            ends_incomplete = self.is_sentence_incomplete(self.buffer.accumulated_text)
            is_last_page = (effective_end_page >= self.total_pages)

            if ends_incomplete and not is_last_page:
                logger.info(f"⏳ [CROSS_BATCH] Teks '{self.buffer.active_pasal or 'Pasal'}' di ujung Spread Halaman {effective_end_page} terpotong, menahan buffer untuk batch berikutnya...")
            else:
                page_start = self.buffer.page_start
                page_end = effective_end_page
                is_cross = (page_start != page_end)
                prange = f"{page_start}-{page_end}" if is_cross else str(page_start)

                completed_sections.append(StitchedSection(
                    dokumen_id=self.dokumen_id,
                    bab=self.buffer.active_bab,
                    pasal=self.buffer.active_pasal,
                    page_start=page_start,
                    page_end=page_end,
                    page_range=prange,
                    content=self.buffer.accumulated_text.strip(),
                    is_cross_page=is_cross,
                    section_type="PASAL" if self.buffer.active_pasal else "UMUM"
                ))
                self.buffer.accumulated_text = ""
                self.buffer.is_active = False

        prange_display = f"{page_left}-{page_right}" if page_left != page_right else str(page_left)

        return {
            "page_left": page_left,
            "page_right": page_right,
            "page_range": prange_display,
            "images_b64": images_b64,
            "img_left_bytes": img_left_bytes,
            "img_right_bytes": img_right_bytes,
            "raw_text": raw_text,
            "completed_sections": completed_sections,
            "pending_buffer": self.buffer.to_dict(),
            "has_continuation": self.buffer.is_active
        }

    def close(self):
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
