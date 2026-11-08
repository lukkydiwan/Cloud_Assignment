# Makefile for Cloud Computing Mini Project
# Supports: make up, make down, make train, make train-v2, make test, make lint

SHELL := /bin/bash
PYTHON ?= $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else which python3 2>/dev/null || echo python; fi)
SUBSET ?=

.PHONY: all help up down train train-v2 test lint clean

help:
	@echo "=========================================================="
	@echo "Cloud Computing Mini Project - Automation Commands"
	@echo "=========================================================="
	@echo "  make up              - Build & deploy k3d cluster, storage, and service"
	@echo "  make down            - Tear down cluster and all resources"
	@echo "  make train           - Fine-tune Pythia-70M student model (v1, 3 epochs)"
	@echo "  make train SUBSET=50 - Quick training run on 50 examples (verification)"
	@echo "  make train-v2        - Train second version (v2, 4 epochs, different seed)"
	@echo "  make test            - Run unit tests and NACL simulator check"
	@echo "  make lint            - Run static code checks"
	@echo "=========================================================="

up:
	@echo ">>> [1/3] Ensuring k3d cluster is created..."
	@k3d cluster get cloud-cluster >/dev/null 2>&1 || k3d cluster create --config cluster/k3d.yaml
	@echo ">>> [2/3] Deploying SeaweedFS storage in data namespace..."
	@kubectl apply -f k8s/data/seaweedfs.yaml
	@kubectl -n data rollout status deployment/seaweedfs --timeout=90s
	@echo ">>> [3/3] Building and deploying parser inference service..."
	@docker build -t parser-service:v1 -f service/Dockerfile .
	@k3d image import parser-service:v1 -c cloud-cluster
	@kubectl apply -f k8s/app/deployment.yaml
	@echo ">>> Deployment complete. Service listening via Ingress on http://localhost:8080/parse"

down:
	@echo ">>> Tearing down k3d cluster..."
	@k3d cluster delete cloud-cluster || true
	@echo ">>> Cluster destroyed."

train:
	@echo ">>> Starting student distillation training on CPU (v1)..."
	@$(PYTHON) training/train.py --config training/config.yaml --version v1 $(if $(SUBSET),--subset $(SUBSET),)

train-v2:
	@echo ">>> Starting student distillation training on CPU (v2, +1 epoch, seed=123)..."
	@$(PYTHON) training/train.py --config training/config.yaml --version v2

test:
	@echo ">>> Running unit test suite..."
	@python3 -m unittest discover -s tests -p "test_*.py" -v
	@echo ">>> Validating NACL rules against test packets..."
	@python3 tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check

lint:
	@echo ">>> Running code quality linter..."
	@python3 -m py_compile worker/worker.py worker/clean.py training/train.py service/app.py tests/test_pipeline.py
	@echo ">>> All Python files compiled cleanly."
