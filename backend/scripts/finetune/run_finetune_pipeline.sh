#!/usr/bin/env bash
# ==============================================================================
# CAKRA AI — Master Fine-Tuning Pipeline Runner (Unlimited by Training)
# ==============================================================================
# Skrip automasi untuk training QLoRA cakra-router (Dispatcher e4b) dan cakra-core (Responder).
# Menggunakan dataset akumulatif hasil training regulasi tanpa batas sampel.
#
# Usage:
#   ./backend/scripts/finetune/run_finetune_pipeline.sh all
#   ./backend/scripts/finetune/run_finetune_pipeline.sh dispatcher
#   ./backend/scripts/finetune/run_finetune_pipeline.sh responder
# ==============================================================================

set -e

TARGET=${1:-"all"}

echo "================================================================="
echo "🚀 CAKRA AI ENTERPRISE FINE-TUNING PIPELINE (UNLIMITED BY TRAINING)"
echo "Target: $TARGET"
echo "================================================================="

ROUTER_DATASET="${ROUTER_DATASET:-data/finetune/merged_dispatcher_router.jsonl}"
if [ ! -f "$ROUTER_DATASET" ]; then
    ROUTER_DATASET="data/finetune/nightly_dispatcher_router.jsonl"
fi

CORE_DATASET="${CORE_DATASET:-data/finetune/merged_cakra_core.jsonl}"
if [ ! -f "$CORE_DATASET" ]; then
    CORE_DATASET="data/finetune/nightly_cakra_core.jsonl"
fi

if [ "$TARGET" == "all" ] || [ "$TARGET" == "dispatcher" ] || [ "$TARGET" == "router" ]; then
    echo ""
    echo "▶️ [STEP 1/2] Menyiapkan Dataset Dispatcher Router (Gemma 4 31B)..."
    if [ ! -s "$ROUTER_DATASET" ]; then
        echo "   Dataset $ROUTER_DATASET kosong atau belum ada, mengekstrak dari ragdb..."
        ./rag_env/bin/python backend/scripts/finetune/generate_dispatcher_dataset.py \
            --output "$ROUTER_DATASET" \
            --from-db
    fi
    TOTAL_ROUTER=$(wc -l < "$ROUTER_DATASET" 2>/dev/null || echo 0)
    echo "   Total Baris Data Latih Router (Gemma 4 31B): $TOTAL_ROUTER baris"

    echo ""
    echo "▶️ [STEP 2/2] Memulai Training QLoRA cakra-router (Gemma 4 31B)..."
    /home/qisthi/vllm_env/bin/python backend/scripts/finetune/train_dispatcher_router.py \
        --dataset "$ROUTER_DATASET" \
        --output_dir models/adapters/cakra-router-lora \
        --epochs "${ROUTER_EPOCHS:-1}" \
        --batch_size "${ROUTER_BATCH_SIZE:-24}" \
        --grad_accum 1
fi

if [ "$TARGET" == "all" ] || [ "$TARGET" == "responder" ] || [ "$TARGET" == "core" ]; then
    echo ""
    echo "▶️ [STEP 1/2] Menyiapkan Dataset CoT Responder Core..."
    if [ ! -s "$CORE_DATASET" ]; then
        echo "   Dataset $CORE_DATASET kosong atau belum ada, mengekstrak dari ragdb..."
        ./rag_env/bin/python backend/scripts/finetune/generate_responder_dataset.py \
            --output "$CORE_DATASET" \
            --from-db
    fi
    TOTAL_CORE=$(wc -l < "$CORE_DATASET" 2>/dev/null || echo 0)
    echo "   Total Baris Data Latih Core 31B: $TOTAL_CORE baris"

    echo ""
    echo "▶️ [STEP 2/2] Memulai Training QLoRA cakra-core..."
    /home/qisthi/vllm_env/bin/python backend/scripts/finetune/train_responder_core.py \
        --dataset "$CORE_DATASET" \
        --output_dir models/adapters/cakra-core-lora \
        --epochs "${CORE_EPOCHS:-1}" \
        --batch_size "${CORE_BATCH_SIZE:-4}" \
        --grad_accum 4
fi

echo ""
echo "================================================================="
echo "✅ PIPELINE FINE-TUNING SELESAI DENGAN SUKSES!"
echo "================================================================="

