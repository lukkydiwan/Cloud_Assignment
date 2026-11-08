# AI Use Disclosure and Verification Report

**Author / Roll Number:** 230103012  
**Course:** CS3081 Cloud Computing  
**Project:** Knowledge Distillation and Deployment of a Lightweight Command-Parsing Language Model  

---

## 1. Overview of AI Tools Utilized

In accordance with the assignment guidelines, AI tools were leveraged as engineering assistants for architecture planning, code synthesis, configuration generation, and debugging. The primary tool utilized was **Antigravity (powered by Google Gemini models)**.

---

## 2. Specific Tasks and AI Applications

| Phase / Task | Purpose of AI Assistance | Specific Output / Role |
| :--- | :--- | :--- |
| **Task 1: Data Preparation** | Prompt engineering & JSON constraint tuning | Designed strict 4-key JSON prompt in `prompts/teacher_prompt.txt`; assisted in configuring Ollama stop tokens and parameters (`num_predict: 64`, `format: "json"`). |
| **Task 2: Model Training** | PyTorch distillation loop implementation | Generated clean PyTorch / Hugging Face Transformers CPU training loop in `training/train.py` with loss logging to CSV and SHA-256 calculation. |
| **Task 3: Inference Service** | Containerized FastAPI service design | Designed `service/app.py` with asynchronous S3 model fetching, schema validation against `data/schema.json`, `FAULT_INJECT` mode, and custom HTTP response headers (`X-Model-Version`, `X-Served-By`). |
| **Task 4: Kubernetes Deployment** | Manifest creation & Chaos testing automation | Authored `k8s/app/deployment.yaml` (Deployments, Secrets, ClusterIP Service, Traefik Ingress, HPA), and automated chaos tests (pod recovery, cold starts). |
| **Task 5: Networking & Security** | Subnetting mathematics and stateless NACL rules | Assisted in binary address partitioning for `10.20.0.0/16` and stateless NACL rule creation in `network/nacl.json`. |
| **Task 6: CI/CD & Reproducibility** | GitHub Actions workflow & Makefile automation | Structured `.github/workflows/ci.yml` with multi-stage verification (lint, unit tests, release eval, quality gate, gitleaks). |
| **Task 7: SRE & Performance** | Cost modeling and review analysis | Formulated rate card cost equations, SLO error budget consumption calculations, and review analysis. |

---

## 3. Verification and Validation Methodology

All AI-suggested code, network configurations, and manifests were subjected to rigorous independent empirical validation:

1. **Deterministic Testing:**
   - Evaluated Network ACL rules using `tools/nacl_sim.py --check` against ground truth packet scenarios, verifying a 100% pass rate.
   - Built a comprehensive unit test suite in `tests/test_pipeline.py` to assert JSON schema constraints, slot validation, and firewall decisions.
2. **Runtime Verification & Benchmarking:**
   - Ran `make train SUBSET=50` to verify CPU memory stability and loss reduction ($9.76 \to 1.97$) before launching full-scale runs.
   - Executed the inference container with resource caps (`--cpus=1 --memory=1g`) and measured actual memory consumption during sequential inference requests.
   - Verified that `FAULT_INJECT=1` reliably triggers an HTTP 500 error matching the schema specification.
3. **Cluster Resilience & Chaos Testing:**
   - Deployed the complete stack into a local `k3d` cluster and empirically verified that rolling updates from `v1` to `v2` maintained 100% availability with instantaneous rollback capability (`kubectl rollout undo`).
   - Ran pod termination chaos tests, recording actual recovery times (18.93s) and multi-run cold start metrics (mean: 18.84s).
   - Validated balanced traffic distribution across replicas (50% / 50%) via the `X-Served-By` response header.
4. **Correction of AI Failures & Gotchas:**
   - *Ollama Binding Issue:* The initial AI setup assumed Ollama bound to `0.0.0.0` by default; when pods inside k3d received connection errors on `host.k3d.internal`, we diagnosed the issue and explicitly launched Ollama with `OLLAMA_HOST=0.0.0.0:11434`.
   - *SeaweedFS OOM Termination:* The original SeaweedFS deployment allocated a 512 MiB memory limit, which triggered the Linux OOM killer during 250 MB model weight uploads. We resolved this by increasing memory limits to 1.5 GiB and configuring persistent volume claims.
   - *Model Runaway Generation:* LLM-generated responses without stop tokens occasionally produced conversational filler; we enforced strict stop tokens (`}\n`, `}\r\n`) and schema validation to ensure clean JSON streams.

---

## 4. Conclusion

AI acceleration was used to streamline boilerplate implementation and architecture design, while human-in-the-loop verification, debugging, and empirical benchmarking ensured correctness, resilience, and adherence to assignment constraints.
