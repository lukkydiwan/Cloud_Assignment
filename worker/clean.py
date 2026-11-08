#!/usr/bin/env python3
"""Data cleaning script for teacher shard outputs.
Reads all shard outputs from data/teacher/shard-*.jsonl (or S3).
Filters bad records based on criteria:
(a) replies that are not valid JSON
(b) replies whose keys are not exactly intent, date, time, and place
(c) replies whose intent is not one of the eight
(d) replies with a slot value that is neither null nor text that appears in the command
(e) duplicate commands (keep the one with the smallest id)

Outputs:
- datasets/v1/train.jsonl (records in id order)
- datasets/v1/train.sha256
Prints the summary table where:
input = (a) + (b) + (c) + (d) + duplicates + kept
"""

import os
import sys
import glob
import json
import hashlib
ALLOWED_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events",
}

REQUIRED_KEYS = {"intent", "date", "time", "place"}

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:8333")
S3_BUCKET = os.environ.get("S3_BUCKET", "datasets")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "admin")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "admin123")



def get_s3_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name="us-east-1",
    )


def extract_json(raw_text):
    """Attempt to parse raw text as JSON, including finding the first JSON block if needed."""
    if not raw_text or not isinstance(raw_text, str):
        return None
    raw = raw_text.strip()
    try:
        return json.loads(raw)
    except Exception:
        # If wrapped in markdown ```json ... ``` or has preamble, try to extract substring between first { and last }
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except Exception:
                return None
        return None


def clean_shards(shard_paths, out_jsonl_path, out_sha_path):
    records = []
    for sp in sorted(shard_paths):
        with open(sp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

    # Sort records by ID ascending
    records.sort(key=lambda r: r["id"])

    total_input = len(records)
    count_a = 0  # not valid JSON
    count_b = 0  # keys not exactly intent, date, time, place
    count_c = 0  # intent not in 8
    count_d = 0  # slot value not null and not appearing in command text
    count_duplicates = 0  # duplicate commands
    kept_records = []

    seen_texts = set()

    for r in records:
        cmd_id = r["id"]
        cmd_text = r["text"]
        raw = r.get("teacher_raw", "")

        # Check (a): valid JSON
        parsed = extract_json(raw)
        if parsed is None or not isinstance(parsed, dict):
            count_a += 1
            continue

        # Check (b): keys exactly intent, date, time, place
        if set(parsed.keys()) != REQUIRED_KEYS:
            count_b += 1
            continue

        # Check (c): intent is one of the eight
        intent = parsed.get("intent")
        if not isinstance(intent, str) or intent not in ALLOWED_INTENTS:
            count_c += 1
            continue

        # Check (d): slot value is null or appears in command text (case-insensitive substring)
        norm_cmd = cmd_text.lower()
        slot_invalid = False
        for slot in ("date", "time", "place"):
            val = parsed.get(slot)
            if val is not None:
                if not isinstance(val, str):
                    slot_invalid = True
                    break
                if val.lower() not in norm_cmd:
                    slot_invalid = True
                    break
        if slot_invalid:
            count_d += 1
            continue

        # Check (e): duplicate commands (keep the one with smallest id)
        # Since records are sorted by id ascending, the first occurrence is kept.
        if norm_cmd in seen_texts:
            count_duplicates += 1
            continue
        seen_texts.add(norm_cmd)

        # Kept record
        kept_records.append({
            "id": cmd_id,
            "text": cmd_text,
            "intent": parsed["intent"],
            "date": parsed["date"],
            "time": parsed["time"],
            "place": parsed["place"],
            "teacher_json": parsed
        })

    # Write output to datasets/v1/train.jsonl
    os.makedirs(os.path.dirname(out_jsonl_path), exist_ok=True)
    with open(out_jsonl_path, "w", encoding="utf-8") as out_f:
        for kr in kept_records:
            # We save the training format per Task 2
            out_f.write(json.dumps(kr, ensure_ascii=False) + "\n")

    # Compute SHA-256
    with open(out_jsonl_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    with open(out_sha_path, "w", encoding="utf-8") as f:
        f.write(f"{file_hash}  train.jsonl\n")

    print("\n" + "=" * 50)
    print("DATA CLEANING SUMMARY TABLE")
    print("=" * 50)
    print(f"Total input records:               {total_input}")
    print(f"Rejected (a) Not valid JSON:       {count_a}")
    print(f"Rejected (b) Wrong keys:           {count_b}")
    print(f"Rejected (c) Invalid intent:       {count_c}")
    print(f"Rejected (d) Slot hallucination:   {count_d}")
    print(f"Rejected (e) Duplicate commands:   {count_duplicates}")
    print(f"Total records kept:                {len(kept_records)}")
    print("-" * 50)
    check_sum_eq = count_a + count_b + count_c + count_d + count_duplicates + len(kept_records)
    print(f"Verification: {check_sum_eq} == {total_input} ({check_sum_eq == total_input})")
    print(f"SHA-256: {file_hash}")
    print("=" * 50 + "\n")

    # Upload to S3 if available
    try:
        s3 = get_s3_client()
        s3.upload_file(out_jsonl_path, S3_BUCKET, "v1/train.jsonl")
        s3.upload_file(out_sha_path, S3_BUCKET, "v1/train.sha256")
        print(f"Uploaded train.jsonl and train.sha256 to s3://{S3_BUCKET}/v1/")
    except Exception as e:
        print(f"Warning: S3 upload failed: {e}", file=sys.stderr)

    return {
        "input": total_input,
        "a": count_a,
        "b": count_b,
        "c": count_c,
        "d": count_d,
        "duplicates": count_duplicates,
        "kept": len(kept_records),
        "sha256": file_hash
    }


def main():
    shard_pattern = os.environ.get("SHARD_PATTERN", "data/teacher/shard-*.jsonl")
    shards = sorted(glob.glob(shard_pattern))
    if not shards:
        print(f"No shard files found matching: {shard_pattern}", file=sys.stderr)
        sys.exit(1)

    out_jsonl = os.environ.get("OUT_TRAIN", "datasets/v1/train.jsonl")
    out_sha = os.environ.get("OUT_SHA", "datasets/v1/train.sha256")
    clean_shards(shards, out_jsonl, out_sha)


if __name__ == "__main__":
    main()
