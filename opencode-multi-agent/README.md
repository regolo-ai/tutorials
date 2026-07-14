<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

<div align="center">
  <h1>opencode Multi-Agent Configuration for Regolo</h1>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

This repository contains the complete multi-agent setup for [opencode](https://opencode.ai) using the [Regolo](https://regolo.ai) inference provider. The **orchestrator** runs on `brick-v1-beta` (a Mixture-of-Models router) and delegates to six specialist subagents, each pinned to the model that fits its workload.

the full guide article is: https://regolo.ai/opencode-brick-for-multi-agent-coding-and-optimize-costs-up-to-80/

## Project Overview

This configuration enables a sophisticated multi-agent architecture where a central orchestrator intelligently routes tasks to specialized subagents based on their capabilities. The system leverages Regolo's advanced `brick-v1-beta` router for optimal model selection per turn, while subagents use fixed, cost-optimized models for predictable workloads.

### Key Features

| Feature | Description | Benefit |
|---------|-------------|---------|
| **Intelligent Task Routing** | `brick-v1-beta` routes each turn to the best-fit subagent | Optimal cost/performance balance |
| **Specialized Roles** | 6 dedicated subagents (planner, coder, researcher, reviewer, devops, explore) | Domain-specific expertise |
| **Zero Configuration Runtime** | Drop-in config replaces existing opencode setup | 5-minute integration |
| **Hidden Subagents** | Subagents run only via delegation, not from picker | Clean UX |
| **Cost Savings Up to 80%** | Leverages open models suited for deterministic tasks | Enterprise-scale affordability |

---

## System Architecture

```
User request
    │
    ▼
Orchestrator (brick-v1-beta)   ← Brick routes each turn to the best backend
    │ delegates via Task tool
    ├── planner    → qwen3.5-122b         deep reasoning / architecture
    ├── coder      → qwen3-coder-next      code generation / bug fixing
    ├── researcher → gemma4-31b            API & docs research
    ├── reviewer   → mistral-small-4-119b  code review / security audit
    ├── devops     → qwen3.6-27b           infra / CI-CD / Docker
    └── explore    → qwen3.5-9b            fast codebase search
```

---

## Repository Structure

```
opencode-multi-agent/
├── opencode.json              # provider + agent definitions (drop-in config)
├── README.md                  # this file
├── agents/                    # agent system prompts (YAML frontmatter)
│   ├── orchestrator.md
│   ├── planner.md
│   ├── coder.md
│   ├── researcher.md
│   ├── reviewer.md
│   ├── devops.md
│   └── explore.md
└── skills/                    # one skill per agent (delegation guidance)
    ├── orchestrator-skill.md
    ├── planner-skill.md
    ├── coder-skill.md
    ├── researcher-skill.md
    ├── reviewer-skill.md
    ├── devops-skill.md
    └── explore-skill.md
```

---

## Installation & Setup

### Step 1: Configure API Key

Set your Regolo API key in [`opencode.json`](opencode.json) (replace `sk-YOUR_REGOLO_API_KEY`):

```json
{
  "provider": {
    "opencode": {
      "regolo": {
        "npm" : "@ai-sdk/openai-compatible",
        "name": "regolo",
        "options": {
          "baseURL": "https://api.regolo.ai/v1",
          "timeout": 12000000,
          "chunkTimeout": 600000,
          "simulateStreaming": true,
          "setCacheKey" : true,
          "headers": {
            "Authorization" : "Bearer sk-YOUR_REGOLO_API_KEY"
          }
        }
      },
      "models": {
        "brick-v1-beta": {
          "id": "brick-v1-beta",
          "name": "brick-v1-beta",
          "tools": true,
          "cost": { "input": 0.5, "output": 2.0 },
          "limit": { "context": 128000, "output": 128000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "qwen3.5-9b": {
          "id": "qwen3.5-9b",
          "name": "qwen3.5-9b",
          "tools": true,
          "cost": { "input": 0.1, "output": 0.4 },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "qwen3.5-122b": {
          "id": "qwen3.5-122b",
          "name": "qwen3.5-122b",
          "tools": true,
          "cost": { "input": 1.0, "output": 4.2 },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "qwen3-coder-next": {
          "id": "qwen3-coder-next",
          "name": "qwen3-coder-next",
          "reasoning": true,
          "tool_call": true,
          "tools": true,
          "limit": { "context": 240000, "output": 120000 },
          "cost": { "input": 0.5, "output": 2.0 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.5,
            "top_p": 0.95,
            "top_k": 40,
            "repetition_penalty": 1.05
          }
        },
        "gemma4-31b": {
          "id": "gemma4-31b",
          "name": "gemma4-31b",
          "tools": true,
          "cost": { "input": 0.4, "output": 2.1 },
          "modalities": { "input": ["text", "image"], "output": ["text"] },
          "limit": { "context": 100000, "output": 100000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "mistral-small-4-119b": {
          "id": "mistral-small-4-119b",
          "name": "mistral-small-4-119b",
          "tools": true,
          "cost": { "input": 0.5, "output": 2.1 },
          "modalities": { "input": ["text", "image"], "output": ["text"] },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "qwen3.6-27b": {
          "id": "qwen3.6-27b",
          "name": "qwen3.6-27b",
          "tools": true,
          "cost": { "input": 0.5, "output": 2.1 },
          "modalities": { "input": ["text", "image"], "output": ["text"] },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "glm5.2-beta": {
          "id": "glm5.2-beta",
          "name": "glm5.2-beta",
          "tools": true,
          "cost": { "input": 0.5, "output": 2.0 },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "gpt-oss-120b": {
          "id": "gpt-oss-120b",
          "name": "gpt-oss-120b",
          "tools": true,
          "cost": { "input": 0.8, "output": 3.2 },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "gpt-oss-20b": {
          "id": "gpt-oss-20b",
          "name": "gpt-oss-20b",
          "tools": true,
          "cost": { "input": 0.2, "output": 0.8 },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "Llama-3.3-70B-Instruct": {
          "id": "Llama-3.3-70B-Instruct",
          "name": "Llama-3.3-70B-Instruct",
          "tools": true,
          "cost": { "input": 0.5, "output": 2.0 },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        },
        "apertus-70b": {
          "id": "apertus-70b",
          "name": "apertus-70b",
          "tools": true,
          "cost": { "input": 0.5, "output": 2.0 },
          "limit": { "context": 120000, "output": 120000 },
          "options": {
            "parallel_tool_calls": true,
            "tool_choice": "auto",
            "temperature": 0.7
          }
        }
      },
      "agent": {
        "orchestrator": {
          "mode": "primary",
          "model": "regolo/brick-v1-beta",
          "description": "Master orchestrator - delega task ai specialisti",
          "prompt": "{file:~/.opencode/agents/orchestrator.md}",
          "permission": {
            "task": {
              "*": "deny",
              "planner": "allow",
              "coder": "allow",
              "researcher": "allow",
              "reviewer": "allow",
              "devops": "allow",
              "explore": "allow"
            },
            "edit": "deny",
            "bash": "ask"
          }
        },
        "planner": {
          "mode": "subagent",
          "hidden": true,
          "model": "regolo/qwen3.5-122b",
          "description": "Architettura, pianificazione, reasoning profondo",
          "prompt": "{file:~/.opencode/agents/planner.md}",
          "permission": { "edit": "deny", "bash": "deny" }
        },
        "coder": {
          "mode": "subagent",
          "hidden": true,
          "model": "regolo/qwen3-coder-next",
          "description": "Implementazione codice, bug fix, feature",
          "prompt": "{file:~/.opencode/agents/coder.md}",
          "permission": { "edit": "allow", "bash": "ask" }
        },
        "researcher": {
          "mode": "subagent",
          "hidden": true,
          "model": "regolo/gemma4-31b",
          "description": "Ricerca API, documentazione, dependencies",
          "prompt": "{file:~/.opencode/agents/researcher.md}",
          "permission": { "edit": "deny", "bash": "ask", "webfetch": "allow", "websearch": "allow" }
        },
        "reviewer": {
          "mode": "subagent",
          "hidden": true,
          "model": "regolo/mistral-small-4-119b",
          "description": "Code review, security audit, quality check",
          "prompt": "{file:~/.opencode/agents/reviewer.md}",
          "permission": { "edit": "deny", "bash": "deny" }
        },
        "devops": {
          "mode": "subagent",
          "hidden": true,
          "model": "regolo/qwen3.6-27b",
          "description": "Infrastruttura, CI/CD, Docker, deployment",
          "prompt": "{file:~/.opencode/agents/devops.md}",
          "permission": { "edit": "allow", "bash": "ask" }
        },
        "explore": {
          "mode": "subagent",
          "hidden": true,
          "model": "regolo/qwen3.5-9b",
          "description": "Fast codebase exploration and file search",
          "prompt": "{file:~/.opencode/agents/explore.md}",
          "permission": { "edit": "deny", "bash": "deny" }
        }
      }
    }
  }
}
```

Get your free API key: **[Sign Up for Free Trial](https://regolo.ai/pricing)**

### Step 2: Merge Configuration

Merge the `regolo` block under `provider` and the whole `agent` block into your opencode config:

- Copy into `~/.config/opencode/opencode.json`, **or**
- Replace the file entirely if you have no other config to keep

### Step 3: Copy Agent Prompts

```bash
cp -r agents/* ~/.opencode/agents/
```

### Step 4: (Optional) Install Skills

Install the skills for explicit delegation guidance:

```bash
mkdir -p ~/.opencode/skills
cp -r skills/* ~/.opencode/skills/
```

### Step 5: Validate Configuration

```bash
python3 -m json.tool ~/.config/opencode/opencode.json > /dev/null && echo OK
```

### Step 6: Start opencode

Launch opencode. You should see 7 agents loaded (1 primary + 6 subagents):

```bash
opencode
```

---

## How It Works

The architecture operates on two distinct levels:

### 1. Dynamic Routing Layer (`brick-v1-beta`)

The orchestrator uses Regolo's `brick-v1-beta` router, which performs per-turn intelligent routing. For each user request, the router evaluates which subagent is best suited for the task and delegates accordingly. This provides optimal cost-performance balance by matching task complexity to model capabilities.

### 2. Specialized Subagents

Each subagent runs on a fixed, well-suited model:

| Subagent | Model | Purpose |
|----------|-------|---------|
| **Orchestrator** | brick-v1-beta | High-level routing and coordination |
| **Planner** | qwen3.5-122b | Deep reasoning, architecture design, planning |
| **Coder** | qwen3-coder-next | Code generation, debugging, refactoring |
| **Researcher** | gemma4-31b | API documentation lookup, web research |
| **Reviewer** | mistral-small-4-119b | Code review, security audits |
| **DevOps** | qwen3.6-27b | Infrastructure, CI/CD, Docker configurations |
| **Explore** | qwen3.5-9b | Fast codebase navigation and search |

Subagents are `hidden: true`, so they only run via delegation, not from the agent picker — keeping the UX clean.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REGOLO_API_KEY` | Your Regolo API key | Required |
| `REGOLO_BASE_URL` | Regolo API endpoint | `https://api.regolo.ai` |

---

## Tips & Notes

- The `explore` agent is referenced in the orchestrator's `permission.task` allow-list — do not remove it without also updating that block.
- Subagents are `hidden: true`, so they only run via delegation, not from the agent picker.
- `brick-v1-beta` performs per-turn routing; subagents use fixed models because their workloads are predictable and adding a routing hop would only add latency.
- This package intentionally omits the `mcp` and `plugin` sections from the live config — those are environment-specific. Add them back from your own config if needed.

---

## Quick Start

```bash
# 1. Clone this repository
git clone https://github.com/regolo-ai/tutorials.git
cd tutorials/opencode-multi-agent

# 2. Get a free API key from Regolo
# https://regolo.ai/pricing

# 3. Update opencode.json with your Regolo API key
# 4. Merge config into ~/.config/opencode/opencode.json
# 5. Copy agents: cp -r agents/* ~/.opencode/agents/
# 6. (Optional) Copy skills: cp -r skills/* ~/.opencode/skills/
# 7. Start opencode: opencode
```

---

## Links

- [Regolo.ai](https://regolo.ai) — European OpenAI-compatible GPU inference
- [Free API key](https://regolo.ai/pricing) — Pay as You Go, no commitment
- [Models Library](https://regolo.ai/models-library/)
- [Documentation](https://regolo.ai/docs)
- [Discord](https://discord.gg/wHxwWCC8)

---

## Sponsor

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
Powered by **[Regolo.ai](https://regolo.ai)**.

---

### Special Offer: 30 Days Free Trial

To power your multi-agent setup, you need an API key. Sign up for Regolo today and get **30 days completely free**, plus a massive **70% discount for the following 3 months!**

🚀 **[CLICK HERE TO GET STARTED AND CLAIM YOUR FREE TRIAL](https://regolo.ai/pricing)** 🚀
