#!/usr/bin/env python3
"""
================================================================================
🏛️ CAKRA AI — 37 SCENARIO AGENTIC & MASTER ROUTER BENCHMARK SUITE
================================================================================
Evaluasi otomatis menyeluruh terhadap 37 Skenario Uji (TC-01 s/d TC-37)
sesuai Master Implementation Plan:
  - TC-01 s/d TC-04: Berkas Fisik (React, Python, Bugfix Edit, Template Spreadsheet)
  - TC-05 s/d TC-07: RAG Regulasi, Anaphora Multi-turn, Visual Alur Turn 3
  - TC-08 s/d TC-12: In-Stream Tools (docsearch, websearch, python_calc, terminal, doc_diff)
  - TC-13 s/d TC-15: HRIS, Zimbra Smart Mail, Pincloud Deck
  - TC-16 s/d TC-20: SOP Mutasi, Ranpur/Senjata, Peta Pindad, Self-Correction, URL Reader
  - TC-21 s/d TC-24: Nota Dinas BUMN, Debugging Coding, Ambiguous Wizard, Selection
  - TC-25 s/d TC-27: Chitchat Greeting, Persona BUMN, Gratitude Closing
  - TC-28 s/d TC-30: Data Simulation, Deep Research, CRAG Fallback Jalur 2
  - TC-31 s/d TC-32: Dual-Layer Memory Recall (Short-term Journal & Long-term Manifest)
  - TC-33 s/d TC-37: Tone Adaptif, Anti-Sycophancy, 4 Persona, Format-Shifting, Guest Guard

Usage:
    # 1. Menjalankan semua 37 skenario dengan model aktif (vLLM / Ollama):
    PYTHONPATH=. ./rag_env/bin/python backend/scripts/finetune/test_agentic_37_benchmark.py

    # 2. Mode validasi skema & fallback (cepat / tanpa beban GPU):
    PYTHONPATH=. ./rag_env/bin/python backend/scripts/finetune/test_agentic_37_benchmark.py --fallback-only

    # 3. Export hasil evaluasi ke JSON:
    PYTHONPATH=. ./rag_env/bin/python backend/scripts/finetune/test_agentic_37_benchmark.py --output benchmark_37_results.json
================================================================================
"""

import sys
import os
import time
import json
import argparse
import asyncio
from typing import Dict, Any, List

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from backend.app.services.pipeline.dispatcher_router import dispatch_intent_route, _build_fallback_routing
from backend.app.services.pipeline.modes.mode_utils import detect_precheck

BENCHMARK_37_CASES = [
    # ── GRUP 1: BERKAS FISIK & CODING (TC-01 s/d TC-04) ──
    {
        "id": "TC-01",
        "category": "File Creation",
        "name": "Pembuatan Berkas Fisik React & Tailwind",
        "msg": "coba buatin flow login plus auth dan berikan codenya memakai react dan tailwind simpan di file AuthContext.jsx dan LoginPage.jsx",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_coding": True, "is_generate_file": True, "file_action": "create"}
    },
    {
        "id": "TC-02",
        "category": "File Creation",
        "name": "Pembuatan Berkas Fisik Python FastAPI",
        "msg": "buatkan skrip backend fastapi lengkap untuk auth jwt beserta model user database sqlite simpan di file auth_service.py",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_coding": True, "is_generate_file": True, "file_action": "create"}
    },
    {
        "id": "TC-03",
        "category": "File Editing",
        "name": "Bugfix Edit File Eksisting",
        "msg": "tolong perbaiki bug di auth.py pada fungsi verify_password karena bcrypt selalu throw invalid salt, update langsung filenya",
        "hist": "[ASSISTANT]: Berikut kode auth.py sebelumnya...",
        "is_first": False,
        "is_guest": False,
        "expected": {"is_coding": True, "is_generate_file": True, "file_action": "edit"}
    },
    {
        "id": "TC-04",
        "category": "File Creation",
        "name": "Template Berkas Spreadsheet Excel",
        "msg": "buatkan format file template spreadsheet excel daftar hadir lembur karyawan pabrik amunisi dan ekspor filenya",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_generate_file": True}
    },

    # ── GRUP 2: RAG REGULASI, MULTI-TURN & VISUAL ANAPHORA (TC-05 s/d TC-07) ──
    {
        "id": "TC-05",
        "category": "RAG Regulasi",
        "name": "RAG Dokumen PKB Pindad",
        "msg": "apa syarat izin cuti tahunan dan hak cuti melahirkan menurut PKB Pindad?",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-06",
        "category": "Multi-Turn Anaphora",
        "name": "Anaphora Turn 2 Regulasi",
        "msg": "kalau yang keguguran dapat berapa lama izinnya?",
        "hist": "[USER]: apa syarat izin cuti melahirkan menurut PKB Pindad?\n[ASSISTANT]: Menurut PKB pasal 24 cuti melahirkan adalah 3 bulan...",
        "is_first": False,
        "prev_top": "Cuti & Hubungan Kerja",
        "prev_sub": "Cuti Melahirkan PKB",
        "is_guest": False,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-07",
        "category": "Visual Anaphora",
        "name": "Visual Flowchart Bagan Alur Turn 3",
        "msg": "bisa tolong gambarkan alur pengajuannya dalam flowchart diagram?",
        "hist": "[USER]: apa syarat cuti melahirkan?\n[ASSISTANT]: syaratnya mengajukan surat dokter ke SDM...\n[USER]: kalau keguguran berapa lama?",
        "is_first": False,
        "prev_top": "Cuti & Hubungan Kerja",
        "prev_sub": "Cuti Melahirkan PKB",
        "is_guest": False,
        "expected": {"requires_visual": True}
    },

    # ── GRUP 3: IN-STREAM AGENTIC TOOLS (TC-08 s/d TC-12) ──
    {
        "id": "TC-08",
        "category": "In-Stream Tools",
        "name": "In-Stream DocSearch Internal",
        "msg": "cari di database regulasi pasal berapa yang mengatur sanksi SP3 dan pemutusan hubungan kerja",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-09",
        "category": "In-Stream Tools",
        "name": "In-Stream WebSearch Berita Terkini",
        "msg": "bagaimana perkembangan berita indeks saham holding defend id dan bumn pertahanan hari ini di internet?",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_web_search": True}
    },
    {
        "id": "TC-10",
        "category": "In-Stream Tools",
        "name": "In-Stream Python Calc Pesangon",
        "msg": "hitung simulasi pesangon pensiun karyawan masa kerja 18 tahun gaji pokok 9,2 juta sesuai formula undang-undang dan PKB",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_analytic": True}
    },
    {
        "id": "TC-11",
        "category": "In-Stream Tools",
        "name": "In-Stream Coding Run & Dependency Check",
        "msg": "coba periksa dependensi package.json ini dan jalankan skrip build vite",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_coding": True}
    },
    {
        "id": "TC-12",
        "category": "In-Stream Tools",
        "name": "In-Stream Doc Diff Komparasi",
        "msg": "bandingkan dan cocokkan perbedaan isi draf surat edaran direksi versi 1 dengan versi revisi 2",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_comparative": True}
    },

    # ── GRUP 4: INTEGRASI MODUL & WORKFLOW (TC-13 s/d TC-15) ──
    {
        "id": "TC-13",
        "category": "HRIS & Kepegawaian",
        "name": "Rekapitulasi Cuti Pegawai",
        "msg": "rekapitulasi jatah cuti tahunan dan absensi karyawan divisi senjata",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-14",
        "category": "Smart Mail",
        "name": "Draf Email Resmi Zimbra",
        "msg": "buatkan draf email resmi zimbra ke kementerian perindustrian perihal undangan rapat koordinasi sertifikasi amunisi",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_generate_email": True}
    },
    {
        "id": "TC-15",
        "category": "Pincloud Deck",
        "name": "Papan Kanban & Manajemen Proyek",
        "msg": "buat papan jadwal timeline gantt chart proyek perakitan batch 3 kendaraan tempur anoa",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"requires_visual": True}
    },

    # ── GRUP 5: DOMAIN PINDAD & ALAT BANTU (TC-16 s/d TC-20) ──
    {
        "id": "TC-16",
        "category": "SOP Mutasi",
        "name": "SOP Prosedur Mutasi Divisi",
        "msg": "bagaimana tata cara dan prosedur mutasi antar divisi di PT Pindad menurut SOP SDM?",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-17",
        "category": "Alutsista",
        "name": "Spesifikasi Kendaraan Khusus Ranpur",
        "msg": "jelaskan spesifikasi teknis dan proteksi balistik ranpur Anoa 6x6 APC Pindad",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-18",
        "category": "Peta Kawasan",
        "name": "Lokasi Divisi Kawasan Pindad",
        "msg": "di mana denah lokasi dan koordinat divisi rekayasa industri di kawasan pindad bandung?",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_map_query": True}
    },
    {
        "id": "TC-19",
        "category": "Self Correction",
        "name": "Koreksi Sanggahan Fakta oleh Pengguna",
        "msg": "bukan, maksud saya bukan cuti tahunan biasa tapi cuti besar 6 tahunan",
        "hist": "[USER]: syarat cuti di pindad?\n[ASSISTANT]: Syarat cuti tahunan adalah telah bekerja 1 tahun...",
        "is_first": False,
        "prev_top": "Cuti Karyawan",
        "is_guest": False,
        "expected": {"is_self_correction": True}
    },
    {
        "id": "TC-20",
        "category": "URL Reader",
        "name": "Membaca Tautan Web Spesifik",
        "msg": "tolong rangkum isi dokumen pengumuman di link https://pindad.com/pengumuman-vendor-2025.html",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_url_read": True}
    },

    # ── GRUP 6: PERSURATAN, TROUBLESHOOTING & WIZARD (TC-21 s/d TC-24) ──
    {
        "id": "TC-21",
        "category": "Naskah Dinas",
        "name": "Draf Nota Dinas BUMN",
        "msg": "buatkan draf nota dinas permohonan pengadaan unit server baru ke kepala divisi IT",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_docwriter": True}
    },
    {
        "id": "TC-22",
        "category": "Troubleshooting",
        "name": "Error Traceback Debugging",
        "msg": "Traceback (most recent call last):\n  File 'app.py', line 12, in <module>\nKeyError: 'jwt_secret'\nbantu beresin crash ini",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_coding": True, "is_troubleshooting": True}
    },
    {
        "id": "TC-23",
        "category": "Ambiguity Wizard",
        "name": "Pertanyaan Terlalu Singkat / Ambigu",
        "msg": "saya mau bikin sistem baru",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_ambiguous": True}
    },
    {
        "id": "TC-24",
        "category": "Wizard Selection",
        "name": "Konfirmasi Jawaban dari Opsi Wizard",
        "msg": "saya pilih opsi 2 arsitektur backend fastapi dengan postgresql",
        "hist": "[ASSISTANT]: Pilih opsi arsitektur: 1. Express 2. FastAPI...",
        "is_first": False,
        "is_guest": False,
        "expected": {"is_ambiguous": False}
    },

    # ── GRUP 7: CHITCHAT & ETIKET BUMN (TC-25 s/d TC-27) ──
    {
        "id": "TC-25",
        "category": "Chitchat",
        "name": "Sapaan Pagi Ramah",
        "msg": "selamat pagi cakra, apa kabar hari ini bro?",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_chitchat": True, "need_rag": False}
    },
    {
        "id": "TC-26",
        "category": "Persona BUMN",
        "name": "Konsultasi Formal BUMN",
        "msg": "Selamat pagi Bapak, mohon arahan mengenai tata laksana penyambutan delegasi kementerian",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-27",
        "category": "Closing Chitchat",
        "name": "Ucapan Terima Kasih Penutup",
        "msg": "terima kasih banyak cakra atas penjelasannya, sangat membantu!",
        "hist": "[ASSISTANT]: Sama-sama rekan, sukses selalu...",
        "is_first": False,
        "is_guest": False,
        "expected": {"is_chitchat": True, "need_rag": False}
    },

    # ── GRUP 8: ANALITIK & DEEP RESEARCH (TC-28 s/d TC-30) ──
    {
        "id": "TC-28",
        "category": "Data Simulation",
        "name": "Simulasi Biaya Operasional",
        "msg": "simulasikan tren peningkatan biaya maintenance kendaraan taktis komodo 5 tahun ke depan dengan chart grafik",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_analytic": True, "requires_visual": True}
    },
    {
        "id": "TC-29",
        "category": "Deep Research",
        "name": "Kajian Mendalam Alutsista Regional",
        "msg": "lakukan kajian komprehensif dan riset mendalam tentang modernisasi senapan serbu kaliber 5.56mm di negara-negara ASEAN",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_deep_research": True}
    },
    {
        "id": "TC-30",
        "category": "CRAG Fallback",
        "name": "Pencarian Berita Luar PT Pindad",
        "msg": "berita terkini uji coba maung garuda oleh presiden prabowo di internet",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_web_search": True}
    },

    # ── GRUP 9: DUAL-LAYER MEMORY RECALL (TC-31 & TC-32) ──
    {
        "id": "TC-31",
        "category": "Short-Term Memory Recall",
        "name": "Rangkuman Diskusi Intra-Sesi (Session Journal)",
        "msg": "buat rangkuman dari hasil diskusi kita tadi dan apa saja yang tadi udah kita list?",
        "hist": "[USER]: mari kita rancang auth...\n[ASSISTANT]: 1. JWT 2. Refresh Token...",
        "is_first": False,
        "is_guest": False,
        "expected": {"history_scope": "full_session"}
    },
    {
        "id": "TC-32",
        "category": "Long-Term Memory Recall",
        "name": "Ingatan Lintas Sesi (Sessions Manifest)",
        "msg": "sesi kemarin kita pernah bahas arsitektur microservices cakra, tolong lanjutkan poin terakhirnya",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"history_scope": "cross_session"}
    },

    # ── GRUP 10: TONE, ANTI-SYCOPHANCY & GUARD (TC-33 s/d TC-37) ──
    {
        "id": "TC-33",
        "category": "Dynamic Tone",
        "name": "Permintaan Eksplisit To-The-Point",
        "msg": "jelaskan aturan lembur secara to the point aja ya langsung ke intinya",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-34",
        "category": "Universal Anti-Sycophancy",
        "name": "Kritik Debat Fakta Regulasi",
        "msg": "kamu salah! cuti hamil di pkb pindad itu 12 bulan bukan 3 bulan, jangan ngawur!",
        "hist": "[ASSISTANT]: Berdasarkan PKB Pasal 24, hak cuti melahirkan adalah 3 bulan...",
        "is_first": False,
        "is_guest": False,
        "expected": {"is_self_correction": True}
    },
    {
        "id": "TC-35",
        "category": "Persona Mirroring",
        "name": "Gaya Gaul Engineer (gue/lo)",
        "msg": "bro gue mau nanya cara deploy docker container cakra di server gimana sih?",
        "hist": "",
        "is_first": True,
        "is_guest": False,
        "expected": {"is_coding": True}
    },
    {
        "id": "TC-36",
        "category": "Format-Shifting",
        "name": "Konversi Jawaban ke Tabel Datagrid",
        "msg": "ubah penjelasan pasal di atas ke dalam format tabel datagrid agar mudah disortir",
        "hist": "[ASSISTANT]: Berikut daftar komponen tunjangan...",
        "is_first": False,
        "is_guest": False,
        "expected": {"requires_visual": True}
    },
    {
        "id": "TC-37",
        "category": "Guest Mode Boundary",
        "name": "Isolasi Tamu terhadap Dokumen Internal",
        "msg": "tampilkan isi dokumen rahasia SKEP direksi PT Pindad nomor 12 tahun 2024",
        "hist": "",
        "is_first": True,
        "is_guest": True,
        "expected": {"need_rag": False, "is_docwriter": False}
    },
]


class DummyReq:
    app = None


async def run_benchmark(model_name: str = None, fallback_only: bool = False, limit: int = None, verbose: bool = False) -> Dict[str, Any]:
    print("=" * 80)
    print(f"🏛️ RUNNING CAKRA AI 37-SCENARIO BENCHMARK SUITE")
    target_model_label = model_name or "DEFAULT"
    mode_str = 'FALLBACK ENGINE (SCHEMA VALIDATION)' if fallback_only else f'LLM ROUTER ({target_model_label})'
    print(f"Mode: {mode_str}")
    cases_to_run = BENCHMARK_37_CASES[:limit] if limit else BENCHMARK_37_CASES
    print(f"Total Test Cases: {len(cases_to_run)}")
    print("=" * 80)

    results = []
    passed_count = 0
    t0_total = time.time()

    for idx, tc in enumerate(cases_to_run, start=1):
        tc_id = tc["id"]
        tc_cat = tc["category"]
        tc_name = tc["name"]
        user_msg = tc["msg"]
        context_history = tc.get("hist", "")
        is_first = tc.get("is_first", True)
        is_guest = tc.get("is_guest", False)
        prev_top = tc.get("prev_top")
        prev_sub = tc.get("prev_sub")
        expected = tc.get("expected", {})

        precheck = detect_precheck(user_msg, "default", False)
        precheck["is_guest"] = is_guest
        precheck["_user_message"] = user_msg
        if prev_top:
            precheck["previous_topic"] = prev_top
        if prev_sub:
            precheck["previous_subject"] = prev_sub

        t_start = time.time()
        if fallback_only:
            # Uji jalur fallback & deterministik
            routing = _build_fallback_routing(precheck)
        else:
            # Uji jalur Master Router
            try:
                routing = await dispatch_intent_route(
                    request=DummyReq(),
                    user_message=user_msg,
                    context_history_str=context_history,
                    is_first_chat=is_first,
                    previous_topic=prev_top,
                    previous_subject=prev_sub,
                    precheck=precheck,
                    model_name=model_name,
                )
            except Exception as e:
                print(f"❌ [{tc_id}] Error running route: {e}")
                routing = _build_fallback_routing(precheck)

        latency_ms = (time.time() - t_start) * 1000

        # Verifikasi kesesuaian ekspektasi
        mismatches = []
        for key, exp_val in expected.items():
            actual_val = routing.get(key)
            if actual_val != exp_val:
                mismatches.append(f"{key}: exp={exp_val}, got={actual_val}")

        passed = len(mismatches) == 0
        if passed:
            passed_count += 1
            status_icon = "✅"
        else:
            status_icon = "⚠️"

        print(f"{status_icon} [{tc_id}] {tc_cat:<22} | {tc_name:<42} | {latency_ms:6.1f}ms")
        if not passed and verbose:
            for mm in mismatches:
                print(f"      └─ Mismatch: {mm}")

        results.append({
            "id": tc_id,
            "category": tc_cat,
            "name": tc_name,
            "passed": passed,
            "latency_ms": latency_ms,
            "mismatches": mismatches,
            "expected": expected,
            "routing": {k: routing.get(k) for k in expected.keys()},
        })

    duration_total = time.time() - t0_total
    pass_rate = (passed_count / len(BENCHMARK_37_CASES)) * 100

    print("=" * 80)
    print(f"📊 SUMMARY REPORT:")
    print(f"   • Passed Cases : {passed_count} / {len(BENCHMARK_37_CASES)} ({pass_rate:.1f}%)")
    print(f"   • Total Time   : {duration_total:.2f}s")
    print("=" * 80)

    return {
        "total_cases": len(BENCHMARK_37_CASES),
        "passed": passed_count,
        "pass_rate_percent": pass_rate,
        "duration_seconds": duration_total,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="Run 37-Scenario Agentic & Master Router Benchmark")
    parser.add_argument("--model", type=str, default=None, help="Target router model")
    parser.add_argument("--fallback-only", action="store_true", help="Run rule-based fallback schema verification only")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test cases to run")
    parser.add_argument("--verbose", action="store_true", default=True, help="Print detailed mismatch logs")
    parser.add_argument("--output", type=str, default=None, help="Save report to JSON file")
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    report = loop.run_until_complete(
        run_benchmark(model_name=args.model, fallback_only=args.fallback_only, limit=args.limit, verbose=args.verbose)
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"💾 Report saved to: {args.output}")


if __name__ == "__main__":
    main()
