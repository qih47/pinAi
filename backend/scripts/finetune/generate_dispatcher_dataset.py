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

DOCWRITER_TOPICS = [
    ("buatkan dokumen surat keputusan direksi tentang tim gugus tugas ai", "Surat Keputusan Gugus Tugas AI", "sk"),
    ("tuliskan dokumen sop operasional pemeliharaan mesin bubut cnc", "SOP Pemeliharaan Mesin CNC", "sop"),
    ("susun draf kebijakan keamanan informasi dan siber perusahaan", "Kebijakan Keamanan Siber", "policy"),
    ("tolong buatkan draf perjanjian kerja sama mou dengan pt dirgantara indonesia", "Draf MoU PT Dirgantara", "mou"),
    ("buatkan dokumen nota dinas resmi laporan progres pengembangan cakra ai", "Nota Dinas Laporan Cakra AI", "nota_dinas"),
    ("tuliskan panduan standar k3 keselamatan kerja bengkel senjata", "Pedoman K3 Bengkel Senjata", "pedoman"),
    ("buka doc studio buatkan dokumen peraturan disiplin kerja karyawan", "Dokumen Peraturan Disiplin", "peraturan"),
    ("buat dokumen telaahan staf untuk perpanjangan sewa gudang amunisi", "Telaahan Staf Sewa Gudang", "telaahan")
]

URL_READ_TOPICS = [
    ("tolong baca dan rangkum isi artikel https://pindad.com/berita-terbaru-tank-harimau", "Rangkuman Berita Pindad", "Berita Tank Harimau"),
    ("https://huggingface.co/Comfy-Org/Qwen-Image-2.1 versi ini di download lebih banyak dari pada https://huggingface.co/Qwen/Qwen-Image-2.1 coba cek", "Komparasi Model AI HuggingFace", "Qwen-Image-2.1 ComfyUI vs Official"),
    ("buka tautan https://github.com/vllm-project/vllm dan jelaskan fitur terbarunya", "Bedah Fitur vLLM", "Fitur Terbaru vLLM Repository"),
    ("coba cek spesifikasi teknis di link https://defensereview.com/anoa-6x6 apa saja", "Spesifikasi Anoa 6x6", "Spesifikasi Kendaraan Anoa 6x6"),
    ("ringkas isi pengumuman tender di https://lpse.kemhan.go.id/eproc4/lelang/view/123", "Ringkasan Tender Kemhan", "Pengumuman Tender LPSE Kemhan"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# GENERATOR ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def to_sparse_router_json(router_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitasi dictionary routing agar 100% mematuhi kaidah Lean Sparse JSON."""
    sparse: Dict[str, Any] = {}
    if not isinstance(router_dict, dict):
        return {"active_topic": "General", "key_subject": "General Inquiry"}

    if "session_title" in router_dict and router_dict["session_title"]:
        sparse["session_title"] = router_dict["session_title"]

    sparse["active_topic"] = router_dict.get("active_topic") or "General"
    sparse["key_subject"] = router_dict.get("key_subject") or "General Inquiry"

    bool_flags = [
        "need_rag", "is_web_search", "is_url_read", "is_coding", "is_troubleshooting",
        "is_docwriter", "is_generate_file", "is_generate_email",
        "is_map_query", "is_ambiguous", "is_chitchat", "is_self_correction",
        "requires_visual", "needs_history"
    ]
    for flag in bool_flags:
        if router_dict.get(flag) is True:
            sparse[flag] = True

    list_fields = ["queries", "query_judul", "search_tags", "visual_types"]
    for lfield in list_fields:
        val = router_dict.get(lfield)
        if isinstance(val, list) and len(val) > 0:
            sparse[lfield] = val

    str_fields = ["ambiguity_reason", "rag_reason", "response_format", "format_constraint"]
    for sfield in str_fields:
        val = router_dict.get(sfield)
        if isinstance(val, str) and val.strip():
            sparse[sfield] = val.strip()

    if isinstance(router_dict.get("wizard"), dict) and router_dict["wizard"]:
        sparse["wizard"] = router_dict["wizard"]

    return sparse


def generate_sample(sample_type: str) -> Dict[str, Any]:
    """Generate one high-quality training instance for Call 1 Router."""
    system_prompt = (
        "Kamu adalah Cakra Router (Call 1) yang sangat presisi dan deterministik. "
        "Analisis pesan pengguna dan kembalikan sparse JSON routing payload murni."
    )

    if sample_type == "DOCUMENTS":
        cat = random.choice(DOC_CATEGORIES)
        user_msg, key_subj, queries = random.choice(cat["examples"])
        
        target_json = to_sparse_router_json({
            "active_topic": cat["topic"],
            "key_subject": key_subj,
            "need_rag": True,
        })

    elif sample_type == "WEB_SEARCH":
        user_msg, active_top, raw_q = random.choice(WEB_SEARCH_TOPICS)
        
        target_json = to_sparse_router_json({
            "active_topic": active_top,
            "key_subject": raw_q,
            "is_web_search": True,
        })

    elif sample_type == "CODING":
        user_msg, active_top, lang = random.choice(CODING_TOPICS)
        
        target_json = to_sparse_router_json({
            "active_topic": active_top,
            "key_subject": f"Pemrograman {lang.upper()}",
            "is_coding": True,
            "is_troubleshooting": True if "error" in user_msg.lower() or "perbaiki" in user_msg.lower() else False
        })

    elif sample_type == "EMAIL":
        user_msg, active_top, tone = random.choice(EMAIL_TOPICS)
        
        target_json = to_sparse_router_json({
            "active_topic": "Penyusunan Surat & Email",
            "key_subject": active_top,
            "is_generate_email": True
        })

    elif sample_type == "DOCWRITER":
        user_msg, active_top, doc_type = random.choice(DOCWRITER_TOPICS)
        
        target_json = to_sparse_router_json({
            "active_topic": "Penyusunan Dokumen Resmi (Document Studio)",
            "key_subject": active_top,
            "is_docwriter": True
        })

    elif sample_type == "URL_READ":
        user_msg, active_top, key_subj = random.choice(URL_READ_TOPICS)
        target_json = to_sparse_router_json({
            "active_topic": active_top,
            "key_subject": key_subj,
            "is_url_read": True,
            "is_comparative": True if any(w in user_msg.lower() for w in ["vs", "bandingkan", "beda"]) else False
        })

    elif sample_type == "GENERATE_FILE":
        user_msg, active_top, ext = random.choice(GENERATE_FILE_TOPICS)
        
        target_json = to_sparse_router_json({
            "active_topic": "Pembuatan Berkas & File",
            "key_subject": active_top,
            "is_generate_file": True
        })

    elif sample_type == "AMBIGUOUS":
        user_msg, active_top, wizard_obj = random.choice(AMBIGUOUS_TOPICS)
        
        target_json = to_sparse_router_json({
            "active_topic": active_top,
            "key_subject": active_top,
            "is_ambiguous": True,
            "ambiguity_reason": "Kebutuhan pengguna belum terperinci secara spesifik.",
            "wizard": wizard_obj
        })

    else:  # CHITCHAT / GREETING
        user_msg, active_top, pronoun, tone = random.choice(CHITCHAT_TOPICS)
        
        target_json = to_sparse_router_json({
            "active_topic": active_top,
            "key_subject": "Sapaan Percakapan",
            "is_chitchat": True
        })

    # ShareGPT Conversation Format
    return {
        "conversations": [
            {"from": "system", "value": system_prompt},
            {"from": "human", "value": user_msg},
            {"from": "gpt", "value": json.dumps(target_json, ensure_ascii=False)}
        ]
    }


def fetch_unlimited_db_samples() -> List[Dict[str, Any]]:
    """Mengekstrak seluruh pertanyaan regulasi aktual dari PostgreSQL ragdb secara UNLIMITED."""
    import asyncio
    try:
        from backend.app.services.training.nightly.db_setup import get_ragdb_conn
        async def _query():
            async with get_ragdb_conn() as conn:
                rows = await conn.fetch("""
                    SELECT q.generated_question, q.page_range, COALESCE(c.judul, 'Regulasi PT Pindad') as judul
                    FROM rag_document_questions q
                    LEFT JOIN nightly_training_checkpoints c ON q.source_id = c.dokumen_id
                    ORDER BY q.id ASC
                """)
                return [dict(r) for r in rows]
        return asyncio.run(_query())
    except Exception as e:
        print(f"⚠️ Gagal membaca dari DB (melewati): {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Generate dataset for Call 1 Router (Unlimited by Training)")
    parser.add_argument("--output", type=str, default="data/finetune/nightly_call1_router.jsonl", help="Output JSONL filepath")
    parser.add_argument("--samples", type=int, default=0, help="Number of synthetic samples (0 = Unlimited by DB)")
    parser.add_argument("--from-db", action="store_true", help="Extract all actual questions from ragdb rag_document_questions")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    generated_data = []

    # Jika --from-db atau samples == 0, utamakan ekstrak dari ragdb
    if args.from_db or args.samples == 0:
        db_records = fetch_unlimited_db_samples()
        if db_records:
            system_prompt = (
                "Kamu adalah Cakra Router (Call 1) yang sangat presisi dan deterministik. "
                "Analisis pesan pengguna dan kembalikan sparse JSON routing payload murni."
            )
            for r in db_records:
                q_text = r.get("generated_question", "").strip()
                if not q_text:
                    continue
                doc_title = r.get("judul", "Regulasi PT Pindad")
                page_str = r.get("page_range", "")
                router_target = to_sparse_router_json({
                    "active_topic": "Regulasi & Kebijakan PT PINDAD",
                    "key_subject": doc_title,
                    "need_rag": True,
                    "rag_reason": f"Menanyakan regulasi internal {doc_title}",
                })
                generated_data.append({
                    "conversations": [
                        {"from": "system", "value": system_prompt},
                        {"from": "human", "value": q_text},
                        {"from": "gpt", "value": json.dumps(router_target, ensure_ascii=False)}
                    ]
                })
            print(f"📦 Berhasil memuat {len(generated_data)} data routing asli regulasi dari ragdb!")

    # Jika jumlah masih 0 atau diminta synthetic tambahan
    if not generated_data or args.samples > 0:
        total_samples = args.samples if args.samples > 0 else 1000
        distribution = [
            ("DOCUMENTS", 0.30),
            ("DOCWRITER", 0.15),
            ("WEB_SEARCH", 0.15),
            ("URL_READ", 0.10),
            ("CODING", 0.15),
            ("EMAIL", 0.08),
            ("GENERATE_FILE", 0.04),
            ("AMBIGUOUS", 0.02),
            ("CHITCHAT", 0.01),
        ]
        counts = {t: int(total_samples * ratio) for t, ratio in distribution}
        for sample_type, count in counts.items():
            for _ in range(count):
                sample = generate_sample(sample_type)
                generated_data.append(sample)

    random.shuffle(generated_data)

    with open(args.output, "w", encoding="utf-8") as f:
        for item in generated_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"✅ Berhasil mengekspor {len(generated_data)} sampel dataset router ke: {args.output} (Unlimited)")


if __name__ == "__main__":
    main()

