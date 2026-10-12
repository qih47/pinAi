#!/usr/bin/env python3
"""
CAKRA AI — Master Dataset Blender & Prompt Sanitizer
===================================================
Menggabungkan dataset regulasi eksisting dengan dataset sintetis agentic (Worker 7)
sekaligus menghapus bias kaku "to-the-point" dari data regulasi lama.

Output:
- /home/qisthi/pinAi/data/finetune/merged_cakra_core.jsonl       (50k Regulasi + 25k Agentic = 75k)
- /home/qisthi/pinAi/data/finetune/merged_dispatcher_router.jsonl (40k Regulasi + 25k Agentic = 65k)
"""

import os
import sys
import json
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any

NEW_CORE_SYSTEM_PROMPT = (
    "Kamu adalah CAKRA AI, asisten kecerdasan buatan berdaulat PT PINDAD. "
    "Sebelum menjawab, lakukan penalaran mendalam di dalam tag <think>...</think> "
    "lalu sajikan jawaban yang komprehensif, mengalir secara natural dan dinamis, profesional, serta akurat. "
    "Bersikaplah adaptif: jelaskan secara kaya, kontekstual, dan elaboratif secara default; "
    "sajikan secara ringkas/to-the-point HANYA jika pengguna secara eksplisit memintanya."
)


def sanitize_core_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
    """Mengganti system prompt lama yang memuat 'to-the-point' dengan prompt baru natural."""
    convs = sample.get("conversations", [])
    if convs and convs[0].get("from") == "system":
        old_val = convs[0].get("value", "")
        if "to-the-point" in old_val.lower() or "to the point" in old_val.lower():
            convs[0]["value"] = NEW_CORE_SYSTEM_PROMPT
    return sample


def blend_core(reg_file: Path, agentic_file: Path, out_file: Path, reg_quota: int = 50000, seed: int = 42):
    print(f"\n📦 [BLENDER_CORE] Membaca data regulasi dari {reg_file} (Quota: {reg_quota:,})...")
    reg_samples = []
    sanitized_count = 0

    if reg_file.exists():
        with open(reg_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # Sanitasi prompt
                    convs = data.get("conversations", [])
                    if convs and "to-the-point" in convs[0].get("value", "").lower():
                        data = sanitize_core_sample(data)
                        sanitized_count += 1
                    reg_samples.append(data)
                    if len(reg_samples) >= reg_quota:
                        break
                except Exception:
                    continue

    print(f"   -> Diambil {len(reg_samples):,} sampel regulasi ({sanitized_count:,} disanitasi dari bias to-the-point).")

    print(f"📦 [BLENDER_CORE] Membaca data agentic dari {agentic_file}...")
    agentic_samples = []
    if agentic_file.exists():
        with open(agentic_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    agentic_samples.append(json.loads(line))
                except Exception:
                    continue
    print(f"   -> Diambil {len(agentic_samples):,} sampel agentic.")

    total_pool = reg_samples + agentic_samples
    print(f"🔀 [BLENDER_CORE] Mengacak total {len(total_pool):,} sampel dengan seed {seed}...")
    random.seed(seed)
    random.shuffle(total_pool)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        for s in total_pool:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"✅ [BLENDER_CORE] File final siap latih tersimpan di: {out_file} ({len(total_pool):,} baris)\n")


def blend_router(reg_file: Path, agentic_file: Path, out_file: Path, reg_quota: int = 40000, seed: int = 42):
    print(f"🧭 [BLENDER_ROUTER] Membaca data regulasi router dari {reg_file} (Quota: {reg_quota:,})...")
    reg_samples = []

    if reg_file.exists():
        with open(reg_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    reg_samples.append(json.loads(line))
                    if len(reg_samples) >= reg_quota:
                        break
                except Exception:
                    continue

    print(f"   -> Diambil {len(reg_samples):,} sampel regulasi router.")

    print(f"🧭 [BLENDER_ROUTER] Membaca data master router dari {agentic_file}...")
    agentic_samples = []
    if agentic_file.exists():
        with open(agentic_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    agentic_samples.append(json.loads(line))
                except Exception:
                    continue
    print(f"   -> Diambil {len(agentic_samples):,} sampel master router.")

    total_pool = reg_samples + agentic_samples
    print(f"🔀 [BLENDER_ROUTER] Mengacak total {len(total_pool):,} sampel dengan seed {seed}...")
    random.seed(seed)
    random.shuffle(total_pool)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        for s in total_pool:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"✅ [BLENDER_ROUTER] File final siap latih tersimpan di: {out_file} ({len(total_pool):,} baris)\n")


def main():
    parser = argparse.ArgumentParser(description="CAKRA Master Dataset Blender & Sanitizer")
    parser.add_argument("--reg_core", default="/home/qisthi/pinAi/data/finetune/nightly_cakra_core.jsonl")
    parser.add_argument("--agentic_core", default="/home/qisthi/pinAi/data/finetune/agentic_core_train.jsonl")
    parser.add_argument("--out_core", default="/home/qisthi/pinAi/data/finetune/merged_cakra_core.jsonl")
    parser.add_argument("--reg_router", default="/home/qisthi/pinAi/data/finetune/nightly_dispatcher_router.jsonl")
    parser.add_argument("--agentic_router", default="/home/qisthi/pinAi/data/finetune/agentic_router_train.jsonl")
    parser.add_argument("--out_router", default="/home/qisthi/pinAi/data/finetune/merged_dispatcher_router.jsonl")
    parser.add_argument("--core_quota", type=int, default=50000)
    parser.add_argument("--router_quota", type=int, default=40000)
    args = parser.parse_args()

    blend_core(Path(args.reg_core), Path(args.agentic_core), Path(args.out_core), reg_quota=args.core_quota)
    blend_router(Path(args.reg_router), Path(args.agentic_router), Path(args.out_router), reg_quota=args.router_quota)
    print("🎉 [BLENDER] Semua dataset berhasil di-blend dan disanitasi siap latih!")


if __name__ == "__main__":
    main()
