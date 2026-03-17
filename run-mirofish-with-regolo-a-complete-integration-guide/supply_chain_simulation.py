#!/usr/bin/env python3
"""
supply_chain_simulation.py
──────────────────────────
Practical example: a 4-round multi-agent simulation on a global semiconductor
supply chain disruption triggered by a Taiwan Strait shipping blockade.

Four agents with distinct roles assess the crisis and propose risk mitigation
strategies. Each agent has its own persistent memory (Mem0 + regolo.ai
embeddings). After all rounds, a ReportAgent produces a structured assessment.

This script mirrors the same LLM + memory architecture that MiroFish uses
internally when you load a seed document through its web interface.

Run:
    python supply_chain_simulation.py

No MiroFish installation required — use this to validate your regolo.ai
setup before launching the full MiroFish UI simulation.

Companion tutorial:
    blog/tutorial-mirofish-supply-chain.md
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

API_KEY     = os.environ.get("REGOLO_API_KEY", "")
BASE_URL    = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
LLM_MODEL   = os.environ.get("MEM0_LLM_MODEL", "Llama-3.3-70B-Instruct")
EMBED_MODEL = os.environ.get("MEM0_EMBEDDER_MODEL", "Qwen3-Embedding-8B")

EMBED_DIMS = {"gte-Qwen2": 3584, "Qwen3-Embedding-8B": 4096}

if not API_KEY or API_KEY == "your_regolo_api_key_here":
    print("✗ REGOLO_API_KEY not set. Copy .env.example to .env and fill in your key.")
    sys.exit(1)


# ── Patch Mem0 embedder (removes unsupported `dimensions` param on regolo.ai) ─

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
                "collection_name": "supply_chain_agents",
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
        id="supply_chain_director",
        name="Elena Kovacs",
        role="Supply Chain Director, European Electronics Manufacturer",
        system_prompt=(
            "You are Elena Kovacs, Supply Chain Director at a mid-size European "
            "electronics manufacturer. 70% of your NAND flash and advanced logic chips "
            "come from Taiwanese fabs. You are focused on operational continuity, "
            "inventory buffer strategies, and alternative sourcing. "
            "Be specific and tactical (2–3 sentences). Reference other participants when relevant."
        ),
    ),
    Agent(
        id="geopolitical_analyst",
        name="James Park",
        role="Senior Geopolitical Risk Analyst",
        system_prompt=(
            "You are James Park, a senior geopolitical risk analyst at a global "
            "consulting firm. You assess the duration, escalation scenarios, and "
            "diplomatic off-ramps of the Taiwan Strait shipping blockade. "
            "Quantify risk where possible (2–3 sentences). Reference other participants when relevant."
        ),
    ),
    Agent(
        id="cfo",
        name="Priya Mehta",
        role="CFO, Semiconductor-Dependent Fintech Company",
        system_prompt=(
            "You are Priya Mehta, CFO of a London-based fintech whose payment "
            "terminals depend on NXP and STMicroelectronics chips. You focus on "
            "financial hedging, balance-sheet resilience, and communicating with "
            "investors. Be concise and financially precise (2–3 sentences). "
            "Reference other participants when relevant."
        ),
    ),
    Agent(
        id="resilience_consultant",
        name="Diego Santos",
        role="Supply Chain Resilience Consultant",
        system_prompt=(
            "You are Diego Santos, a supply chain resilience consultant who has "
            "advised Fortune 500 companies on nearshoring and multi-sourcing after "
            "COVID disruptions. You push for structural redesign over short-term "
            "patches. Be pragmatic and framework-driven (2–3 sentences). "
            "Reference other participants when relevant."
        ),
    ),
]

TOPIC = (
    "A Taiwan Strait shipping blockade has halted 60% of advanced semiconductor "
    "exports from Taiwan. Lead times for logic chips have jumped from 12 to 52+ "
    "weeks. European manufacturers face production halts within 90 days. "
    "What immediate and structural responses should European companies adopt?"
)

ROUNDS = [
    "Initial threat assessment — what is your highest-priority concern in the first 30 days?",
    "React to the most important point raised by another participant. Propose one concrete "
    "short-term action (0–90 days) your organisation will take immediately.",
    "Identify the single biggest structural vulnerability this crisis has exposed "
    "in European supply chains and propose a 12-month remediation plan.",
    "Final synthesis — if this blockade lasts 18 months, what does the European "
    "electronics landscape look like? Who survives and who doesn't?",
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
        max_tokens=220,
    )
    return resp.choices[0].message.content.strip()


# ── Simulation ────────────────────────────────────────────────────────────────

def run_simulation() -> None:
    print(f"\n{'═' * 72}")
    print("  MULTI-AGENT SIMULATION — Semiconductor Supply Chain Crisis")
    print(f"{'═' * 72}")
    print(f"\nScenario:\n{textwrap.fill(TOPIC, width=70)}\n")
    print(f"Agents : {', '.join(f'{a.name} ({a.role.split(',')[0]})' for a in AGENTS)}")
    print(f"Rounds : {len(ROUNDS)}")
    print(f"LLM    : {LLM_MODEL} via regolo.ai")
    print(f"Memory : Mem0 + {EMBED_MODEL}\n")

    memory = build_memory()
    round_transcript: list[str] = []

    for round_idx, round_prompt in enumerate(ROUNDS, start=1):
        print(f"\n{'─' * 72}")
        print(f"  Round {round_idx}: {textwrap.fill(round_prompt, width=66, subsequent_indent='           ')}")
        print(f"{'─' * 72}\n")

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
                f"Crisis scenario: {TOPIC}\n\n"
                f"Your recalled context and prior statements:\n{memory_context}\n\n"
                f"Previous round transcript:\n"
                + ("\n".join(round_transcript[-8:]) if round_transcript else "(first round)")
                + f"\n\nYour task for this round: {round_prompt}"
            )

            response = chat(agent.system_prompt, context_block)

            # Store this agent's statement in memory
            memory.add(
                [{"role": "assistant", "content": response}],
                user_id=agent.id,
            )

            entry = f"{agent.name} ({agent.role.split(',')[0]}): {response}"
            round_transcript.append(entry)

            print(f"  {agent.name}  —  {agent.role.split(',')[0]}")
            print(textwrap.indent(textwrap.fill(response, width=66), "  │  "))
            print()

    # ── Report Agent ─────────────────────────────────────────────────────────
    print(f"\n{'═' * 72}")
    print("  REPORT AGENT — Supply Chain Crisis Assessment")
    print(f"{'═' * 72}\n")

    full_transcript = "\n".join(round_transcript)
    report_prompt = (
        f"You are a neutral supply chain and geopolitical analyst.\n\n"
        f"Crisis context:\n{TOPIC}\n\n"
        f"Full simulation transcript:\n{full_transcript}\n\n"
        f"Write a structured assessment covering:\n"
        f"1. Consensus points — where all four participants agreed\n"
        f"2. Critical divergences — the sharpest disagreements and why they matter\n"
        f"3. Top 3 actionable recommendations that emerged from the debate\n"
        f"4. Resilience score (0–10) for European electronics supply chains "
        f"   based on the 18-month scenario, with one-sentence justification\n\n"
        f"Be specific. Name the agents, cite their proposals."
    )

    report = chat(
        "You are a concise risk analyst. Write plain prose with numbered sections. No bullet points.",
        report_prompt,
    )
    print(textwrap.fill(report, width=72))
    print(f"\n{'═' * 72}\n")

    print("  Next step: load seed_supply_chain.md into MiroFish UI to run")
    print("  the full multi-hundred-agent version of this simulation.")
    print(f"{'═' * 72}\n")


if __name__ == "__main__":
    run_simulation()
