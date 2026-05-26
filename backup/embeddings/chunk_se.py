import re
from typing import List, Dict, Any

def chunk_se(text: str) -> List[str]:
    """
    Chunk Surat Edaran berdasarkan butir utama (1., 2., dst.).
    Menangani:
      - Butir utama di baris terpisah 
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

        # Deteksi butir utama: "1.", "2.", "10.", dll.
        if re.match(r'^\d+\.\s*$', stripped) or re.match(r'^\d+\.\s+\S', stripped):
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_main_number = True
        else:
            if current_main_number:
                current_chunk.append(line)

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    if not chunks:
        body = text.strip()
        if signature_block:
            body += "\n\n" + signature_block
        return [body] if body else []

    if signature_block:
        chunks[-1] = chunks[-1].rstrip() + "\n\n" + signature_block

    return chunks