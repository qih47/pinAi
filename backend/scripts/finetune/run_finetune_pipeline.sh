#!/usr/bin/env bash
# ==============================================================================
# CAKRA AI — Master Fine-Tuning Pipeline Runner
# ==============================================================================
# Skrip automasi satu-klik untuk generate dataset, training QLoRA, dan export GGUF.
#
# Usage:
#   ./backend/scripts/finetune/run_finetune_pipeline.sh all
#   ./backend/scripts/finetune/run_finetune_pipeline.sh call1
#   ./backend/scripts/finetune/run_finetune_pipeline.sh call2
# ==============================================================================

set -e

TARGET=${1:-"all"}

echo "================================================================="
echo "🚀 CAKRA AI ENTERPRISE FINE-TUNING PIPELINE"
echo "Target: $TARGET"
echo "================================================================="

if [ "$TARGET" == "all" ] || [ "$TARGET" == "call1" ]; then
    echo ""
    echo "▶️ [STEP 1/3] Menghasilkan 3.000 Dataset Call 1 Router..."
    python3 backend/scripts/finetune/generate_call1_dataset.py \
        --output data/finetune/call1_train_3000.jsonl \
        --samples 3000

    echo ""
    echo "▶️ [STEP 2/3] Memulai Training QLoRA cakra-router..."
    python3 backend/scripts/finetune/train_call1_router.py \
        --dataset data/finetune/call1_train_3000.jsonl \
        --output_dir models/adapters/cakra-router-lora \
        --epochs 3
fi

if [ "$TARGET" == "all" ] || [ "$TARGET" == "call2" ]; then
    echo ""
    echo "▶️ [STEP 1/3] Menghasilkan 2.000 Dataset CoT Call 2 Core..."
    python3 backend/scripts/finetune/generate_call2_dataset.py \
        --output data/finetune/call2_train_2000.jsonl \
        --samples 2000

    echo ""
    echo "▶️ [STEP 2/3] Memulai Training QLoRA cakra-core..."
    python3 backend/scripts/finetune/train_call2_core.py \
        --dataset data/finetune/call2_train_2000.jsonl \
        --output_dir models/adapters/cakra-core-lora \
        --epochs 3
fi

echo ""
echo "================================================================="
echo "✅ PIPELINE FINE-TUNING SELESAI DENGAN SUKSES!"
echo "================================================================="
