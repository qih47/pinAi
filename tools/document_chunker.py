import re
from typing import List, Dict, Optional

def detect_document_type(text: str) -> str:
    """Deteksi jenis dokumen berdasarkan pola awal teks."""
    sample = text[:800].upper()
    
    if "SURAT EDARAN" in sample and re.search(r"NOMOR\s*[:：]\s*SE[/\d]", sample):
        return "SE"
    elif "SURAT KEPUTUSAN" in sample or ("MENIMBANG" in sample and "MENGINGAT" in sample and "MEMUTUSKAN" in sample):
        return "SKEP"
    elif "INSTRUKSI KERJA" in sample and re.search(r"I[-\s]\d{3}", sample):
        return "IK"
    elif "PROSEDUR" in sample or re.search(r"P\s*[-–]\s*\d+\s*[-–]\s*[A-Z]", sample):
        return "PROSEDUR"
    else:
        return "UNKNOWN"

def extract_metadata(text: str, doc_type: str) -> Dict[str, Optional[str]]:
    """Ekstrak metadata umum dari dokumen."""
    metadata = {
        "doc_type": doc_type,
        "nomor": None,
        "tanggal": None,
        "tentang": None,
        "judul": None
    }
    
    # Nomor
    if doc_type == "SE":
        nomor_match = re.search(r'Nomor\s*[:：]\s*(SE[/\d\w\s\-\.]+)', text, re.IGNORECASE)
    elif doc_type == "SKEP":
        nomor_match = re.search(r'Nomor\s*[:：]\s*(SKEP[/\d\w\s\-\.]+)', text, re.IGNORECASE)
    elif doc_type == "IK":
        nomor_match = re.search(r'(I[-\s]\d{3}[-\w\d]+)', text)
    elif doc_type == "PROSEDUR":
        nomor_match = re.search(r'(P\s*[-–]\s*\d+\s*[-–]\s*[A-Z\d\s\-]+)', text)
    else:
        nomor_match = re.search(r'Nomor\s*[:：]\s*([A-Z\d/\-\s\.]+)', text, re.IGNORECASE)
    
    if nomor_match:
        metadata["nomor"] = nomor_match.group(1).strip()

    # Tanggal
    tanggal_match = re.search(r'(Dikeluarkan di|Ditetapkan di).*?\n.*?tanggal\s*[:：]?\s*([\d\s\w,\.]+)', text, re.IGNORECASE)
    if not tanggal_match:
        tanggal_match = re.search(r'Pada tanggal\s*[:：]?\s*([\d\s\w,\.]+)', text, re.IGNORECASE)
    if tanggal_match:
        metadata["tanggal"] = tanggal_match.group(2).strip()

    # Tentang / Judul
    if doc_type in ["SE", "SKEP"]:
        tentang_match = re.search(r'Tentang\s*\n\s*([^\n]+)', text, re.IGNORECASE)
        if tentang_match:
            tentang_clean = tentang_match.group(1).strip()
            metadata["tentang"] = tentang_clean
            metadata["judul"] = tentang_clean  # <-- Tambahkan ini
        else:
            metadata["judul"] = None
    else:
        # Untuk IK / Prosedur, ambil judul dari header
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) > 2:
            first_line = lines[0]
            if "INSTRUKSI KERJA" in first_line.upper() or "PROSEDUR" in first_line.upper():
                # Cari baris setelah nomor (biasanya baris ke-2 atau ke-3)
                for i in range(1, min(5, len(lines))):
                    if lines[i] and not re.match(r'(Nomor|Edisi|I-\d|P\s*[-–])', lines[i], re.IGNORECASE):
                        metadata["judul"] = lines[i]
                        break
            else:
                metadata["judul"] = first_line

    return metadata


def chunk_se(text: str) -> List[str]:
    """
    Chunk Surat Edaran berdasarkan butir utama (1., 2., dst.).
    Menangani:
      - Butir utama di baris terpisah (misal: "1." lalu baris baru lalu "Berdasarkan")
      - Sub-butir (a., b., i), -, • tetap dalam chunk
      - Tanda tangan di akhir ditambahkan ke chunk terakhir
      - Bagian 'Tembusan' dihapus
    """
    # Normalisasi
    text = re.sub(r'={5,}\s*PAGE\s+\d+\s*={5,}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Hapus bagian Tembusan
    tembusan_match = re.search(r'\n\s*Tembusan\s*:', text, re.IGNORECASE)
    if tembusan_match:
        text = text[:tembusan_match.start()]

    # Ekstrak blok tanda tangan
    signature_block = ""
    sig_pattern = r'(\n\s*Dikeluarkan\s+di\s*:\s*[^\n]+\s*\n\s*Pada\s+tanggal\s*:\s*[^\n]+(?:\s*\n[^\n]*){0,4})'
    sig_match = re.search(sig_pattern, text, re.IGNORECASE)
    if sig_match:
        signature_block = sig_match.group(1).strip()
        text = text[:sig_match.start()]

    lines = text.splitlines()
    chunks = []
    current_chunk = []
    current_main_number = None

    for line in lines:
        stripped = line.strip()

        # Deteksi butir utama: "1.", "2.", "10.", dll. — di awal baris (boleh ada spasi)
        if re.match(r'^\d+\.\s*$', stripped) or re.match(r'^\d+\.\s+\S', stripped):
            # Simpan chunk sebelumnya
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_main_number = True
        else:
            # Jika sudah dalam butir utama, tambahkan semua baris berikutnya
            if current_main_number:
                current_chunk.append(line)
            # Jika belum ketemu butir utama, abaikan (header)

    # Tambahkan chunk terakhir
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    # Jika tidak ada butir → kembalikan seluruh isi
    if not chunks:
        body = text.strip()
        if signature_block:
            body += "\n\n" + signature_block
        return [body] if body else []

    # Tambahkan signature ke chunk terakhir
    if signature_block:
        chunks[-1] = chunks[-1].rstrip() + "\n\n" + signature_block

    return chunks

def chunk_skep(text: str) -> List[Dict[str, str]]:
    """
    Chunk SKEP dengan hierarki:
    - Pertimbangan (Menimbang, Mengingat, MEMUTUSKAN)
    - BAB I, BAB II, ...
    - Pasal 1, Pasal 2, ... (child dari BAB)
    - Tanda tangan & Lampiran "A" sebagai section terpisah
    """
    # Normalisasi
    text = re.sub(r'={5,}\s*PAGE\s+\d+\s*={5,}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Potong bagian 'Kepada Yth.' dan setelahnya
    recipient_match = re.search(r'\n\s*Kepada\s+Yth\.', text, re.IGNORECASE)
    if recipient_match:
        core_text = text[:recipient_match.start()]
    else:
        core_text = text

    # Ekstrak LAMPIRAN (fleksibel: "LAMPIRAN", "LAMPIRAN A", "LAMPIRAN 1", dll)
    lampiran = ""
    lampiran_match = re.search(
        r'(\n\s*LAMPIRAN(?:\s+["A-Z0-9]+)?(?:\s+.*?)*?)(?=\n\s*Kepada\s+Yth\.|\Z)',
        core_text,
        re.IGNORECASE | re.DOTALL
    )
    if lampiran_match:
        lampiran = lampiran_match.group(1).strip()
        core_text = core_text[:lampiran_match.start()]

    # Ekstrak blok tanda tangan (Ditetapkan di... DIREKTUR UTAMA)
    signature_block = ""
    sig_pattern = r'(\n\s*Ditetapkan\s+di\s*:.*?\n\s*Pada\s+tanggal\s*:.*?(?:\n\s*[A-Z\s\(\)]+){2,4})'
    sig_match = re.search(sig_pattern, core_text, re.IGNORECASE | re.DOTALL)
    if sig_match:
        signature_block = sig_match.group(1).strip()
        core_text = core_text[:sig_match.start()]

    # Ekstrak bagian pertimbangan (Menimbang ... MEMUTUSKAN)
    pertimbangan = ""
    memutuskan_match = re.search(r'(Menimbang\s*:.*?MEMUTUSKAN.*?)(?=\n\s*BAB\s+[IVXLCDM]|\Z)', core_text, re.IGNORECASE | re.DOTALL)
    if memutuskan_match:
        pertimbangan = memutuskan_match.group(1).strip()
        body_start = memutuskan_match.end()
        body = core_text[body_start:]
    else:
        # Jika tidak ada BAB, ambil seluruh isi setelah MEMUTUSKAN
        memutuskan_end = re.search(r'MEMUTUSKAN', core_text, re.IGNORECASE)
        if memutuskan_end:
            pertimbangan = core_text[:memutuskan_end.end()]
            body = core_text[memutuskan_end.end():]
        else:
            pertimbangan = ""
            body = core_text

    sections = []

    # 1. Tambahkan pertimbangan
    if pertimbangan.strip():
        sections.append({
            "type": "pertimbangan",
            "title": "Pertimbangan Hukum",
            "content": pertimbangan,
            "parent_title": None
        })

    # 2. Parse BAB dan Pasal dari body
    current_bab_title = None
    lines = body.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Deteksi BAB
        bab_match = re.match(r'^(BAB\s+[IVXLCDM]+)\s+(.+)$', line, re.IGNORECASE)
        if bab_match:
            bab_no = bab_match.group(1).strip().upper()
            bab_name = bab_match.group(2).strip()
            current_bab_title = f"{bab_no} – {bab_name}"
            sections.append({
                "type": "bab",
                "title": current_bab_title,
                "content": "",
                "parent_title": None
            })
            i += 1
            continue

        # Deteksi Pasal
        if re.match(r'^Pasal\s+\d+', line, re.IGNORECASE):
            pasal_lines = []
            j = i
            while j < len(lines):
                next_line = lines[j].strip()
                if re.match(r'^(BAB\s+[IVXLCDM]|Pasal\s+\d+)', next_line, re.IGNORECASE) and j != i:
                    break
                pasal_lines.append(lines[j])
                j += 1

            pasal_content = "\n".join(pasal_lines)
            pasal_title_match = re.search(r'^(Pasal\s+\d+)\s*(.+)?', lines[i], re.IGNORECASE)
            if pasal_title_match:
                pasal_no = pasal_title_match.group(1)
                pasal_name = (pasal_title_match.group(2) or "").strip()
                pasal_title = f"{pasal_no} – {pasal_name}" if pasal_name else pasal_no
            else:
                pasal_title = lines[i].strip()

            sections.append({
                "type": "pasal",
                "title": pasal_title,
                "content": pasal_content,
                "parent_title": current_bab_title
            })
            i = j
            continue

        i += 1

    # 3. Tambahkan tanda tangan ke chunk terakhir (jika ada pasal/BAB)
    if signature_block.strip():
        if sections:
            sections[-1]["content"] = sections[-1]["content"].rstrip() + "\n\n" + signature_block
        else:
            sections.append({
                "type": "signature",
                "title": "Tanda Tangan",
                "content": signature_block,
                "parent_title": None
            })

    # 4. Tambahkan lampiran sebagai section terpisah
    if lampiran.strip():
        sections.append({
            "type": "lampiran",
            "title": "Lampiran A – Surat Pernyataan",
            "content": lampiran,
            "parent_title": None
        })

    return sections

def chunk_ik(text: str) -> List[str]:
    """Chunk Instruksi Kerja per bagian utama (1., 2., 3., dst)"""
    # Ambil dari bagian "1. TUJUAN" dst
    start_match = re.search(r'\n\s*1\.\s+[A-Z]', text)
    if not start_match:
        return [text.strip()]
    
    body = text[start_match.start():]
    # Split berdasarkan angka titik kapital
    chunks = re.split(r'(\n\s*\d+\.\s+[A-Z][^.\n]*\n)', body)
    result = []
    for i in range(1, len(chunks), 2):
        heading = chunks[i].strip()
        content = chunks[i+1].strip() if i+1 < len(chunks) else ""
        result.append(f"{heading}\n{content}")
    return result or [body.strip()]

def chunk_prosedur(text: str) -> List[str]:
    """Chunk Prosedur per bagian utama (1., 2., 3., dst)"""
    return chunk_ik(text)  # struktur mirip IK

def chunk_document(text: str, doc_type: str) -> List[Dict[str, str]]:
    """
    Chunk teks berdasarkan jenis dokumen yang DIPILIH USER.
    doc_type: "SKEP", "SE", "IK", "PROSEDUR"
    """
    text = re.sub(r'={5,}\s*PAGE\s+\d+\s*={5,}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)

    metadata = extract_metadata(text, doc_type)

    if doc_type == "SE":
        raw_strings = chunk_se(text)
        structured = []
        for i, content in enumerate(raw_strings):
            structured.append({
                "content": content,
                "section_type": "butir",
                "title": f"Butir {i+1}",
                "parent_title": None
            })

    elif doc_type == "SKEP":
        structured = chunk_skep(text)

    elif doc_type == "IK":
        raw_strings = chunk_ik(text)
        structured = []
        for i, content in enumerate(raw_strings):
            lines = content.strip().split('\n')
            title = lines[0].strip() if lines else f"Bagian {i+1}"
            structured.append({
                "content": content,
                "section_type": "bagian",
                "title": title,
                "parent_title": None
            })

    elif doc_type == "PROSEDUR":
        raw_strings = chunk_prosedur(text)
        structured = []
        for i, content in enumerate(raw_strings):
            lines = content.strip().split('\n')
            title = lines[0].strip() if lines else f"Bagian {i+1}"
            structured.append({
                "content": content,
                "section_type": "bagian",
                "title": title,
                "parent_title": None
            })

    else:
        # Fallback
        structured = [{
            "content": text.strip(),
            "section_type": "dokumen",
            "title": "Dokumen Lengkap",
            "parent_title": None
        }]

    # Tambahkan metadata & chunk_id
    final_chunks = []
    for i, sec in enumerate(structured):
        if not sec["content"].strip():
            continue
        chunk_meta = metadata.copy()
        chunk_meta.update({
            "chunk_id": i + 1,
            "content": sec["content"],
            "section_type": sec.get("section_type", "bagian"),
            "section_title": sec.get("title", f"Bagian {i+1}"),  # <-- PAKAI "title"
            "parent_title": sec.get("parent_title", None)
        })
        final_chunks.append(chunk_meta)

    return final_chunks