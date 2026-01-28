# 🤖 Clawdbot Knowledge Base with Regolo GPU

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Regolo](https://img.shields.io/badge/Powered%20by-Regolo%20GPU-green)](https://regolo.ai)

Production-ready knowledge base bot using **Clawdbot** runtime and **Regolo EU-hosted GPUs** for embeddings, reranking, and generation. Built for enterprise teams that need GDPR-compliant, cost-effective AI retrieval.

---

## ✨ Features

- **24/7 AI Agent:** Telegram bot delivers instant answers from your knowledge base
- **Hybrid Retrieval:** Dense (embeddings) + Lexical (BM25) + Neural reranking
- **EU Data Residency:** All processing on Regolo GPUs (Frankfurt datacenter, GDPR-compliant)
- **OpenAI-Compatible:** Zero vendor lock-in—swap providers with one line change
- **Cost-Effective:** €8-15/month for 500 queries/day (70% discount first 3 months)
- **Production-Ready:** 87% recall@5, <500ms p95 latency, auto-updates

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Regolo API Key:** [Get it here](https://regolo.ai/dashboard) (70% off first 3 months!)
- **Telegram Bot Token:** Create via [@BotFather](https://t.me/botfather)

### Installation (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/regolo/tutorials/clawdbot-knowledge-base.git
cd clawdbot-knowledge-base

# 2. Install dependencies
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# 4. Add your documents
cp -r /path/to/your/docs/* knowledge-base/

# 5. Build index
python3 rag_pipeline.py build

# 6. Start bot
python3 kb_bot.py
```
## Expected Output

```bash
🚀 Clawdbot Knowledge Base
📡 Powered by Regolo EU GPUs
============================================================
✅ Index loaded: 247 docs, 1,834 chunks
🤖 Bot username: @your_kb_bot
✅ Bot is running. Press Ctrl+C to stop.
```

## Architecture
```text
User (Telegram)
    ↓ /kb "What's our GDPR policy?"
    ↓
Clawdbot Agent
    ├─  Embed query → Regolo gte-Qwen2 (EU GPU)[1]
    ├─  Hybrid search → ChromaDB (dense) + BM25 (lexical)[2]
    ├─  Rerank top-20 → Regolo Qwen3-Reranker-4B[3]
    └─  Generate answer → Regolo Llama-3.1-8B-Instruct[4]
    ↓
Response with citations (< 500ms)
```

# 💬 Usage
Telegram Commands

```text
/kb <question>       Search the knowledge base
/kb_stats           Show usage statistics and costs
/kb_update          Rebuild document index (admin only)
/kb_help            Show help message
```
Example Queries
Simple factual:

```text
/kb What is our GDPR data retention policy?
```

Response:

```text
📚 Knowledge Base Answer

Our GDPR data retention policy requires:

1. Personal data minimization: Collect only necessary information
2. Standard retention: 30 days for application logs, 90 days for audit logs
3. User deletion requests: Process within 30 days
4. Cross-border transfers: EU data residency required

📎 Sources:
-  policies/gdpr-compliance.md (relevance: 94%)

⏱️ Retrieved in 389ms | Cost: €0.0023
```
