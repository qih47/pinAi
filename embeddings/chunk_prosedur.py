import re
from typing import List, Dict

def chunk_prosedur(text: str) -> List[Dict[str, str]]:
    """
    Chunk Prosedur dengan struktur:
    - Header (judul, nomor, edisi)
    - Bagian utama (1., 2., 3., 4., 5.) — setiap bagian mencakup semua sub-butir di dalamnya
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
    # Cari header sampai sebelum bagian pertama (1.)
    header_match = re.search(r'(PROSEDUR[\s\S]*?)(?=\n\s*1\.\s+)', main_content, re.IGNORECASE)
    if header_match:
        header = header_match.group(1).strip()
        main_content = main_content[header_match.end():]
    else:
        # Jika tidak ada 1., coba cari sampai akhir
        header = main_content
        main_content = ""

    sections = []

    # Tambahkan header
    if header:
        sections.append({
            "type": "header",
            "title": "Header Prosedur",
            "content": header,
            "parent_title": None
        })

    # Jika tidak ada main_content, langsung return
    if not main_content.strip():
        if pengesahan_content:
            sections.append({
                "type": "pengesahan",
                "title": "LEMBAR PENGESAHAN",
                "content": pengesahan_content,
                "parent_title": None
            })
        return sections

    # Split berdasarkan pola: \n + angka + titik + spasi
    if not main_content.startswith('\n'):
        main_content = '\n' + main_content
    
    parts = re.split(r'(\n\s*\d+\.\s+)', main_content)
    
    # Proses pasangan
    i = 1
    while i < len(parts):
        if i + 1 < len(parts):
            header_part = parts[i]
            content_part = parts[i + 1]
            
            # Gabungkan untuk ekstrak judul
            full_text = header_part + content_part
            
            # Ekstrak nomor dan judul
            title_match = re.match(r'^\s*(\d+)\.\s*(.+?)(?:\n|$)', full_text, re.DOTALL)
            if title_match:
                number = title_match.group(1)
                title = title_match.group(2).strip()
                section_title = f"{number}. {title}"
                
                sections.append({
                    "type": "bagian",
                    "title": section_title,
                    "content": full_text.strip(),
                    "parent_title": None
                })
            else:
                # Fallback: gunakan seluruh teks
                sections.append({
                    "type": "bagian",
                    "title": f"Bagian {i//2 + 1}",
                    "content": full_text.strip(),
                    "parent_title": None
                })
            
            i += 2
        else:
            i += 1

    # Tambahkan LEMBAR PENGESAHAN
    if pengesahan_content:
        sections.append({
            "type": "pengesahan",
            "title": "LEMBAR PENGESAHAN",
            "content": pengesahan_content,
            "parent_title": None
        })

    return sections