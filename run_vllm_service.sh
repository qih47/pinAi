#!/bin/bash
# ==============================================================================
# CAKRA AI - vLLM Inference Service Runner
# Runs Gemma-4-31B-AWQ on port 8080 with 16k context window and AWQ quantization
# ==============================================================================

VLLM_PYTHON="/home/qisthi/vllm_env/bin/python"
MODEL_PATH="/home/qisthi/models/gemma-4-31B-it-AWQ"
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
export VLLM_DISABLED_KERNELS="MarlinLinearKernel"
export VLLM_USE_FLASHINFER_SAMPLER=0

echo "=================================================================="
echo "🚀 Starting CAKRA AI vLLM Engine (Hybrid Call 2 Persona)"
echo "   Model Path   : $MODEL_PATH"
echo "   Listening on : http://$HOST:$PORT"
echo "   Quantization : AWQ (4-bit GEMM)"
echo "   Context Len  : 16,384 tokens"
echo "   GPU VRAM Util: 0.65 (~31.9 GB on RTX A40)"
echo "=================================================================="

exec "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --quantization awq \
    --port "$PORT" \
    --host "$HOST" \
    --gpu-memory-utilization 0.65 \
    --max-model-len 16384 \
    --trust-remote-code \
    --served-model-name "$MODEL_PATH"
