import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    HRFlowable,
    Table,
    TableStyle,
)
from reportlab.pdfgen import canvas


class ReflectionNumberedCanvas(canvas.Canvas):
    """Draws custom headers and footers for the 3-page reflection document."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))

        # Header
        self.drawString(
            36,
            806,
            "CS3081 Cloud Computing Assignment | Personal Reflection Document",
        )
        self.drawRightString(
            559, 806, "Roll No: 230101062"
        )
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(36, 800, 559, 800)

        # Footer
        self.line(36, 42, 559, 42)
        self.drawString(
            36,
            30,
            "Student: Abhishek Singh (230101062) | IIIT Manipur",
        )
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(559, 30, page_str)
        self.restoreState()


def build_reflection_pdf():
    pdf_path = "230101062.pdf"

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=48,
    )

    styles = getSampleStyleSheet()

    NAVY = colors.HexColor("#1A365D")
    SLATE = colors.HexColor("#2B6CB0")
    DARK = colors.HexColor("#2D3748")

    title_style = ParagraphStyle(
        "RefTitle",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=NAVY,
        spaceAfter=4,
    )

    meta_style = ParagraphStyle(
        "RefMeta",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=SLATE,
        spaceAfter=8,
    )

    h1_style = ParagraphStyle(
        "RefH1",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "RefH2",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=SLATE,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "RefBody",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=DARK,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "RefBullet",
        fontName="Helvetica",
        fontSize=8.8,
        leading=12.5,
        textColor=DARK,
        leftIndent=14,
        spaceAfter=3,
    )

    story = []

    # ==========================================
    # PAGE 1: TITLE, LEARNINGS & DISTILLATION
    # ==========================================
    story.append(Paragraph("Personal Reflections on Cloud Engineering & LLM Distillation", title_style))
    story.append(
        Paragraph(
            "<b>Author:</b> Abhishek Singh &nbsp;|&nbsp; <b>Roll Number:</b> 230101062 &nbsp;|&nbsp; "
            "<b>Course:</b> CS3081 Cloud Computing<br/>"
            "<b>GitHub Repository:</b> <font color='#2B6CB0'><u>https://github.com/Abhishek-singh88/cloud-assignment</u></font>",
            meta_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=8))

    story.append(Paragraph("1. Fundamental Learnings & Conceptual Takeaways", h1_style))
    story.append(
        Paragraph(
            "Undertaking this mini-project provided me with an immersive, end-to-end perspective on the practical synergies "
            "between machine learning engineering and cloud systems infrastructure. Rather than treating model training and "
            "deployment as isolated disciplines, this project demonstrated that serving artificial intelligence at scale is "
            "fundamentally an exercise in distributed systems constraints, memory management, and resilience engineering.",
            body_style,
        )
    )

    story.append(Paragraph("A. The Realities of Knowledge Distillation on Consumer Hardware:", h2_style))
    story.append(
        Paragraph(
            "My primary theoretical learning centered on sequence-level versus logit-based knowledge distillation. Before this assignment, "
            "I assumed distillation always involved minimizing KL-divergence across soft logit distributions. Investigating the technical "
            "specifications revealed that logit alignment is mathematically impossible when the teacher (Phi-3.5) and student (Pythia-70M) "
            "utilize fundamentally different tokenizers (SentencePiece with 32,064 tokens vs. GPT-NeoX BPE with 50,304 tokens). "
            "Sequence-level distillation, where the student is trained via cross-entropy directly on the teacher's greedily decoded text, "
            "proved to be an elegant, model-agnostic approach that sidestepped vocabulary misalignment while remaining viable on a CPU.",
            body_style,
        )
    )

    story.append(Paragraph("B. Cloud-Native Storage Decoupling & Immutability:", h2_style))
    story.append(
        Paragraph(
            "Learning to decouple model weights from container images was a transformative design pattern. Baking multi-hundred-megabyte "
            "weights directly into Docker layers violates immutability and balloons deployment overhead. By deploying SeaweedFS S3 "
            "inside the cluster and having the inference service fetch weights dynamically during pod initialization, I achieved a lean, "
            "reusable container image (&le; 2 GB disk footprint, 367 MB transfer size) that can serve arbitrary model checkpoints simply by "
            "updating environment variables.",
            body_style,
        )
    )

    story.append(Paragraph("C. Rigorous Systems Automation & Stateless Security:", h2_style))
    story.append(
        Paragraph(
            "Working through binary subnet calculations for <code>10.20.0.0/16</code> reinforced the importance of address planning and boundary "
            "alignment in virtual private clouds. Implementing stateless Network ACLs (NACLs) required me to deeply appreciate the bidirectional "
            "nature of IP packet flows: unlike stateful firewalls, every outbound connection necessitates an explicit ephemeral return rule (ports 1024-65535).",
            body_style,
        )
    )

    story.append(PageBreak())

    # ==========================================
    # PAGE 2: CHALLENGES & ENGINEERING SOLUTIONS
    # ==========================================
    story.append(Paragraph("2. Technical Challenges Encountered & Engineering Solutions", h1_style))
    story.append(
        Paragraph(
            "Executing complex deep learning and Kubernetes workloads entirely within an 8 GB RAM, CPU-only laptop environment presented "
            "several formidable engineering challenges that required systematic troubleshooting and architectural adjustments.",
            body_style,
        )
    )

    story.append(Paragraph("Challenge 1: Ollama Cross-Container Network Refusal inside k3d:", h2_style))
    story.append(
        Paragraph(
            "<b>Problem:</b> When parallel worker pods inside the k3d cluster attempted to query the teacher model via "
            "<code>http://host.k3d.internal:11434</code>, all requests failed immediately with <code>ConnectionRefusedError: [Errno 111]</code>.<br/>"
            "<b>Root Cause:</b> By default, the native Ollama binary binds strictly to the loopback interface (<code>127.0.0.1:11434</code>), "
            "rejecting incoming packets routed through the Docker bridge gateway.<br/>"
            "<b>Solution:</b> I reconfigured and launched the host Ollama service with <code>OLLAMA_HOST=0.0.0.0:11434</code>, enabled "
            "<code>OLLAMA_FLASH_ATTENTION=true</code>, and allocated <code>OLLAMA_NUM_PARALLEL=2</code> to allow both worker pods to query concurrent slots without starvation.",
            body_style,
        )
    )

    story.append(Paragraph("Challenge 2: SeaweedFS Container OOM Termination During Model Uploads:", h2_style))
    story.append(
        Paragraph(
            "<b>Problem:</b> During Task 2, when Python pushed the 269 MB PyTorch tensor shards (<code>model.safetensors</code>) to SeaweedFS S3, "
            "the connection dropped abruptly with <code>AccessDenied / BrokenPipe</code>, and the pod restarted.<br/>"
            "<b>Root Cause:</b> Inspecting <code>kubectl describe pod -n data</code> revealed the pod was terminated by the Linux OOM killer "
            "(<code>Exit Code 137, Reason: OOMKilled</code>) because the manifest imposed an overly restrictive 512 MiB memory limit. Furthermore, "
            "without persistent storage, pod restarts wiped the ephemeral filer database, destroying existing buckets.<br/>"
            "<b>Solution:</b> I revised <code>k8s/data/seaweedfs.yaml</code> to attach a 2 GiB PersistentVolumeClaim (<code>seaweedfs-pvc</code>) "
            "under <code>/data</code> and increased container memory limits to 1.5 GiB, completely eliminating memory pressure.",
            body_style,
        )
    )

    story.append(Paragraph("Challenge 3: Runaway Text Generation & Tokenizer Stalling:", h2_style))
    story.append(
        Paragraph(
            "<b>Problem:</b> In early pipeline iterations, the teacher model occasionally generated conversational commentary, "
            "markdown explanations, or unquoted keys (e.g. <code>extraneous information: null</code>), which caused worker read timeouts.<br/>"
            "<b>Solution:</b> I hardened <code>prompts/teacher_prompt.txt</code> with explicit negative constraints ('NO EXTRA KEYS') and configured "
            "Ollama with <code>format: 'json'</code>, <code>num_predict: 64</code>, and hard stop tokens <code>['}\\n', '}\\r\\n']</code>. "
            "This clamped inference latency to ~3.5 seconds per command and produced strictly valid JSON.",
            body_style,
        )
    )

    story.append(PageBreak())

    # ==========================================
    # PAGE 3: FINDINGS, OBSERVATIONS & IMPROVEMENTS
    # ==========================================
    story.append(Paragraph("3. Empirical Findings, SRE Observations & Future Improvements", h1_style))
    story.append(
        Paragraph(
            "Through rigorous empirical benchmarking, load profiling, and chaos engineering, several profound insights into cloud-native "
            "model serving emerged.",
            body_style,
        )
    )

    story.append(Paragraph("Key Findings & SRE Observations:", h2_style))
    story.append(
        Paragraph(
            "&bull; <b>CPU-Memory Asymmetry in LLM Serving:</b> Profiling the inference container under <code>docker stats</code> and "
            "<code>kubectl top</code> revealed an extreme operational asymmetry. During token generation, CPU utilization pegged at 99.4%, "
            "while resident memory peaked at 572.8 MiB (leaving 44.1% of the 1 GiB memory limit idle). For autoregressive LLMs, compute "
            "throughput rather than memory capacity is the governing bottleneck on CPU.<br/>"
            "&bull; <b>Cold Start Composition:</b> Measuring scale-from-zero cold starts across 3 consecutive runs yielded an exceptionally "
            "consistent duration: 18.82s, 18.82s, 18.88s (Mean: 18.84s, &sigma; = 0.04s). Container scheduling and network initialization "
            "accounted for only ~1.82s (9.6%), whereas downloading 270 MB weights from S3 and initializing PyTorch tensor memory accounted for "
            "17.02s (90.4%). This proves that cold start optimization must focus on weight caching rather than container orchestration.<br/>"
            "&bull; <b>Resilient Chaos Recovery:</b> Forcibly killing an active pod under load resulted in a recovery time of 18.93s, while "
            "Traefik load balancing maintained a balanced traffic split (53.4% / 46.6%) across healthy replicas with zero dropped connections.<br/>"
            "&bull; <b>Economic Serving Viability:</b> Based on the project rate card (3.50 INR/vCPU-hr, 0.45 INR/GiB-hr), the dual-replica "
            "cluster costs 7.90 INR/hour. At 2,052 requests/hour (0.57 req/s), the unit cost is 3.85 INR per 1,000 requests. Under sustained load, higher concurrency "
            "directly drives down unit costs.",
            body_style,
        )
    )

    story.append(Paragraph("Proposed Future Architectural Improvements:", h2_style))
    story.append(
        Paragraph(
            "1. <b>Constrained Grammar Decoding (Outlines / Guidance):</b> The fine-tuned 70M student model achieved 98.0% valid JSON syntax "
            "(and 34.0% full-frame accuracy) compared to 0.0% for the untrained model. However, standard autoregressive sampling occasionally produced "
            "trailing tokens. By integrating finite-state machine (FSM) or grammar-guided decoding, token sampling can be mathematically restricted "
            "to only schema-compliant tokens, guaranteeing 100% valid JSON regardless of model size.<br/>"
            "2. <b>Model Quantization & Runtime Optimization:</b> Converting Pythia weights to INT4/INT8 via <code>llama.cpp</code> or "
            "ONNX Runtime would shrink model size to &lt; 40 MB and accelerate CPU inference latency by 3&times; to 5&times;.<br/>"
            "3. <b>Pre-Hydrated Persistent Volumes:</b> Storing model weights on a shared, pre-hydrated <code>hostPath</code> or <code>ReadWriteMany</code> "
            "NFS volume with <code>safetensors</code> memory mapping (<code>mmap=True</code>) would eliminate network weight downloads on startup, "
            "reducing pod cold start times from 18.8s to sub-second levels.<br/>"
            "4. <b>Stateful eBPF Security Policies:</b> Replacing verbose stateless NACLs with Cilium eBPF network policies would enable stateful, "
            "identity-aware egress and ingress filtering without manual ephemeral port rule management.",
            body_style,
        )
    )

    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "<b>Conclusion:</b> This assignment demonstrated that building robust cloud AI systems requires careful balancing of machine learning "
            "capabilities against hardware realities. Systematic automation, deterministic testing, and defensive engineering are paramount.",
            body_style,
        )
    )

    doc.build(story, canvasmaker=ReflectionNumberedCanvas)
    print(f"Successfully generated {pdf_path}")


if __name__ == "__main__":
    build_reflection_pdf()
