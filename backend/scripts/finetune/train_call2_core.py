#!/usr/bin/env python3
"""
CAKRA AI — Call 2 Core Knowledge & CoT Reasoning QLoRA Pipeline
===============================================================
Melatih model utama `cakra-core` (31B/32B/14B) dengan QLoRA 4-bit,
penalaran Chain-of-Thought (<think>), dan domain PT Pindad.

Usage:
    python backend/scripts/finetune/train_call2_core.py \
        --model_name "unsloth/gemma-2-27b-it-bnb-4bit" \
        --dataset "data/finetune/call2_train_2000.jsonl" \
        --output_dir "models/adapters/cakra-core-lora" \
        --epochs 3
"""

import os
import sys
import json
import argparse
import torch
from datasets import Dataset

def load_and_format_dataset(jsonl_path: str, tokenizer) -> Dataset:
    if not os.path.exists(jsonl_path):
        raise FileNotFoundError(f"File dataset tidak ditemukan: {jsonl_path}")

    raw_items = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw_items.append(json.loads(line))

    print(f"📦 Memuat {len(raw_items)} data CoT latih dari: {jsonl_path}")

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

        try:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        except Exception:
            text = ""
            for m in messages:
                text += f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n"

        formatted_texts.append({"text": text})

    return Dataset.from_list(formatted_texts)


def train(args):
    print("=" * 65)
    print("🚀 MEMULAI PROSES FINE-TUNING CAKRA CORE (CALL 2)")
    print("=" * 65)
    print(f"🖥️  GPU Tersedia   : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    print(f"📦 Base Model     : {args.model_name}")
    print(f"📄 Dataset Path   : {args.dataset}")
    print(f"🎯 Output Adapter : {args.output_dir}")
    print(f"🔄 Epochs         : {args.epochs}")
    print("=" * 65)

    use_unsloth = False
    try:
        from unsloth import FastLanguageModel
        use_unsloth = True
        print("⚡ Menggunakan Unsloth FastLanguageModel Engine")
        
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=args.model_name,
            max_seq_length=args.max_seq_length,
            load_in_4bit=True,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=args.lora_r,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_alpha=args.lora_alpha,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
        )

    except ImportError:
        print("ℹ️ Menggunakan Hugging Face Transformers + PEFT standar...")
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

    dataset = load_and_format_dataset(args.dataset, tokenizer)

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

    print("\n🔥 Memulai training Call 2 Core...")
    trainer_stats = trainer.train()

    print("\n✅ Training Call 2 Selesai!")
    os.makedirs(args.output_dir, exist_ok=True)
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"💾 Adapter tersimpan ke: {args.output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Cakra Core (Call 2)")
    parser.add_argument("--model_name", type=str, default="unsloth/gemma-2-27b-it-bnb-4bit", help="Base Model")
    parser.add_argument("--dataset", type=str, default="data/finetune/call2_train_2000.jsonl", help="Dataset")
    parser.add_argument("--output_dir", type=str, default="models/adapters/cakra-core-lora", help="Output dir")
    parser.add_argument("--epochs", type=int, default=3, help="Epochs")
    parser.add_argument("--batch_size", type=int, default=2, help="Batch size")
    parser.add_argument("--grad_accum", type=int, default=8, help="Grad accum")
    parser.add_argument("--learning_rate", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--max_seq_length", type=int, default=4096, help="Max Seq Length")
    parser.add_argument("--lora_r", type=int, default=32, help="LoRA Rank")
    parser.add_argument("--lora_alpha", type=int, default=64, help="LoRA Alpha")
    args = parser.parse_args()

    train(args)


if __name__ == "__main__":
    main()
