<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# 🤖 Clawdbot Knowledge Base with Regolo GPU

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

This repository contains all the code from the guide [Build an Internal Knowledge Bot with Clawdbot: Embeddings + Rerank + Chat in 30 Minutes](https://regolo.ai/build-an-internal-knowledge-bot-with-clawdbot-embeddings-rerank-chat-in-30-minutes/) — ready to test and deploy.

--- 
### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.

> [!IMPORTANT]  
> ## 🎁 Special Offer: 30 Days Free Trial
> 
> To power your AI agent, you need an API key. Sign up for Regolo today and get **30 days completely free**, plus a massive **70% discount for the following 3 months!**
> 
> 🚀 **[CLICK HERE TO GET STARTED AND CLAIM YOUR FREE TRIAL](https://regolo.ai/pricing)** 🚀
> 
> ---
> **Explore Regolo:** [Platform](https://regolo.ai) | [Models Library](https://regolo.ai/models-library/) | [Documentation & Guides](https://regolo.ai/docs) | [YouTube](https://www.youtube.com/@regoloai) | [Discord](https://discord.gg/wHxwWCC8)
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
