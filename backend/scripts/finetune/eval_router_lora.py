#!/usr/bin/env python3
"""
CAKRA AI — Automated Benchmark & Evaluation Suite for Call 1 Router
==================================================================
Menguji akurasi routing JSON hasil fine-tuning LoRA (cakra-router) atau base model
terhadap puluhan skenario intent nyata (RAG, Diffing, HRIS, Zimbra, Deck, Chitchat).

Usage:
    /home/qisthi/rag_env/bin/python backend/scripts/finetune/eval_router_lora.py \
        --model "cakra-router" \
        --url "http://localhost:8005/v1"
"""

import sys
import os
import json
import time
import argparse
import asyncio
import httpx

# Test Suite: Skenario input pengguna dan ekspektasi routing intent
TEST_CASES = [
    # ── 1. RAG & Regulasi PT Pindad ──
    {
        "query": "Berapa plafon klaim kacamata untuk karyawan golongan 3 di PT Pindad menurut perdir terbaru?",
        "expected_intent": "rag",
        "category": "Regulasi HR / Plafon",
    },
    {
        "query": "Jelaskan spesifikasi teknis Ranpur Anoa 6x6 APC buatan PT Pindad.",
        "expected_intent": "rag",
        "category": "Alutsista & Manufaktur",
    },
    {
        "query": "Apa saja syarat pemberian insentif tahunan berdasarkan SK Direksi Pindad?",
        "expected_intent": "rag",
        "category": "Regulasi Internal",
    },
    {
        "query": "Bagaimana prosedur permohonan dinas luar kota bagi staf logistik?",
        "expected_intent": "rag",
        "category": "SOP Operasional",
    },
    {
        "query": "Berapa kapasitas magasin dan jarak tembak efektif senapan SS2-V4?",
        "expected_intent": "rag",
        "category": "Spesifikasi Senjata",
    },

    # ── 2. Document Diffing / Perbandingan Regulasi ──
    {
        "query": "Tolong bandingkan draft revisi Perdir Nomor 12 Tahun 2023 dengan draft 2024 terlampir.",
        "expected_intent": "diff",
        "category": "Document Diffing",
    },
    {
        "query": "Apa saja pasal yang mengalami perubahan antara SK Direksi lama dengan yang baru ini?",
        "expected_intent": "diff",
        "category": "Document Diffing",
    },
    {
        "query": "Bandingkan klausul jaminan asuransi pada kedua kontrak vendor berikut.",
        "expected_intent": "diff",
        "category": "Document Diffing",
    },

    # ── 3. HRIS & Kalkulasi Payroll ──
    {
        "query": "Hitung upah lembur saya jika gaji pokok 6.500.000 dan lembur 4 jam di hari libur resmi.",
        "expected_intent": "calculation",
        "category": "Payroll Calculation",
    },
    {
        "query": "Simulasikan perhitungan pesangon masa kerja 7 tahun 8 bulan sesuai UU Ketenagakerjaan.",
        "expected_intent": "calculation",
        "category": "Kalkulasi Pesangon",
    },
    {
        "query": "Berapa sisa kuota cuti tahunan saya untuk tahun berjalan?",
        "expected_intent": "hris",
        "category": "HRIS Data Query",
    },

    # ── 4. Zimbra Corporate Mail ──
    {
        "query": "Cek apakah ada email masuk baru dari Kadiv Keuangan di inbox Zimbra saya hari ini.",
        "expected_intent": "zimbra",
        "category": "Zimbra Inbox",
    },
    {
        "query": "Tolong buatkan draf balasan email ke vendor PT Krakatau Steel perihal jadwal inspeksi.",
        "expected_intent": "zimbra",
        "category": "Zimbra Compose",
    },

    # ── 5. Nextcloud Deck / Kanban ──
    {
        "query": "Tampilkan daftar kartu tugas yang masih pending di board Sprint Renval.",
        "expected_intent": "nextcloud",
        "category": "Kanban Deck",
    },
    {
        "query": "Pindahkan kartu 'Audit ISO 9001' ke kolom In Review di Nextcloud Deck.",
        "expected_intent": "nextcloud",
        "category": "Kanban Action",
    },

    # ── 6. Web Search / Real-time External Intelligence ──
    {
        "query": "Berapa kurs dollar AS terhadap rupiah hari ini menurut Bank Indonesia?",
        "expected_intent": "web",
        "category": "Web Search / Realtime",
    },
    {
        "query": "Apa berita terbaru tentang kunjungan Menhan ke pabrik munisi Pindad di Turen Malang pekan ini?",
        "expected_intent": "web",
        "category": "Berita Eksternal",
    },
    {
        "query": "Siapa menteri pertahanan yang dilantik pada kabinet terbaru?",
        "expected_intent": "web",
        "category": "Web Knowledge",
    },

    # ── 7. Coding & Technical Implementation ──
    {
        "query": "Buatkan script Python FastAPI untuk membaca tabel PostgreSQL dengan async asyncpg.",
        "expected_intent": "coding",
        "category": "Coding / Script",
    },
    {
        "query": "Tuliskan query SQL untuk mencari pegawai dengan total jam lembur tertinggi di bulan September.",
        "expected_intent": "coding",
        "category": "SQL Query",
    },

    # ── 8. Casual Chitchat & Persona Greeting ──
    {
        "query": "Halo, selamat pagi Cakra! Apa kabar?",
        "expected_intent": "chitchat",
        "category": "Chitchat / Greeting",
    },
    {
        "query": "Siapa yang menciptakanmu dan apa fungsi utamamu di Pindad?",
        "expected_intent": "chitchat",
        "category": "Identity Query",
    },
    {
        "query": "Terima kasih banyak atas bantuannya, sangat informatif!",
        "expected_intent": "chitchat",
        "category": "Gratitude Closing",
    },
]


SYSTEM_ROUTER_PROMPT = """Anda adalah Call 1 Dispatcher Router AI untuk sistem CAKRA AI di PT Pindad.
Tugas Anda adalah membaca pesan pengguna dan menghasilkan output routing JSON terstruktur dan akurat.
JSON Format:
{
  "mode": "rag" | "diff" | "calculation" | "hris" | "zimbra" | "nextcloud" | "web" | "coding" | "chitchat",
  "confidence": 0.0 - 1.0,
  "reasoning": "penjelasan singkat"
}
HANYA kembalikan JSON tanpa teks markdown pembuka atau penutup."""


async def evaluate_router(base_url: str, model_name: str, verbose: bool = False):
    print("=" * 70)
    print(f"🧪 CAKRA AI ROUTER BENCHMARK & ACCURACY SUITE")
    print("=" * 70)
    print(f"🎯 Target Model  : {model_name}")
    print(f"🌐 vLLM Base URL : {base_url}")
    print(f"📊 Total Uji Coba: {len(TEST_CASES)} skenario beragam")
    print("=" * 70)

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    passed = 0
    total = len(TEST_CASES)
    latencies = []
    failures = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        for idx, tc in enumerate(TEST_CASES, 1):
            query = tc["query"]
            expected = tc["expected_intent"]
            category = tc["category"]

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": SYSTEM_ROUTER_PROMPT},
                    {"role": "user", "content": query}
                ],
                "temperature": 0.0,
                "max_tokens": 150,
                "response_format": {"type": "json_object"}
            }

            t0 = time.time()
            try:
                resp = await client.post(endpoint, json=payload)
                elapsed_ms = (time.time() - t0) * 1000
                latencies.append(elapsed_ms)

                if resp.status_code != 200:
                    failures.append((idx, category, query, expected, f"HTTP {resp.status_code}", elapsed_ms))
                    print(f"[{idx:02d}/{total}] ❌ {category:<25} | Error HTTP {resp.status_code}")
                    continue

                res_json = resp.json()
                content_str = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = json.loads(content_str)
                detected_mode = parsed.get("mode", "").lower()

                # Flexible matching (e.g. calculation matches hris/calculation, rag matches documents/rag)
                is_match = (
                    detected_mode == expected or
                    (expected == "rag" and detected_mode in ["rag", "documents", "document_search"]) or
                    (expected == "diff" and detected_mode in ["diff", "document_diff", "diffing"]) or
                    (expected == "calculation" and detected_mode in ["calculation", "payroll", "hris_calc"]) or
                    (expected == "hris" and detected_mode in ["hris", "calculation", "employee_data"]) or
                    (expected == "chitchat" and detected_mode in ["chitchat", "greeting", "casual"]) or
                    (expected == "coding" and detected_mode in ["coding", "code_expert", "technical"]) or
                    (expected == "web" and detected_mode in ["web", "web_search", "search"])
                )

                if is_match:
                    passed += 1
                    status_icon = "✅"
                else:
                    status_icon = "❌"
                    failures.append((idx, category, query, expected, detected_mode, elapsed_ms))

                if verbose or not is_match:
                    print(f"[{idx:02d}/{total}] {status_icon} {category:<25} | Exp: {expected:<12} Got: {detected_mode:<12} ({elapsed_ms:.1f}ms)")
                else:
                    print(f"[{idx:02d}/{total}] {status_icon} {category:<25} | Match: {detected_mode:<12} ({elapsed_ms:.1f}ms)")

            except Exception as e:
                elapsed_ms = (time.time() - t0) * 1000
                failures.append((idx, category, query, expected, f"Exception: {e}", elapsed_ms))
                print(f"[{idx:02d}/{total}] ❌ {category:<25} | Exception: {e}")

    # ── Scorecard Summary ──
    acc = (passed / total) * 100
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    print("\n" + "=" * 70)
    print("📈 HASIL AKURASI EVALUASI ROUTER")
    print("=" * 70)
    print(f"  • Total Uji Coba      : {total} kasus")
    print(f"  • Berhasil Cocok (Pass): {passed} ({acc:.1f}%)")
    print(f"  • Salah Routing (Fail) : {len(failures)}")
    print(f"  • Rata-rata Latensi   : {avg_latency:.1f} ms / query")
    print("=" * 70)

    if failures:
        print("\n🔍 DAFTAR KASUS YANG SALAH / MISCLASSIFIED:")
        for idx, cat, q, exp, got, ms in failures:
            print(f"  - [#{idx}] ({cat})")
            print(f"    Query   : \"{q[:75]}...\"")
            print(f"    Expected: {exp} | Actual: {got} ({ms:.1f}ms)")
        print("=" * 70)

    return acc, avg_latency


def main():
    parser = argparse.ArgumentParser(description="Evaluate Cakra Router Accuracy against Benchmark Suite")
    parser.add_argument("--model", type=str, default="cakra-router", help="Model name on vLLM (e.g. cakra-router or /home/qisthi/models/gemma-4-31B-it-AWQ)")
    parser.add_argument("--url", type=str, default="http://localhost:8005/v1", help="vLLM OpenAI-compatible base URL")
    parser.add_argument("--verbose", action="store_true", help="Print detailed diagnostic for all queries")
    args = parser.parse_args()

    asyncio.run(evaluate_router(base_url=args.url, model_name=args.model, verbose=args.verbose))


if __name__ == "__main__":
    main()
