#!/usr/bin/env python3
"""
demo_simulation.py
──────────────────
Practical example: a 3-round multi-agent social simulation on EU AI regulation.

Three agents with distinct personas discuss a policy proposal.
Each agent has its own persistent memory (via Mem0 + regolo.ai embeddings).
After all rounds, a ReportAgent summarises the emergent dynamics.

Run:
    python demo_simulation.py

No MiroFish installation needed — this shows the same LLM + memory pattern
that MiroFish uses internally, in ~150 lines of plain Python.
"""

import os
import sys
import textwrap
from pathlib import Path
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    print("✗ openai not installed. Run: pip install openai")
    sys.exit(1)

try:
    from mem0 import Memory
    from mem0.embeddings.openai import OpenAIEmbedding
except ImportError:
    print("✗ mem0ai not installed. Run: pip install mem0ai")
    sys.exit(1)


# ── Config ──────────────────────────────────────────────────────────────────

API_KEY    = os.environ.get("REGOLO_API_KEY", "")
BASE_URL   = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
LLM_MODEL  = os.environ.get("MEM0_LLM_MODEL", "Llama-3.3-70B-Instruct")
EMBED_MODEL = os.environ.get("MEM0_EMBEDDER_MODEL", "Qwen3-Embedding-8B")

EMBED_DIMS = {"gte-Qwen2": 3584, "Qwen3-Embedding-8B": 4096}

if not API_KEY or API_KEY == "your_regolo_api_key_here":
    print("✗ REGOLO_API_KEY not set. Copy .env.example to .env and fill in your key.")
    sys.exit(1)


# ── Patch Mem0 embedder (removes unsupported `dimensions` param) ─────────────

def _patch_mem0_embedder() -> None:
    def _embed(self, text, memory_action=None):
        text = text.replace("\n", " ")
        return (
            self.client.embeddings.create(input=[text], model=self.config.model)
            .data[0].embedding
        )
    OpenAIEmbedding.embed = _embed

_patch_mem0_embedder()


# ── Build shared Mem0 instance ───────────────────────────────────────────────

def build_memory() -> Memory:
    dims = EMBED_DIMS.get(EMBED_MODEL, 4096)
    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": LLM_MODEL,
                "openai_base_url": BASE_URL,
                "api_key": API_KEY,
                "temperature": 0.3,
                "max_tokens": 512,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": EMBED_MODEL,
                "openai_base_url": BASE_URL,
                "api_key": API_KEY,
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "demo_agents",
                "embedding_model_dims": dims,
                "on_disk": False,
            },
        },
    }
    return Memory.from_config(config)


# ── Agents ────────────────────────────────────────────────────────────────────

@dataclass
class Agent:
    id: str
    name: str
    role: str
    system_prompt: str


AGENTS = [
    Agent(
        id="policymaker",
        name="Sofia Ricci",
        role="EU Policy Analyst",
        system_prompt=(
            "You are Sofia Ricci, a senior EU policy analyst at the European Commission. "
            "You favour strong AI regulation to protect citizens and maintain competitiveness. "
            "Be concise (2–3 sentences). Reference previous points when relevant."
        ),
    ),
    Agent(
        id="startup_cto",
        name="Marc Dupont",
        role="CTO at an EU AI startup",
        system_prompt=(
            "You are Marc Dupont, CTO of a Paris-based AI startup. "
            "You worry that excessive regulation will stifle innovation in Europe. "
            "Be concise (2–3 sentences). Reference previous points when relevant."
        ),
    ),
    Agent(
        id="ethicist",
        name="Layla Hassan",
        role="AI Ethics Researcher",
        system_prompt=(
            "You are Layla Hassan, an AI ethics researcher at a Berlin university. "
            "You push for transparency and accountability but want practical, not bureaucratic solutions. "
            "Be concise (2–3 sentences). Reference previous points when relevant."
        ),
    ),
]

TOPIC = (
    "The EU is proposing mandatory real-time human oversight for all high-risk AI systems "
    "deployed in public services. Should this requirement be adopted as currently written?"
)

ROUNDS = [
    "Opening statement — share your initial position on the proposal.",
    "Respond to the strongest point made by another participant in the previous round.",
    "Propose one concrete amendment to the proposal that you could accept.",
]


# ── LLM helper ───────────────────────────────────────────────────────────────

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def chat(system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.7,
        max_tokens=200,
    )
    return resp.choices[0].message.content.strip()


# ── Simulation ────────────────────────────────────────────────────────────────

def run_simulation() -> None:
    print(f"\n{'═' * 70}")
    print("  MULTI-AGENT SIMULATION — EU AI Regulation Policy Debate")
    print(f"{'═' * 70}")
    print(f"\nTopic: {TOPIC}\n")
    print(f"Agents : {', '.join(f'{a.name} ({a.role})' for a in AGENTS)}")
    print(f"Rounds : {len(ROUNDS)}")
    print(f"LLM    : {LLM_MODEL} via regolo.ai")
    print(f"Memory : Mem0 + {EMBED_MODEL}\n")

    memory = build_memory()
    round_transcript: list[str] = []

    for round_idx, round_prompt in enumerate(ROUNDS, start=1):
        print(f"\n{'─' * 70}")
        print(f"  Round {round_idx}: {round_prompt}")
        print(f"{'─' * 70}\n")

        for agent in AGENTS:
            # Retrieve this agent's relevant memories
            hits = memory.search(round_prompt, user_id=agent.id)
            results = hits.get("results", hits) if isinstance(hits, dict) else hits
            memory_context = (
                "\n".join(f"- {r['memory']}" for r in results[:3])
                if results else "No prior context."
            )

            # Build the user prompt
            context_block = (
                f"Topic: {TOPIC}\n\n"
                f"Your previous statements and recalled context:\n{memory_context}\n\n"
                f"Previous round transcript:\n"
                + ("\n".join(round_transcript[-6:]) if round_transcript else "(first round)")
                + f"\n\nYour task: {round_prompt}"
            )

            response = chat(agent.system_prompt, context_block)

            # Store the agent's statement in memory
            memory.add(
                [{"role": "assistant", "content": response}],
                user_id=agent.id,
            )

            entry = f"{agent.name} ({agent.role}): {response}"
            round_transcript.append(entry)

            print(f"  {agent.name} ({agent.role})")
            print(textwrap.indent(textwrap.fill(response, width=64), "  │  "))
            print()

    # ── Report Agent ─────────────────────────────────────────────────────────
    print(f"\n{'═' * 70}")
    print("  REPORT AGENT — Emergent Dynamics Summary")
    print(f"{'═' * 70}\n")

    full_transcript = "\n".join(round_transcript)
    report_prompt = (
        f"You are a neutral analyst summarising a multi-agent policy debate.\n\n"
        f"Topic: {TOPIC}\n\n"
        f"Full transcript:\n{full_transcript}\n\n"
        f"Write a structured summary covering:\n"
        f"1. Areas of agreement\n"
        f"2. Unresolved tensions\n"
        f"3. The most concrete proposal that emerged\n"
        f"4. Predicted outcome if the debate continued for 10 more rounds\n\n"
        f"Be specific. Reference agent names."
    )

    report = chat(
        "You are a concise policy analyst. Use plain prose, no bullet points.",
        report_prompt,
    )
    print(textwrap.fill(report, width=70))
    print(f"\n{'═' * 70}\n")


if __name__ == "__main__":
    run_simulation()
