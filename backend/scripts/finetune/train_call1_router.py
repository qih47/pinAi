#!/usr/bin/env python3
"""
CAKRA AI — Call 1 Router QLoRA / SFT Training Pipeline
======================================================
Melatih model router deterministik `cakra-router` menggunakan QLoRA (4-bit).
Kompatibel dengan Unsloth & Hugging Face TRL SFTTrainer.

Usage:
    python backend/scripts/finetune/train_call1_router.py \
        --model_name "unsloth/gemma-2-9b-it-bnb-4bit" \
        --dataset "data/finetune/call1_train_3000.jsonl" \
        --output_dir "models/adapters/cakra-router-lora" \
        --epochs 3 \
        --batch_size 4
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
        messages = []
        for c in convs:
            role = c.get("from")
            content = c.get("value")
            if role == "human":
                messages.append({"role": "user", "content": content})
            elif role == "gpt":
                messages.append({"role": "assistant", "content": content})
            elif role == "system":
                messages.append({"role": "system", "content": content})

        # Apply chat template
        try:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        except Exception:
            # Fallback format jika chat template default tokenizer bermasalah
            text = ""
            for m in messages:
                text += f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n"

        formatted_texts.append({"text": text})

    return Dataset.from_list(formatted_texts)


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def train(args):
    print("=" * 60)
    print("🚀 MEMULAI PROSES FINE-TUNING CAKRA ROUTER (CALL 1)")
    print("=" * 60)
    print(f"🖥️  GPU Tersedia   : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU (Not Recommended)'}")
    print(f"📦 Base Model     : {args.model_name}")
    print(f"📄 Dataset Path   : {args.dataset}")
    print(f"🎯 Output Adapter : {args.output_dir}")
    print(f"🔄 Epochs         : {args.epochs}")
    print(f"⚡ Batch Size     : {args.batch_size} (Grad Accum: {args.grad_accum})")
    print("=" * 60)

    # 1. Coba Menggunakan Unsloth (Jalur Paling Cepat & Hemat VRAM)
    use_unsloth = False
    try:
        from unsloth import FastLanguageModel
        use_unsloth = True
        print("⚡ Menggunakan Unsloth FastLanguageModel Engine (2x Faster Training)")
        
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=args.model_name,
            max_seq_length=args.max_seq_length,
            dtype=None,  # Auto detect float16 / bfloat16
            load_in_4bit=True,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=args.lora_r,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_alpha=args.lora_alpha,
            lora_dropout=0,  # Unsloth supports 0 for maximum speed
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=3407,
        )

    except ImportError:
        print("ℹ️ Unsloth tidak terpasang. Menggunakan Hugging Face Transformers + PEFT standar...")
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            args.model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        model = prepare_model_for_kbit_training(model)

        peft_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, peft_config)

    # 2. Format & Tokenize Dataset
    dataset = load_and_format_dataset(args.dataset, tokenizer)

    # 3. Setup Trainer (TRL SFTTrainer)
    from trl import SFTTrainer
    from transformers import TrainingArguments

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=10,
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
        save_strategy="epoch",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        dataset_num_proc=2,
        packing=False,
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

    # 6. Petunjuk Export GGUF untuk Ollama
    print("\n" + "=" * 60)
    print("📋 LANGKAH SELANJUTNYA: EXPORT KE OLLAMA (GGUF)")
    print("=" * 60)
    print("Jalankan perintah berikut untuk mengonversi adapter ke GGUF:")
    if use_unsloth:
        print(f"  model.save_pretrained_gguf('{args.output_dir}_gguf', tokenizer, quantization_method='q8_0')")
    else:
        print(f"  python llama.cpp/convert_hf_to_gguf.py {args.output_dir} --outtype q8_0")
    print(f"  ollama create cakra-router -f Modelfile.cakra-router")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Cakra Router via QLoRA")
    parser.add_argument("--model_name", type=str, default="unsloth/gemma-2-9b-it-bnb-4bit", help="Hugging Face / Unsloth Base Model")
    parser.add_argument("--dataset", type=str, default="data/finetune/call1_train_3000.jsonl", help="Training JSONL dataset")
    parser.add_argument("--output_dir", type=str, default="models/adapters/cakra-router-lora", help="Output directory for LoRA adapter")
    parser.add_argument("--epochs", type=int, default=3, help="Training Epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch Size per device")
    parser.add_argument("--grad_accum", type=int, default=4, help="Gradient Accumulation Steps")
    parser.add_argument("--learning_rate", type=float, default=2e-4, help="Learning Rate")
    parser.add_argument("--max_seq_length", type=int, default=2048, help="Max Token Sequence Length")
    parser.add_argument("--lora_r", type=int, default=16, help="LoRA Rank r")
    parser.add_argument("--lora_alpha", type=int, default=32, help="LoRA Alpha")
    args = parser.parse_args()

    train(args)


if __name__ == "__main__":
    main()
