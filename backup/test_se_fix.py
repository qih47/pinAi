#!/usr/bin/env python3
"""
Test script to verify that SE chunking works without hierarchy issues
"""

from embeddings.chunk_se import chunk_se
import os

# Read the SE document content
se_file_path = "./temp_uploads/SE Seragam.pdf"

if os.path.exists(se_file_path):
    # Convert PDF to text for testing
    import fitz
    doc = fitz.open(se_file_path)
    text = ""
    for page_num in range(min(5, doc.page_count)):  # Just first 5 pages to avoid too much text
        page = doc.load_page(page_num)
        text += page.get_text()
    doc.close()
    
    print("Testing chunk_se function...")
    sections = chunk_se(text)
    
    print(f"Number of sections returned: {len(sections)}")
    
    # Check if any section has parent_id that's not None
    for i, section in enumerate(sections[:5]):  # Just check first 5 sections
        print(f"Section {i+1}: type={section['type']}, title='{section['title'][:50]}...', parent_id={section.get('parent_id')}")
        
    # Look for any problematic parent_id values
    problematic_sections = [s for s in sections if s.get('parent_id') is not None]
    if problematic_sections:
        print(f"\nWARNING: Found {len(problematic_sections)} sections with non-None parent_id:")
        for ps in problematic_sections[:5]:  # Show first 5
            print(f"  - Type: {ps['type']}, Title: '{ps['title'][:50]}...', parent_id: {ps['parent_id']}")
    else:
        print("\n✓ No sections with problematic parent_id values found!")
else:
    print(f"File {se_file_path} not found. Using sample text instead.")
    
    # Sample text for testing
    sample_text = """
    SURAT EDARAN
    
    Nomor : SE-123/XXX/2024
    
    Tentang:
    Pedoman Penggunaan Seragam Pegawai
    
    BAB I
    KETENTUAN UMUM
    
    Pasal 1
    Dalam Surat Edaran ini yang dimaksud dengan:
    1. Seragam Pegawai adalah pakaian resmi yang digunakan oleh pegawai...
    
    2. Instansi adalah lembaga pemerintah atau swasta yang mempekerjakan pegawai...
    
    a. Dinas Pendidikan
    b. Dinas Kesehatan
    
    Pasal 2
    Seragam Pegawai terdiri atas:
    1. Seragam harian
    2. Seragam kerja khusus
    3. Seragam pelaksana teknis
    
    BAB II
    PENGGUNAAN SERAGAM
    
    Pasal 3
    Pegawai wajib menggunakan seragam sesuai dengan ketentuan berikut:
    1. Waktu penggunaan
    2. Tempat penggunaan
    3. Jenis kegiatan
    
    Dikeluarkan di: Jakarta
    Pada tanggal: 1 Januari 2024
    """
    
    print("Testing chunk_se function with sample text...")
    sections = chunk_se(sample_text)
    
    print(f"Number of sections returned: {len(sections)}")
    
    # Check if any section has parent_id that's not None
    for i, section in enumerate(sections):
        print(f"Section {i+1}: type={section['type']}, title='{section['title'][:50]}...', parent_id={section.get('parent_id')}")
        
    # Look for any problematic parent_id values
    problematic_sections = [s for s in sections if s.get('parent_id') is not None and s.get('parent_id') != s.get('order')]
    if problematic_sections:
        print(f"\nFound {len(problematic_sections)} sections with potentially problematic parent_id:")
        for ps in problematic_sections:
            print(f"  - Type: {ps['type']}, Title: '{ps['title'][:50]}...', parent_id: {ps['parent_id']}, order: {ps.get('order')}")
    else:
        print("\nNo problematic parent_id values found!")