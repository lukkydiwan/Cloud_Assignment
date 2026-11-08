import os
import json
import requests
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434")
VALIDATION_FILE = "data/validation.jsonl"
PROMPT_FILE = "prompts/teacher_prompt.txt"
RESULTS_DIR = "results"

os.makedirs(RESULTS_DIR, exist_ok=True)


def evaluate_teacher():
    print("=== Evaluating Teacher (Phi-3.5 via Ollama) ===")
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt_template = f.read().strip()

    with open(VALIDATION_FILE, "r", encoding="utf-8") as f:
        val_records = [json.loads(line) for line in f if line.strip()]

    predictions = []
    out_file = os.path.join(RESULTS_DIR, "teacher_predictions.jsonl")

    for idx, rec in enumerate(val_records, 1):
        prompt = f"{prompt_template}\n\nCommand: {rec['text']}\nJSON:"
        try:
            resp = requests.post(
                f"{OLLAMA_ENDPOINT}/api/generate",
                json={
                    "model": "phi3.5",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.0,
                        "seed": 42,
                        "num_predict": 64,
                        "stop": ["}\n", "}\r\n", "}\n\n"],
                    },
                },
                timeout=45,
            )
            raw = resp.json().get("response", "").strip()
        except Exception as e:
            print(f"Error querying teacher for {rec['id']}: {e}")
            raw = ""

        predictions.append({"id": rec["id"], "prediction": raw})
        if idx % 10 == 0 or idx == len(val_records):
            print(f"Teacher evaluated {idx}/{len(val_records)}")

    with open(out_file, "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Saved teacher predictions to {out_file}")


def evaluate_student(model_path, out_name):
    print(f"=== Evaluating Student Model ({model_path}) ===")
    with open(VALIDATION_FILE, "r", encoding="utf-8") as f:
        val_records = [json.loads(line) for line in f if line.strip()]

    print(f"Loading {model_path} on CPU...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float32)
    model.eval()

    predictions = []
    out_file = os.path.join(RESULTS_DIR, f"{out_name}_predictions.jsonl")

    for idx, rec in enumerate(val_records, 1):
        prompt = f"Command: {rec['text']}\nJSON:"
        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=64,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = outputs[0][inputs["input_ids"].shape[1] :]
        raw = tokenizer.decode(generated, skip_special_tokens=True).strip()
        predictions.append({"id": rec["id"], "prediction": raw})
        if idx % 20 == 0 or idx == len(val_records):
            print(f"{out_name} evaluated {idx}/{len(val_records)}")

    with open(out_file, "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Saved predictions to {out_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", action="store_true", help="Evaluate Teacher model")
    parser.add_argument("--untrained", action="store_true", help="Evaluate Untrained Pythia-70m")
    parser.add_argument("--student", type=str, help="Path to trained student model")
    args = parser.parse_args()

    if args.teacher:
        evaluate_teacher()
    if args.untrained:
        evaluate_student("EleutherAI/pythia-70m", "untrained")
    if args.student:
        evaluate_student(args.student, "student")
