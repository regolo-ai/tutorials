"""worker_pool.py — Registro dei worker disponibili (Worker Pool)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from crewai import Agent
from agents import worker_agent

@dataclass(slots=True)
class WorkerProfile:
    worker_id: str
    specialty: str
    description: str
    agent: Agent

class WorkerPool:
    """Pool di worker specializzati selezionabili dinamicamente."""

    def __init__(self) -> None:
        self._workers: Dict[str, WorkerProfile] = {
            "writer": WorkerProfile(
                worker_id="writer", specialty="writing",
                description="Ideale per: spiegazioni, documentazione, tutorial, articoli, proposte.",
                agent=worker_agent("writer", "writing",
                    "Sei un technical writer esperto. Trasformi piani complessi in testi "
                    "chiari, ben strutturati e immediatamente leggibili."),
            ),
            "coder": WorkerProfile(
                worker_id="coder", specialty="coding",
                description="Ideale per: codice Python/JS/SQL, script, architettura software, API design.",
                agent=worker_agent("coder", "coding",
                    "Sei uno sviluppatore senior pragmatico. Scrivi codice pulito, manutenibile "
                    "e documentato. Rispetti PEP8 e le best practice per ogni linguaggio."),
            ),
            "analyst": WorkerProfile(
                worker_id="analyst", specialty="analysis",
                description="Ideale per: analisi comparative, decision table, valutazione opzioni, report.",
                agent=worker_agent("analyst", "analysis",
                    "Sei un analista rigoroso. Strutturi le analisi con pro/contro, criteri "
                    "ponderati e raccomandazioni finali motivate."),
            ),
        }

    def get(self, worker_id: str) -> WorkerProfile:
        return self._workers[worker_id]

    def ids(self) -> List[str]:
        return list(self._workers.keys())

    def catalog(self) -> str:
        return "\n".join(f"  - {w.worker_id}: {w.description}" for w in self._workers.values())

    def fallback(self, current_worker: str) -> str:
        for wid in self._workers:
            if wid != current_worker:
                return wid
        return current_worker
