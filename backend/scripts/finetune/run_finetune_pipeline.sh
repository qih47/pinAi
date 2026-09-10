#!/usr/bin/env bash
# ==============================================================================
# CAKRA AI — Master Fine-Tuning Pipeline Runner (Unlimited by Training)
# ==============================================================================
# Skrip automasi untuk training QLoRA cakra-router (Call 1 e4b) dan cakra-core (Call 2).
# Menggunakan dataset akumulatif hasil training regulasi tanpa batas sampel.
#
# Usage:
#   ./backend/scripts/finetune/run_finetune_pipeline.sh all
#   ./backend/scripts/finetune/run_finetune_pipeline.sh call1
#   ./backend/scripts/finetune/run_finetune_pipeline.sh call2
# ==============================================================================

set -e

TARGET=${1:-"all"}

echo "================================================================="
echo "🚀 CAKRA AI ENTERPRISE FINE-TUNING PIPELINE (UNLIMITED BY TRAINING)"
echo "Target: $TARGET"
echo "================================================================="

ROUTER_DATASET="data/finetune/nightly_call1_router.jsonl"
CORE_DATASET="data/finetune/nightly_cakra_core.jsonl"

if [ "$TARGET" == "all" ] || [ "$TARGET" == "call1" ]; then
    echo ""
    echo "▶️ [STEP 1/2] Menyiapkan Dataset Call 1 Router e4b (Unlimited)..."
    if [ ! -s "$ROUTER_DATASET" ]; then
        echo "   Dataset $ROUTER_DATASET kosong atau belum ada, mengekstrak dari ragdb..."
        ./rag_env/bin/python backend/scripts/finetune/generate_call1_dataset.py \
            --output "$ROUTER_DATASET" \
            --from-db
    fi
    TOTAL_ROUTER=$(wc -l < "$ROUTER_DATASET" 2>/dev/null || echo 0)
    echo "   Total Baris Data Latih Router e4b: $TOTAL_ROUTER baris"

    echo ""
    echo "▶️ [STEP 2/2] Memulai Training QLoRA cakra-router (e4b)..."
    ./rag_env/bin/python backend/scripts/finetune/train_call1_router.py \
        --dataset "$ROUTER_DATASET" \
        --output_dir models/adapters/cakra-router-lora \
        --epochs 3
fi

if [ "$TARGET" == "all" ] || [ "$TARGET" == "call2" ]; then
    echo ""
    echo "▶️ [STEP 1/2] Menyiapkan Dataset CoT Call 2 Core (Unlimited)..."
    if [ ! -s "$CORE_DATASET" ]; then
        echo "   Dataset $CORE_DATASET kosong atau belum ada, mengekstrak dari ragdb..."
        ./rag_env/bin/python backend/scripts/finetune/generate_call2_dataset.py \
            --output "$CORE_DATASET" \
            --from-db
    fi
    TOTAL_CORE=$(wc -l < "$CORE_DATASET" 2>/dev/null || echo 0)
    echo "   Total Baris Data Latih Core 31B: $TOTAL_CORE baris"

    echo ""
    echo "▶️ [STEP 2/2] Memulai Training QLoRA cakra-core..."
    ./rag_env/bin/python backend/scripts/finetune/train_call2_core.py \
        --dataset "$CORE_DATASET" \
        --output_dir models/adapters/cakra-core-lora \
        --epochs 3
fi

echo ""
echo "================================================================="
echo "✅ PIPELINE FINE-TUNING SELESAI DENGAN SUKSES!"
echo "================================================================="

