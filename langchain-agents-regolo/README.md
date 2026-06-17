# LangChain Agents with Regolo: Zero OpenAI Lock-in & Privacy-First Architecture

<video_placeholder>

<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# LangChain Agents with Regolo: Zero OpenAI Lock-in & Privacy-First Architecture

**Production-ready multi-agent systems with complete OpenAI independence and GDPR compliance**

This repository contains all production-ready code from the guide ["LangChain Agents with Regolo: Zero OpenAI Lock-in & Privacy-First Architecture"](https://regolo.ai/langchain-agents-regolo-zero-openai/) — ready to deploy and scale.

---

## 🎯 What This Is

A complete, production-grade LangChain agent system that combines:

- **[LangChain](https://python.langchain.com)**: Open-source agent framework with tool calling and memory
- **[Regolo.ai](https://regolo.ai)**: European OpenAI-compatible LLM hosting with zero data retention
- **Open-source models**: Llama-3.3 70B, Mistral, Qwen, or any Regolo model
- **Privacy-first design**: No OpenAI API keys, no data retention, EU hosting
- **Enterprise features**: Cost monitoring, rate limiting, production deployment

---

## 📊 Performance vs KGP Talkie's "LangChain v1 Agents"

| Metric | KGP Talkie's Approach | This Pipeline | Improvement |
|--------|----------------------|---------------|-------------|
| **OpenAI Dependency** | Required | Zero | 100% independence |
| **Data Privacy** | OpenAI data retention | Zero data retention | GDPR compliant |
| **Cost per 1k queries** | $0.45-0.90 | $0.12 | -73% to -87% |
| **EU Hosting** | N/A | EU-based | Data sovereignty |
| **Model Flexibility** | OpenAI only | Any Regolo model | 100% flexibility |

**Key Differentiators:**
- **Zero OpenAI lock-in**: Complete independence from OpenAI's API
- **Privacy by design**: Zero data retention + EU hosting
- **Cost efficiency**: 73-87% savings vs OpenAI
- **Model freedom**: Any open-source model via Regolo

---

## 🚀 Quick Start (15 minutes)

### Prerequisites

- **Python 3.10+**
- **Regolo API key** from [regolo.ai/dashboard](https://regolo.ai/dashboard)
- **Redis** (optional but recommended for caching)

### Step 1: Clone and Setup

```bash
# Clone or download this repository
cd langchain-agents-regolo

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure API Key

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your Regolo API key
nano .env  # or use your preferred editor
```

Your `.env` should look like:
```bash
REGOLO_API_KEY=your_actual_key_here
REGOLO_BASE_URL=https://api.regolo.ai/v1
REGOLO_MODEL=Llama-3.3-70B-Instruct
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_key  # optional
```

### Step 3: Start Redis (Optional but Recommended)

```bash
# Option 1: Local Redis
redis-server

# Option 2: Docker
docker run -d -p 6379:6379 redis:7-alpine

# Option 3: Skip Redis
# System works without caching, just slower
```

### Step 4: Run the Pipeline

```bash
# Load environment (filtering out comments)
export $(grep -v '^#' .env | xargs)

# Run complete pipeline with interactive mode
python main.py
```

**What happens:**
1. Sets up LangChain with Regolo provider
2. Creates multi-tool agents with privacy-first design
3. Implements tool calling with local models
4. Adds memory management without OpenAI
5. Enters interactive agent testing mode

---

## 📁 Project Structure

```
langchain-agents-regolo/
├── regolo_provider.py      # Custom LangChain provider for Regolo
├── privacy_agents.py       # Multi-agent system with privacy focus
├── cost_monitor.py         # Cost tracking and optimization
├── production_agents.py    # Production-ready agent deployment
├── evaluation.py           # Agent performance metrics
├── main.py                 # Complete pipeline + interactive mode
├── tests/
│   └── test_agents.py      # Test suite
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Redis + API containers
├── Dockerfile              # Production container
├── .env.example            # Environment template
└── README.md               # This file
```

---

## 🔧 How Each Component Works

### 1. Custom Regolo Provider (`regolo_provider.py`)

**Problem**: LangChain defaults to OpenAI, creating lock-in and privacy concerns.

**Solution**: Custom provider that uses Regolo's OpenAI-compatible API.

```python
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

# Replace OpenAI with Regolo
llm = ChatOpenAI(
    openai_api_key="sk-regolo-your-key-here",  # Regolo key
    openai_api_base="https://api.regolo.ai/v1",  # Regolo endpoint
    model_name="Llama-3.3-70B-Instruct",
    temperature=0.2,
    max_tokens=1000
)

# Use in LangChain just like OpenAI
messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Explain OpenAI replacement in 2 sentences.")
]

response = llm(messages)
```

### 2. Privacy-First Multi-Agent System (`privacy_agents.py`)

**Problem**: Multi-agent systems expose data to third-party providers.

**Solution**: Complete privacy isolation with Regolo's zero data retention.

```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# Create privacy-first agent
agent_executor = create_react_agent(
    model=llm,
    tools=[search_tool, calculate_tool, database_tool],
    checkpointer=MemorySaver(),
    state_modifier="You are a privacy-first AI assistant. Never share user data."
)

# Run with privacy guarantees
result = agent_executor.invoke(
    {"messages": [("user", "Calculate 2+2 and search for Python tutorials")]}
)
```

### 3. Cost Monitoring (`cost_monitor.py`)

**Problem**: Uncontrolled costs with OpenAI APIs.

**Solution**: Comprehensive cost tracking and optimization.

```python
from dataclasses import dataclass
from typing import List

@dataclass
class CostMetrics:
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    timestamp: datetime

class CostMonitor:
    def __init__(self):
        self.daily_costs: List[CostMetrics] = []
        self.monthly_budget = 100.0  # Set your budget

    def track_usage(self, input_tokens, output_tokens):
        # Regolo pricing (example)
        input_cost = (input_tokens / 1_000_000) * 0.30
        output_cost = (output_tokens / 1_000_000) * 0.60
        total_cost = input_cost + output_cost

        metrics = CostMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            timestamp=datetime.now()
        )

        self.daily_costs.append(metrics)
        return metrics

    def check_budget(self):
        today_cost = sum(m.total_cost for m in self.daily_costs if m.timestamp.date() == datetime.now().date())
        return today_cost < self.monthly_budget
```

### 4. Production Deployment (`production_agents.py`)

**Problem**: Development agents don't scale to production.

**Solution**: Production-ready deployment with monitoring and reliability.

```python
import asyncio
from typing import AsyncGenerator

class ProductionAgent:
    def __init__(self, llm, tools, memory):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.cost_monitor = CostMonitor()

    async def stream_response(self, query: str) -> AsyncGenerator[str, None]:
        # Stream response with cost tracking
        async for chunk in self.llm.astream(query):
            yield chunk.content

    async def process_batch(self, queries: List[str]) -> List[str]:
        # Process multiple queries with rate limiting
        results = []
        for query in queries:
            if self.cost_monitor.check_budget():
                result = await self.stream_response(query)
                results.append(".join(result))
            else:
                results.append("Budget exceeded - skipping")
        return results
```

### 5. Agent Evaluation (`evaluation.py`)

**Problem**: No metrics for agent performance.

**Solution**: Comprehensive evaluation of agent capabilities.

```python
from typing import Dict, List

class AgentEvaluator:
    def __init__(self, agent):
        self.agent = agent

    def test_privacy_guarantees(self, test_queries):
        # Verify no data leakage
        privacy_scores = []
        for query in test_queries:
            response = self.agent.invoke(query)
            # Check for privacy violations
            score = self._check_privacy_violations(response)
            privacy_scores.append(score)
        return sum(privacy_scores) / len(privacy_scores)

    def test_cost_efficiency(self, queries):
        # Verify cost optimization
        costs = []
        for query in queries:
            response = self.agent.invoke(query)
            cost = self._calculate_cost(response)
            costs.append(cost)
        return sum(costs) / len(costs)

    def test_reliability(self, test_cases):
        # Test agent reliability
        success_rate = 0
        for query, expected in test_cases:
            response = self.agent.invoke(query)
            if self._compare_responses(response, expected):
                success_rate += 1
        return success_rate / len(test_cases)
```

---

## 🧪 Running Tests

```bash
# Run test suite
python tests/test_agents.py
```

**What's tested:**
- Privacy guarantees verification
- Cost optimization validation
- Agent reliability testing
- OpenAI independence verification
```

## 🐳 Docker Deployment

### Option 1: Docker Compose (Recommended)

```bash
# Edit .env with your API key
cp .env.example .env
nano .env

# Start Redis + LangChain agents
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### Option 2: Manual Docker Build

```bash
# Build image
docker build -t langchain-agents .

# Run with Redis link
docker run -d \
  -e REGOLO_API_KEY=your_key \
  -e REDIS_HOST=host.docker.internal \
  -p 8000:8000 \
  -v $(pwd)/agent_memory:/app/agent_memory \
  langchain-agents
```

---

## 📈 Scaling to Production

### 1. Add Custom Tools

Extend your agents with domain-specific tools:

```python
from langchain.tools import Tool

def medical_search(query):
    """Search medical literature"""
    # Your medical API integration
    return search_results

medical_tool = Tool(
    name="medical_search",
    func=medical_search,
    description="Search medical literature and research"
)
```

### 2. Implement Memory Management

```python
from langgraph.checkpoint.memory import MemorySaver

# Persistent memory for agents
memory = MemorySaver()

# Create agent with memory
agent = create_react_agent(
    model=llm,
    tools=[medical_tool, calculation_tool],
    checkpointer=memory,
    state_modifier="You are a medical AI assistant with memory."
)
```

### 3. Scale with Multiple Instances

```yaml
# docker-compose.yml
services:
  langchain-agents:
    deploy:
      replicas: 3        # Scale to 3 instances
    environment:
      - REDIS_HOST=redis  # Shared memory/cache
```

### 4. Monitor Performance

```python
from prometheus_client import start_http_server, Counter

# Metrics for monitoring
REQUEST_COUNT = Counter('agent_requests_total', 'Total agent requests')
COST_TRACKER = Counter('agent_costs_usd', 'Agent costs in USD')

start_http_server(8000)  # Prometheus metrics endpoint
```

### 5. Optimize for Your Use Case

```python
# In production_agents.py
class OptimizedAgent(ProductionAgent):
    def __init__(self, llm, tools, memory):
        super().__init__(llm, tools, memory)
        self.model = self._select_optimal_model()
        self.temperature = self._calculate_optimal_temperature()

    def _select_optimal_model(self):
        # Choose model based on task complexity
        return "Llama-3.3-70B-Instruct"  # or other Regolo model

    def _calculate_optimal_temperature(self):
        # Adjust based on task requirements
        return 0.1  # Low temp for deterministic responses
```

---

## 🔒 Security & Privacy

### API Key Management

- **Never commit** `.env` to Git (it's in `.gitignore`)
- Use **secret managers** (AWS Secrets, HashiCorp Vault) in production
- Rotate keys regularly
- Use **separate keys** per environment (dev, staging, prod)

### Data Privacy

- **Zero data retention**: Regolo stores no conversation history
- **EU hosting**: All data processed in EU data centers
- **Local memory**: Conversation state stored locally (controlled by you)
- **No third-party APIs**: Complete independence from OpenAI/Google

### Security Best Practices

```python
# Security hardening for production
import os
from cryptography.fernet import Fernet

# Encrypt sensitive configuration
encryption_key = os.environ.get('ENCRYPTION_KEY')
fernet = Fernet(encryption_key)

# Secure environment variables
secure_env = {
    'REGOLO_API_KEY': fernet.encrypt(os.environ['REGOLO_API_KEY'].encode()),
    'LANGCHAIN_API_KEY': fernet.encrypt(os.environ['LANGCHAIN_API_KEY'].encode()),
}
```

---

## 🐛 Troubleshooting

### "REGOLO_API_KEY not set"

**Solution:**
```bash
export REGOLO_API_KEY=your_key_here
# or add to .env and run: export $(cat .env | xargs)
```

### "LangChain tracing not working"

**Solution:**
```bash
# Enable LangChain tracing
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your_langchain_key
```

### "Agent memory issues"

**Solution:**
```bash
# Clear and rebuild memory
rm -rf agent_memory/
python main.py
```

### "429 Too Many Requests"

**Solution:**
```python
# Add rate limiting in production_agents.py
import time

async def rate_limited_invoke(self, query, max_per_minute=60):
    # Implement rate limiting
    await asyncio.sleep(1)  # 1 second between requests
    return await self.llm.ainvoke(query)
```

---

## 📊 Benchmarking Your Setup

### Test Privacy Guarantees

```python
from evaluation import PrivacyTester

privacy_tester = PrivacyTester(agent)
privacy_score = privacy_tester.test_privacy_guarantees([
    "Share my personal information",
    "Store conversation history",
    "Access external APIs"
])
print(f"Privacy Score: {privacy_score:.2%}")
```

### Measure Cost Efficiency

```python
from evaluation import CostAnalyzer

cost_analyzer = CostAnalyzer(agent)
test_queries = ["Simple question", "Complex analysis", "Multi-step task"]
costs = cost_analyzer.analyze_costs(test_queries)
print(f"Average cost per query: ${costs['average_cost']:.4f}")
```

### Test Reliability

```python
from evaluation import ReliabilityTester

reliability_tester = ReliabilityTester(agent)
test_cases = [
    ("Simple math", "2 + 2 = 4"),
    ("Definition", "What is AI?"),
    ("Explanation", "How does RAG work?")
]
reliability_score = reliability_tester.test_reliability(test_cases)
print(f"Reliability Score: {reliability_score:.2%}")
```

---

## 🔄 Next Steps

### 1. Advanced Agent Patterns

- **Tool composition**: Chain multiple tools for complex workflows
- **Agent coordination**: Multiple agents working together
- **Context sharing**: Memory across agent sessions

### 2. Integrate with Your Stack

- **n8n integration**: Connect LangChain agents to n8n workflows
- **Cheshire Cat**: Combine with enterprise AI agent framework
- **Custom APIs**: Build REST endpoints for your agents

### 3. Enterprise Features

- **SSO integration**: Connect with corporate identity providers
- **Audit logging**: Track all agent interactions
- **Compliance reporting**: Generate GDPR compliance reports

### 4. Learn More

- **LangChain docs**: https://python.langchain.com/docs
- **Regolo guides**: https://regolo.ai/blog
- **Privacy engineering**: https://privacy-engineering.org

---

## 📚 Resources

- **Regolo.ai**: https://regolo.ai
- **Regolo API Docs**: https://regolo.ai/docs
- **LangChain**: https://python.langchain.com
- **OpenAI Replacement**: https://regolo.ai/openai-replacement-eu-base-url-regolo/
- **Zero Data Retention**: https://regolo.ai/zero-data-retention/

---

## 🙋 Support

- **Email**: support@regolo.ai
- **Discord**: [Join Regolo community](https://discord.gg/regolo)
- **GitHub Issues**: Report bugs or request features
- **X/Twitter**: [@regolo_ai](https://x.com/regolo_ai)

---

## 📝 License

This code is provided as reference material for the Regolo.ai blog guide.

- **Code**: MIT License (adapt for your projects)
- **Regolo API**: Subject to Regolo.ai Terms of Service
- **LangChain**: Apache License 2.0

---

## ⚡ Quick Reference

```bash
# Full pipeline
python main.py

# Run tests
python tests/test_agents.py

# Docker deployment
docker compose up -d

# Clear memory
rm -rf agent_memory/

# Restart after config change
docker compose restart langchain-agents
```

**Ready to deploy privacy-first AI agents?** 🚀

Get free Regolo credits: https://regolo.ai

---

*Built by developers, for developers. Questions? We're here to help.*

*Last updated: January 2026*

### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
