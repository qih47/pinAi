"""
CAKRA AI — Document Structure Parser (Mata AI)
==============================================
Modul untuk membaca dan membedah struktur isi berkas .docx secara semantik
(Nomor, Tentang, Dasar/Menimbang, Ketentuan/Diktum, Penutup) tanpa merusak berkas.
Menghasilkan snapshot teks ringkas untuk diinjeksikan ke System Prompt LLM (Call 2).
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from docx import Document

logger = logging.getLogger("DOC_STRUCTURE_PARSER")


def is_placeholder_text(text: str) -> bool:
    """Mendeteksi apakah suatu string merupakan garis titik-titik placeholder (misal: ...........)."""
    if not text:
        return False
    t = text.strip()
    if not t:
        return False
    cleaned = re.sub(r'[….\s_–-]', '', t)
    return len(cleaned) == 0 and len(t) >= 3


class DocumentStructureParser:
    """
    Parser semantik untuk dokumen resmi PT Pindad (Surat Edaran, SKEP, Memo, dll).
    """

    @classmethod
    def parse_docx(cls, docx_path: Path) -> Dict[str, Any]:
        if not docx_path or not Path(docx_path).exists():
            return {}

        try:
            doc = Document(str(docx_path))
        except Exception as e:
            logger.warning(f"Gagal membuka docx untuk diparse: {docx_path}, err: {e}")
            return {}

        structure: Dict[str, Any] = {
            "type": "unknown",
            "nomor": "",
            "tentang": "",
            "dasar": {},
            "menimbang": {},
            "mengingat": {},
            "ketentuan": [],
            "penutup": "",
            "tembusan": []
        }

        full_text_lower = " ".join(p.text.lower() for p in doc.paragraphs[:10])
        if "surat   -  edaran" in full_text_lower or "surat edaran" in full_text_lower:
            structure["type"] = "Surat Edaran"
        elif "surat keputusan" in full_text_lower or "keputusan direksi" in full_text_lower:
            structure["type"] = "Surat Keputusan (SKEP)"
        elif "nota dinas" in full_text_lower or "memo" in full_text_lower:
            structure["type"] = "Nota Dinas / Memo"

        current_section = None
        current_item_key = None

        for idx, p in enumerate(doc.paragraphs):
            raw_text = p.text.strip()
            if not raw_text:
                continue

            text_lower = raw_text.lower()

            # 1. Nomor Surat
            if "nomor:" in text_lower or "nomor :" in text_lower:
                structure["nomor"] = raw_text
                continue

            # 2. Judul / Tentang
            if text_lower in ["tentang", "t e n t a n g"]:
                current_section = "tentang_detect"
                continue

            if current_section == "tentang_detect":
                if not is_placeholder_text(raw_text):
                    structure["tentang"] = raw_text
                else:
                    structure["tentang"] = "(Draft / Belum diisi)"
                current_section = None
                continue

            # 3. Dasar (Surat Edaran)
            if "dasar:" in text_lower or text_lower == "dasar":
                current_section = "dasar"
                continue

            # 4. Menimbang & Mengingat (SKEP)
            if "menimbang:" in text_lower or text_lower == "menimbang":
                current_section = "menimbang"
                continue
            if "mengingat:" in text_lower or text_lower == "mengingat":
                current_section = "mengingat"
                continue

            # 5. Ketentuan (Point 2 pada Surat Edaran) atau Memutuskan (SKEP)
            if text_lower.startswith("2.") and current_section in ["dasar", "menimbang", None]:
                current_section = "ketentuan"
                clean_intro = raw_text[2:].strip()
                if clean_intro and not is_placeholder_text(clean_intro):
                    structure["ketentuan"].append(clean_intro)
                continue

            if "memutuskan:" in text_lower or "menetapkan:" in text_lower:
                current_section = "ketentuan"
                continue

            # 6. Penutup
            if "demikian surat edaran" in text_lower or "demikian nota dinas" in text_lower or text_lower.startswith("3. demikian"):
                structure["penutup"] = raw_text
                current_section = None
                continue

            # 7. Tembusan
            if "tembusan :" in text_lower or "tembusan:" in text_lower:
                current_section = "tembusan"
                continue

            # Parsing item di dalam section
            if current_section in ["dasar", "menimbang", "mengingat"]:
                # Deteksi pola 'a. Teks' atau 'a.   Teks'
                match = re.match(r"^([a-z])[\.\)]\s*(.*)$", raw_text, flags=re.IGNORECASE)
                if match:
                    current_item_key = match.group(1).lower()
                    val = match.group(2).strip()
                    if is_placeholder_text(val) or not val:
                        val = "(Belum diisi / Placeholder)"
                    structure[current_section][current_item_key] = val
                elif is_placeholder_text(raw_text):
                    # Placeholder tanpa label eksplisit di paragrafnya
                    # Jika sudah ada key sebelumnya yang belum punya text, beri placeholder
                    pass
                elif current_item_key and current_item_key in structure[current_section]:
                    # Baris lanjutan dari poin yang sama (multiline)
                    if not structure[current_section][current_item_key].startswith("("):
                        structure[current_section][current_item_key] += " " + raw_text

            elif current_section == "ketentuan":
                if not is_placeholder_text(raw_text):
                    structure["ketentuan"].append(raw_text)

            elif current_section == "tembusan":
                structure["tembusan"].append(raw_text)

        return structure

    @classmethod
    def get_prompt_snapshot(cls, docx_path: Path) -> str:
        """
        Menghasilkan teks ringkas dan padat untuk disuntikkan langsung ke prompt LLM.
        """
        st = cls.parse_docx(docx_path)
        if not st:
            return ""

        lines = []
        lines.append("=== [DOKUMEN KERJA AKTIF DI EDITOR SAAT INI (LIVE STATE)] ===")
        lines.append(f"Format Template: {st.get('type', 'Surat Resmi')}")
        if st.get("nomor"):
            lines.append(f"Nomor: {st['nomor']}")
        if st.get("tentang"):
            lines.append(f"Tentang / Perihal: {st['tentang']}")

        # Bagian Dasar
        if st.get("dasar"):
            lines.append("1. Dasar:")
            for k in sorted(st["dasar"].keys()):
                lines.append(f"   {k}. {st['dasar'][k]}")

        # Bagian Menimbang & Mengingat
        if st.get("menimbang"):
            lines.append("Menimbang:")
            for k in sorted(st["menimbang"].keys()):
                lines.append(f"   {k}. {st['menimbang'][k]}")

        if st.get("mengingat"):
            lines.append("Mengingat:")
            for k in sorted(st["mengingat"].keys()):
                lines.append(f"   {k}. {st['mengingat'][k]}")

        # Bagian Ketentuan
        if st.get("ketentuan"):
            lines.append("2. Ketentuan / Isi Surat:")
            for idx, item in enumerate(st["ketentuan"][:4]):
                clean_snippet = item if len(item) < 180 else item[:180] + "..."
                lines.append(f"   - {clean_snippet}")

        lines.append("=============================================================")
        lines.append("PANDUAN EDIT PRESISI (SURGICAL EDITING):")
        lines.append("- Kamu memiliki akses penglihatan langsung ke dokumen di atas.")
        lines.append("- Jika user meminta merevisi/menambah bagian (misal poin 'a' pada Dasar):")
        lines.append("  Gunakan target yang jelas pada blok ```docwriter dengan action: 'patch', section: 'dasar', item: 'a'.")
        lines.append("- JANGAN mengubah atau menghapus poin lain (seperti b, c) yang tidak diminta diubah!")
        lines.append("=============================================================")

        return "\n".join(lines)


document_structure_parser = DocumentStructureParser()
