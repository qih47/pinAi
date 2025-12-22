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
    # Cari pola INSTRUKSI KERJA sampai sebelum angka pertama yang diikuti titik
    header_match = re.search(r'(INSTRUKSI\s+KERJA.*?)(?=\n\s*1\.\s+TUJUAN)', main_content, re.IGNORECASE | re.DOTALL)
