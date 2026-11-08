# Cloud Computing (CS3081) - Mini Project
## Knowledge Distillation and Containerized Kubernetes Deployment of a Lightweight Command-Parsing Language Model

**Author / Roll Number:** 230103012 
**Repository:** [https://github.com/lukkydiwan/cloud_assignment](https://github.com/lukkydiwan/cloud_assignment)  

---

## Quickstart: Build, Deploy, Test, and Tear Down

This project is completely automated through the provided `Makefile`. Complete lifecycle orchestration requires at most three commands.

### 1. Build and Deploy Cluster (`make up`)
Provisions the local `k3d` cluster from `cluster/k3d.yaml`, deploys SeaweedFS S3 object storage in the `data` namespace, builds the CPU-optimized parser inference service container, imports the image into the cluster, and applies Kubernetes manifests in the `app` namespace:
```bash
make up
```
* Once deployed, the service answers HTTP requests via Traefik Ingress at:  
  `http://localhost:8080/parse`

### 2. Run Test Suite (`make test`)
Executes unit tests validating the 4-key JSON schema, slot value extraction, cleaner logic, and verifies the stateless Network Access Control List (NACL) against test packets:
```bash
make test
```

### 3. Run Static Code Linting (`make lint`)
Runs Python syntax verification across all pipeline and service scripts:
```bash
make lint
```

### 4. Student Model Training (`make train`)
Fine-tunes `EleutherAI/pythia-70m` on CPU using sequence-level knowledge distillation targets:
```bash
# Full training run (reading training/config.yaml, outputs to models/v1 and training/loss.csv)
make train

# Fast reproducible verification run on first 50 records only:
make train SUBSET=50

# Train version 2 (+1 epoch, seed variation for canary/rolling update):
make train-v2
```

### 5. Tear Down and Cleanup (`make down`)
Tears down the `k3d` cluster and cleans up all associated container resources cleanly:
```bash
make down
```

---

##  Repository Structure

```
├── cluster/
│   └── k3d.yaml                  # k3d cluster configuration with Ingress and S3 port mappings
├── data/
│   ├── commands_pool.jsonl       # 3,000 raw input commands
│   ├── validation.jsonl          # 100 gold validation records for scoring
│   ├── schema.json               # 4-key JSON schema (intent, date, time, place)
│   └── rate_card.json            # Resource pricing rates for cost estimation
├── datasets/v1/
│   ├── train.jsonl               # Cleaned training dataset (754 records)
│   └── train.sha256              # SHA-256 integrity checksum of training data
├── k8s/
│   ├── data/seaweedfs.yaml       # SeaweedFS S3 object store deployment & PVC in data namespace
│   ├── pipeline/workers.yaml     # Parallel worker jobs (shard-0, shard-1) in pipeline namespace
│   └── app/deployment.yaml       # Deployment (2 replicas), Service, HPA, Secret, and Ingress
├── models/
│   ├── v1/                       # Distilled student model v1 & model.sha256
│   └── v2/                       # Second version student model v2 & model.sha256
├── network/
│   ├── nacl.json                 # Stateless NACL rules for public load balancer subnet
│   ├── subnets.md                # 10.20.0.0/16 subnet calculation table and binary working
│   └── packets_sample.jsonl      # Test packet scenarios for firewall verification
├── prompts/
│   └── teacher_prompt.txt        # Structured prompt for teacher LLM
├── report/
│   ├── build_report.py           # ReportLab generation script for official 8-page PDF
│   └── report.pdf                # Compiled final project report
├── results/                      # Empirical benchmark evidence (Locust stats, cold-start, telemetry)
├── service/
│   ├── app.py                    # FastAPI inference service with /parse, /healthz, /readyz
│   ├── Dockerfile                # CPU-only PyTorch container image (<= 2 GB)
│   └── requirements.txt          # Pinned dependency versions
├── tests/
│   └── test_pipeline.py          # Unit test suite (Schema, Data Cleaning, NACL rules)
├── tools/
│   ├── nacl_sim.py               # Stateless NACL simulator
│   ├── score.py                  # Model accuracy and JSON validity scorer
│   ├── locustfile.py             # Locust load-testing script
│   ├── run_loadtest.py           # Automated load test execution with telemetry logging
│   └── benchmark_limits.py       # Sequential inference benchmark under 1 CPU / 1 GiB limits
├── training/
│   ├── config.yaml               # Pinned hyperparameters and environment library versions
│   ├── loss.csv                  # Recorded per-epoch training loss trajectory
│   └── train.py                  # PyTorch CPU sequence-level distillation training loop
├── worker/
│   ├── worker.py                 # Sharded data generation worker
│   └── clean.py                  # Strict schema cleaner and deduplication filter
├── .github/workflows/ci.yml      # 5-stage GitHub Actions CI/CD workflow
├── AI_USE.md                     # Disclosure of AI tools used and human verification methodology
├── Makefile                      # Automated orchestration commands (up, down, train, test, lint)
└── README.md                     # System documentation and execution instructions
```
