# Regolo Labs: Production AI Playbooks

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Runnable Code](https://img.shields.io/badge/Code-Runnable%20Examples-1F9D55)
![GPU Ready](https://img.shields.io/badge/GPU-100%25%20Ready-0A84FF)
![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI%20Compatible-black)

Runnable playbooks for building sharp, production-ready AI workflows with Regolo.
Each folder includes code, setup notes, and a companion article.

### 🎁 Get Started Free of Use for 30 Days

Sign up for Regolo and get **30 days free and 70% off for next 3 months:**

[Get Started](https://regolo.ai) · [**REGOLO FREE TRIAL**](https://regolo.ai/pricing)

[Regolo Platform](https://regolo.ai)

[Models Library](https://regolo.ai/models-library/)

[Documentation & Guides](https://regolo.ai/docs)

[Discord & Support](https://discord.gg/wHxwWCC8)

---

Welcome to the **Regolo.ai** tutorials repository.

This collection focuses on practical, runnable AI examples for developers and product teams.
Each tutorial is designed to be easy to follow, easy to run, and easy to adapt.

## What You Get
- Ready-to-run AI blueprints
- Practical implementation notes
- OpenAI-compatible Regolo integrations
- Examples focused on real workflows, not toy demos

## Why teams use these tutorials
- Faster setup with minimal moving parts
- Code structured for real-world usage
- Clear article-to-code mapping
- Regolo-hosted workflows with a production-friendly API

## Focus Areas
- Multi-agent systems for launch automation and campaign execution
- Enterprise support and operations workflows
- RAG pipelines with retrieval, reranking, and evaluation
- Predictable orchestration for policy-constrained AI behavior

## Tutorials

| Tutorial | Description | Labels | Article Link |
|----------|-------------|--------|--------------|
| **[Clawdbot Knowledge Base](clawdbot-knowledge-base/)** | Internal knowledge bot with hybrid retrieval (embeddings + BM25 + reranker) and Telegram interface. | `Python` · `Runnable` · `GPU 100% Ready` | [Read Article](https://regolo.ai/build-an-internal-knowledge-bot-with-clawdbot-embeddings-rerank-chat-in-30-minutes/) |
| **[CrewAI Product Launch Campaign](crewai-product-launch-campaign/)** | Automated product launch system with crewAI multi-agent workflow and Regolo infrastructure. | `Python` · `Runnable` · `GPU 100% Ready` | [Read Article](https://regolo.ai/build-multi-agent-workflows-with-crewai-teams/) |
| **[Cheshire Cat AI + Regolo: Enterprise AI Agent Setup](from-zero-to-hero-cheshire-cat-and-regolo/)** | Enterprise-ready AI agent setup via OpenAI-compatible API and open models. | `Python` · `Runnable` · `GPU 100% Ready` | [Read Article](https://regolo.ai/from-zero-to-an-enterprise-ready-ai-agent-with-cheshire-cat-and-regolo-a-practical-guide-using-only-open-source-llms/) |
| **[Build Faster: LLMaaS with Qwen 3.5 122b](build-faster-llm-as-a-service-for-developers-with-qwen-3-5-122b/)** | Practical LLMaaS patterns for developers: boilerplate generation, streaming assistant, lightweight RAG, and structured extraction. | `Python` · `Runnable` · `GPU 100% Ready` | [Read Article](https://regolo.ai/build-faster-llm-as-a-service-for-developers-with-qwen-3-5-122b/) |
| **[Orchestrating Predictable AI Agents with Parlant and Regolo](orchestrating-predictable-ai-agents-with-parlant-and-regolo/)** | Deterministic policy orchestration with Parlant-style control layer and Regolo backend. | `Python` · `Runnable` · `GPU 100% Ready` | [Read Article](https://regolo.ai/orchestrating-predictable-ai-agents-with-parlant-and-regolo/) |
| **[Advanced RAG in 2026: Long Context Is Not Memory](advanced-rag-in-2026-long-context-is-not-memory/)** | Enterprise ticket triage that uses Regolo for structured incident analysis, escalation, and mitigation planning. | `Python` · `Runnable` · `Enterprise Triage` | [Read Article](https://regolo.ai/advanced-rag-in-2026-long-context-is-not-memory/) |
| **[Programmatic Tool Calling on Regolo GPUs](programmatic-tool-calling-how-to-build-smarter-llm-agents-on-regolo-gpus/)** | Build smarter agents with classic JSON tool calling and programmatic tool calling using a restricted runtime and multi-step orchestration. | `Python` · `Runnable` · `GPU 100% Ready` | [Read Article](https://regolo.ai/programmatic-tool-calling-how-to-build-smarter-llm-agents-on-regolo-gpus/) |
| **[Production-Ready RAG on Open Models](production-ready-RAG-on-open-models/)** | End-to-end production RAG: chunking, retrieval, reranking, evaluation, and optimization. | `Python` · `Runnable` · `GPU 100% Ready` | [Read Article](https://regolo.ai/production-ready-rag-on-open-models-chunking-retrieval-reranking-evaluation/) |
| **[Build Hybrid Inference Stack Without Sacrificing Quality](build-hybrid-inference-stack/)** | Regolo-only incident triage demo with colored logs, local `.env` loading, and structured JSON responses. | `Python` · `Runnable` · `Logging` | [Read Article](https://regolo.ai/small-language-models-are-growing-up-how-to-build-a-hybrid-inference-stack-without-sacrificing-quality/) |
| **[LLM Architectures in 2026: Optimize for What Matters, Not Benchmarks](llm-architectures-optimize-for-instead-of-chasing-benchmarks/)** | A lightweight architecture router that loads `.env`, reads `REGOLO_CORE_MODEL`, and selects a Regolo model before sending the request. | `Python` · `Runnable` · `Model Routing` | [Read Article](https://regolo.ai/new-llm-architectures-in-2026-what-ctos-should-optimize-for-instead-of-chasing-benchmarks/) |
| **[AI Agents and Tool Chaining in 2026](ai-agents-and-tool-chaining-in-2026/)** | Contract-review workflow that chains extraction, reranking, and policy decisions into one runnable script. | `Python` · `Runnable` · `Workflow` | [Read Article](https://regolo.ai/ai-agents-and-tool-chaining-in-2026-how-to-build-workflows-that-actually-finish-the-job/) |
| **[How to Build a PR Review Assistant](how-to-build-a-pr-review-assistant/)** | Automated PR review assistant that reads local `.env` settings, picks a model, and reviews Git diffs through Regolo. | `Python` · `Runnable` · `Code Review` | [Read Article](https://regolo.ai/ai-native-software-development-how-to-build-a-pr-review-assistant-with-regolo-instead-of-another-generic-copilot/) |
| **[AI Governance & Copyright Policy Gateway](ai-governance-copyright/)** | Policy gateway example con rimozione PII, classificazione BLOCK/ALLOW/TRANSFORM e compliance in due fasi. | `Python` · `Runnable` · `Governance` | [Read Article](https://regolo.ai/ai-governance-copyright-and-enterprise-risk-how-to-build-a-policy-gateway-before-you-ship/) |
| **[OpenClaw vs Hermes Agent Memory Benchmark](openclaw-hermes-agent-memory/)** | Direct comparison between Hermes Agent and OpenClaw measuring local RAM, disk, and recall latency on a Regolo backend. | `Python` · `Runnable` · `Agent Memory` | [Read Article](https://regolo.ai/privacy-first-ai-in-europe-zero-retention-sovereignty-and-the-new-risks-we-cannot-ignore/) |
| **[TurboQuant Outperforms Traditional KV Quantization](turboquant-outperforms-traditional-KV-quantization/)** | Official benchmark comparing TurboQuant to classic scalar KV quantization for LLMs. Measures accuracy, bias, KL divergence, and speed. | `Python` · `Benchmark` · `Quantization` | [Read Article](https://regolo.ai/turboquant-benchmark-what-to-measure-what-matters-and-how-to-read-the-results/) |
| **[Run MiroFish with regolo.ai: A Complete Integration Guide](https://regolo.ai/run-mirofish-with-regolo-ai-a-complete-integration-guide/)** | This guide walks you through every step: cloning MiroFish, configuring it to point at regolo.ai, running your first simulation, and tuning for performance. | `Python` · `Runnable` · `GPU 100% Ready` | [Read Article](https://regolo.ai/run-mirofish-with-regolo-ai-a-complete-integration-guide/) |
| **[Accelerate LLM Inference with DFlash Speculative Decoding](accelerate-llm-inference-dflash/)** | Train and serve a DFlash block-diffusion speculator with vLLM. Generates up to 15 candidate tokens in one parallel forward pass for 3–5× throughput gains with mathematically lossless output. | `Python` · `vLLM` · `GPU 100% Ready` | [Read Article](https://regolo.ai/train-run-dflash-speculative-decoding-vllm/) |
| **[Context Engineered Agent](context-engineered-agent/)** | Compact demo of context engineering for long-horizon agents: just-in-time data ingestion, active compaction, structured external memory, and sub-agent isolation — all without prompt stuffing. | `Python` · `Runnable` · `Ollama Compatible` | [Read Article](https://regolo.ai/context-engineering-tutorial-build-lightweight-local-ai-agents-in-python/) |
| **[Stateful Agent Memory & Dreaming Pipeline](dreaming_agents_that_remember/)** | Three-layer memory architecture inspired by Anthropic's memory system. Decouples live runtime execution from background contextual database consolidation. Supports Ollama and Regolo backends. | `Python` · `Runnable` · `Agent Memory` | [Read Article](https://regolo.ai/implementing-stateful-ai-agents-how-to-build-anthropics-memory-store-and-dreaming-architecture-in-python/) |
| **[StockPilot — Decomposed AI Agent (Anthropic Workshop Style)](decompose-agent-anthropic-workshops-open-source/)** | Inventory management agent that routes queries to specialized subagents and code-execution tools. Implements the decomposed agent pattern with skill-specific context injection and verifiable results. | `Python` · `Runnable` · `GPU 100% Ready` | — |

### How to Use
1. Clone this repository: `git clone https://github.com/yourusername/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md.
4. Check out the full article for detailed explanations.

### Fast Start
1. Pick one tutorial and configure `.env`.
2. Run the local setup from that folder README.
3. Launch your first production-ready AI feature.

### Startup Playbook
1. Start with the use case closest to revenue or cost reduction.
2. Deploy a pilot in one team, measure response quality and throughput.
3. Expand to additional workflows once baseline KPIs are stable.

## Contributing
Feel free to contribute by adding new tutorials or improving existing ones. Please follow the contribution guidelines.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Powered by [Regolo.ai](https://regolo.ai)* 
