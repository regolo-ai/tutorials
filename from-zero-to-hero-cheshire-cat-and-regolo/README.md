# Cheshire Cat AI + Regolo: Enterprise AI Agent Setup

**Production-ready AI agent using open-source LLMs via OpenAI-compatible API**

This repository contains all the code from the guide ["From Zero to an Enterprise-Ready AI Agent with Cheshire Cat and Regolo"](https://regolo.ai/from-zero-to-an-enterprise-ready-ai-agent-with-cheshire-cat-and-regolo-a-practical-guide-using-only-open-source-llms/) — ready to test and deploy.

---

## What This Is

A complete setup that combines:

- **[Cheshire Cat AI](https://cheshirecat.ai)**: Open-source AI agent framework with conversation memory, plugins, and REST API
- **[Regolo.ai](https://regolo.ai)**: European LLM inference and service provider with OpenAI-compatible endpoint and 100% Green
- **Open-source models**: Llama 3.3 70B Instruct, gpt-oss-120b, and others

### What You Get

- ✅ Docker-based Cheshire Cat deployment with persistent storage
- ✅ Pre-configured connection to Regolo's OpenAI-compatible API
- ✅ Python client library for direct Regolo API calls
- ✅ Test suite to verify your setup
- ✅ Example Cheshire Cat plugin using Regolo models
- ✅ Ready for enterprise: memory, tools, authentication, extensibility

---

## 📋 Prerequisites

Before starting, make sure you have:

1. **Docker & Docker Compose** installed
   ```bash
   docker --version
   docker compose version
   ```

2. **Regolo API Key**
   - Sign up at [regolo.ai](https://regolo.ai)
   - Generate an API key from your dashboard
   - Keep it secure (never commit to Git)

3. **Python 3.8+** (for testing the client library)
   ```bash
   python3 --version
   ```

---

## 🚀 Quick Start (5 minutes)

### Step 1: Clone and Configure

```bash
# Clone this repository
git clone <your-repo-url>
cd from-zero-to-hero-cheshire-cat-and-regolo

# Copy environment template
cp env.example .env

# Edit .env and add your Regolo API key
nano .env  # or use your preferred editor
```

Your `.env` should look like:
```bash
REGOLO_API_KEY=sk-proj-your-actual-key-here
REGOLO_MODEL=Llama-3.3-70B-Instruct
```

### Step 2: Start Cheshire Cat

```bash
# Start the container
docker compose up -d

# Verify the container is running
docker compose ps

# Check logs (if no output, container may not be running - check with 'docker compose ps')
docker compose logs -f cheshire-cat
```

Wait ~30 seconds for initialization.

### Step 3: Access the Admin UI

Open in your browser:
```
http://localhost:1865/admin
```

Default credentials:
- Username: `admin`
- Password: `admin`

⚠️ **Change these immediately in production!**

### Step 4: Configure LLM Provider

In the Cheshire Cat admin UI:

1. Go to **Settings → Large Language Model**
2. Select provider: **"OpenAI-compatible API"** (or similar)
3. Fill in:
   - **API Base URL**: `https://api.regolo.ai/v1`
   - **API Key**: Your `REGOLO_API_KEY`
   - **Model**: `Llama-3.3-70B-Instruct`
   - **Temperature**: `0.2` (start here)
4. Click **Save**

### Step 5: Test the Connection

Go to the **Chat** tab and send:
```
You are now using Regolo as your LLM backend. Confirm this in one sentence.
```

If you get a response, you're live! 🎉

---

## 🧪 Testing the Python Client

The repository includes a standalone Python client for Regolo that you can use in scripts, tests, or plugins.

### Install Dependencies

```bash
# Install required packages
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Run the Test Suite

```bash
# Load your API key
export REGOLO_API_KEY=your_key_here

# Run all tests
python test_regolo.py
```

You should see:
```
============================================================
Regolo API Integration Test Suite
============================================================

[TEST 1] Basic completion...
Response: Hello from Regolo!
✓ PASSED

[TEST 2] Technical query...
Response: OpenAI-compatible APIs are useful for AI agents because they provide a standardized interface for accessing advanced language models and other AI capabilities, enabling agents to leverage powerful AI functionality without requiring extensive development or maintenance efforts. By integrating with OpenAI-compatible APIs, AI agents can tap into a wide range of AI-powered features, such as natural language processing, text generation, and conversational understanding, to enhance their overall intelligence and capabilities.
✓ PASSED

[TEST 3] Multi-turn conversation...
Response: Your name is Alice.
✓ PASSED

[TEST 4] Temperature variation...
Low temp (0.1): Here are some creative startup name ideas for an AI company:

1. **Augmend**: A combination of "augment" and "amend," suggesting the enhancement and improvement of human capabilities through AI.
2. **Cognita**: Derived from the Latin word "cognitio," meaning knowledge or understanding, implying a deep understanding of AI and its applications.
3. **NexaMind**: A combination of "nexus" and "mind," suggesting a connection between human and artificial intelligence.
4. **Luminari**: Inspired by the word "luminary," implying a bright and innovative approach to AI.
5. **PulseAI**: Suggesting the rhythmic and dynamic nature of AI, with "pulse" implying energy and vitality.
6. **Synapsea**: Derived from "synapse," the connection between neurons, and "sea," implying a vast and expansive approach to AI.
7. **Aurora Labs**: Inspired by the breathtaking natural light display of the aurora borealis, suggesting a company that illuminates new possibilities with AI.
8. **Cerebrox**: A combination of "cerebral" and "box," implying a company that thinks outside the box and pushes the boundaries of AI.
9. **MindSprint**: Suggesting a company that accelerates innovation and progress in AI, with "sprint" implying speed and agility.
10. **AxionAI**: Derived from the word "axion," a hypothetical particle in physics, implying a company that explores the unknown and pushes the frontiers of AI.

Choose the one that resonates with your vision and mission, or feel free to modify these suggestions to create a unique name that reflects your brand identity!
High temp (0.9): Here are some creative startup name ideas for an AI company:

1. **Aximo**: A combination of "axis" and "maximize," suggesting a company that helps customers maximize their potential with AI.
2. **Luminari**: Derived from "luminary," implying a company that sheds light on the possibilities of AI and illuminates the path to innovation.
3. **Cognita**: A play on "cognition," highlighting the company's focus on artificial intelligence and cognitive computing.
4. **Nexa**: Short for "nexus," implying a connection or link between humans, machines, and AI.
5. **PulseAI**: Suggesting a company that has its finger on the pulse of AI innovation and is always ahead of the curve.
6. **Augmend**: A combination of "augment" and "amend," implying a company that enhances and improves human capabilities with AI.
7. **SynapseAI**: Referencing the connections between neurons in the human brain, suggesting a company that facilitates connections between humans, machines, and AI.
8. **Kaidō**: A Japanese-inspired name that means "firm, strong, and steadfast," conveying a sense of reliability and trust in AI solutions.
9. **MindSprint**: Implying a company that helps customers accelerate their progress and achieve their goals with AI-powered solutions.
10. **Apexion**: A combination of "apex" and "ion," suggesting a company that helps customers reach the pinnacle of success with AI-driven innovation.

Choose the one that resonates with your vision and values, or feel free to modify these suggestions to fit your startup's unique identity!
✓ PASSED

============================================================
✓ All tests passed!
============================================================
```

### Use the Client in Your Code

```python
from regolo_client import regolo_chat

# Simple completion
response = regolo_chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain OpenAI-compatible APIs in 2 sentences."}
    ],
    temperature=0.2
)

print(response)
```

---

## 🔌 Installing the Cheshire Cat Plugin

The `plugins/regolo_tools/` directory contains a sample plugin with two tools:

1. **summarize_text**: Summarize long documents into bullet points
2. **technical_qa**: Answer technical questions with context

### Installation

```bash
# Copy the plugin to Cheshire Cat's plugin directory
cp -r plugins/regolo_tools cat-data/plugins/

# Restart Cheshire Cat to load the plugin
docker compose restart cheshire-cat
```

### Usage

In the Cheshire Cat chat:

```
Summarize this text: [paste long email or meeting notes]
```

or

```
Technical question: Should I use microservices or a monolith for a 5-person startup?
```

The plugin calls Regolo directly, so you can customize prompts, temperature, and models per tool.

---

## 📁 Repository Structure

```
cheshire-regolo-agent/
├── docker-compose.yml          # Cheshire Cat container config
├── .env.example                # Environment template (copy to .env)
├── .gitignore                  # Ignore secrets and generated files
├── requirements.txt            # Python dependencies
├── regolo_client.py            # Standalone Regolo API client
├── test_regolo.py              # Test suite for API integration
├── plugins/
│   └── regolo_tools/
│       ├── __init__.py         # Plugin metadata
│       └── summarizer.py       # Example tools (summarize, QA)
├── cat-data/                   # Created by Docker (persistent storage)
└── README.md                   # This file
```

---

## 🛠️ Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REGOLO_API_KEY` | ✅ Yes | — | Your Regolo API key |
| `REGOLO_MODEL` | ❌ No | `Llama-3.3-70B-Instruct` | You can use any models you want |

### Cheshire Cat LLM Settings

Configure in the admin UI under **Settings → Large Language Model**:

- **API Base URL**: `https://api.regolo.ai/v1` (fixed)
- **Model**: Choose from [Regolo's model library](https://regolo.ai/models-library/)
  - `Llama-3.3-70B-Instruct` (recommended for most tasks)
  - `gpt-oss-120b` (larger, more capable)
  - Other open-source models available
- **Temperature**: `0.1`-`0.3` for deterministic, `0.7`-`1.0` for creative
- **Max Tokens**: Adjust based on use case (default varies by model)

### Available Models on Regolo

Check the full list at: **https://regolo.ai/models-library/**

Popular choices:
- `Llama-3.3-70B-Instruct` — Best balance of quality and cost
- `Llama-3.1-8B-Instruct` — Fast, lightweight
- `gpt-oss-120b` — Higher capability for complex reasoning

---

## 🔒 Security & Production Notes

### API Key Management

- **Never commit** `.env` to Git (it's in `.gitignore`)
- Use **secret managers** (AWS Secrets Manager, HashiCorp Vault) in production
- Rotate keys regularly
- Use **separate keys** per environment (dev, staging, prod)

### Cheshire Cat Security

- **Change default admin password** immediately
- Run behind a **reverse proxy** (nginx, Traefik) with TLS
- Enable **authentication** for the REST API
- Use Docker secrets or env files for sensitive config

### Data Flow & Privacy

- **Conversation state**: Stored locally in `cat-data/` (controlled by you)
- **LLM inference**: Only prompts sent to Regolo (stateless)
- **Regolo**: EU-based hosting, GDPR-compliant, no data retention by default

Check [Regolo's privacy policy](https://regolo.ai) for details.

### Monitoring & Observability

For production, add:

- **Request logging**: Track token usage and costs
- **Latency metrics**: Measure TTFT (Time To First Token) and TPOT (Time Per Output Token)
- **Error handling**: Implement retries, circuit breakers, fallback models
- **Rate limiting**: Respect Regolo's rate limits, add client-side throttling

Example with Python:
```python
import time
from regolo_client import regolo_chat

start = time.time()
response = regolo_chat([...])
latency = time.time() - start

print(f"Response time: {latency:.2f}s")
```

---

## 🐛 Troubleshooting

### "REGOLO_API_KEY environment variable is not set"

**Solution**: Make sure you:
1. Created `.env` from `.env.example`
2. Added your actual API key
3. Restarted Docker Compose: `docker compose down && docker compose up -d`

### Cheshire Cat won't start

**Check logs**:
```bash
docker compose logs cheshire-cat
```

Common issues:
- Port 1865 already in use → change port in `docker-compose.yml`
- Permission issues on `cat-data/` → `chmod -R 755 cat-data/`

### "Connection refused" or timeout errors

**Check**:
1. Your API key is valid (test at https://regolo.ai dashboard)
2. Your machine has internet access to `api.regolo.ai`
3. Firewall isn't blocking port 443

### Plugin not loading

**Debug**:
```bash
# Check if plugin directory is mounted
docker compose exec cheshire-cat ls /app/.cheshire-cat/plugins/

# Check Cheshire Cat logs for plugin errors
docker compose logs cheshire-cat | grep -i plugin
```

---

## 📊 Cost & Performance

### Typical Costs (Regolo)

Based on Llama-3.3-70B-Instruct pricing:

- **Input**: ~$0.30 per 1M tokens
- **Output**: ~$0.60 per 1M tokens

Example: 100 conversations/day × 2000 tokens avg = ~$12-18/month

Check latest pricing: [https://regolo.ai/subscriptions](https://regolo.ai)

### Expected Latency

| Model | Context | TTFT | Throughput |
|-------|---------|------|------------|
| Llama-3.3-70B | 8k tokens | ~300ms | ~50 tok/s |
| Llama-3.1-8B | 8k tokens | ~150ms | ~100 tok/s |

*Varies by region, load, and prompt complexity*

---

## 🔄 Next Steps

### Extend Your Agent

1. **Add more tools**: Integrate APIs, databases, internal services
2. **Build RAG pipelines**: Use vector stores (Qdrant, Pinecone) for knowledge retrieval
3. **Multi-agent workflows**: Combine multiple Cheshire Cat instances
4. **Automation**: Connect to n8n, Langflow, or custom orchestrators

### Learn More

- **Cheshire Cat docs**: https://cheshire-cat-ai.github.io/docs/
- **Regolo guides**: https://regolo.ai/blog
- **OpenAI API reference**: https://platform.openai.com/docs/api-reference (same schema)

### Community & Support

- **Regolo Discord**: Join for integration help and updates
- **Cheshire Cat GitHub**: https://github.com/cheshire-cat-ai/core
- **X/Twitter**: Follow [@regolo_ai](https://x.com/regolo_ai) for news

---

## 📝 License

This code is provided as example/reference material for the Regolo.ai blog guide.

- **Cheshire Cat AI**: Licensed under GPL-3.0
- **Regolo client code**: MIT License (feel free to adapt for your projects)

---

## 🙋 Contributing

Found a bug or want to improve this setup?

1. Open an issue describing the problem
2. Submit a PR with your fix
3. Share your use case in the Regolo community

---

## ⚡ Quick Reference Card

```bash
# Start agent
docker compose up -d

# View logs
docker compose logs -f

# Stop agent
docker compose down

# Run tests
python test_regolo.py

# Access UI
open http://localhost:1865/admin

# Restart after config change
docker compose restart cheshire-cat
```

---

**Built by developers, for developers** 🚀

Questions? Reach out to our [Discord](https://discord.gg/gVcxQz7Y) or visit https://regolo.ai

---

*Last updated: January 2026*
