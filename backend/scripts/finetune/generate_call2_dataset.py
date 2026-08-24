#!/usr/bin/env python3
"""
CAKRA AI — Call 2 Core Chain-of-Thought (CoT) & Visual Dataset Generator
=======================================================================
Menghasilkan dataset berbobot tinggi dengan penalaran eksplisit `<think>...</think>`,
penguasaan regulasi PT Pindad, dan sintesis komponen UI visual (`datagrid`, `infographic`, `chart`, `smartmail`).

Usage:
    python backend/scripts/finetune/generate_call2_dataset.py --output data/finetune/call2_train_2000.jsonl --samples 2000
"""

import os
import json
import random
import argparse
from typing import List, Dict, Any

# ═══════════════════════════════════════════════════════════════════════════════
# DOMAIN KNOWLEDGE BASES (PKB, SOP, PRODUK, & VISUAL TEMPLATES)
# ═══════════════════════════════════════════════════════════════════════════════

PKB_CASES = [
    {
        "query": "Berapa jatah cuti tahunan saya jika baru bekerja 1 tahun di Pindad dan bagaimana pengajuannya?",
        "context": "Perjanjian Kerja Bersama (PKB) PT PINDAD Bab V Pasal 24: Hak Cuti Tahunan diberikan sebanyak 12 (dua belas) hari kerja bagi pekerja yang telah bekerja selama 1 (satu) tahun terus menerus. Pengajuan dilakukan melalui portal HRIS minimal 3 hari sebelum pelaksanaan.",
        "thought": (
            "1. User menanyakan hak cuti tahunan untuk masa kerja 1 tahun dan prosedur pengajuan.\n"
            "2. Berdasarkan PKB Bab V Pasal 24, hak cuti adalah 12 hari kerja.\n"
            "3. Prosedur pengajuan via portal HRIS H-3.\n"
            "4. Format respon: Langsung to-the-point, sebutkan pasal resmi, dan buatkan tabel ringkas DataGrid atau langkah alur agar informatif."
        ),
        "response": (
            "Berdasarkan **Perjanjian Kerja Bersama (PKB) PT PINDAD Bab V Pasal 24**, pekerja yang telah memiliki masa kerja 1 tahun terus-menerus berhak atas **12 hari kerja** cuti tahunan.\n\n"
            "Berikut adalah ringkasan ketentuan dan alur pengajuannya:\n\n"
            "```datagrid\n"
            "{\n"
            "  \"title\": \"Ketentuan Hak Cuti Tahunan Pegawai\",\n"
            "  \"columns\": [\n"
            "    { \"key\": \"aspek\", \"label\": \"Aspek Ketentuan\" },\n"
            "    { \"key\": \"detail\", \"label\": \"Rincian Aturan PKB\" }\n"
            "  ],\n"
            "  \"rows\": [\n"
            "    { \"aspek\": \"Jumlah Hak Cuti\", \"detail\": \"12 Hari Kerja per tahun\" },\n"
            "    { \"aspek\": \"Syarat Masa Kerja\", \"detail\": \"Minimal 1 tahun terus-menerus\" },\n"
            "    { \"aspek\": \"Mekanisme Pengajuan\", \"detail\": \"Input via Portal HRIS (H-3 pelaksanaan)\" },\n"
            "    { \"aspek\": \"Persetujuan\", \"detail\": \"Verifikasi Manajer Unit / Atasan Langsung\" }\n"
            "  ]\n"
            "}\n"
            "```\n\n"
            "💡 **Catatan Penting:** Pastikan sisa kuota cuti pada portal HRIS mencukupi sebelum mengajukan permohonan agar proses verifikasi berjalan lancar."
        )
    },
    {
        "query": "Cuy, aturan cuti istri melahirkan dapat berapa hari ya?",
        "context": "PKB PT PINDAD Pasal 27 ayat (2) huruf b: Izin Meninggalkan Pekerjaan dengan Tetap Memperoleh Upah untuk Istri Melahirkan/Keguguran diberikan selama 2 (dua) hari kerja.",
        "thought": (
            "1. User bertanya santai/informal ('Cuy') tentang cuti istri melahirkan.\n"
            "2. Merujuk PKB Pasal 27 ayat 2 huruf b, hak izin adalah 2 hari kerja dengan upah penuh.\n"
            "3. Tone: Santai, akrab ('Gue-Lo' / 'Boss'), to-the-point tanpa basa-basi."
        ),
        "response": (
            "Sesuai dengan **PKB PT PINDAD Pasal 27 ayat (2) huruf b**, lo berhak dapet izin meninggalkan pekerjaan dengan upah penuh selama **2 (dua) hari kerja** saat istri melahirkan atau mengalami keguguran kandungan.\n\n"
            "### 📋 Dokumen yang Perlu Dilampirkan:\n"
            "* Surat keterangan lahir dari dokter/bidan atau rumah sakit.\n"
            "* Input permohonan izin dispensasi di portal HRIS begitu kembali masuk kerja.\n\n"
            "Semoga persalinan istri lancar dan keluarga sehat selalu ya, cuy! 👶🍼"
        )
    },
    {
        "query": "Tolong buatkan draf nota dinas permohonan pengadaan 3 unit laptop developer untuk Divisi IT.",
        "context": "Standar Surat Dinas PT PINDAD: Format mencakup Nomor Nota Dinas, Kepada (Kadiv Pengadaan), Dari (Kadiv IT), Perihal, dan rincian justifikasi kebutuhan perangkat.",
        "thought": (
            "1. User meminta pembuatan Nota Dinas resmi pengadaan laptop.\n"
            "2. Gunakan visual widget `smartmail` agar user bisa langsung preview dan copy/export surat dengan format standar korporat.\n"
            "3. Format struktur surat harus rapi dan profesional."
        ),
        "response": (
            "Berikut adalah draf **Nota Dinas Internal** untuk pengadaan laptop kerja Divisi IT yang sudah disesuaikan dengan format tata naskah dinas PT Pindad:\n\n"
            "```smartmail\n"
            "{\n"
            "  \"to\": \"Kepala Divisi Pengadaan & Logistik\",\n"
            "  \"from\": \"Kepala Divisi Teknologi Informasi\",\n"
            "  \"subject\": \"Permohonan Pengadaan 3 Unit Laptop High-Performance Developer\",\n"
            "  \"date\": \"24 Agustus 2026\",\n"
            "  \"body\": \"Dengan hormat,\\n\\nSehubungan dengan peningkatan beban kerja pengembangan sistem internal CAKRA AI dan infrastruktur digital perusahaan, bersama ini kami mengajukan permohonan pengadaan perangkat kerja sebagai berikut:\\n\\n1. Jenis Perangkat: Laptop High-Performance (RAM 32GB, Core i7/Ryzen 7, SSD 1TB)\\n2. Jumlah: 3 (tiga) Unit\\n3. Peruntukan: Tim Software Engineering Divisi IT\\n4. Justifikasi: Mendukung proses kompilasi kode dan pemodelan AI lokal.\\n\\nDemikian permohonan ini kami sampaikan. Atas perhatian dan kerja samanya, kami ucapkan terima kasih.\"\n"
            "}\n"
            "```\n\n"
            "Silakan ditinjau atau diedit kembali detail spesifikasinya sebelum diajukan ke sistem persuratan resmi."
        )
    },
    {
        "query": "coba cariin cuaca bandung seminggu kedepan dan buatkan infografisnya",
        "context": "Data Cuaca BMKG Bandung 24-30 Agustus 2026: Suhu 21-32°C, Senin-Rabu cerah berawan, Kamis-Sabtu potensi hujan ringan di sore hari.",
        "thought": (
            "1. User meminta prakiraan cuaca seminggu ke depan dan infografis.\n"
            "2. Gunakan komponen `infographic` dengan `layout: weather` yang sudah kita standarisasi.\n"
            "3. Sertakan saran aktivitas dan pakaian."
        ),
        "response": (
            "Ini dia rangkuman prakiraan cuaca wilayah Bandung untuk seminggu ke depan berdasarkan data meteorologi terbaru:\n\n"
            "```infographic\n"
            "{\n"
            "  \"layout\": \"weather\",\n"
            "  \"title\": \"PRAKIRAAN CUACA BANDUNG MINGGUAN\",\n"
            "  \"location\": \"Bandung & Sekitarnya (Basis Pindad)\",\n"
            "  \"days\": [\n"
            "    { \"day\": \"Senin, 24 Ags\", \"condition\": \"Cerah Berawan\", \"temp_max\": \"32°C\", \"temp_min\": \"21°C\", \"humidity\": \"65%\", \"wind\": \"12 km/h\", \"advice\": \"Ideal untuk aktivitas lapangan siang hari\" },\n"
            "    { \"day\": \"Selasa, 25 Ags\", \"condition\": \"Cerah Berawan\", \"temp_max\": \"31°C\", \"temp_min\": \"21°C\", \"humidity\": \"68%\", \"wind\": \"10 km/h\", \"advice\": \"Gunakan pakaian katun menyerap keringat\" },\n"
            "    { \"day\": \"Rabu, 26 Ags\", \"condition\": \"Berawan Tebal\", \"temp_max\": \"30°C\", \"temp_min\": \"20°C\", \"humidity\": \"74%\", \"wind\": \"14 km/h\", \"advice\": \"Suhu cukup sejuk dan nyaman\" },\n"
            "    { \"day\": \"Kamis, 27 Ags\", \"condition\": \"Hujan Ringan\", \"temp_max\": \"28°C\", \"temp_min\": \"20°C\", \"humidity\": \"82%\", \"wind\": \"16 km/h\", \"advice\": \"Sedia payung untuk mobilitas sore hari\" },\n"
            "    { \"day\": \"Jumat, 28 Ags\", \"condition\": \"Hujan Ringan\", \"temp_max\": \"29°C\", \"temp_min\": \"19°C\", \"humidity\": \"80%\", \"wind\": \"15 km/h\", \"advice\": \"Waspadai jalanan licin saat pulang kantor\" }\n"
            "  ],\n"
            "  \"recommendation\": \"Awal minggu didominasi cuaca cerah terik, namun potensi hujan ringan meningkat menjelang akhir pekan.\"\n"
            "}\n"
            "```\n\n"
            "Secara umum cuaca sangat mendukung operasional harian. Pastikan tetap terhidrasi di awal minggu saat suhu mencapai 32°C ya, Boss! ☀️🥤"
        )
    }
]


def generate_cot_sample(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """Mengemas satu data CoT ke dalam format ShareGPT standar."""
    system_prompt = (
        "Kamu adalah CAKRA AI, asisten kecerdasan buatan berdaulat PT PINDAD. "
        "Sebelum menjawab, lakukan penalaran terstruktur di dalam tag <think>...</think> "
        "lalu sajikan jawaban profesional, akurat, to-the-point, dan sertakan visual UI jika relevan."
    )

    human_msg = case_data["query"]
    if case_data.get("context"):
        human_msg = f"[DOKUMEN RUJUKAN]\n{case_data['context']}\n\n[PERTANYAAN PENGGUNA]\n{case_data['query']}"

    assistant_msg = f"<think>\n{case_data['thought']}\n</think>\n\n{case_data['response']}"

    return {
        "conversations": [
            {"from": "system", "value": system_prompt},
            {"from": "human", "value": human_msg},
            {"from": "gpt", "value": assistant_msg}
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic CoT dataset for Call 2 Core")
    parser.add_argument("--output", type=str, default="data/finetune/call2_train_2000.jsonl", help="Output JSONL filepath")
    parser.add_argument("--samples", type=int, default=2000, help="Number of samples to generate")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    generated_data = []
    for _ in range(args.samples):
        base_case = random.choice(PKB_CASES)
        sample = generate_cot_sample(base_case)
        generated_data.append(sample)

    random.shuffle(generated_data)

    with open(args.output, "w", encoding="utf-8") as f:
        for item in generated_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"✅ Berhasil men-generate {len(generated_data)} sampel CoT Reasoning dataset ke: {args.output}")


if __name__ == "__main__":
    main()
