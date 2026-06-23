"""agents.py — Factory degli agenti CrewAI specializzati."""
from __future__ import annotations
from crewai import Agent
from config import settings

def thinker_agent() -> Agent:
    """Agente Thinker: Decompose + Route."""
    return Agent(
        role="Thinker / Orchestration Planner",
        goal=(
            "Analizzare il task utente, scomporlo in passi concreti, "
            "scegliere il worker piu adatto e definire criteri di successo verificabili. "
            "Rispondere sempre con un JSON conforme allo schema PlanPacket."
        ),
        backstory=(
            "Sei un architetto di soluzioni specializzato in decomposizione di problemi. "
            "Non esegui mai direttamente il lavoro: pianifichi, instradi e ottimizzi. "
            "Conosci le capacita di ogni worker nel pool e sai scegliere quello giusto. "
            "Quando il problema e troppo complesso, segnali requires_self_call=true."
        ),
        llm=settings.thinker_llm,
        verbose=settings.verbose,
        allow_delegation=False,
        max_iter=3,
    )

def worker_agent(worker_id: str, specialty: str, backstory: str) -> Agent:
    """Factory generica per un Worker specializzato."""
    return Agent(
        role=f"Worker - {worker_id.title()} Specialist",
        goal=(
            f"Produrre un output di alta qualita con specializzazione in {specialty}. "
            "Seguire fedelmente il piano, rispettare i criteri e incorporare il feedback ricevuto."
        ),
        backstory=backstory,
        llm=settings.worker_llm,
        verbose=settings.verbose,
        allow_delegation=False,
        max_iter=5,
    )

def verifier_agent() -> Agent:
    """Agente Verifier: Test / Compile / Check."""
    return Agent(
        role="Verifier / Quality Assurance Reviewer",
        goal=(
            "Valutare rigorosamente l'output del worker rispetto ai criteri del piano. "
            "Produrre un JSON conforme a VerificationReport con raccomandazione "
            "tra FINISH, RETRY, REASSIGN e REPLAN."
        ),
        backstory=(
            "Sei un quality assurance engineer imparziale. "
            "Valuti solo su criteri oggettivi, citi esempi specifici e scegli "
            "la raccomandazione piu efficiente per correggere il problema."
        ),
        llm=settings.verifier_llm,
        verbose=settings.verbose,
        allow_delegation=False,
        max_iter=3,
    )
