#!/bin/bash
# ==============================================================================
# CAKRA AI - vLLM Inference Service Runner
# Runs Gemma-4-31B-AWQ on port 8080 with 16k context window and AWQ quantization
# ==============================================================================

# Load environment variables if .env exists
if [ -f "/home/qisthi/pinAi/.env" ]; then
    eval $(grep -E '^MODEL_BASE=' /home/qisthi/pinAi/.env) 2>/dev/null || true
fi

VLLM_PYTHON="/home/qisthi/vllm_env/bin/python"
MODEL_PATH="${MODEL_BASE:-/home/qisthi/models/gemma-4-31B-it-AWQ}"
PORT=8005
HOST="127.0.0.1"

if [ ! -f "$VLLM_PYTHON" ]; then
    echo "❌ [ERROR] vLLM virtual environment not found at $VLLM_PYTHON"
    exit 1
fi

if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ [ERROR] Model directory not found at $MODEL_PATH"
    exit 1
fi

export PATH="/home/qisthi/vllm_env/bin:$PATH"
export LD_LIBRARY_PATH=$(find /home/qisthi/vllm_env/lib/python3.10/site-packages/nvidia -type d -name "lib" 2>/dev/null | tr '\n' ':'):$LD_LIBRARY_PATH
# Marlin Linear Kernel enabled for high-performance AWQ GEMM (31+ tok/s, TTFT ~60ms)
export VLLM_USE_FLASHINFER_SAMPLER=0

# ==============================================================================
# Modular Multi-LoRA Adapter Discovery (Scheme B)
# ==============================================================================
LORA_ARGS=()
ROUTER_LORA_PATH="/home/qisthi/pinAi/models/adapters/cakra-router-lora"
CORE_LORA_PATH="/home/qisthi/pinAi/models/adapters/cakra-core-lora"

LORA_MODULES=()
if [ -f "$ROUTER_LORA_PATH/adapter_config.json" ]; then
    echo "🎯 [vLLM LoRA] Found Call 1 Router adapter: $ROUTER_LORA_PATH"
    LORA_MODULES+=("cakra-router=$ROUTER_LORA_PATH")
else
    # Auto-detect latest checkpoint if training is still in progress (e.g. checkpoint-500)
    LATEST_CKPT=$(ls -td "$ROUTER_LORA_PATH"/checkpoint-* 2>/dev/null | head -n 1)
    if [ -n "$LATEST_CKPT" ] && [ -f "$LATEST_CKPT/adapter_config.json" ]; then
        echo "🎯 [vLLM LoRA] Found intermediate checkpoint adapter: $LATEST_CKPT"
        LORA_MODULES+=("cakra-router=$LATEST_CKPT")
    fi
fi

if [ -f "$CORE_LORA_PATH/adapter_config.json" ]; then
    echo "🎯 [vLLM LoRA] Found Call 2 Core Persona adapter: $CORE_LORA_PATH"
    LORA_MODULES+=("cakra-core=$CORE_LORA_PATH")
fi

if [ ${#LORA_MODULES[@]} -gt 0 ]; then
    LORA_ARGS+=(
        "--enable-lora"
        "--max-lora-rank" "16"
        "--max-loras" "4"
        "--max-cpu-loras" "8"
        "--lora-modules" "${LORA_MODULES[@]}"
    )
    echo "✅ [vLLM LoRA] Multi-LoRA serving active with ${#LORA_MODULES[@]} adapter(s)."
else
    echo "ℹ️  [vLLM LoRA] No LoRA adapters found yet. Serving standard Base AWQ model."
fi

echo "=================================================================="
echo "🚀 Starting CAKRA AI vLLM Engine (Hybrid Call 1 & 2 Modular Engine)"
echo "   Model Path   : $MODEL_PATH"
echo "   Listening on : http://$HOST:$PORT"
echo "   Quantization : AWQ (4-bit GEMM)"
echo "   Context Len  : 32,768 tokens"
echo "   GPU VRAM Util: 0.72 (~34.5 GB on RTX A40 | ~10.8 GB Free Buffer)"
if [ ${#LORA_MODULES[@]} -gt 0 ]; then
    echo "   LoRA Modules : ${LORA_MODULES[*]}"
fi
echo "=================================================================="

exec "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --quantization awq \
    --port "$PORT" \
    --host "$HOST" \
    --gpu-memory-utilization 0.72 \
    --max-model-len 32768 \
    --limit-mm-per-prompt '{"image": 20}' \
    --trust-remote-code \
    --enable-prefix-caching \
    --served-model-name "$MODEL_PATH" "gemma4:31b" \
    "${LORA_ARGS[@]}"

