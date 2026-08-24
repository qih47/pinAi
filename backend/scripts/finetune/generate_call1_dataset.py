#!/usr/bin/env python3
"""
CAKRA AI — Call 1 Router Synthetic Dataset Generator
===================================================
Menghasilkan ribuan dataset sintetis terstruktur (ShareGPT / Alpaca JSONL format)
untuk melatih model `cakra-router` agar 100% deterministik dan sub-detik.

Usage:
    python backend/scripts/finetune/generate_call1_dataset.py --output data/call1_train.jsonl --samples 3000
"""

import os
import json
import random
import argparse
from typing import List, Dict, Any

# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATES & DOMAIN REPOSITORIES
# ═══════════════════════════════════════════════════════════════════════════════

PRONOUNS = ["informal_gue_lo", "formal_saya_anda", "familiar_aku_kamu"]
TONES = ["casual", "formal", "direct_concise", "empathetic"]

DOC_CATEGORIES = [
    {
        "topic": "Cuti & Izin Kerja",
        "doc_title": "Perjanjian Kerja Bersama (PKB) PT PINDAD",
        "examples": [
            ("berapa jatah cuti tahunan karyawan baru?", "cuti tahunan karyawan baru", ["cuti tahunan bagi pekerja baru", "ketentuan jatah cuti tahunan"]),
            ("aturan cuti melahirkan buat istri karyawan berapa hari ya?", "cuti istri melahirkan", ["hak cuti suami istri melahirkan", "cuti mendampingi istri bersalin"]),
            ("kalau mau izin cuti haji prosedurnya gimana bos?", "prosedur cuti ibadah haji", ["izin cuti menunaikan ibadah haji", "syarat cuti haji pkb"]),
            ("apakah cuti besar bisa diuangkan saat resign?", "kompensasi cuti besar", ["uang penggantian cuti besar", "pembayaran cuti besar resign"]),
            ("syarat izin dispensasi menikah di pkb pasal berapa?", "dispensasi menikah", ["izin dispensasi pernikahan pekerja", "cuti menikah pekerja"]),
            ("ketentuan cuti sakit berkepanjangan dengan surat dokter", "cuti sakit berkepanjangan", ["prosedur cuti sakit menahun", "surat dokter cuti sakit pkb"]),
        ]
    },
    {
        "topic": "Gaji, Tunjangan & Lembur",
        "doc_title": "Pedoman Penggajian & Remunerasi PT PINDAD",
        "examples": [
            ("cara hitung upah lembur di hari libur nasional", "perhitungan lembur libur nasional", ["rumus upah kerja lembur hari libur", "tarif lembur hari libur resmi"]),
            ("tunjangan hari raya (THR) cairnya kapan ya?", "jadwal pencairan THR", ["ketentuan pembayaran tunjangan hari raya", "jadwal pemberian thr pekerja"]),
            ("komponen tunjangan operasional dinas luar kota apa saja?", "tunjangan perjalanan dinas", ["rincian biaya perjalanan dinas", "tunjangan dinas luar kota"]),
            ("apakah ada insentif shift malam untuk staf produksi amunisi?", "insentif shift malam", ["tunjangan shift malam pabrik amunisi", "premi kerja giliran malam"]),
        ]
    },
    {
        "topic": "Disiplin & Sanksi Kerja",
        "doc_title": "Peraturan Disiplin Pegawai & Kode Etik",
        "examples": [
            ("tahapan pemberian Surat Peringatan (SP 1, 2, 3) di perusahaan", "mekanisme surat peringatan", ["prosedur penerbitan sp1 sp2 sp3", "sanksi disiplin tingkat sedang"]),
            ("sanksi keterlambatan fingerprint lebih dari 3 kali sebulan", "sanksi absensi keterlambatan", ["potongan keterlambatan absen", "aturan fingerprint pegawai"]),
            ("prosedur pemanggilan karyawan terkait dugaan pelanggaran integritas", "pemeriksaan pelanggaran integritas", ["sidang etik komite disiplin", "klarifikasi dugaan pelanggaran"]),
        ]
    },
    {
        "topic": "Jaminan Kesehatan & Pensiun",
        "doc_title": "Program BPJS Ketenagakerjaan & Dana Pensiun Pindad",
        "examples": [
            ("cara klaim kacamata dari plafon asuransi kesehatan pindad", "plafon klaim kacamata", ["reimburse kacamata pegawai", "plafon asuransi kesehatan kacamata"]),
            ("usia pensiun normal karyawan tetap pindad berapa tahun?", "usia pensiun normal", ["batas usia pensiun pkb", "usia pensiun normal pegawai"]),
            ("manfaat dana pensiun dplk pindad saat purna tugas", "manfaat pensiun dplk", ["perhitungan manfaat dana pensiun pindad", "hak purna tugas dplk"]),
        ]
    }
]

WEB_SEARCH_TOPICS = [
    ("coba cariin prakiraan cuaca bandung seminggu kedepan", "prakiraan cuaca bandung", "prakiraan cuaca bandung seminggu kedepan"),
    ("info berita terbaru tentang peluncuran tank harimau pindad", "berita tank harimau pindad", "berita peluncuran tank harimau pindad terbaru"),
    ("kurs dollar ke rupiah hari ini berapa ya?", "kurs usd idr hari ini", "kurs dollar ke rupiah hari ini"),
    ("spesifikasi senjata ss2 v4 kaliber berapa?", "spesifikasi senjata ss2 v4", "spesifikasi teknis pindad ss2 v4"),
    ("update harga minyak mentah dunia brent dan wti", "harga minyak mentah dunia", "harga minyak mentah brent wti hari ini"),
    ("siapa direktur utama defend id sekarang?", "direktur utama defend id", "direktur utama defend id saat ini"),
]

CODING_TOPICS = [
    ("bikinin function python async buat download file dari s3 pake aiobotocore", "python async s3 downloader", "python"),
    ("gimana cara bikin useEffect di react biar ga infinite loop saat fetch api?", "react useEffect dependency array", "javascript"),
    ("tulis query SQL postgresql buat cari 5 user dengan transaksi tertinggi bulan ini", "query top 5 customer sql", "sql"),
    ("bantu perbaiki error fastapi: TypeError: object async_generator can't be used in 'await' expression", "fix fastapi async generator error", "python"),
    ("bikin hook zustand custom buat manage state audio player di react", "zustand audio store hook", "javascript"),
]

EMAIL_TOPICS = [
    ("tolong buatkan draf email formal ke direksi untuk pengajuan perpanjangan lisensi software CAD", "pengajuan lisensi software cad", "formal"),
    ("bikinin email balasan sopan buat nolak tawaran vendor karena anggaran belum disetujui", "penolakan penawaran vendor sopan", "formal"),
    ("buatkan surat nota dinas internal permintaan pengadaan laptop kerja divisi IT", "nota dinas pengadaan laptop IT", "formal"),
    ("draf email undangan rapat koordinasi mingguan tim engineering hari kamis jam 10 pagi", "undangan rapat koordinasi engineering", "formal"),
]

GENERATE_FILE_TOPICS = [
    ("tolong buatkan file excel (.xlsx) template rekap kehadiran dan absensi pegawai 1 bulan", "template absensi pegawai excel", "xlsx"),
    ("buatkan file word (.docx) draf proposal pengadaan server AI GPU local", "proposal pengadaan server ai word", "docx"),
    ("export data perbandingan spesifikasi panser anoa vs komodo ke file CSV", "perbandingan anoa komodo csv", "csv"),
    ("bikinin skrip python scraper selenium simpan ke file report.py", "script python scraper", "python"),
]

AMBIGUOUS_TOPICS = [
    (
        "carikan saya undang undang cipta kerja",
        "undang-undang cipta kerja",
        {
            "type": "single_choice",
            "question": "Apakah Anda ingin mencari Undang-Undang Cipta Kerja pada dokumen internal perusahaan atau regulasi nasional di internet?",
            "options": [
                {"label": "📂 Dokumen Internal (PKB & Kebijakan Pindad)", "value": "internal"},
                {"label": "🌐 Regulasi Resmi Nasional (Pencarian Web)", "value": "web"},
                {"label": "🔍 Cari di Keduanya", "value": "both"}
            ]
        }
    ),
    (
        "tolong carikan data spesifikasi amunisi",
        "spesifikasi amunisi",
        {
            "type": "single_choice",
            "question": "Pilih jenis amunisi yang ingin Anda telusuri:",
            "options": [
                {"label": "Amunisi Kaliber Kecil (AKK - 5.56mm / 9mm)", "value": "akk"},
                {"label": "Amunisi Kaliber Sedang & Besar (AKS/AKB)", "value": "akb"},
                {"label": "Katalog Lengkap Amunisi", "value": "all"}
            ]
        }
    )
]

CHITCHAT_TOPICS = [
    ("halo selamat pagi cakra", "sapaan pagi", "informal_gue_lo", "casual"),
    ("kamu bisa bantu apa aja disini?", "kapabilitas cakra ai", "formal_saya_anda", "formal"),
    ("siapa yang menciptakan kamu?", "identitas cakra ai", "informal_gue_lo", "casual"),
    ("terima kasih banyak ya infonya sangat membantu", "ucapan terima kasih", "familiar_aku_kamu", "empathetic"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# GENERATOR ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def generate_sample(sample_type: str) -> Dict[str, Any]:
    """Generate one high-quality training instance for Call 1 Router."""
    system_prompt = (
        "Kamu adalah Cakra Router (Call 1) yang sangat presisi dan deterministik. "
        "Analisis pesan pengguna dan kembalikan sparse JSON routing payload murni."
    )

    if sample_type == "DOCUMENTS":
        cat = random.choice(DOC_CATEGORIES)
        user_msg, key_subj, queries = random.choice(cat["examples"])
        pronoun = random.choice(PRONOUNS)
        tone = "formal" if pronoun == "formal_saya_anda" else "casual"
        
        target_json = {
            "active_topic": cat["topic"],
            "key_subject": key_subj,
            "need_rag": True,
            "queries": queries,
            "query_judul": [cat["doc_title"]],
            "is_coding": False,
            "is_ambiguous": False,
            "pronoun": pronoun,
            "tone_hint": tone
        }

    elif sample_type == "WEB_SEARCH":
        user_msg, active_top, raw_q = random.choice(WEB_SEARCH_TOPICS)
        pronoun = random.choice(PRONOUNS)
        
        target_json = {
            "active_topic": active_top,
            "key_subject": raw_q,
            "need_rag": False,
            "is_web_search": True,
            "queries": [raw_q],
            "query_judul": [],
            "is_coding": False,
            "is_ambiguous": False,
            "pronoun": pronoun,
            "tone_hint": "casual"
        }

    elif sample_type == "CODING":
        user_msg, active_top, lang = random.choice(CODING_TOPICS)
        pronoun = random.choice(PRONOUNS)
        
        target_json = {
            "active_topic": active_top,
            "key_subject": f"Pemrograman {lang.upper()}",
            "need_rag": False,
            "is_coding": True,
            "is_ambiguous": False,
            "pronoun": pronoun,
            "tone_hint": "direct_concise"
        }

    elif sample_type == "EMAIL":
        user_msg, active_top, tone = random.choice(EMAIL_TOPICS)
        pronoun = "formal_saya_anda" if tone == "formal" else "informal_gue_lo"
        
        target_json = {
            "active_topic": "Penyusunan Surat & Email",
            "key_subject": active_top,
            "need_rag": False,
            "is_generate_email": True,
            "is_ambiguous": False,
            "pronoun": pronoun,
            "tone_hint": tone
        }

    elif sample_type == "GENERATE_FILE":
        user_msg, active_top, ext = random.choice(GENERATE_FILE_TOPICS)
        pronoun = random.choice(PRONOUNS)
        
        target_json = {
            "active_topic": "Pembuatan Berkas & File",
            "key_subject": active_top,
            "need_rag": False,
            "is_generate_file": True,
            "is_ambiguous": False,
            "pronoun": pronoun,
            "tone_hint": "direct_concise"
        }

    elif sample_type == "AMBIGUOUS":
        user_msg, active_top, wizard_obj = random.choice(AMBIGUOUS_TOPICS)
        pronoun = random.choice(PRONOUNS)
        
        target_json = {
            "active_topic": active_top,
            "key_subject": active_top,
            "need_rag": False,
            "is_ambiguous": True,
            "queries": [],
            "query_judul": [],
            "wizard": wizard_obj,
            "pronoun": pronoun,
            "tone_hint": "casual"
        }

    else:  # CHITCHAT / GREETING
        user_msg, active_top, pronoun, tone = random.choice(CHITCHAT_TOPICS)
        
        target_json = {
            "active_topic": active_top,
            "key_subject": "Sapaan Percakapan",
            "need_rag": False,
            "is_chitchat": True,
            "is_ambiguous": False,
            "pronoun": pronoun,
            "tone_hint": tone
        }

    # ShareGPT Conversation Format
    return {
        "conversations": [
            {"from": "system", "value": system_prompt},
            {"from": "human", "value": user_msg},
            {"from": "gpt", "value": json.dumps(target_json, ensure_ascii=False)}
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic dataset for Call 1 Router")
    parser.add_argument("--output", type=str, default="data/call1_train.jsonl", help="Output JSONL filepath")
    parser.add_argument("--samples", type=int, default=3000, help="Number of samples to generate")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    distribution = [
        ("DOCUMENTS", 0.40),
        ("WEB_SEARCH", 0.20),
        ("CODING", 0.15),
        ("EMAIL", 0.10),
        ("GENERATE_FILE", 0.08),
        ("AMBIGUOUS", 0.04),
        ("CHITCHAT", 0.03),
    ]

    total_samples = args.samples
    counts = {t: int(total_samples * ratio) for t, ratio in distribution}

    generated_data = []
    for sample_type, count in counts.items():
        for _ in range(count):
            sample = generate_sample(sample_type)
            generated_data.append(sample)

    random.shuffle(generated_data)

    with open(args.output, "w", encoding="utf-8") as f:
        for item in generated_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"✅ Berhasil men-generate {len(generated_data)} sampel dataset ke: {args.output}")
    print(f"📊 Distribusi Dataset:")
    for t, c in counts.items():
        print(f"   - {t:<15}: {c} sampel ({c/len(generated_data)*100:.1f}%)")


if __name__ == "__main__":
    main()
