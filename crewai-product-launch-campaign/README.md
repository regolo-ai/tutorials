# crewAI Product Launch - Multi-Agent Workflow

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Regolo](https://img.shields.io/badge/Powered%20by-Regolo%20GPU-green)](https://regolo.ai)


An automated product launch system powered by crewAI multi-agent framework and Regolo.ai LLM infrastructure.
Blog article reference: [Build Multi-Agent Workflows with crewAI](https://regolo.ai/build-multi-agent-workflows-with-crewai-teams/)

--- 
### 🎁 Get Started Free of Use for 30 Days

Sign up for Regolo and get **30 days free and 70% off for next 3 months:**

[Get Started](https://regolo.ai) · [**REGOLO FREE TRIAL**](https://regolo.ai/pricing)

### Questions? Open an issue or join our [Discord](https://discord.gg/wHxwWCC8) 
---

## Overview

This project deploys a team of specialized AI agents that collaborate to create complete product launch campaigns:

- **Competitive Analyst**: Analyzes market positioning and competitor strategies
- **Copywriter**: Creates conversion-focused marketing copy
- **Campaign Manager**: Designs comprehensive launch strategies with KPIs

## The Output 
In this example the you'll generate a competitive analysis in 0.0425€

[Link to the output example](output.md)

## Architecture

```
Flask API → crewAI Crew → Regolo LLM → Results
```

## Prerequisites

- Python 3.10+
- Regolo API key ([Get one here + FREE Credits](https://regolo.ai))
- Docker (optional, for containerized deployment)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` and add your Regolo API key:

```
REGOLO_API_KEY=your-actual-api-key
```

Or update `llm_config.py` directly with your API key.

### 3. Test the Crew Locally

```bash
python crew.py
```

This will run a test product launch for "Premium Organic Face Serum".

### 4. Start the API Server

```bash
python api_server.py
```

The API will be available at `http://localhost:5000`

### 5. Trigger a Launch via API

```bash
curl -X POST http://localhost:5000/kickoff \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "Eco-Friendly Water Bottle",
    "market_segment": "Sustainable Living"
  }'
```

Response:
```json
{
  "job_id": "abc-123-def-456",
  "status": "running",
  "message": "Product launch crew initiated"
}
```

### 6. Check Job Status

```bash
curl http://localhost:5000/status/abc-123-def-456
```

## Docker Deployment

### Build the Image

```bash
docker build -t crew-product-launch .
```

### Run the Container

```bash
docker run -e REGOLO_API_KEY=your-key -p 5000:5000 crew-product-launch
```

## n8n Integration (optional)

### Workflow Setup

1. **Webhook Trigger**: Create a POST endpoint `/launch-product`
2. **HTTP Request**: POST to `http://localhost:5000/kickoff`
3. **Wait Node**: 30 seconds
4. **HTTP Request**: GET status with job_id
5. **IF Node**: Check if `status === "completed"`
6. **Slack/Email**: Send results when complete

See the full guide at: [TOOOOOOO REPLACEEEEEE | Build Multi-Agent Workflows: n8n + crewAI Teams](https://regolo.ai)

## Project Structure

```
crewai-product-launch/
├── llm_config.py      # Regolo LLM configuration
├── agents.py          # Agent definitions
├── tasks.py           # Task definitions
├── crew.py            # Crew assembly and test runner
├── api_server.py      # Flask REST API
├── requirements.txt   # Python dependencies
├── Dockerfile         # Container configuration
├── .env.example       # Environment template
└── README.md          # This file
```

## Customization

### Add New Agents

Edit `agents.py` to add specialized agents:

```python
social_media_manager = Agent(
    role="Social Media Strategist",
    goal="Create viral social media content for {product_name}",
    backstory="You've grown multiple brands to 100K+ followers.",
    llm=regolo_llm,
    verbose=True
)
```

### Add Tools to Agents

Install crewAI tools:

```bash
pip install crewai-tools
```

Add to agents:

```python
from crewai_tools import SerperDevTool, WebsiteSearchTool

competitive_analyst = Agent(
    role="Senior Competitive Intelligence Analyst",
    tools=[SerperDevTool(), WebsiteSearchTool()],
    llm=regolo_llm,
    verbose=True
)
```

### Change LLM Model

Edit `llm_config.py`:

```python
regolo_llm = LLM(
    model="llama-3.3-70b-instruct",  # or gpt-oss-120b
    temperature=0.7,
    base_url="https://api.regolo.ai/v1",
    api_key="your-key"
)
```

## Performance

- **Execution Time**: 2-5 minutes for complete campaign
- **Cost**: ~$0.50-$1.50 per launch (DeepSeek-R1-70B)
- **Token Usage**: ~15K-30K tokens (3 agents)

## Troubleshooting

### "Module not found" Error

```bash
pip install --upgrade crewai crewai-tools
```

### API Key Invalid

Verify your key at [regolo.ai/dashboard](https://regolo.ai)

### Crew Hangs

Reduce task complexity or increase timeout in n8n Wait node.

## Recommended Production Checklist

- [ ] Use environment variables for API keys (never hardcode)
- [ ] Implement Redis for job storage (replace in-memory dict)
- [ ] Add authentication to Flask API endpoints
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Configure rate limiting
- [ ] Deploy to cloud platform (Render, Railway, DigitalOcean)
- [ ] Set up CI/CD pipeline

## Resources

- [Regolo.ai | Sign Up for FREE Credits](https://regolo.ai)
- [crewAI Documentation](https://docs.crewai.com)
- [Growth Hacking Guide](https://regolo.ai/labs)

## License

MIT License - feel free to use for commercial projects.

## Support

- Community: [Talk with us on Discord](https://discord.gg/gVcxQz7Y)
- Issues: Open a GitHub issue

---

Built with ❤️ by the [Regolo team](https://regolo.ai)
