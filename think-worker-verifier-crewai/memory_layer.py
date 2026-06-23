"""
memory_layer.py
===============
Nodo MEMORY del diagramma TWV basato sulla classe Memory ufficiale di CrewAI (ChromaDB).
Questo modulo utilizza una patch a runtime (monkeypatching) applicata all'avvio in main.py
per risolvere definitivamente gli errori extra_forbidden lanciati da Pydantic v2
quando si utilizzano LLM compatibili OpenAI non-standard.
"""
from __future__ import annotations
from typing import Iterable
from crewai import Memory
from config import settings
from models import PlanPacket, VerificationReport, WorkerResult

class MemoryManager:
    """Manager di persistenza semantica basato su ChromaDB nativo di CrewAI."""

    def __init__(self) -> None:
        self.memory = Memory(embedder=settings.embedder, llm=settings.thinker_llm)
        self.root = settings.memory_scope_root

    def _scope(self, suffix: str) -> str:
        return f"{self.root}/{suffix.strip('/')}"

    def _join(self, matches: Iterable) -> str:
        lines = []
        for m in matches:
            content = getattr(getattr(m, "record", None), "content", None)
            if content:
                lines.append(f"- {content}")
        return "\n".join(lines)

    # STORE
    def remember_input(self, user_input: str) -> None:
        self.memory.remember(user_input, scope=self._scope("session/input"), source="system")

    def remember_plan(self, plan: PlanPacket) -> None:
        self.memory.remember(plan.model_dump_json(indent=2), scope=self._scope("session/plan"), source="thinker")

    def remember_worker_result(self, result: WorkerResult) -> None:
        self.memory.remember(result.model_dump_json(indent=2), scope=self._scope(f"workers/{result.worker_id}"), source=f"worker:{result.worker_id}")

    def remember_verification(self, report: VerificationReport) -> None:
        self.memory.remember(report.model_dump_json(indent=2), scope=self._scope("session/verification"), source="verifier")

    # RECALL
    def recall_for_thinker(self, query: str) -> str:
        matches = self.memory.recall(query, scope=self._scope("session"), limit=5)
        return self._join(matches)

    def recall_for_worker(self, worker_id: str, query: str) -> str:
        view = self.memory.slice(
            scopes=[self._scope("session"), self._scope(f"workers/{worker_id}")],
            read_only=True,
        )
        matches = view.recall(query, limit=6)
        return self._join(matches)
