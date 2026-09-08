"""
CAKRA AI — Document Writer & Official Publishing Service
========================================================
Layanan backend untuk kompilasi dokumen resmi (SE, SKEP, Memo Dinas)
dari Tiptap/ProseMirror ke format Microsoft Word (.docx) berbasis docxtpl & python-docx.
"""

import os
import io
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

logger = logging.getLogger("DOC_WRITER_SERVICE")

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(TEMPLATES_DIR, exist_ok=True)


class DocWriterService:
    """
    Service pengelola template dan kompilasi dokumen dinamis (.docx).
    """

    @staticmethod
    def get_available_templates() -> List[Dict[str, Any]]:
        """
        Daftar template dokumen dinamis yang didukung oleh sistem.
        """
        return [
            {
                "id": "template_skep",
                "name": "Surat Keputusan Direksi (SKEP)",
                "category": "Regulasi & Kebijakan",
                "description": "Format baku Surat Keputusan Direksi PT Pindad dengan bagian Menimbang, Mengingat, dan Diktum Putusan KESATU/KEDUA.",
                "icon": "FileCheck2",
                "default_title": "SURAT KEPUTUSAN DIREKSI PT PINDAD",
                "default_number": "SKEP/     /PINDAD/2026",
                "sections": [
                    {"id": "kop", "label": "Kop Surat", "type": "header"},
                    {"id": "judul", "label": "Judul & Nomor Keputusan", "type": "title"},
                    {"id": "tentang", "label": "Tentang (Perihal)", "type": "subject"},
                    {"id": "menimbang", "label": "Menimbang", "type": "considerations"},
                    {"id": "mengingat", "label": "Mengingat (Dasar Hukum)", "type": "legal_basis"},
                    {"id": "memutuskan", "label": "Memutuskan / Menetapkan", "type": "decisions"},
                    {"id": "penutup", "label": "Penutup & Tanda Tangan", "type": "signature"},
                ]
            },
            {
                "id": "template_se",
                "name": "Surat Edaran Direksi (SE)",
                "category": "Pengumuman & Kebijakan",
                "description": "Format Surat Edaran Direksi PT Pindad untuk petunjuk pelaksanaan kebijakan atau instruksi operasional.",
                "icon": "ScrollText",
                "default_title": "SURAT EDARAN DIREKSI PT PINDAD",
                "default_number": "SE/     /PINDAD/2026",
                "sections": [
                    {"id": "kop", "label": "Kop Surat", "type": "header"},
                    {"id": "judul", "label": "Judul Surat Edaran", "type": "title"},
                    {"id": "tentang", "label": "Perihal / Tentang", "type": "subject"},
                    {"id": "latar_belakang", "label": "1. Latar Belakang", "type": "paragraph"},
                    {"id": "maksud_tujuan", "label": "2. Maksud dan Tujuan", "type": "paragraph"},
                    {"id": "ruang_lingkup", "label": "3. Ruang Lingkup", "type": "paragraph"},
                    {"id": "isi_edaran", "label": "4. Ketentuan / Isi Edaran", "type": "paragraph"},
                    {"id": "penutup", "label": "5. Penutup & Tanda Tangan", "type": "signature"},
                ]
            },
            {
                "id": "template_memo",
                "name": "Nota Dinas / Memo Internal",
                "category": "Korespondensi Internal",
                "description": "Format komunikasi kedinasan antar divisi / unit kerja di lingkungan PT Pindad.",
                "icon": "Mail",
                "default_title": "NOTA DINAS",
                "default_number": "ND/     /TI/2026",
                "sections": [
                    {"id": "kop", "label": "Kop Dokumen", "type": "header"},
                    {"id": "metadata", "label": "Kepada, Dari, Tanggal, Perihal", "type": "metadata_table"},
                    {"id": "isi_memo", "label": "Isi Pembahasan / Permohonan", "type": "paragraph"},
                    {"id": "penutup", "label": "Penutup & Tanda Tangan", "type": "signature"},
                ]
            },
            {
                "id": "template_blank",
                "name": "Dokumen Standar PT Pindad (Blank)",
                "category": "Umum",
                "description": "Kertas kerja kosong berformat margin A4 standar corporate PT Pindad dengan Kop Surat.",
                "icon": "FileText",
                "default_title": "DOKUMEN KERJA PT PINDAD",
                "default_number": "",
                "sections": [
                    {"id": "kop", "label": "Kop Surat", "type": "header"},
                    {"id": "body", "label": "Isi Dokumen Bebas", "type": "paragraph"},
                ]
            }
        ]

    @staticmethod
    def _set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        """Helper untuk mengatur padding cell tabel docx"""
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{m}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    @classmethod
    def compile_html_to_docx(
        cls,
        html_content: str,
        title: str = "Dokumen Resmi PT Pindad",
        template_id: str = "template_blank",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Mengonversi konten HTML dari Tiptap editor menjadi berkas Microsoft Word (.docx)
        dengan margin A4 berstandar PT Pindad dan tipografi resmi.
        """
        metadata = metadata or {}
        doc = Document()

        # 1. Konfigurasi Halaman A4 & Margin Resmi (Top/Bottom 2.5cm, Left/Right 2.5cm)
        section = doc.sections[0]
        section.page_width = Inches(8.27)    # 210 mm (A4)
        section.page_height = Inches(11.69)  # 297 mm (A4)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

        # 2. Styling Default Font (Arial 11pt, warna hitam)
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)
        font.color.rgb = RGBColor(0, 0, 0)

        # 3. Header Kop Dokumen Resmi PT Pindad (Jika bukan memo polos)
        include_kop = metadata.get("include_kop", True)
        if include_kop:
            kop_p = doc.add_paragraph()
            kop_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            kop_p.paragraph_format.space_after = Pt(2)
            
            run_pt = kop_p.add_run("PT PINDAD (PERSERO)\n")
            run_pt.bold = True
            run_pt.font.size = Pt(14)
            run_pt.font.name = 'Arial'
            
            run_sub = kop_p.add_run("DIVISI TEKNOLOGI INFORMASI & KOMUNIKASI\n")
            run_sub.bold = True
            run_sub.font.size = Pt(11)

            run_addr = kop_p.add_run("Jl. Gatot Subroto No. 517, Bandung 40284 | Telp: (022) 7321964 | www.pindad.com")
            run_addr.font.size = Pt(8.5)
            run_addr.font.italic = True
            run_addr.font.color.rgb = RGBColor(100, 100, 100)

            # Garis Pembatas Ganda Kop Surat
            divider = doc.add_paragraph()
            divider.paragraph_format.space_after = Pt(18)
            pBdr = OxmlElement('w:pBdr')
            bottom_border = OxmlElement('w:bottom')
            bottom_border.set(qn('w:val'), 'single')
            bottom_border.set(qn('w:sz'), '18') # ketebalan garis
            bottom_border.set(qn('w:space'), '4')
            bottom_border.set(qn('w:color'), '000000')
            pBdr.append(bottom_border)
            divider._p.get_or_add_pPr().append(pBdr)

        # 4. Parsing HTML Tiptap dengan BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Parser elemen per elemen
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

            # Heading 1, 2, 3
            if tag_name in ['h1', 'h2', 'h3', 'h4']:
                level = int(tag_name[1])
                h_p = doc.add_paragraph()
                h_p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
                h_p.paragraph_format.space_after = Pt(4)
                h_run = h_p.add_run(element.get_text())
                h_run.bold = True
                h_run.font.name = 'Arial'
                if level == 1:
                    h_run.font.size = Pt(13)
                    if "center" in (element.get("style") or "") or "text-center" in (element.get("class") or []):
                        h_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif level == 2:
                    h_run.font.size = Pt(12)
                else:
                    h_run.font.size = Pt(11)

            # Paragraf Biasa
            elif tag_name == 'p':
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.line_spacing = 1.15
                
                # Check alignment
                style_str = element.get("style", "")
                if "text-align: center" in style_str:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif "text-align: right" in style_str:
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                elif "text-align: justify" in style_str:
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

                cls._render_inline_elements(element, p)

            # Daftar Butir (List: ul / ol)
            elif tag_name in ['ul', 'ol']:
                is_ordered = tag_name == 'ol'
                for idx, li in enumerate(element.find_all('li', recursive=False)):
                    p = doc.add_paragraph(style='List Bullet' if not is_ordered else 'List Number')
                    p.paragraph_format.space_after = Pt(3)
                    p.paragraph_format.line_spacing = 1.15
                    cls._render_inline_elements(li, p)

            # Tabel (Tiptap Table)
            elif tag_name == 'table':
                rows = element.find_all('tr')
                if rows:
                    num_rows = len(rows)
                    num_cols = max(len(r.find_all(['td', 'th'])) for r in rows)
                    table = doc.add_table(rows=num_rows, cols=num_cols)
                    table.alignment = WD_TABLE_ALIGNMENT.CENTER
                    table.style = 'Table Grid'

                    for r_idx, row in enumerate(rows):
                        cells = row.find_all(['td', 'th'])
                        for c_idx, cell in enumerate(cells):
                            if c_idx < num_cols:
                                docx_cell = table.cell(r_idx, c_idx)
                                docx_cell.text = ""
                                cls._set_cell_margins(docx_cell)
                                cell_p = docx_cell.paragraphs[0]
                                cell_p.paragraph_format.space_after = Pt(2)
                                cls._render_inline_elements(cell, cell_p)

                    doc.add_paragraph().paragraph_format.space_after = Pt(6)

            # Blockquote
            elif tag_name == 'blockquote':
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.5)
                p.paragraph_format.space_after = Pt(6)
                cls._render_inline_elements(element, p)

        # Simpan ke byte buffer in-memory
        output_stream = io.BytesIO()
        doc.save(output_stream)
        output_stream.seek(0)
        return output_stream.getvalue()

    @staticmethod
    def _render_inline_elements(parent_tag: Tag, paragraph):
        """Membedah tag inline seperti <strong>, <em>, <u>, <span> ke runs python-docx"""
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
                elif tag in ['code']:
                    run.font.name = 'Consolas'
                    run.font.size = Pt(9.5)


doc_writer_service = DocWriterService()
