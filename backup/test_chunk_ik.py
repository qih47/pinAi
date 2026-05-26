#!/usr/bin/env python3
"""
Test script to debug chunk_ik function with sample text
"""

from embeddings.chunk_ik import chunk_ik

# Sample text similar to the one mentioned in the user's issue
sample_text = """
INSTRUKSI KERJA
I-03-MI-555
EDISI 01

1. TUJUAN
a. Sebagai panduan...
d. Meningkatkan life time mesin

2. DEFINISI
a. Mesin painting penambat rel adalah...
g. CCW (Counter ClockWise), ...

3. URAIAN INSTRUKSI
a. Izin Kerja
f. Kondisi Darurat...

4. REFERENSI DOKUMEN TERKAIT
a. Surat Keputusan Direksi...

LEMBAR PENGESAHAN
Tabel NO DISI...
"""

print("Testing chunk_ik function...")
result = chunk_ik(sample_text)

print(f"\nNumber of sections found: {len(result)}")
for i, section in enumerate(result):
    print(f"\nSection {i+1}:")
    print(f"  Type: {section['type']}")
    print(f"  Title: {section['title']}")
    print(f"  Content preview: {section['content'][:100]}...")
    print(f"  Length of content: {len(section['content'])}")