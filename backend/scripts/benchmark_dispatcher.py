#!/usr/bin/env python3
"""
================================================================================
⚡ CAKRA AI — Call 1 Router Benchmark & Ground Truth Evaluation Suite
================================================================================
Menguji akurasi routing, multi-flag classification, dan kecepatan (ms)
pada 18 Ground Truth Test Cases.

Usage:
    # 1. Menguji model default router (gemma4:e4b):
    PYTHONPATH=. ./rag_env/bin/python backend/scripts/benchmark_call1.py

    # 2. Menguji model tertentu (misal: granite4.2:8b):
    PYTHONPATH=. ./rag_env/bin/python backend/scripts/benchmark_call1.py --model granite4.2:8b

    # 3. Menguji dan membandingkan semua model + export JSON:
    PYTHONPATH=. ./rag_env/bin/python backend/scripts/benchmark_call1.py --all --output results.json

    # 4. Menguji murni kecerdasan model tanpa regex precheck:
    PYTHONPATH=. ./rag_env/bin/python backend/scripts/benchmark_call1.py --no-precheck
================================================================================
"""

import sys
import os
import time
import json
import argparse
import asyncio
from typing import Dict, Any, List

from backend.app.services.pipeline.call1_router import execute_call1_routing
from backend.app.services.pipeline.modes.mode_utils import detect_precheck

# 18 Ground Truth Benchmark Test Cases
TEST_CASES = [
    {
        "id": "TC-01",
        "name": "Web Search + Visual",
        "msg": "Cuy ramalan cuaca Bandung 7 hari ke depan dong sekalian buatkan grafik suhunya",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_web_search": True, "requires_visual": True}
    },
    {
        "id": "TC-02",
        "name": "Web Search (Komparasi Tank)",
        "msg": "Bandingkan spesifikasi tank Leopard 2 vs Abrams X terbaru dong",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_web_search": True}
    },
    {
        "id": "TC-03",
        "name": "RAG (Cuti PKB)",
        "msg": "Jelaskan alur pengajuan cuti tahunan menurut PKB sekalian bikinin diagram alir / flowchart",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-04",
        "name": "RAG (Pasal Lembur PKB)",
        "msg": "Apa perbedaan pasal tunjangan lembur di PKB 2021 dibanding PKB 2024?",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-05",
        "name": "RAG (SOP Mutasi)",
        "msg": "Gimana prosedur dan syarat mutasi antar divisi di Pindad sesuai SOP?",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-06",
        "name": "Coding (Debug 401)",
        "msg": "Bro ini kenapa ya axios post ke backend muncul error 401 unauthorized, bantu debug dong",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_coding": True}
    },
    {
        "id": "TC-07",
        "name": "Coding (JWT Express)",
        "msg": "Buatkan skrip middleware Express JS untuk autentikasi JWT token dan verifikasi role admin",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_coding": True}
    },
    {
        "id": "TC-08",
        "name": "Coding + Ambiguous",
        "msg": "Bikinin aplikasi web todo list",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_coding": True, "is_ambiguous": True}
    },
    {
        "id": "TC-09",
        "name": "Map Query",
        "msg": "Dimana alamat lokasi pabrik munisi PT Pindad yang di Turen Malang?",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_map_query": True}
    },
    {
        "id": "TC-10",
        "name": "Self-Correction",
        "msg": "Salah bro, The Nun itu rilis tahun 2018 bukan 2020 coba cek lagi yang bener",
        "hist": "User: tahun berapa the nun?\nAI: The nun rilis 2020...",
        "is_first": False,
        "prev_top": "Film Horor",
        "prev_sub": "The Conjuring Universe",
        "expected": {"is_self_correction": True}
    },
    {
        "id": "TC-11",
        "name": "Follow-up Web Search",
        "msg": "Cari di web",
        "hist": "User: info berita ntt dong\nAI: Berita NTT...",
        "is_first": False,
        "prev_top": "Berita Terkini",
        "prev_sub": "Berita NTT Hari Ini",
        "expected": {"is_web_search": True}
    },
    {
        "id": "TC-12",
        "name": "Follow-up PKB / RAG",
        "msg": "Ada dasar hukum pasalnya ga di PKB?",
        "hist": "User: sanksi SP3 gimana?\nAI: Sanksi SP3...",
        "is_first": False,
        "prev_top": "Regulasi SDM",
        "prev_sub": "Sanksi SP3 Karyawan",
        "expected": {"need_rag": True}
    },
    {
        "id": "TC-13",
        "name": "Wizard Stack Selection",
        "msg": "Pilih React + Tailwind",
        "hist": "User: mau bikin web\nAI: Pilih stack: 1. React 2. Vue",
        "is_first": False,
        "prev_top": "Frontend Web",
        "prev_sub": "Aplikasi Web Todo List",
        "expected": {"is_coding": True, "is_ambiguous": False}
    },
    {
        "id": "TC-14",
        "name": "Data Simulation Chat",
        "msg": "Bikinin 5 contoh data dummy penjualan divisi senjata dalam bentuk tabel di sini",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_generate_file": False}
    },
    {
        "id": "TC-15",
        "name": "File Export Fisik",
        "msg": "Buatkan dan ekspor file Excel (.xlsx) untuk daftar inventaris senjata ringan",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_generate_file": True}
    },
    {
        "id": "TC-16",
        "name": "Ambient Weather Chitchat",
        "msg": "Cuy cuaca Bandung hari ini panas ga ya?",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_chitchat": True, "is_web_search": False}
    },
    {
        "id": "TC-17",
        "name": "URL Reader / Web",
        "msg": "Tolong baca dan rangkum isi link ini ya https://pindad.com/profil-perusahaan",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_web_search": True}
    },
    {
        "id": "TC-18",
        "name": "Email / Nota Dinas",
        "msg": "Buatkan draf email resmi undangan rapat koordinasi anggaran ke Kadiv Keuangan",
        "hist": "",
        "is_first": True,
        "prev_top": None,
        "prev_sub": None,
        "expected": {"is_generate_email": True}
    },
]

class DummyReq:
    app = None

async def evaluate_model(model_name: str, use_precheck: bool = True) -> Dict[str, Any]:
    print("\n" + "=" * 68)
    print(f"🚀 MENJALANKAN BENCHMARK MODEL: \033[1;36m{model_name}\033[0m (Precheck: {use_precheck})")
    print("=" * 68)
    
    # 1. Warmup Run (Mencegah Cold Start Latency Spike)
    print(f"⏳ Melakukan VRAM Warmup untuk {model_name}...")
    try:
        w_precheck = detect_precheck("halo", "default", False) if use_precheck else {}
        await execute_call1_routing(
            request=DummyReq(),
            user_message="halo",
            context_history_str="",
            precheck=w_precheck,
            is_first_chat=True,
            model_name=model_name
        )
        print(f"✅ VRAM Warmup {model_name} selesai.\n")
    except Exception as e:
        print(f"⚠️ Warmup warning: {e}\n")

    results = []
    total_latency = 0.0
    passed_count = 0
    
    for tc in TEST_CASES:
        t0 = time.perf_counter()
        precheck = detect_precheck(tc["msg"], "default", False) if use_precheck else {}
        try:
            res = await execute_call1_routing(
                request=DummyReq(),
                user_message=tc["msg"],
                context_history_str=tc["hist"],
                precheck=precheck,
                is_first_chat=tc["is_first"],
                previous_topic=tc["prev_top"],
                previous_subject=tc["prev_sub"],
                model_name=model_name
            )
            latency = (time.perf_counter() - t0) * 1000
            total_latency += latency
            
            passed = True
            mismatches = []
            for exp_k, exp_v in tc["expected"].items():
                actual_v = res.get(exp_k, False)
                if exp_v is True and not actual_v:
                    passed = False
                    mismatches.append(f"Expected {exp_k}=True, got {actual_v}")
                elif exp_v is False and actual_v:
                    passed = False
                    mismatches.append(f"Expected {exp_k}=False, got {actual_v}")
            
            if passed:
                passed_count += 1
                status_str = "\033[1;32m✅ PASS\033[0m"
            else:
                status_str = f"\033[1;31m❌ FAIL\033[0m ({', '.join(mismatches)})"
                
            active_flags = {k: v for k, v in res.items() if v is True or (isinstance(v, list) and v and k in ["queries", "query_judul"])}
            print(f"[{tc['id']}] {status_str} | \033[1;33m{latency:.1f}ms\033[0m")
            print(f"   Input: '{tc['msg'][:48]}...'")
            print(f"   Flags: {active_flags}")
            
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "passed": passed,
                "latency_ms": round(latency, 1),
                "mismatches": mismatches,
                "active_flags": active_flags
            })
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000
            total_latency += latency
            print(f"[{tc['id']}] \033[1;31m💥 ERROR:\033[0m {str(e)} | {latency:.1f}ms")
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "passed": False,
                "latency_ms": round(latency, 1),
                "error": str(e)
            })

    avg_latency = total_latency / len(TEST_CASES)
    accuracy = (passed_count / len(TEST_CASES)) * 100
    
    print("\n" + "-" * 55)
    print(f"📊 REKAPITULASI HASIL: \033[1;36m{model_name}\033[0m")
    print("-" * 55)
    print(f"Total Test Cases : {len(TEST_CASES)}")
    print(f"Akurasi Lolos    : \033[1;32m{passed_count}/{len(TEST_CASES)} ({accuracy:.1f}%)\033[0m")
    print(f"Rata-rata Latensi: \033[1;33m{avg_latency:.1f} ms\033[0m\n")
    
    return {
        "model": model_name,
        "use_precheck": use_precheck,
        "passed": passed_count,
        "total": len(TEST_CASES),
        "accuracy": round(accuracy, 1),
        "avg_latency_ms": round(avg_latency, 1),
        "details": results
    }

async def main():
    parser = argparse.ArgumentParser(description="CAKRA AI Call 1 Benchmark Runner")
    parser.add_argument("--model", type=str, default="gemma4:e4b", help="Nama model Ollama untuk diuji (default: gemma4:e4b)")
    parser.add_argument("--all", action="store_true", help="Uji dan bandingkan gemma4:e4b vs granite4.2:8b")
    parser.add_argument("--no-precheck", action="store_true", help="Uji murni model LLM tanpa hint regex precheck")
    parser.add_argument("--output", type=str, default=None, help="Path file untuk export hasil JSON (contoh: results.json)")
    args = parser.parse_args()

    use_precheck = not args.no_precheck

    if args.all:
        models = ["gemma4:e4b", "granite4.2:8b"]
    else:
        models = [args.model]

    summary = {}
    for m in models:
        summary[m] = await evaluate_model(m, use_precheck=use_precheck)

    if len(summary) > 1:
        print("\n" + "=" * 72)
        print("🏆 FINAL BENCHMARK COMPARISON TABLE (18 TEST CASES)")
        print("=" * 72)
        print(f"{'Model Name':<20} | {'Accuracy':<15} | {'Avg Latency (ms)':<20} | {'Status'}")
        print("-" * 72)
        best_acc = max(r['accuracy'] for r in summary.values())
        for m, res in summary.items():
            is_best = res['accuracy'] == best_acc
            status_text = "👑 BEST" if is_best else "RUNNER-UP"
            print(f"{m:<20} | {res['passed']}/{res['total']} ({res['accuracy']:.1f}%) | {res['avg_latency_ms']:<20.1f} | {status_text}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Hasil benchmark berhasil diekspor ke: {args.output}")

if __name__ == "__main__":
    asyncio.run(main())
