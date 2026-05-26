import re
from typing import List, Dict, Any

def chunk_se(text: str) -> List[Dict[str, Any]]:
    """
    Chunk Surat Edaran berdasarkan struktur dokumen hukum formal (BAB, Pasal, dll).
    Menangani:
      - BAB (struktur utama)
      - Pasal (sub utama)
      - Butir (1., 2., 3., dll)
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
    sections = []
    current_section = None
    current_sub_items = []
    
    # Counter untuk urutan
    item_counter = 1
    
    # Status untuk melacak apakah kita sedang dalam konteks pasal (baru mulai dari BAB ke atas)
    in_structured_section = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Deteksi BAB: BAB I, BAB II, dll.
        if re.match(r'^BAB\s+[IVX]+', stripped, re.IGNORECASE):
            # Simpan section sebelumnya jika ada
            if current_section:
                # Gabungkan sub-items ke main section
                full_content = current_section['content']
                if current_sub_items:
                    full_content += "\n" + "\n".join([sub['content'] for sub in current_sub_items])
                
                current_section['content'] = full_content
                sections.append(current_section)
            
            current_section = {
                'type': 'bab',
                'title': stripped,
                'content': line,
                'level': 0,
                'order': item_counter,
                'parent_id': None,
                'metadata': {'section_type': 'bab'}
            }
            current_sub_items = []
            item_counter += 1
            in_structured_section = True  # Mulai dari sini kita anggap dalam konteks struktur hukum
            
        # Deteksi Pasal: Pasal 1, Pasal 2, dll.
        elif re.match(r'^Pasal\s+\d+', stripped, re.IGNORECASE):
            # Simpan section sebelumnya jika ada
            if current_section:
                # Gabungkan sub-items ke main section
                full_content = current_section['content']
                if current_sub_items:
                    full_content += "\n" + "\n".join([sub['content'] for sub in current_sub_items])
                
                current_section['content'] = full_content
                sections.append(current_section)
            
            current_section = {
                'type': 'pasal',
                'title': stripped,
                'content': line,
                'level': 1,
                'order': item_counter,
                'parent_id': None,  # Akan diisi di database berdasarkan BAB jika ada
                'metadata': {'section_type': 'pasal', 'pasal_number': re.search(r'\d+', stripped).group()}
            }
            current_sub_items = []
            item_counter += 1
            in_structured_section = True  # Tetap dalam konteks struktur hukum
            
        # Deteksi butir utama: "1.", "2.", "10.", dll. (juga sebagai indikator awal struktur hukum)
        elif (re.match(r'^\s*\d+\\\s*$', stripped) or re.match(r'^\s*\d+\\\s+\S', stripped)):
            # Set status bahwa kita sekarang dalam konteks struktur hukum
            in_structured_section = True
            # Simpan section sebelumnya jika ada
            if current_section:
                # Gabungkan sub-items ke main section
                full_content = current_section['content']
                if current_sub_items:
                    full_content += "\n" + "\n".join([sub['content'] for sub in current_sub_items])
                
                current_section['content'] = full_content
                sections.append(current_section)
            
            # Ekstrak nomor dan judul
            parts = re.split(r'\s*', stripped, 1)
            number = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else ""
            
            current_section = {
                'type': 'butir',
                'title': f"{number}. {title}".strip(),
                'content': stripped,
                'level': 2,
                'order': item_counter,
                'parent_id': None,  # Akan diisi di database berdasarkan pasal/bab jika ada
                'metadata': {'item_number': number}
            }
            current_sub_items = []
            item_counter += 1
            
        elif current_section:  # Jika sedang dalam section
            # Deteksi sub-item (a., b., c., i., ii., dst.)
            if re.match(r'^\s*[a-zA-Z]\.\s', line) or \
               re.match(r'^\s*[ivx]+\)\s', line) or \
               re.match(r'^\s*-\s', line) or \
               re.match(r'^\s*•\s', line):
                
                # Simpan sub-item
                sub_item = {
                    'type': 'sub_item',
                    'title': line.strip(),
                    'content': line,
                    'level': current_section['level'] + 1,
                    'order': len(current_sub_items) + 1,
                    'parent_id': current_section['order'],  # Referensi ke order dari parent section
                    'metadata': {'parent_item': current_section.get('metadata', {}).get('item_number') or current_section.get('metadata', {}).get('pasal_number')}
                }
                current_sub_items.append(sub_item)
            else:
                # Tambahkan ke konten dari section saat ini
                current_section['content'] += f"\n{line}"

        i += 1

    # Tambahkan section terakhir
    if current_section:
        full_content = current_section['content']
        if current_sub_items:
            full_content += "\n" + "\n".join([sub['content'] for sub in current_sub_items])
        
        current_section['content'] = full_content
        sections.append(current_section)
        
        # Tambahkan sub-items
        for sub_item in current_sub_items:
            sections.append(sub_item)

    # Jika tidak ada section terstruktur → kembalikan seluruh isi sebagai header/deskripsi
    if not sections:
        body = text.strip()
        if signature_block:
            body += "\n\n" + signature_block
        
        if body:
            sections.append({
                'type': 'header',
                'title': 'Deskripsi Surat Edaran',
                'content': body,
                'level': 0,
                'order': 1,
                'parent_id': None,
                'metadata': {}
            })

    # Tambahkan signature ke section terakhir jika ada
    if signature_block and sections:
        sections[-1]['content'] = sections[-1]['content'].rstrip() + "\n\n" + signature_block
        # Update metadata untuk menunjukkan ini termasuk signature
        if 'includes_signature' not in sections[-1]['metadata']:
            sections[-1]['metadata']['includes_signature'] = True

    return sections