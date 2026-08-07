import fitz

pdf_path = "/home/qisthi/pinAi/file_peraturan/BUKU_PKB_PERIODE_2024-2026.pdf"
doc = fitz.open(pdf_path)

print("--- PAGE 4 (0-indexed) ---")
print(doc[4].get_text()[:500])

print("\n--- PAGE 53 (0-indexed) ---")
print(doc[53].get_text()[:500])

print("\n--- PAGE 60 (0-indexed) ---")
print(doc[60].get_text()[:500])
