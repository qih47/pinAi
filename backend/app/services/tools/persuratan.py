"""
CAKRA AI — Persuratan Tool
===========================
Generator naskah dinas korporat PT Pindad.

Mendukung:
- Nota Dinas
- Surat Biasa / Surat Tugas / Surat Keputusan (template dasar)
- Export ke .docx via python-docx

Di Step 1 ini berdiri sendiri.
Step 6 akan menghubungkan ke mode_email dan corporate_service.
"""

import re
import logging
import asyncio
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("CAKRA_PERSURATAN")


# ─── Data Model ───────────────────────────────────────────────────────────────
class NaskahDinas:
    """Representasi naskah dinas sebelum di-render."""

    def __init__(
        self,
        jenis: str,                  # "nota_dinas" | "surat_biasa" | "surat_tugas"
        kepada: str,
        dari: str,
        hal: str,
        isi: str,
        nomor: Optional[str] = None,
        tanggal: Optional[str] = None,
        tembusan: Optional[List[str]] = None,
        lampiran: Optional[str] = None,
    ):
        self.jenis = jenis
        self.kepada = kepada
        self.dari = dari
        self.hal = hal
        self.isi = isi
        self.nomor = nomor or _generate_draft_number(jenis)
        self.tanggal = tanggal or _today_indonesian()
        self.tembusan = tembusan or []
        self.lampiran = lampiran or "-"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jenis": self.jenis,
            "kepada": self.kepada,
            "dari": self.dari,
            "hal": self.hal,
            "isi": self.isi,
            "nomor": self.nomor,
            "tanggal": self.tanggal,
            "tembusan": self.tembusan,
            "lampiran": self.lampiran,
        }

    def to_markdown(self) -> str:
        """Render naskah ke format Markdown untuk preview AI."""
        label_map = {
            "nota_dinas": "NOTA DINAS",
            "surat_biasa": "SURAT",
            "surat_tugas": "SURAT TUGAS",
        }
        label = label_map.get(self.jenis, "NASKAH DINAS")

        lines = [
            f"# {label}",
            "",
            f"**Nomor  :** {self.nomor}",
            f"**Tanggal:** {self.tanggal}",
            f"**Lampiran:** {self.lampiran}",
            "",
            f"**Kepada :** {self.kepada}",
            f"**Dari   :** {self.dari}",
            f"**Hal    :** {self.hal}",
            "",
            "---",
            "",
            self.isi,
        ]

        if self.tembusan:
            lines += ["", "**Tembusan:**"]
            for i, t in enumerate(self.tembusan, 1):
                lines.append(f"{i}. {t}")

        return "\n".join(lines)


# ─── DOCX Renderer ────────────────────────────────────────────────────────────
async def render_docx(naskah: NaskahDinas, output_path: str) -> Path:
    """
    Render naskah ke file .docx menggunakan python-docx.

    Args:
        naskah: Objek NaskahDinas yang sudah diisi.
        output_path: Path absolut untuk file .docx output.

    Returns:
        Path ke file .docx yang ditulis.
    """
    def _build_docx():
        try:
            from docx import Document
            from docx.shared import Pt, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            raise RuntimeError("python-docx tidak terinstal — jalankan: pip install python-docx")

        doc = Document()

        # Setup margin
        section = doc.sections[0]
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2)

        # Header Instansi
        header_p = doc.add_paragraph("PT PINDAD (PERSERO)")
        header_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = header_p.runs[0]
        run.bold = True
        run.font.size = Pt(14)

        doc.add_paragraph("")

        # Judul Naskah
        label_map = {
            "nota_dinas": "NOTA DINAS",
            "surat_biasa": "SURAT",
            "surat_tugas": "SURAT TUGAS",
        }
        title_p = doc.add_paragraph(label_map.get(naskah.jenis, "NASKAH DINAS"))
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_p.runs[0]
        title_run.bold = True
        title_run.font.size = Pt(12)

        doc.add_paragraph("")

        # Metadata tabel
        meta_table = doc.add_table(rows=5, cols=3)
        meta_table.style = "Table Grid"

        def set_cell(row, col, text, bold=False):
            cell = meta_table.cell(row, col)
            cell.text = text
            if bold:
                for run in cell.paragraphs[0].runs:
                    run.bold = True

        set_cell(0, 0, "Nomor", bold=True)
        set_cell(0, 1, ":")
        set_cell(0, 2, naskah.nomor)

        set_cell(1, 0, "Tanggal", bold=True)
        set_cell(1, 1, ":")
        set_cell(1, 2, naskah.tanggal)

        set_cell(2, 0, "Lampiran", bold=True)
        set_cell(2, 1, ":")
        set_cell(2, 2, naskah.lampiran)

        set_cell(3, 0, "Kepada", bold=True)
        set_cell(3, 1, ":")
        set_cell(3, 2, naskah.kepada)

        set_cell(4, 0, "Hal", bold=True)
        set_cell(4, 1, ":")
        set_cell(4, 2, naskah.hal)

        doc.add_paragraph("")

        # Isi surat
        for paragraph in naskah.isi.split("\n"):
            p = doc.add_paragraph(paragraph)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        doc.add_paragraph("")

        # Dari / Pengirim
        dari_p = doc.add_paragraph(naskah.dari)
        dari_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Tembusan
        if naskah.tembusan:
            doc.add_paragraph("")
            t_p = doc.add_paragraph("Tembusan:")
            t_p.runs[0].bold = True
            for i, t in enumerate(naskah.tembusan, 1):
                doc.add_paragraph(f"{i}. {t}", style="List Number")

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))
        return out

    return await asyncio.to_thread(_build_docx)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _today_indonesian() -> str:
    """Format tanggal hari ini dalam bahasa Indonesia: '3 September 2026'."""
    months = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    today = datetime.date.today()
    return f"{today.day} {months[today.month]} {today.year}"


def _generate_draft_number(jenis: str) -> str:
    """Generate nomor draft sementara."""
    prefix_map = {
        "nota_dinas": "ND",
        "surat_biasa": "S",
        "surat_tugas": "ST",
    }
    prefix = prefix_map.get(jenis, "NK")
    now = datetime.datetime.now()
    return f"DRAFT/{prefix}/CAKRA/{now.year}/{now.month:02d}/{now.day:02d}"
