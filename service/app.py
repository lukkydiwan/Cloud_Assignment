import os
import sys
import json
import socket
import threading
import torch
import boto3
import jsonschema
from fastapi import FastAPI, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

app = FastAPI(title="Command Parser Inference Service")

MODEL_URI = os.environ.get("MODEL_URI", "models/v1")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://seaweedfs-s3.data.svc.cluster.local:8333")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", 64))
FAULT_INJECT = os.environ.get("FAULT_INJECT", "0")
POD_NAME = os.environ.get("POD_NAME", os.environ.get("HOSTNAME", socket.gethostname()))

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "admin")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "admin123")

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "schema.json")
if not os.path.exists(SCHEMA_FILE):
    SCHEMA_FILE = "/app/data/schema.json"

SCHEMA = None
if os.path.exists(SCHEMA_FILE):
    try:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            full_schema = json.load(f)
            SCHEMA = full_schema.get("json_schema")
    except Exception as e:
        print(f"Warning: Could not load schema from {SCHEMA_FILE}: {e}", file=sys.stderr)

if SCHEMA is None:
    SCHEMA = {
        "type": "object",
        "additionalProperties": False,
        "required": ["intent", "date", "time", "place"],
        "properties": {
            "intent": {
                "enum": [
                    "alarm_set",
                    "alarm_query",
                    "calendar_set",
                    "calendar_query",
                    "calendar_remove",
                    "weather_query",
                    "datetime_query",
                    "recommendation_events",
                ]
            },
            "date": {"type": ["string", "null"]},
            "time": {"type": ["string", "null"]},
            "place": {"type": ["string", "null"]},
        },
    }

model = None
tokenizer = None
is_model_ready = False
model_loading_error = None


class ParseRequest(BaseModel):
    text: str


def download_model_from_s3(s3_uri, local_dest):
    print(f"Downloading model from {s3_uri} via {S3_ENDPOINT} to {local_dest}...")
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name="us-east-1",
    )

    clean_uri = s3_uri
    if clean_uri.startswith("s3://"):
        clean_uri = clean_uri[5:]
    parts = clean_uri.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""

    os.makedirs(local_dest, exist_ok=True)
    paginator = s3.get_paginator("list_objects_v2")
    found_files = 0

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rel_path = os.path.relpath(key, prefix) if prefix else key
            target_path = os.path.join(local_dest, rel_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            print(f"Fetching s3://{bucket}/{key} -> {target_path}")
            s3.download_file(bucket, key, target_path)
            found_files += 1

    if found_files == 0:
        raise RuntimeError(f"No model files found at s3://{bucket}/{prefix}")
    print(f"Successfully downloaded {found_files} files from S3.")


def load_model_worker():
    global model, tokenizer, is_model_ready, model_loading_error
    local_model_dir = f"/tmp/model_{MODEL_VERSION}"
    try:
        try:
            download_model_from_s3(MODEL_URI, local_model_dir)
        except Exception as s3_err:
            if os.path.exists(MODEL_URI) and os.path.isdir(MODEL_URI):
                print(f"S3 download failed ({s3_err}), falling back to local directory {MODEL_URI}...", file=sys.stderr)
                local_model_dir = MODEL_URI
            else:
                raise s3_err

        print(f"Loading tokenizer and model from {local_model_dir} into CPU memory...")
        try:
            tokenizer = AutoTokenizer.from_pretrained(local_model_dir, local_files_only=True)
            model = AutoModelForCausalLM.from_pretrained(local_model_dir, dtype=torch.float32, local_files_only=True)
        except Exception:
            tokenizer = AutoTokenizer.from_pretrained(local_model_dir)
            model = AutoModelForCausalLM.from_pretrained(local_model_dir, dtype=torch.float32)

        model.eval()
        is_model_ready = True
        print(f"Model {MODEL_VERSION} loaded and ready!")
    except Exception as e:
        model_loading_error = str(e)
        print(f"Error loading model: {e}", file=sys.stderr)


@app.on_event("startup")
def startup_event():
    threading.Thread(target=load_model_worker, daemon=True).start()


@app.get("/healthz")
def healthz():
    return Response(content="OK", status_code=status.HTTP_200_OK)


@app.get("/readyz")
def readyz():
    if is_model_ready:
        return Response(content="Ready", status_code=status.HTTP_200_OK)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "loading", "error": model_loading_error},
    )


@app.post("/parse")
def parse(req: ParseRequest, response: Response):
    fault_inject = os.environ.get("FAULT_INJECT", FAULT_INJECT)
    model_version = os.environ.get("MODEL_VERSION", MODEL_VERSION)
    pod_name = os.environ.get("POD_NAME", os.environ.get("HOSTNAME", POD_NAME))
    response.headers["X-Model-Version"] = model_version
    response.headers["X-Served-By"] = pod_name

    if fault_inject == "1":
        raw_output = "not json"
    else:
        if not is_model_ready or model is None:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "model_not_ready"},
                headers={"X-Model-Version": model_version, "X-Served-By": pod_name},
            )

        prompt = f"Command: {req.text}\nJSON:"
        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated_tokens = outputs[0][inputs["input_ids"].shape[1] :]
        raw_output = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

    # Validate output against schema
    try:
        parsed_json = json.loads(raw_output)
    except Exception:
        start = raw_output.find("{")
        end = raw_output.find("}", start)
        if start != -1 and end != -1:
            try:
                parsed_json = json.loads(raw_output[start : end + 1])
            except Exception:
                parsed_json = None
        else:
            parsed_json = None

    try:
        if parsed_json is None:
            raise ValueError("invalid_model_output")
        jsonschema.validate(instance=parsed_json, schema=SCHEMA)
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "invalid_model_output"},
            headers={"X-Model-Version": model_version, "X-Served-By": pod_name},
        )

    # Return pure 4-key JSON on success
    return JSONResponse(
        content=parsed_json,
        status_code=status.HTTP_200_OK,
        headers={"X-Model-Version": model_version, "X-Served-By": pod_name},
    )
