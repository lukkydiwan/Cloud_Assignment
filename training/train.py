#!/usr/bin/env python3
"""Training script for sequence-level knowledge distillation into Pythia-70M.
Reads hyperparameters and library versions from training/config.yaml.
Supports full training (first 1,500 records) or SUBSET=N (e.g. SUBSET=50 for quick verification).
Saves training loss for every epoch to training/loss.csv.
Saves model and tokenizer to models/<version>/, computes SHA-256 in models/<version>/model.sha256,
and uploads artefacts to SeaweedFS S3.
"""

import os
import sys
import yaml
import json
import random
import hashlib
import argparse
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForCausalLM
import boto3

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:8333")
S3_BUCKET = os.environ.get("S3_MODELS_BUCKET", "models")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "admin")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "admin123")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name="us-east-1",
    )


class CommandDataset(Dataset):
    def __init__(self, texts, tokenizer, max_length=128):
        self.encodings = []
        for text in texts:
            enc = tokenizer(
                text + tokenizer.eos_token,
                truncation=True,
                max_length=max_length,
                padding="max_length",
                return_tensors="pt"
            )
            input_ids = enc["input_ids"].squeeze(0)
            attention_mask = enc["attention_mask"].squeeze(0)
            # Standard causal LM labels: replace padding tokens with -100
            labels = input_ids.clone()
            labels[attention_mask == 0] = -100
            self.encodings.append({
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": labels
            })

    def __len__(self):
        return len(self.encodings)

    def __getitem__(self, idx):
        return self.encodings[idx]


def compute_dir_sha256(dir_path):
    """Compute sha256 checksum across all files in directory."""
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(dir_path)):
        for fname in sorted(files):
            if fname.endswith(".sha256"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
    return h.hexdigest()


def upload_dir_to_s3(local_dir, s3_prefix):
    try:
        s3 = get_s3_client()
        for root, _, files in os.walk(local_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, local_dir)
                s3_key = f"{s3_prefix}/{rel_path}"
                s3.upload_file(fpath, S3_BUCKET, s3_key)
                print(f"Uploaded s3://{S3_BUCKET}/{s3_key}")
    except Exception as e:
        print(f"Warning: S3 upload failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Pythia-70M on teacher JSON outputs")
    parser.add_argument("--config", default="training/config.yaml", help="Path to config.yaml")
    parser.add_argument("--subset", type=int, default=None, help="Subset size (e.g. 50)")
    parser.add_argument("--version", default="v1", help="Model version tag (v1 or v2)")
    parser.add_argument("--train-file", default="datasets/v1/train.jsonl", help="Cleaned train.jsonl")
    args = parser.parse_args()

    # Support SUBSET from environment variable if make train SUBSET=50 is passed
    env_subset = os.environ.get("SUBSET")
    if env_subset is not None and args.subset is None:
        try:
            args.subset = int(env_subset)
        except ValueError:
            pass

    # Read config.yaml
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    hp = cfg.get("hyperparameters", {})
    seed = hp.get("random_seed", 42)
    lr = float(hp.get("learning_rate", 5e-4))
    batch_size = int(hp.get("batch_size", 8))
    epochs = int(hp.get("num_epochs", 3))
    max_len = int(hp.get("max_seq_length", 128))
    model_name = cfg.get("model", {}).get("name", "EleutherAI/pythia-70m")

    # If training v2, optionally add 1 epoch for version differentiation
    if args.version == "v2":
        epochs = epochs + 1

    # Set fixed seeds (v2 uses a different seed for reproducible variation)
    actual_seed = seed if args.version == "v1" else 123
    torch.manual_seed(actual_seed)
    np.random.seed(actual_seed)
    random.seed(actual_seed)

    print("=" * 60)
    print(f"TRAINING PYTHIA-70M ({args.version.upper()}) ON CPU")
    print("=" * 60)
    print(f"Model:           {model_name}")
    print(f"Seed:            {actual_seed} ({'default' if args.version == 'v1' else 'v2 override'})")
    print(f"Learning Rate:   {lr}")
    print(f"Batch Size:      {batch_size}")
    print(f"Epochs:          {epochs}")
    print(f"Max Seq Length:  {max_len}")
    print(f"Subset Limit:    {args.subset if args.subset else 'Full (1,500 max)'}")
    print("=" * 60)

    # Read training data
    if not os.path.exists(args.train_file):
        # Fallback to local data/teacher shards or S3 if not yet cleaned
        print(f"Error: Training file {args.train_file} not found!", file=sys.stderr)
        sys.exit(1)

    raw_samples = []
    with open(args.train_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw_samples.append(json.loads(line))

    # Slice subset or max 1,500 records per assignment constraint
    if args.subset:
        train_samples = raw_samples[:args.subset]
    else:
        train_samples = raw_samples[:1500]

    print(f"Loaded {len(train_samples)} training examples.")

    # Format training examples:
    # Command: <the command>\nJSON: <the teacher's JSON reply>
    formatted_texts = []
    for s in train_samples:
        cmd_text = s["text"]
        # Format JSON reply exactly
        if "teacher_json" in s:
            json_text = json.dumps(s["teacher_json"], ensure_ascii=False)
        else:
            json_text = json.dumps({
                "intent": s.get("intent"),
                "date": s.get("date"),
                "time": s.get("time"),
                "place": s.get("place")
            }, ensure_ascii=False)
        formatted_texts.append(f"Command: {cmd_text}\nJSON: {json_text}")

    print("Sample formatted training record:")
    print("---")
    print(formatted_texts[0])
    print("---")

    # Load tokenizer and model
    print(f"Loading {model_name}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(model_name)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    try:
        model = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.float32, local_files_only=True)
    except Exception:
        model = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.float32)
    model.train()

    dataset = CommandDataset(formatted_texts, tokenizer, max_length=max_len)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)

    loss_records = []
    os.makedirs("training", exist_ok=True)
    loss_csv_path = "training/loss.csv"

    # Train loop on CPU
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        batch_count = 0
        for batch in dataloader:
            optimizer.zero_grad()
            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                labels=batch["labels"]
            )
            loss = outputs.loss
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            batch_count += 1

        avg_loss = total_loss / max(1, batch_count)
        loss_records.append((epoch, avg_loss))
        print(f"Epoch {epoch}/{epochs} - Training Loss: {avg_loss:.4f}")

    # Save loss.csv
    with open(loss_csv_path, "w", encoding="utf-8") as f:
        f.write("epoch,loss\n")
        for ep, l in loss_records:
            f.write(f"{ep},{l:.4f}\n")
    print(f"Saved training loss to {loss_csv_path}")

    # Save model and tokenizer
    out_model_dir = f"models/{args.version}"
    os.makedirs(out_model_dir, exist_ok=True)
    model.save_pretrained(out_model_dir)
    tokenizer.save_pretrained(out_model_dir)
    print(f"Saved model and tokenizer to {out_model_dir}/")

    # Compute checksum
    sha256_hash = compute_dir_sha256(out_model_dir)
    sha_path = f"{out_model_dir}/model.sha256"
    with open(sha_path, "w", encoding="utf-8") as f:
        f.write(f"{sha256_hash}  model\n")
    print(f"Saved model checksum ({sha256_hash}) to {sha_path}")

    # Upload to SeaweedFS S3
    upload_dir_to_s3(out_model_dir, f"models/{args.version}")
    print(f"=== Completed Training for {args.version} ===")


if __name__ == "__main__":
    main()
