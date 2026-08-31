"""
Intent Dictionary & Semantic Pattern Matcher untuk CAKRA AI Pipeline.
Menyediakan kamus kata kunci dan regex terstruktur untuk mengidentifikasi intent pengguna secara presisi.
"""

import re
from typing import Dict, Any, Optional, Tuple

# ── 1. EXPLICIT WEB SEARCH TRIGGERS ──────────────────────────────────────────
# 5 Spektrum Luas Kebutuhan Akses Web
EXPLICIT_SEARCH_PATTERNS = [
    # A. Perintah Penelusuran Online
    r"\b(cari|searching|googling|browsing|surfing|crawling|telusuri|lacak|riset)\s+(di\s+)?(web|internet|google|online|situs)\b",
    r"\b(coba\s+)?(cariin|googling|browsing)\b",
    r"\b(bisa\s+tolong\s+)?(carikan|carikan\s+info|carikan\s+referensi)\s+(online|di\s+web|di\s+internet)\b",
    r"\b(scrape|fetch|baca\s+link|baca\s+url)\b",
    
    # B. Validasi & Verifikasi Faktual
    r"\b(cek|periksa|verifikasi|cross[- ]?check)\s+(fakta|kebenaran|datanya|infonya|berita|sumber)\b",
    r"\b(cek\s+faktanya|faktanya\s+gimana|apa\s+beneran\s+ada\s+kabarnya|ada\s+bukti\s+valid(nya)?)\b",
    r"\b(cek|lihat)\s+(berita|rilis|klarifikasi)\s+resmi(nya)?\b",
    
    # C. Kabar Terkini & Informasi Mutakhir
    r"\b(berita|kabar|informasi|isu|kondisi|situasi|update)\s+(terkini|terbaru|teranyar|terupdate|terakhir|paling\s+baru|hari\s+ini|minggu\s+ini|saat\s+ini|sekarang)\b",
    r"\b(update|perkembangan)\s+(terkini|terbaru|terakhir|teranyar)\b",
    r"\b(ada\s+apa\s+hari\s+ini|ada\s+kejadian\s+apa|gempa\s+hari\s+ini|banjir\s+hari\s+ini)\b",
    
    # D. Data Dinamis & Real-Time Publik
    r"\b(prakiraan|ramalan|prediksi)\s+cuaca\s+(besok|lusa|minggu\s+depan|\d+\s+hari\s+ke\s+depan)\b",
    r"\b(kurs|harga\s+saham|nilai\s+tukar)\s+(rupiah|dollar|usd|ihsg|emas)\s+(hari\s+ini|terkini|saat\s+ini)\b",
    r"\b(kapan|jadwal)\s+(tayang|rilis|keluar|kick[- ]?off|tanding)\s+(film|game|gadget|iphone|samsung|pesawat|pertandingan)\b",
    
    # E. Sanggahan & Koreksi Pengguna (Self-Correction)
    r"\b(salah\s+(bro|bang|cuy|boss|min|ai)|bukan\s+itu|cek\s+lagi|coba\s+cek\s+lagi|yang\s+bener\s+kapan|jangan\s+ngaco)\b"
]

# ── 2. OPINION, AFFIRMATION, & CONVERSATIONAL TRIGGERS ───────────────────────
# Kalimat Opini, Curhat, Refleksi, dan Afirmasi (WAJIB Chitchat / Internal Reasoning)
OPINION_AFFIRMATION_PATTERNS = [
    r"^(susah|sulit|berat|ribet|parah|kacau|lucu|ironis|miris|ngeri|serem|gila)\s+(emang|banget|sih|ya|bro|cuy|boss|brother|kalau|kalo|jika)\b",
    r"\b(menurut\s+(lu|kamu|anda|lo|ai)|gimana\s+menurut(mu|mu\s+sendiri|mu\s+soal\s+ini))\b",
    r"\b(setuju\s+(ga|nggak|tidak)|bener\s+(ga|nggak|kan)|iya\s+kan|setuju\s+kan)\b",
    r"\b(kesel\s+(gue|gw|aku)|capek\s+(gue|gw|aku)|curhat\s+dikit|bingung\s+deh|gak\s+habis\s+pikir)\b",
    r"\b(kok\s+bisa\s+gitu|kok\s+bisa\s+ya|kenapa\s+harus\s+gitu|logikanya\s+gimana)\b",
    r"\b(haha+|hehe+|wkwk+|anjir|gokil|mantap|keren|asik)\b"
]

_search_compiled = [re.compile(p, re.IGNORECASE) for p in EXPLICIT_SEARCH_PATTERNS]
_opinion_compiled = [re.compile(p, re.IGNORECASE) for p in OPINION_AFFIRMATION_PATTERNS]


def is_explicit_web_search_required(text: str) -> bool:
    """
    Mengecek apakah pesan pengguna secara tegas membutuhkan pencarian web eksternal
    berdasarkan 5 spektrum luas pencarian internet.
    """
    if not text:
        return False
    stripped = text.strip()
    return any(p.search(stripped) for p in _search_compiled)


def is_pure_opinion_or_chitchat(text: str) -> bool:
    """
    Mengecek apakah pesan pengguna merupakan pernyataan opini, afirmasi, refleksi sosial,
    keluh kesah, atau reaksi percakapan yang TIDAK memerlukan web search.
    """
    if not text:
        return False
    stripped = text.strip()
    
    # Jika ada perintah eksplisit cari di web, jangan anggap murni opini
    if is_explicit_web_search_required(stripped):
        return False
        
    return any(p.search(stripped) for p in _opinion_compiled)


# ── 3. SLANG & GREETING MIRRORING DICTIONARY (3 TINGKAT FORMALITAS) ───────────

# LEVEL 1: Formal & Kesantunan Baku (Aman untuk mode 'formal_saya_anda')
GREETINGS_LEVEL1_FORMAL = {
    "mas": [r"\b(mas|masbro)\b"],
    "mbak": [r"\b(mbak|mba|mbas)\b"],
    "kang": [r"\b(kang|akang|aa)\b"],
    "teh": [r"\b(teh|teteh)\b"],
    "bang": [r"\b(bang|abang)\b"],
    "pak": [r"\b(bapak|pak)\b"],
    "bu": [r"\b(ibu|bu)\b"],
}

# LEVEL 2: Familiar & Akrab Hangat (Aman untuk mode 'familiar_aku_kamu' & 'informal_gue_lo')
GREETINGS_LEVEL2_FAMILIAR = {
    "kak": [r"\b(kak|kakak|kaka)\b"],
    "bro": [r"\b(bro|brother|bray|bre)\b"],
    "sis": [r"\b(sis|sist|sista|sistah)\b"],
    "bestie": [r"\b(bestie|beb|fren)\b"],
    "guys": [r"\b(guys|gaes|ges|gengs)\b"],
}

# LEVEL 3: Informal, Slang Gaul & Kedaerahan (KHUSUS mode 'informal_gue_lo')
GREETINGS_LEVEL3_INFORMAL = {
    # Urban & Slang Internet
    "cuy": [r"\b(cuy|kuy|cuyy|kuyy)\b"],
    "ngab": [r"\b(ngab|ngabs|abangkuh|abangkua|king)\b"],
    "gan": [r"\b(gan|agan|juragan)\b"],
    "bos": [r"\b(bos|boss|bosku|big\s+boss)\b"],
    "min": [r"\b(min|mimin)\b"],
    
    # Gaul Kedaerahan (Jawa / Arekan / Sunda / Nusantara)
    "bolo": [r"\b(bolo|boloku|konco|kancaku)\b"],
    "rek": [r"\b(rek|arek|arekan)\b"],
    "cak": [r"\b(cak|sam)\b"],
    "lur": [r"\b(lur|dulur|sedulur|dab)\b"],
    "euy": [r"\b(euy|ceuceu)\b"],
    "lae": [r"\b(lae|ito|tulang)\b"],
    "pace": [r"\b(pace|mace)\b"],
    "daeng": [r"\b(daeng|tabe)\b"],
    
    # Slang Pisuhan Akrab (Hanya di mode santai gue-lo)
    "cok": [r"\b(cok|cuk|su|asu)\b"],
}

def _compile_greeting_dict(d: Dict[str, list]) -> Dict[str, list]:
    return {
        canonical: [re.compile(pat, re.IGNORECASE) for pat in patterns]
        for canonical, patterns in d.items()
    }

_lvl1_compiled = _compile_greeting_dict(GREETINGS_LEVEL1_FORMAL)
_lvl2_compiled = _compile_greeting_dict(GREETINGS_LEVEL2_FAMILIAR)
_lvl3_compiled = _compile_greeting_dict(GREETINGS_LEVEL3_INFORMAL)


def extract_slang_mirror(text: str, user_pronoun: str = "formal_saya_anda") -> Optional[str]:
    """
    Mengekstrak kata sapaan aktif yang diizinkan berdasarkan tingkat formalitas gaya komunikasi user:
    - 'formal_saya_anda': HANYA Level 1 (Mas, Mbak, Kang, Teh, Bang, Pak, Bu). Sapaan slang/bolo/cuy DIABAIKAN.
    - 'familiar_aku_kamu': Level 1 + Level 2 (Kak, Bro, Sis, Bestie, Guys).
    - 'informal_gue_lo': Full Level 1 + Level 2 + Level 3 (Bolo, Cuy, Ngab, Gan, Bos, Cok, dll).
    """
    if not text:
        return None
    stripped = text.strip()

    # Tentukan kamus target berdasarkan gaya komunikasi aktif
    target_dicts = [_lvl1_compiled]
    if user_pronoun == "familiar_aku_kamu":
        target_dicts.append(_lvl2_compiled)
    elif user_pronoun == "informal_gue_lo":
        target_dicts.extend([_lvl2_compiled, _lvl3_compiled])

    for g_dict in target_dicts:
        for canonical, compiled_list in g_dict.items():
            for regex in compiled_list:
                if regex.search(stripped):
                    return canonical

    return None
