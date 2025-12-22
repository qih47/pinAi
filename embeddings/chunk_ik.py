import re
from typing import List, Dict

def chunk_ik(text: str) -> List[Dict[str, str]]:
    """
    Chunk Instruksi Kerja dengan struktur:
    - Header (judul, nomor, edisi)
    - Bagian utama (1., 2., 3., 4.) — setiap bagian mencakup semua sub-butir di dalamnya
    - LEMBAR PENGESAHAN sebagai bagian terpisah
    """
    text = re.sub(r'={5,}\s*PAGE\s+\d+\s*={5,}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Pisahkan bagian utama dari LEMBAR PENGESAHAN
    pengesahan_match = re.search(r'(\n\s*LEMBAR\s+PENGESAHAN.*$)', text, re.IGNORECASE | re.DOTALL)
    if pengesahan_match:
        pengesahan_content = pengesahan_match.group(1).strip()
        main_content = text[:pengesahan_match.start()].strip()
    else:
        pengesahan_content = ""
        main_content = text

    # Ekstrak header (judul, nomor, edisi)
    header = ""
    header_match = re.search(r'(INSTRUKSI\s+KERJA.*?)(\n\s*\d+\.\s+)', main_content, re.IGNORECASE | re.DOTALL)
    if header_match:
        header = header_match.group(1).strip()
        main_content = main_content[header_match.end(1):]

    sections = []

    # Tambahkan header sebagai bagian awal
    if header:
        sections.append({
            "type": "header",
            "title": "Header Instruksi Kerja",
            "content": header,
            "parent_title": None
        })

    # Split berdasarkan bagian utama: 1., 2., 3., 4. (angka 1 digit + titik)
    # Gunakan regex yang fleksibel: ^\s*\d\.\s+ atau \n\s*\d\.\s+
    parts = re.split(r'(\n?\s*\d\.\s+)', main_content)

    current_section = None
    current_content = ""

    for i, part in enumerate(parts):
        stripped = part.strip()

        # Jika ini adalah awal bagian utama (1., 2., 3., dst)
        if re.match(r'^\s*\d\.\s+', stripped):
            # Simpan section sebelumnya
            if current_section:
                sections.append({
                    "type": "bagian",
                    "title": current_section,
                    "content": current_content.strip(),
                    "parent_title": None
                })
            
            # Ekstrak nomor dan judul
            title_match = re.match(r'^\s*(\d+)\.\s*(.+)', stripped)
            if title_match:
                number = title_match.group(1)
                title = title_match.group(2).strip()
                current_section = f"{number}. {title}"
                current_content = stripped  # simpan awal section
            else:
                current_section = stripped
                current_content = stripped
        
        else:
            # Tambahkan ke konten section saat ini
            if current_section:
                current_content += part

    # Tambahkan section terakhir
    if current_section:
        sections.append({
            "type": "bagian",
            "title": current_section,
            "content": current_content.strip(),
            "parent_title": None
        })

    # Tambahkan LEMBAR PENGESAHAN jika ada
    if pengesahan_content:
        sections.append({
            "type": "pengesahan",
            "title": "LEMBAR PENGESAHAN",
            "content": pengesahan_content,
            "parent_title": None
        })

    return sections