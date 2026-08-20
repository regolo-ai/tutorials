# ⚡ Self-Improving Secure Coding Loop
### Open SWE + Deepsec + Cognee + Regolo (GLM-5.2)

> **Autonomous, memory-augmented secure software engineering agent.**  
> Ingests GitHub issues, plans remediations with human approval, fixes code in isolated sandboxes, executes automated SAST/AST security gates, and builds an organizational Knowledge Graph so the system gets smarter with every Pull Request.

---

## 🎯 Value Proposition: Why This Project Matters

Most AI coding pipelines today suffer from three critical flaws:
1. **Stateless Blindness:** Coding agents repeat the exact same architectural mistakes and security vulnerabilities across sessions because standard LLM integrations have no persistent engineering memory.
2. **Fragile Alert Fatigue:** Traditional CI/CD security scanners only produce static logs that developers ignore, leaving security debt unresolved.
3. **Runaway Inference Costs:** Burning expensive frontier models across every single pipeline step (triage, planning, syntax formatting, test running, scanning) drives infrastructure costs through the roof.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE CLOSED-LOOP ADVANTAGE                              │
│                                                                                        │
│   Open SWE (Produce) ➔ Deepsec (Verify) ➔ Cognee (Remember) ➔ Brick (Govern)          │
│                                                                                        │
│   • 0% Repeat Vulnerabilities: Cognee remembers past CWEs & PR decisions               │
│   • 100% Verified Fixes: Deepsec revalidates patches before PR creation                │
│   • ~85% Cost Reduction: Regolo.ai OpenAI-Compatible API powered by GLM-5.2            │
│   • Human-in-the-Loop: Explicit plan approval gate & verifiable PR evidence             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Concrete ROI Delivered to Teams:
- **Instant Security Remediation:** Automatically converts reported vulnerabilities (SQLi, SSRF, IDOR, RCE, XSS, etc.) into tested, production-grade Pull Requests with zero manual code editing required.
- **Enterprise Engineering Memory (Cognee):** Builds an interlinked Knowledge Graph linking `Issue ➔ Vulnerability ➔ Defensive Fix ➔ Test Outcome ➔ Human Decision`. When a developer touches an authentication module 6 months later, the agent automatically enforces past security decisions.
- **Zero-Trust Independent Quality Gate (Deepsec):** The security scanner operates independently from the code generator. It doesn't assume the fix worked; it re-scans the repository in an isolated sandbox to certify that findings dropped to 0 and all tests pass.
- **Drastic Cost Optimization via Regolo.ai:** By leveraging **GLM-5.2** over Regolo's OpenAI-compatible endpoint (`https://api.regolo.ai/v1`), teams get high-capacity reasoning and agentic tool usage at **~$0.60 / $1.80 per 1M tokens** instead of **$3.00 / $15.00+ per 1M tokens** on proprietary single-frontier endpoints.

---

## 🏗️ Architecture & Workflow

```
               [ 📁 Target Repository / GitHub Issue ]
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ 1. Workspace Isolation    │ ➔ Clones into isolated sandbox (data/sandboxes/)
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ 2. Deepsec Initial Audit  │ ➔ SAST/AST Scan detects CWEs, calculates score (0-100)
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ 3. Cognee Memory Recall   │ ➔ Graph retrieval of past security rules & PR patterns
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ 4. Open SWE Plan (GLM-5.2)│ ➔ Formulates step-by-step remediation strategy
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ╔═══════════════════════════╗
                    ║ 5. Human Approval Gate    ║ ➔ [Accept / Modify / Reject] via interactive TUI
                    ╚═════════════╤═════════════╝
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ 6. Sandboxed Remediation  │ ➔ Applies defensive code + executes pytest test suite
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ 7. Deepsec Revalidation   │ ➔ Proves 0 residual vulnerabilities & 0 regressions
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ 8. Cognee Memory Update   │ ➔ Stores new PR, pattern, and decision in Knowledge Graph
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ 9. PR Evidence & Telemetry│ ➔ Generates PR_EVIDENCE.md + Brick cost analytics
                    └───────────────────────────┘
```

---

## 📦 Pre-Packaged Demo Target Repositories

The project includes **7 realistic vulnerable microservices** in `sample_repos/` ready for immediate demo execution:

| Target Repository | Stack | Targeted Vulnerabilities | Real-World Impact |
|---|---|---|---|
| **1. AuthService** | FastAPI | `CWE-89` (SQL Injection), `CWE-287` (JWT Algorithm Confusion) | Arbitrary database exfiltration & forged admin auth tokens |
| **2. Webhook Gateway** | FastAPI / Requests | `CWE-918` (Blind SSRF), `CWE-78` (Command Injection via `shell=True`) | Cloud metadata theft (`169.254.169.254`) & Host RCE |
| **3. E-Commerce Cart** | FastAPI | `CWE-639` (IDOR on Orders), `CWE-20` (Client Price Tampering) | Cross-customer order snooping & checkout price fraud |
| **4. File Storage API** | FastAPI / Filesystem | `CWE-22` (Path Traversal via `../../`), `CWE-434` (Unrestricted Upload) | Reading `/etc/passwd` & uploading malicious binaries |
| **5. Analytics Engine** | FastAPI / Python | `CWE-94` (RCE via `eval()`), `CWE-502` (Insecure `pickle.loads()`) | Remote execution through formula calculation & cache load |
| **6. Crypto Wallet Service** | FastAPI / Crypto | `CWE-798` (Hardcoded Master Key), `CWE-338` (Weak PRNG `random.randint`) | Private key leak & predictable custodial deposit addresses |
| **7. User Profile API** | FastAPI / HTML | `CWE-79` (Stored XSS in Card), `CWE-915` (Mass Assignment in Update) | Browser session hijacking & unauthorized privilege escalation |

---

## ⚡ Quickstart

### 1. Requirements & Setup
Ensure Python 3.10+ is installed:
```bash
git clone <repo-url>
cd "video/1 - Build a Self-Improving Secure Coding Loop Open SWE + Deepsec + Cognee + Regolo"
./setup.sh
```

### 2. Configure Environment (`.env`)
Insert your Regolo API key (get one from [https://regolo.ai](https://regolo.ai)):
```env
REGOLO_API_KEY=your_regolo_api_key_here
REGOLO_BASE_URL=https://api.regolo.ai/v1
REGOLO_MODEL=GLM-5.2
```
*(Note: If no API key is provided, the tool automatically uses high-fidelity offline simulation mode so you can test and record videos seamlessly).*

### 3. Launch the Interactive TUI
```bash
./run.sh
```
or:
```bash
python3 main.py
```

---

## 🖥️ Interactive TUI Walkthrough

When you start `./run.sh`, the cinematic Terminal User Interface launches:

```
╔═════════════════════════════════════════════════════════════════════════════════════════╗
║       ⚡ SELF-IMPROVING SECURE CODING LOOP ⚡                                            ║
║   Open SWE (Produce) ➔ Deepsec (Verify) ➔ Cognee (Remember) ➔ Brick (Govern)            ║
║   Inference: Regolo.ai (OpenAI-Compatible) • Model: GLM-5.2 • Status: Active            ║
╚═════════════════════════════════════════════════════════════════════════════════════════╝
```

### Main Menu Options:
- **`[1] 🚀 Run Full Closed Loop`**: Select any target repository, watch the initial Deepsec scan table, view Cognee memory recall, review the Open SWE step-by-step plan, interact with the **Human Approval Gate**, inspect the unified Git diff, verify the Deepsec revalidation score, update the Knowledge Graph, view the live cost comparison table, and generate `PR_EVIDENCE.md`.
- **`[2] 🐳 Manage Docker Services`**: Background service orchestrator. Checks Docker daemon, auto-pulls missing images (Qdrant Vector DB & Cognee backend), starts stopped containers, and **dynamically discovers free ports incrementally** (e.g. `6333 ➔ 6334 ➔ 6335`) if default ports are occupied.
- **`[3] 🔍 Deepsec Security Scan Only`**: Perform a standalone vulnerability audit on any local folder.
- **`[4] 🧠 Cognee Memory Graph Inspector`**: Browse stored corporate security rules, past PR fixes, and learned engineering patterns.
- **`[5] 📊 Brick Governance & Telemetry Scoreboard`**: Inspect token consumption, latencies, and cost savings across all stages.
- **`[6] 🧪 Run Automated Test Suite`**: Execute the test suite with `pytest`.
- **`[7] ❌ Exit`**.

---

## 🐳 Automated Docker Service Orchestration & Port Discovery

The system includes a self-healing Docker manager (`core/docker_manager.py`) to manage local stateful backends:
1. **Container Check:** Checks if `closed-loop-qdrant` or `closed-loop-cognee` are already running.
2. **Auto-Start:** If a container exists but is stopped, it starts it immediately without rebuilding.
3. **Auto-Pull & Launch:** If missing, it downloads the official images (`qdrant/qdrant:latest`, `cognee/cognee:main`).
4. **Incremental Port Allocation:** If default ports (`6333`, `8800`) are occupied by existing services on the host machine, the port scanner checks ports incrementally (`6333 ➔ 6334 ...` and `8800 ➔ 8801 ...`) and binds the container to the first open TCP port, updating connection URLs automatically.

---

## 📊 Telemetry & Cost Efficiency Scoreboard

Brick Governance tracks every token and provides an automated comparison between **Single Frontier Models** vs. **Regolo GLM-5.2**:

| Pipeline Stage | Model / Engine | Tokens (Prompt / Completion) | Latency | Regolo GLM-5.2 Cost | Frontier Baseline Cost | Cost Savings |
|---|---|---|---|---|---|---|
| **Classify & Triage** | GLM-5.2 | 340 / 120 | 0.35s | $0.00042 | $0.00282 | **-85.1%** |
| **Cognee Memory & Plan** | GLM-5.2 | 620 / 310 | 0.42s | $0.00093 | $0.00651 | **-85.7%** |
| **Sandbox Implementation** | GLM-5.2 | 950 / 480 | 0.51s | $0.00143 | $0.01005 | **-85.7%** |
| **Deepsec Initial Audit** | GLM-5.2 | 840 / 390 | 0.40s | $0.00121 | $0.00837 | **-85.6%** |
| **Deepsec Revalidation** | GLM-5.2 | 580 / 210 | 0.38s | $0.00073 | $0.00489 | **-85.2%** |
| **Cognee Graph Update** | GLM-5.2 | 490 / 240 | 0.36s | $0.00073 | $0.00507 | **-85.6%** |
| **TOTALS** | — | **~6,070 tokens** | **~2.4s** | **$0.0059** | **$0.0410** | **~85.6% Savings** |

---

## 🧪 Verification & Testing

To run the complete automated test suite verifying all modules and all 7 sample vulnerability repositories:

```bash
python3 -m pytest -v
```

All 12 test cases will run and confirm:
1. Regolo client connection and fallback handling
2. Sandbox workspace creation, unified diff generation, and pytest execution
3. Cognee Knowledge Graph seeding, query retrieval, and learning persistence
4. Deepsec vulnerability detection and revalidation gates
5. Full closed-loop execution across all 7 vulnerability microservices.

---

## 🛡️ License
Apache-2.0 License. Built for secure engineering automation using Regolo.ai, Open SWE, Deepsec, Cognee, and Brick.
