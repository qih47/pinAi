# embeddings/chunk_skep.py

import re
from typing import List, Dict

def chunk_skep(text: str) -> List[Dict[str, str]]:
    """
    Chunk SKEP dengan hierarki:
    - Pertimbangan (Menimbang, Mengingat, MEMUTUSKAN)
    - BAB I, BAB II, ...
    - Pasal 1, Pasal 2, ... (child dari BAB)
    - Tanda tangan & Lampiran sebagai section terpisah
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

    # Ekstrak LAMPIRAN
    lampiran = ""
    lampiran_match = re.search(
        r'(\n\s*LAMPIRAN(?:\s+["A-Z0-9]+)?(?:\s+.*?)*?)(?=\n\s*Kepada\s+Yth\.|\Z)',
        core_text,
        re.IGNORECASE | re.DOTALL
    )
    if lampiran_match:
        lampiran = lampiran_match.group(1).strip()
        core_text = core_text[:lampiran_match.start()]

    # Ekstrak tanda tangan
    signature_block = ""
    sig_pattern = r'(\n\s*Ditetapkan\s+di\s*:.*?\n\s*Pada\s+tanggal\s*:.*?(?:\n\s*[A-Z\s\(\)]+){2,4})'
    sig_match = re.search(sig_pattern, core_text, re.IGNORECASE | re.DOTALL)
    if sig_match:
        signature_block = sig_match.group(1).strip()
        core_text = core_text[:sig_match.start()]

    # Ekstrak pertimbangan
    pertimbangan = ""
    memutuskan_match = re.search(r'(Menimbang\s*:.*?MEMUTUSKAN.*?)(?=\n\s*BAB\s+[IVXLCDM]|\Z)', core_text, re.IGNORECASE | re.DOTALL)
    if memutuskan_match:
        pertimbangan = memutuskan_match.group(1).strip()
        body = core_text[memutuskan_match.end():]
    else:
        memutuskan_end = re.search(r'MEMUTUSKAN', core_text, re.IGNORECASE)
        if memutuskan_end:
            pertimbangan = core_text[:memutuskan_end.end()]
            body = core_text[memutuskan_end.end():]
        else:
            pertimbangan = ""
            body = core_text

    sections = []

    # 1. Pertimbangan
    if pertimbangan.strip():
        sections.append({
            "type": "pertimbangan",
            "title": "Pertimbangan Hukum",
            "content": pertimbangan,
            "parent_title": None
        })

    # 2. Parse BAB dan Pasal - dengan struktur hirarki yang benar
    current_bab_title = None
    current_bab_content = ""
    current_bab_index = -1
    lines = body.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Deteksi BAB - sekarang kita juga mencari BAB yang judulnya di baris berikutnya
        bab_match = re.match(r'^(BAB\s+[IVXLCDM]+)\s*(.*)$', line, re.IGNORECASE)
        if bab_match:
            bab_no = bab_match.group(1).strip().upper()
            bab_name = bab_match.group(2).strip()
            
            # Jika nama BAB kosong, coba ambil baris berikutnya sebagai nama BAB
            if not bab_name and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Jika baris berikutnya bukan Pasal atau BAB, maka mungkin itu nama BAB
                if not re.match(r'^(Pasal\s+\d+|BAB\s+[IVXLCDM]+)', next_line, re.IGNORECASE):
                    bab_name = next_line
                    i += 1  # Lewati baris nama BAB juga
            
            # Jika masih kosong, gunakan nama umum
            if not bab_name:
                bab_name = "BAB TANPA NAMA"
                
            bab_title = f"{bab_no} – {bab_name}"
            
            # Jika sebelumnya ada BAB yang sedang diproses, simpan dulu
            if current_bab_title and current_bab_content.strip():
                sections[current_bab_index]["content"] = current_bab_content.strip()
            
            current_bab_title = bab_title
            
            # Tambahkan BAB ke sections
            sections.append({
                "type": "bab",
                "title": current_bab_title,
                "content": "",  # Akan diisi nanti
                "parent_title": None
            })
            current_bab_index = len(sections) - 1
            current_bab_content = f"{bab_no} {bab_name}"  # Mulai dengan judul BAB
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
            
            # Tambahkan pasal ke konten BAB saat ini
            if current_bab_content:
                current_bab_content += "\n\n" + pasal_content
            else:
                current_bab_content = pasal_content
            
            i = j
            continue
        
        # Jika bukan BAB atau Pasal, tambahkan ke konten BAB saat ini
        if current_bab_title:
            current_bab_content += "\n" + line
        
        i += 1
    
    # Jangan lupa simpan konten BAB terakhir jika ada
    if current_bab_title and current_bab_content.strip() and current_bab_index >= 0:
        sections[current_bab_index]["content"] = current_bab_content.strip()

    # 3. Tambahkan tanda tangan ke chunk terakhir
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

    # 4. Tambahkan lampiran
    if lampiran.strip():
        sections.append({
            "type": "lampiran",
            "title": "Lampiran – Surat Pernyataan",
            "content": lampiran,
            "parent_title": None
        })

    return sections