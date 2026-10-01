#!/usr/bin/env python3
"""
CAKRA AI — Dispatcher Router QLoRA / SFT Training Pipeline
======================================================
Melatih model router deterministik `cakra-router` menggunakan QLoRA (4-bit)
pada arsitektur Gemma 4 (31B).
Kompatibel dengan TRL SFTTrainer, PEFT, dan Hugging Face Transformers 5.x.

Usage:
    /home/qisthi/vllm_env/bin/python backend/scripts/finetune/train_dispatcher_router.py \
        --model_name "unsloth/gemma-4-31B-it-unsloth-bnb-4bit" \
        --tokenizer_name "/home/qisthi/models/gemma-4-31B-it-AWQ" \
        --dataset "data/finetune/nightly_dispatcher_router.jsonl" \
        --output_dir "models/adapters/cakra-router-lora" \
        --epochs 1 \
        --batch_size 2 \
        --grad_accum 8
"""

import os
import sys
import json
import argparse
import torch
from datasets import Dataset

# ═══════════════════════════════════════════════════════════════════════════════
# DATASET LOADER & FORMATTER
# ═══════════════════════════════════════════════════════════════════════════════

def load_and_format_dataset(jsonl_path: str, tokenizer) -> Dataset:
    """Membaca file JSONL ShareGPT dan memformatnya ke Chat Template Tokenizer."""
    if not os.path.exists(jsonl_path):
        raise FileNotFoundError(f"File dataset tidak ditemukan: {jsonl_path}")

    raw_items = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw_items.append(json.loads(line))

    print(f"📦 Memuat {len(raw_items)} data latih dari: {jsonl_path}")

    formatted_texts = []
    for item in raw_items:
        convs = item.get("conversations", [])
        text = "<bos>"
        for c in convs:
            role = c.get("from")
            content = c.get("value", "")
            if role == "human":
                role_tag = "user"
            elif role == "gpt":
                role_tag = "model"
            else:
                role_tag = "system"
            text += f"<|turn>{role_tag}\n{content}<turn|>\n"

        formatted_texts.append({"text": text})

    return Dataset.from_list(formatted_texts)


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def train(args):
    print("=" * 60)
    print("🚀 MEMULAI PROSES FINE-TUNING CAKRA ROUTER (CALL 1) - GEMMA 4 31B")
    print("=" * 60)
    print(f"🖥️  GPU Tersedia   : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU (Not Recommended)'}")
    print(f"📦 Base Model     : {args.model_name}")
    print(f"🔤 Tokenizer      : {args.tokenizer_name}")
    print(f"📄 Dataset Path   : {args.dataset}")
    print(f"🎯 Output Adapter : {args.output_dir}")
    print(f"🔄 Epochs         : {args.epochs}")
    print(f"⚡ Batch Size     : {args.batch_size} (Grad Accum: {args.grad_accum})")
    print(f"📐 Effective Batch: {args.batch_size * args.grad_accum}")
    print("=" * 60)

    # 1. Setup Tokenizer & Model
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    print("⏳ Memuat tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"⏳ Memuat Base Model BNB 4-bit ({args.model_name})...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )
    model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable()

    print(f"🔧 Mengonfigurasi LoRA Adapter (Rank={args.lora_r}, Alpha={args.lora_alpha})...")
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)",
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 2. Format & Tokenize Dataset
    dataset = load_and_format_dataset(args.dataset, tokenizer)

    # 3. Setup Trainer (TRL SFTTrainer)
    from trl import SFTTrainer, SFTConfig

    training_args = SFTConfig(
        output_dir=args.output_dir,
        dataset_text_field="text",
        max_length=args.max_seq_length,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=20,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=3407,
        report_to="none",
        save_strategy="steps",
        save_steps=500,
        save_total_limit=2,
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset,
        args=training_args,
    )

    # 4. Eksekusi Training
    print("\n🔥 Memulai training step...")
    trainer_stats = trainer.train()

    print("\n✅ Training selesai dengan sukses!")
    print(f"⏱️  Total Waktu Training : {trainer_stats.metrics.get('train_runtime', 0):.2f} detik")
    print(f"📉 Final Loss          : {trainer_stats.metrics.get('train_loss', 0):.4f}")

    # 5. Simpan LoRA Adapter
    os.makedirs(args.output_dir, exist_ok=True)
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"💾 LoRA Adapter berhasil disimpan ke: {args.output_dir}")

    # 6. Petunjuk Deployment ke vLLM (Native Multi-LoRA)
    print("\n" + "=" * 60)
    print("📋 LANGKAH DEPLOYMENT: vLLM NATIVE MULTI-LORA")
    print("=" * 60)
    print(f"  vLLM membaca adapter ini secara native langsung dari folder:")
    print(f"  --> {os.path.abspath(args.output_dir)}")
    print("\n  Tambahkan argumen berikut pada run_vllm_service.sh:")
    print(f"    --enable-lora --lora-modules cakra-router={os.path.abspath(args.output_dir)}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Cakra Router via QLoRA for Gemma 4 31B")
    parser.add_argument("--model_name", type=str, default="unsloth/gemma-4-31B-it-unsloth-bnb-4bit", help="Hugging Face BNB 4-bit Base Model")
    parser.add_argument("--tokenizer_name", type=str, default="/home/qisthi/models/gemma-4-31B-it-AWQ", help="Path to Tokenizer")
    parser.add_argument("--dataset", type=str, default="data/finetune/nightly_dispatcher_router.jsonl", help="Training JSONL dataset")
    parser.add_argument("--output_dir", type=str, default="models/adapters/cakra-router-lora", help="Output directory for LoRA adapter")
    parser.add_argument("--epochs", type=int, default=1, help="Training Epochs")
    parser.add_argument("--batch_size", type=int, default=24, help="Batch Size per device")
    parser.add_argument("--grad_accum", type=int, default=1, help="Gradient Accumulation Steps")
    parser.add_argument("--learning_rate", type=float, default=2e-4, help="Learning Rate")
    parser.add_argument("--max_seq_length", type=int, default=1024, help="Max Token Sequence Length")
    parser.add_argument("--lora_r", type=int, default=8, help="LoRA Rank r")
    parser.add_argument("--lora_alpha", type=int, default=16, help="LoRA Alpha")
    args = parser.parse_args()

    train(args)


if __name__ == "__main__":
    main()
