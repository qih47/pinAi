# parser_se.py (VERSI FIX SESUAI FORMAT SE ASLI)
import re
from database.db import get_db

def clean_text(text):
    """Hilangkan baris kosong dan whitespace."""
    lines = text.split("\n")
    return [l.strip() for l in lines if l.strip()]


# =============================================================
#   PARSER SURAT EDARAN - FORMAT FINAL
# =============================================================
def parse_se_structure(text_lines):

    sections = []

    header = []
    content = []
    signature = []
    tembusan = []
    footer = []

    current = None

    # ====== REGEX DETECTION ======
    re_header = re.compile(r"(surat edaran|nomor|tentang)", re.IGNORECASE)
    re_start_content = re.compile(r"^(\d+[\.\)])")   # contoh: 1. / 2) / 1)
    re_signature = re.compile(r"(bandung|jakarta).*\d{4}", re.IGNORECASE)
    re_tembusan = re.compile(r"^(tembusan|kepada)", re.IGNORECASE)
    re_footer = re.compile(r"(head office|representative office|www\.pindad\.com)", re.IGNORECASE)

    # === FLAGS ===
    found_content = False
    found_signature = False

    for line in text_lines:
        l = line.lower()

        # 1. HEADER (awal dokumen)
        if not found_content and re_header.search(l):
            current = "header"
            header.append(line)
            continue

        # 2. CONTENT dimulai dari angka 1.
        if re_start_content.match(l):
            current = "content"
            found_content = True
            content.append(line)
            continue

        # 3. SIGNATURE (Bandung, ... 15 November 2025)
        if re_signature.search(l):
            current = "signature"
            found_signature = True
            signature.append(line)
            continue

        # 4. TEMBUSAN
        if found_signature and re_tembusan.match(l):
            current = "tembusan"
            tembusan.append(line)
            continue

        # 5. FOOTER
        if re_footer.search(l):
            current = "footer"
            footer.append(line)
            continue

        # APPEND TO CURRENT SECTION
        if current == "header":
            header.append(line)
        elif current == "content":
            content.append(line)
        elif current == "signature":
            signature.append(line)
        elif current == "tembusan":
            tembusan.append(line)
        elif current == "footer":
            footer.append(line)

    # =============================================================
    # BUILD SECTIONS
    # =============================================================
    def add(type, title, arr):
        if arr:
            sections.append({
                "section_type": type,
                "section_title": title,
                "content": "\n".join(arr)
            })

    add("header", "Header", header)
    add("content", "Isi Surat", content)
    add("signature", "Tanda Tangan", signature)
    add("tembusan", "Tembusan", tembusan)
    add("footer", "Footer", footer)

    return sections


# =============================================================
#  SAVE TO DB
# =============================================================
def save_se_sections(dokumen_id, sections):
    conn = get_db()
    cur = conn.cursor()

    for i, sec in enumerate(sections, start=1):
        cur.execute("""
            INSERT INTO dokumen_section (dokumen_id, section_type, section_title, content, section_order)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            dokumen_id,
            sec["section_type"],
            sec["section_title"],
            sec["content"],
            i
        ))

    conn.commit()
    cur.close()
    conn.close()


# =============================================================
#  ENTRY POINT DIPANGGIL DARI main_parser
# =============================================================
def parse_se_document(dokumen_id, full_text):
    print(f"🟦 Parsing: SE (dokumen_id={dokumen_id})")

    lines = clean_text(full_text)
    sections = parse_se_structure(lines)

    save_se_sections(dokumen_id, sections)

    print(f"✅ SE berhasil diparsing: {len(sections)} section.")
    return sections
