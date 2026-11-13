<div align="center">
  <a href="https://regolo.ai/?utm_source=github&utm_medium=readme&utm_campaign=tutorials">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://regolo.ai/wp-content/themes/regolo/img/regolo-logo.svg" />
      <img src="static-assets/regolo-logo-light-background.svg" alt="Regolo.ai logo" width="320" />
    </picture>
  </a>
</div>

<div align="center">
  <h1>Regolo Labs tutorials for AI agents, RAG and LLM inference</h1>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: runnable examples" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="OpenAI-compatible API" />
  <img src="https://img.shields.io/badge/MCP-Ready-7c3aed.svg" alt="MCP ready" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<div align="center">
  <br />
  <a href="https://regolo.ai/pricing?utm_source=github&utm_medium=readme&utm_campaign=tutorials">
    <img src="https://img.shields.io/badge/Get_a_free_API_key-30_days_free-05df72?style=for-the-badge" alt="Get a free API key: 30 days free" />
  </a>
  <br /><br />
</div>

Runnable playbooks for building AI agents, retrieval-augmented generation (RAG), MCP tools and LLM evaluation on Regolo.ai. Regolo serves open-weight models such as Qwen, GLM, Gemma and gpt-oss through an OpenAI-compatible API, hosted in European data centers. Each folder includes working code, setup notes and a companion article on regolo.ai.

> [!IMPORTANT]
> ## Get 30 days free and 70% off for 3 months
>
> Every tutorial needs an API key. Sign up on Regolo to get **30 days completely free**, plus a **70% discount for the following 3 months**.
>
> 🚀 **[Start your free trial on regolo.ai](https://regolo.ai/pricing?utm_source=github&utm_medium=readme&utm_campaign=tutorials)** 🚀
>
> ---
> **Explore Regolo:** [Platform](https://regolo.ai/?utm_source=github&utm_medium=readme&utm_campaign=tutorials) | [Models library](https://regolo.ai/models-library/?utm_source=github&utm_medium=readme&utm_campaign=tutorials) | [Docs and guides](https://docs.regolo.ai/?utm_source=github&utm_medium=readme&utm_campaign=tutorials) | [YouTube](https://www.youtube.com/@regoloai) | [Discord](https://discord.gg/wHxwWCC8)

---

## Why Regolo

- **OpenAI-compatible.** Point your existing OpenAI SDK at `https://api.regolo.ai/v1` and keep your code.
- **Open-weight models.** Choose the right model for each task, from compact models to the 122B-parameter Qwen 3.5 used in several tutorials.
- **European hosting.** Zero Data Retention in EU data centers, powered by renewable energy.
- **Pay as you go or a flat plan.** Start with pay-as-you-go pricing, then compare it with the Core subscription as your usage grows.

## Get started in three steps

1. **Clone the repository:** `git clone https://github.com/regolo-ai/tutorials.git`
2. **Open a tutorial folder** and read its `README.md`.
3. **Get a free API key** on [regolo.ai/pricing](https://regolo.ai/pricing?utm_source=github&utm_medium=readme&utm_campaign=tutorials), export it as `REGOLO_API_KEY`, and run the code.

## Tutorials

| Tutorial | Description | Labels | Article link |
|----------|-------------|--------|--------------|
| **[Private long-term memory for coding agents](AI-agent-cognee-closed-loop-memory/)** | Cognitive long-term memory framework with Cognee Knowledge Graph, vector store, ReAct self-healing loop, and Regolo Zero Data Retention. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/ai-agent-long-term-memory-cognee-regolo/) |
| **[Closed-loop: self-correcting AI code reviewer](closed-loop/)** | Self-correcting AI code reviews with dual-gate verification, Qdrant semantic memory, cross-encoder reranking, and persistent skill accumulation. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/how-to-build-a-closed-loop-ai-agent-that-catches-its-own-hallucinations/) |
| **[Self-improving secure coding loop](self-Improving-secure-coding-loop/)** | Memory-augmented secure coding agent with Open SWE, Deepsec verification, Cognee Knowledge Graph, and Regolo GLM-5.2. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/how-to-build-a-closed-loop-ai-agent-that-catches-its-own-hallucinations/) |
| **[Deep agents: tool synthesis with Brick routing](deepagents-multi-agent-brick/)** | Autonomous multi-agent framework with dynamic DAG planning and Brick semantic complexity routing on Regolo.ai. | `Python` · `Runnable` · `GPU 100% Ready` | — |
| **[Clawdbot knowledge base](clawdbot-knowledge-base/)** | Internal knowledge bot with hybrid retrieval (embeddings, BM25 and reranker) and a Telegram interface. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/build-an-internal-knowledge-bot-with-clawdbot-embeddings-rerank-chat-in-30-minutes/) |
| **[CrewAI product launch campaign](crewai-product-launch-campaign/)** | Automated product launch system with a crewAI multi-agent workflow and Regolo infrastructure. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/build-multi-agent-workflows-with-crewai-teams/) |
| **[Cheshire Cat AI and Regolo: enterprise AI agent setup](from-zero-to-hero-cheshire-cat-and-regolo/)** | Enterprise-ready AI agent setup via an OpenAI-compatible API and open models. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/from-zero-to-an-enterprise-ready-ai-agent-with-cheshire-cat-and-regolo-a-practical-guide-using-only-open-source-llms/) |
| **[Build faster: LLM as a service with Qwen 3.5 122B](build-faster-llm-as-a-service-for-developers-with-qwen-3-5-122b/)** | Practical LLM-as-a-service patterns for developers: boilerplate generation, a streaming assistant, lightweight RAG, and structured extraction. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/build-faster-llm-as-a-service-for-developers-with-qwen-3-5-122b/) |
| **[Orchestrating predictable AI agents with Parlant and Regolo](orchestrating-predictable-ai-agents-with-parlant-and-regolo/)** | Deterministic policy orchestration with a Parlant-style control layer and a Regolo backend. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/orchestrating-predictable-ai-agents-with-parlant-and-regolo/) |
| **[Advanced RAG in 2026: long context is not memory](advanced-rag-in-2026-long-context-is-not-memory/)** | Enterprise ticket triage that uses Regolo for structured incident analysis, escalation, and mitigation planning. | `Python` · `Runnable` · `Enterprise triage` | — |
| **[Programmatic tool calling on Regolo GPUs](programmatic-tool-calling-how-to-build-smarter-llm-agents-on-regolo-gpus/)** | Build smarter agents with classic JSON tool calling and programmatic tool calling, using a restricted runtime and multi-step orchestration. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/programmatic-tool-calling-how-to-build-smarter-llm-agents-on-regolo-gpus/) |
| **[Production-ready RAG on open models](production-ready-RAG-on-open-models/)** | End-to-end production RAG: chunking, retrieval, reranking, evaluation, and optimization. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/production-ready-rag-on-open-models-chunking-retrieval-reranking-evaluation/) |
| **[Build a hybrid inference stack without sacrificing quality](build-hybrid-inference-stack/)** | Regolo-only incident triage demo with coloured logs, local `.env` loading, and structured JSON responses. | `Python` · `Runnable` · `Logging` | [Read article](https://regolo.ai/small-language-models-are-growing-up-how-to-build-a-hybrid-inference-stack-without-sacrificing-quality/) |
| **[LLM architectures in 2026: optimize for what matters, not benchmarks](llm-architectures-optimize-for-instead-of-chasing-benchmarks/)** | A lightweight architecture router that loads `.env`, reads `REGOLO_CORE_MODEL`, and selects a Regolo model before sending the request. | `Python` · `Runnable` · `Model routing` | [Read article](https://regolo.ai/new-llm-architectures-in-2026-what-ctos-should-optimize-for-instead-of-chasing-benchmarks/) |
| **[AI agents and tool chaining in 2026](ai-agents-and-tool-chaining-in-2026/)** | Contract-review workflow that chains extraction, reranking, and policy decisions into one runnable script. | `Python` · `Runnable` · `Workflow` | [Read article](https://regolo.ai/ai-agents-and-tool-chaining-in-2026-how-to-build-workflows-that-actually-finish-the-job/) |
| **[How to build a PR review assistant](how-to-build-a-pr-review-assistant/)** | Automated PR review assistant that reads local `.env` settings, picks a model, and reviews Git diffs through Regolo. | `Python` · `Runnable` · `Code review` | [Read article](https://regolo.ai/ai-native-software-development-how-to-build-a-pr-review-assistant-with-regolo-instead-of-another-generic-copilot/) |
| **[AI governance and copyright policy gateway](ai-governance-copyright/)** | Policy gateway example with PII removal, BLOCK, ALLOW and TRANSFORM classification, and two-stage compliance. | `Python` · `Runnable` · `Governance` | [Read article](https://regolo.ai/ai-governance-copyright-and-enterprise-risk-how-to-build-a-policy-gateway-before-you-ship/) |
| **[OpenClaw vs Hermes Agent memory benchmark](openclaw-hermes-agent-memory/)** | Direct comparison between Hermes Agent and OpenClaw, measuring local RAM, disk, and recall latency on a Regolo backend. | `Python` · `Runnable` · `Agent memory` | [Read article](https://regolo.ai/privacy-first-ai-in-europe-zero-retention-sovereignty-and-the-new-risks-we-cannot-ignore/) |
| **[TurboQuant outperforms traditional KV quantization](turboquant-outperforms-traditional-KV-quantization/)** | Official benchmark comparing TurboQuant to classic scalar KV quantization for LLMs. Measures accuracy, bias, KL divergence, and speed. | `Python` · `Benchmark` · `Quantization` | [Read article](https://regolo.ai/turboquant-benchmark-what-to-measure-what-matters-and-how-to-read-the-results/) |
| **[Run MiroFish with regolo.ai: a complete integration guide](run-mirofish-with-regolo-a-complete-integration-guide/)** | Walks you through every step: cloning MiroFish, configuring it to point at regolo.ai, running your first simulation, and tuning for performance. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/run-mirofish-with-regolo-ai-a-complete-integration-guide/) |
| **[Accelerate LLM inference with DFlash speculative decoding](accelerate-llm-inference-dflash/)** | Train and serve a DFlash block-diffusion speculator with vLLM. Generates up to 15 candidate tokens in one parallel forward pass for 3–5× throughput gains with lossless output. | `Python` · `vLLM` · `GPU 100% Ready` | [Read article](https://regolo.ai/train-run-dflash-speculative-decoding-vllm/) |
| **[Context-engineered agent](context-engineered-agent/)** | Compact demo of context engineering for long-horizon agents: just-in-time data ingestion, active compaction, structured external memory, and sub-agent isolation, without prompt stuffing. | `Python` · `Runnable` · `Ollama compatible` | [Read article](https://regolo.ai/context-engineering-tutorial-build-lightweight-local-ai-agents-in-python/) |
| **[Context engineering for agents 101: harness kit for OpenCode, Claude Code and Codex](context-engineering-101/)** | Four runnable modules and an MCP server: progressive skill disclosure, retrieve-offload-delegate, reversible compaction with cache-safe memory, and a long-running harness with an independent evaluator. Measured token savings included. | `Python` · `MCP` · `Runnable` · `Context engineering` | [Read article](https://regolo.ai/context-engineering-for-agents-101-part-1-progressive-disclosure/) |
| **[Stateful agent memory and dreaming pipeline](dreaming_agents_that_remember/)** | Three-layer memory architecture inspired by Anthropic's memory system. Decouples live runtime execution from background database consolidation. Supports Ollama and Regolo backends. | `Python` · `Runnable` · `Agent memory` | [Read article](https://regolo.ai/implementing-stateful-ai-agents-how-to-build-anthropics-memory-store-and-dreaming-architecture-in-python/) |
| **[StockPilot: decomposed AI agent in the Anthropic workshop style](decompose-agent-anthropic-workshops-open-source/)** | Inventory management agent that routes queries to specialized subagents and code-execution tools. Implements the decomposed agent pattern with skill-specific context injection and verifiable results. | `Python` · `Runnable` · `GPU 100% Ready` | — |
| **[Regolo Eval Studio: evaluate open-weight models with Langfuse](langfuse-eval-studio/)** | Local web studio that benchmarks open-weight models on your own dataset, compares PAYG and Core costs, streams traces to Langfuse, and generates a GitHub Actions faithfulness gate. | `Python` · `Langfuse` · `LLM evaluation` | [Read article](https://regolo.ai/tracing-evaluating-open-weight-models-regolo-langfuse/) |
| **[SearXNG private research scraper](searxng-scraper/)** | Private web research agent fleet with a SearXNG search backend, intent-orchestrated six-worker subagent query expansion, topic relevance filtering, spatial chunking, and grounded synthesis on Regolo.ai. | `Python` · `Runnable` · `GPU 100% Ready` | [Read article](https://regolo.ai/self-hosted-web-search-for-ai-agents-replace-tavily-cut-costs-80-and-keep-every-token-private/) |
| **[Advanced local RAG with Regolo and ChromaDB](advanced-rag-regolo/)** | Production RAG pipeline with ChromaDB dense search, BM25 lexical search and Regolo models. | `Python` · `Runnable` · `RAG` | — |
| **[Agentic RAG: hierarchical retrieval and reasoning](agentic-rag/)** | Agentic retrieval that plans, searches in layers and reasons over the results before it answers. | `Python` · `Runnable` · `RAG` | [Read article](https://regolo.ai/agentic-rag-tutorial-build-retrieval-that-reasons/) |
| **[Controlled analytics assistant with LangChain, Qdrant and Regolo](analytics-assistant-chromadb-qdrant/)** | An analytics assistant that answers data questions under explicit guardrails, with Qdrant retrieval on Regolo models. | `Python` · `Runnable` · `Analytics` | [Read article](https://regolo.ai/build-a-controlled-analytics-assistant-with-langchain-qdrant-and-regolo/) |
| **[RAG chatbot widget for websites, auto-updated from the sitemap](autoupdate-agent-for-websites/)** | A website chatbot widget that re-indexes pages from the sitemap, with ChromaDB and LangChain. | `Python` · `Runnable` · `RAG` · `Chatbot` | — |
| **[Closed-loop code reviewer and CI repair agent](ci-repair-agent/)** | An agent that reads failing CI runs, proposes fixes, verifies them with tests and stops on clear limits. | `Python` · `Runnable` · `CI/CD` | [Read article](https://regolo.ai/agent-harness-evaluate-efficiency-production/) |
| **[Project folder to architecture diagram, measured on Regolo](diagram-studio/)** | A local web app and terminal TUI that turns a project folder into an architecture diagram and a Markdown knowledge base for AI agents. | `Python` · `Runnable` · `Architecture` | [Read article](https://regolo.ai/getting-started-diagram-design-regolo-architecture-maps/) |
| **[EmbeddingGemma 2 vs Qwen3-Embedding with reranker benchmarks](embeddinggemma-2-vs-qwen3-embedding/)** | Benchmarks of EmbeddingGemma 2 and Qwen3-Embedding (0.6B and 8B) for code retrieval, with Matryoshka compression and reranking. | `Python` · `Benchmark` · `Embeddings` | [Read article](https://regolo.ai/embeddinggemma-2-vs-qwen3-embedding-benchmarks/) |
| **[Regolo CodeOps ZDR: a zero-data-retention coding harness](harness-agent-zero-data-retention/)** | A coding harness that keeps data under zero data retention, with targeted AST context for coding agents. | `Python` · `Runnable` · `Zero Data Retention` | [Read article](https://regolo.ai/why-git-diffs-break-coding-agents-building-targeted-ast-context-in-python/) |
| **[Codebase comprehension benchmark: context-mode, Headroom and Regolo](headroom-regolo/)** | A benchmark of codebase comprehension with context-mode and Headroom, reducing token cost on large repositories. | `Python` · `Benchmark` · `Context` | [Read article](https://regolo.ai/getting-started-context-mode-headroom-regolo/) |
| **[How to make RAG 32x memory-efficient with binary quantization](how-to-make-rag-32x-efficient/)** | Binary quantization of embeddings that cuts RAG memory by 32x while keeping retrieval quality. | `Python` · `Runnable` · `RAG` | [Read article](https://regolo.ai/how-to-make-rag-32x-memory-efficient-with-binary-quantization/) |
| **[Insurance claims and policy triage with right-sized models](intelligent-insurance-claims-policy-triage/)** | Claims and policy triage with small local models, routing each case to the right level of intelligence. | `Python` · `Runnable` · `Enterprise triage` | [Read article](https://regolo.ai/right-sized-models-insurance-claims-triage/) |
| **[BACO Scanner TUI: local SAST with Regolo](local-sast-baco-scanner/)** | A local static security scanner with a terminal UI, using Regolo models to explain and patch findings. | `Python` · `Runnable` · `Security` | [Read article](https://regolo.ai/local-sast-with-baco-scanner-scan-and-patch-codebases/) |
| **[MCP security gate and AI remediation](mcp-security-gate/)** | A security gate that checks MCP tools for injection and rug-pull risks, with AI-assisted remediation. | `Python` · `Runnable` · `MCP` · `Security` | [Read article](https://regolo.ai/how-to-stop-malicious-mcp-tools-from-hijacking-your-ai-agent/) |
| **[Cross-agent codebase memory and handoffs, measured on Regolo](memory-studio/)** | A web app and terminal TUI that builds a shared memory wiki and handoff brief for coding agents, and measures the token savings. | `Python` · `Runnable` · `Agent memory` | [Read article](https://regolo.ai/getting-started-ai-memory-regolo-persistent-codebase-memory/) |
| **[Enterprise AI code review and security audit with CrewAI](multi-agent-brick-crewai-reviewer-security-code/)** | A DevSecOps review pipeline with CrewAI agents, Brick routing, ChromaDB retrieval and zero data retention. | `Python` · `Runnable` · `CrewAI` · `Security` | — |
| **[OpenCode multi-agent configuration for Regolo](opencode-multi-agent/)** | A multi-agent OpenCode setup with Brick routing that reduces coding costs across agents. | `Config` · `OpenCode` · `Multi-agent` | [Read article](https://regolo.ai/opencode-brick-for-multi-agent-coding-and-optimize-costs-up-to-80/) |
| **[REA Studio: reverse-engineering IPC and binary evidence inspector](rea-studio/)** | A local inspector that reduces Electron IPC and native binary dumps to evidence, then rebuilds specifications on Regolo models. | `Python` · `Runnable` · `Reverse engineering` | — |
| **[Review reply copilot with guardrails](review-reply-copilot/)** | Drafts replies to customer reviews, with a classifier that decides what needs a human before anything is sent. | `Python` · `Runnable` · `Guardrails` | [Read article](https://regolo.ai/ai-review-responses-with-guardrails-clef-flash-decides-an-llm-writes-a-person-approves/) |
| **[Sub-second European payment fraud scoring with Clef-Flash](sub-second-bank-fraud-clef-flash/)** | Three-tier payment fraud engine and local web console combining microsecond YAML security policies, pre-scoring, HMAC pseudonymisation, SHA-256 audit chains, and single-pass Clef-Flash (`/v1/systemone`) judgement on Regolo. | `Python` · `Runnable` · `FinTech` · `Zero Data Retention` | [Read article](https://regolo.ai/sub-second-bank-fraud-detection-clef-flash-yaml-policies/) |
| **[SoL-Pi with Regolo: context reduction benchmark](sol-pi-tutorial/)** | Coding-agent setup with SoL-Pi on Regolo, benchmarking how much context reduction cuts token costs. | `Benchmark` · `Coding agents` | [Read article](https://regolo.ai/cut-coding-agent-token-costs-sol-pi-regolo/) |
| **[Thinker, worker and verifier: stateful system with CrewAI](think-worker-verifier-crewai/)** | A stateful CrewAI system where a thinker plans, a worker executes and a verifier checks each result. | `Python` · `Runnable` · `CrewAI` | [Read article](https://regolo.ai/how-to-build-self-improving-agents-that-actually-get-better-over-time/) |

## Contributing

Contributions are welcome: new tutorials, fixes and clearer explanations. Open an issue or a pull request, and follow the folder structure of the existing tutorials, with a `README.md` in each one.

## Links

- [Regolo.ai](https://regolo.ai/?utm_source=github&utm_medium=readme&utm_campaign=tutorials): European OpenAI-compatible GPU inference
- [Free API key](https://regolo.ai/pricing?utm_source=github&utm_medium=readme&utm_campaign=tutorials): pay as you go, no commitment
- [Models library](https://regolo.ai/models-library/?utm_source=github&utm_medium=readme&utm_campaign=tutorials)
- [Documentation](https://docs.regolo.ai/?utm_source=github&utm_medium=readme&utm_campaign=tutorials)
- [YouTube](https://www.youtube.com/@regoloai)
- [Discord](https://discord.gg/wHxwWCC8)

## License

MIT. See [LICENSE](LICENSE) for details.

## Powered by

- [Regolo.ai](https://regolo.ai/?utm_source=github&utm_medium=readme&utm_campaign=tutorials): Zero Data Retention in EU data centers, powered by 100% green, carbon-free energy. OpenAI-compatible LLM API.
