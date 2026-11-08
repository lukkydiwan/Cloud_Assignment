#!/usr/bin/env python3
"""Worker script for parallel teacher labelling using Ollama (Phi-3.5).
Reads SHARD_INDEX and SHARD_COUNT from environment.
Selects lines where line_number % SHARD_COUNT == SHARD_INDEX.
Sends each command to the teacher with prompts/teacher_prompt.txt.
Writes {"id": "...", "text": "...", "teacher_raw": "<raw reply>"}
to datasets/teacher/shard-<SHARD_INDEX>.jsonl in SeaweedFS S3 and local storage.
"""

import os
import sys
import json
import time
import requests
import boto3

SHARD_INDEX = int(os.environ.get("SHARD_INDEX", 0))
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", 2))
OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:8333")
S3_BUCKET = os.environ.get("S3_BUCKET", "datasets")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "dummy")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "dummy")
PROMPT_FILE = os.environ.get("PROMPT_PATH", "prompts/teacher_prompt.txt")
COMMANDS_FILE = os.environ.get("COMMANDS_PATH", "data/commands_pool.jsonl")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name="us-east-1",
    )


def load_teacher_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def query_teacher(prompt_base, command_text):
    full_prompt = f"{prompt_base}\n\nCommand: {command_text}\nJSON:"
    payload = {
        "model": "phi3.5",
        "prompt": full_prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_predict": 64,
            "stop": ["}\n", "}\r\n", "}\n\n"],
        },
    }
    for attempt in range(5):
        try:
            resp = requests.post(f"{OLLAMA_ENDPOINT}/api/generate", json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
            else:
                print(f"[Worker {SHARD_INDEX}] Ollama error HTTP {resp.status_code}, retrying...", file=sys.stderr)
        except Exception as e:
            print(f"[Worker {SHARD_INDEX}] Request exception: {e}, retrying in 2s...", file=sys.stderr)
        time.sleep(2)
    return ""


def main():
    print(f"=== Starting Worker Shard {SHARD_INDEX}/{SHARD_COUNT} ===")
    prompt_base = load_teacher_prompt()

    # Read commands from local file or download from S3
    if not os.path.exists(COMMANDS_FILE):
        print(f"Downloading {COMMANDS_FILE} from S3 {S3_BUCKET}...", file=sys.stderr)
        s3 = get_s3_client()
        os.makedirs(os.path.dirname(COMMANDS_FILE) or ".", exist_ok=True)
        s3.download_file(S3_BUCKET, "commands_pool.jsonl", COMMANDS_FILE)

    commands = []
    with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                commands.append(json.loads(line))

    # Filter assigned shard commands
    shard_commands = [
        (idx, cmd) for idx, cmd in enumerate(commands)
        if idx % SHARD_COUNT == SHARD_INDEX
    ]

    out_filename = f"shard-{SHARD_INDEX}.jsonl"
    local_out_dir = "data/teacher"
    os.makedirs(local_out_dir, exist_ok=True)
    local_out_path = os.path.join(local_out_dir, out_filename)

    # Resume capability if partially processed
    processed_ids = set()
    if os.path.exists(local_out_path):
        with open(local_out_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        processed_ids.add(record["id"])
                    except Exception:
                        pass
        print(f"[Worker {SHARD_INDEX}] Found {len(processed_ids)} already processed records, resuming...")

    total_shard = len(shard_commands)
    count = len(processed_ids)

    with open(local_out_path, "a", encoding="utf-8") as out_f:
        for line_num, cmd in shard_commands:
            cmd_id = cmd["id"]
            if cmd_id in processed_ids:
                continue

            raw_reply = query_teacher(prompt_base, cmd["text"])
            record = {
                "id": cmd_id,
                "text": cmd["text"],
                "teacher_raw": raw_reply
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

            count += 1
            if count % 10 == 0 or count == total_shard:
                print(f"[Worker {SHARD_INDEX}] Processed {count}/{total_shard} ({count*100.0/total_shard:.1f}%)")

    # Upload final shard to S3
    try:
        s3 = get_s3_client()
        s3_key = f"teacher/{out_filename}"
        s3.upload_file(local_out_path, S3_BUCKET, s3_key)
        print(f"[Worker {SHARD_INDEX}] Uploaded {local_out_path} to s3://{S3_BUCKET}/{s3_key}")
    except Exception as e:
        print(f"[Worker {SHARD_INDEX}] Warning: Failed to upload to S3: {e}", file=sys.stderr)

    print(f"=== Worker Shard {SHARD_INDEX} Completed Successfully ({count} records) ===")


if __name__ == "__main__":
    main()
