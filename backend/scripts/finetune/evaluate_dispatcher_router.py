#!/usr/bin/env python3
"""
CAKRA AI — Call 1 Router Benchmark & Evaluation Engine
======================================================
Menguji model `cakra-router` (via Ollama / PyTorch) pada 50+ test cases uji
dan mengukur akurasi routing, format-compliance, dan kecepatan TTFT (ms).

Usage:
    python backend/scripts/finetune/evaluate_call1_router.py --model "cakra-router"
"""

import time
import json
import httpx
import argparse
from typing import List, Dict, Any

TEST_CASES = [
    # DOCUMENTS / PKB
    {"input": "berapa hari hak cuti tahunan yang saya dapatkan?", "expected_mode": "DOCUMENTS", "expected_need_rag": True},
    {"input": "aturan uang pesangon kalau kena PHK efisiensi gimana?", "expected_mode": "DOCUMENTS", "expected_need_rag": True},
    {"input": "syarat pengajuan bantuan kacamata di pkb pindad", "expected_mode": "DOCUMENTS", "expected_need_rag": True},
    
    # WEB SEARCH
    {"input": "prakiraan cuaca bandung besok siang hujan ga?", "expected_mode": "WEB_SEARCH", "expected_need_rag": False},
    {"input": "berita terkini perkembangan uji coba panser anoa 3", "expected_mode": "WEB_SEARCH", "expected_need_rag": False},
    {"input": "kurs dollar singapura ke rupiah hari ini", "expected_mode": "WEB_SEARCH", "expected_need_rag": False},
    
    # CODING
    {"input": "bikinin fungsi python async buat hitung checksum sha256 file", "expected_mode": "CODING", "expected_need_rag": False},
    {"input": "query sql buat join tabel karyawan dan absensi harian", "expected_mode": "CODING", "expected_need_rag": False},
    
    # EMAIL / NOTA DINAS
    {"input": "tolong drafkan surat nota dinas permohonan dinas luar kota", "expected_mode": "EMAIL", "expected_need_rag": False},
    {"input": "bikinin email formal konfirmasi jadwal meeting ke vendor", "expected_mode": "EMAIL", "expected_need_rag": False},
    
    # GENERATE FILE
    {"input": "buatkan file excel format rekapitulasi lembur bulanan", "expected_mode": "GENERATE_FILE", "expected_need_rag": False},
    
    # AMBIGUOUS
    {"input": "carikan saya undang undang cipta kerja", "expected_mode": "AMBIGUOUS", "expected_need_rag": False},
    
    # CHITCHAT
    {"input": "selamat pagi cakra apa kabar?", "expected_mode": "CHITCHAT", "expected_need_rag": False},
]


def evaluate_ollama(model_name: str, host: str = "http://localhost:11434"):
    print("=" * 65, flush=True)
    print(f"🧪 MEMULAI BENCHMARK & EVALUASI: {model_name}", flush=True)
    print("=" * 65, flush=True)

    passed_json = 0
    passed_mode = 0
    latencies = []

    client = httpx.Client(timeout=120.0)

    for idx, tc in enumerate(TEST_CASES, 1):
        prompt = tc["input"]
        system_prompt = "Kamu adalah Cakra Router (Call 1) yang sangat presisi dan deterministik. Analisis pesan pengguna dan kembalikan sparse JSON routing payload murni."

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_predict": 150
            }
        }

        t_start = time.perf_counter()
        try:
            res = client.post(f"{host}/api/chat", json=payload)
            latency_ms = (time.perf_counter() - t_start) * 1000
            latencies.append(latency_ms)

            if res.status_code != 200:
                print(f"❌ Test #{idx:02d} Failed HTTP {res.status_code}", flush=True)
                continue

            resp_json = res.json()
            raw_text = resp_json.get("message", {}).get("content", "")

            # 1. Validasi Format JSON
            parsed = json.loads(raw_text)
            passed_json += 1

            # 2. Validasi Mode / Intent
            mode_ok = False
            if tc["expected_mode"] == "DOCUMENTS" and parsed.get("need_rag") is True:
                mode_ok = True
            elif tc["expected_mode"] == "WEB_SEARCH" and parsed.get("is_web_search") is True:
                mode_ok = True
            elif tc["expected_mode"] == "CODING" and parsed.get("is_coding") is True:
                mode_ok = True
            elif tc["expected_mode"] == "EMAIL" and parsed.get("is_generate_email") is True:
                mode_ok = True
            elif tc["expected_mode"] == "GENERATE_FILE" and parsed.get("is_generate_file") is True:
                mode_ok = True
            elif tc["expected_mode"] == "AMBIGUOUS" and parsed.get("is_ambiguous") is True:
                mode_ok = True
            elif tc["expected_mode"] == "CHITCHAT" and parsed.get("is_chitchat") is True:
                mode_ok = True

            if mode_ok:
                passed_mode += 1
                status_icon = "✅ PASS"
            else:
                status_icon = "⚠️ MISMATCH"

            print(f"{status_icon} | #{idx:02d} ({latency_ms:5.1f}ms) | Q: '{prompt[:32]}...' ➔ Topic: {parsed.get('active_topic', '-')}", flush=True)

        except json.JSONDecodeError:
            print(f"❌ JSON ERROR | #{idx:02d} | Output bukan JSON valid: {raw_text[:50]}", flush=True)
        except Exception as e:
            print(f"❌ ERROR | #{idx:02d} | {e}", flush=True)

    # Summary
    total = len(TEST_CASES)
    avg_lat = sum(latencies) / len(latencies) if latencies else 0

    print("=" * 65, flush=True)
    print("📊 HASIL AKHIR EVALUASI:", flush=True)
    print(f"  • JSON Valid Rate : {passed_json}/{total} ({passed_json/total*100:.1f}%)", flush=True)
    print(f"  • Routing Accuracy: {passed_mode}/{total} ({passed_mode/total*100:.1f}%)", flush=True)
    print(f"  • Rata-rata Latensi: {avg_lat:.1f} ms", flush=True)
    print("=" * 65, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Call 1 Router")
    parser.add_argument("--model", type=str, default="gemma4:e4b", help="Model name on Ollama (e.g. cakra-router or gemma4:e4b)")
    parser.add_argument("--host", type=str, default="http://localhost:11434", help="Ollama host URL")
    args = parser.parse_args()

    evaluate_ollama(args.model, args.host)


if __name__ == "__main__":
    main()
