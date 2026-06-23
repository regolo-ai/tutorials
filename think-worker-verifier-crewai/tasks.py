"""tasks.py — Factory dei task CrewAI con prompt contrattuali."""
from __future__ import annotations
from crewai import Agent, Task
from models import PlanPacket


def planning_task(thinker: Agent, user_input: str, worker_catalog: str,
                  memory_context: str, verifier_feedback: str = "") -> Task:
    """Task di pianificazione: il Thinker produce un PlanPacket JSON."""
    feedback_section = (
        f"\n---\nFEEDBACK DA ITERAZIONE PRECEDENTE:\n{verifier_feedback}\n---"
        if verifier_feedback else ""
    )
    return Task(
        description=(
            "Analizza il task utente e rispondi SOLO con JSON valido.\n\n"
            f"TASK UTENTE:\n{user_input}\n\n"
            f"WORKER DISPONIBILI:\n{worker_catalog}\n\n"
            f"CONTESTO MEMORIA:\n{memory_context or 'Nessuno'}"
            f"{feedback_section}\n\n"
            "Formato obbligatorio:\n"
            "```json\n"
            "{\n"
            '  "summary": "...",\n'
            '  "decomposition": ["passo 1", "passo 2"],\n'
            '  "success_criteria": ["criterio 1"],\n'
            '  "risks": ["rischio 1"],\n'
            '  "selected_worker": "writer|coder|analyst",\n'
            '  "alternative_workers": ["..."],\n'
            '  "requires_self_call": false,\n'
            '  "thinker_notes": ""\n'
            "}\n"
            "```"
        ),
        expected_output="JSON conforme a PlanPacket.",
        agent=thinker,
    )


def execution_task(worker: Agent, plan: PlanPacket, memory_context: str,
                   feedback: str, user_input: str) -> Task:
    """Task di esecuzione: il Worker produce l'output finale."""
    steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan.decomposition))
    criteria = "\n".join(f"  - {c}" for c in plan.success_criteria)
    risks = "\n".join(f"  - {r}" for r in (plan.risks or ["Nessuno dichiarato"]))
    feedback_section = f"\n---\nFEEDBACK DA INCORPORARE:\n{feedback}\n---" if feedback else ""
    return Task(
        description=(
            "Esegui il task seguendo il piano. Produci direttamente l'output finale.\n\n"
            f"TASK UTENTE:\n{user_input}\n\n"
            f"SINTESI PIANO:\n{plan.summary}\n\n"
            f"PASSI:\n{steps}\n\n"
            f"CRITERI DI SUCCESSO:\n{criteria}\n\n"
            f"RISCHI NOTI:\n{risks}\n\n"
            f"CONTESTO MEMORIA:\n{memory_context or 'Nessuno'}"
            f"{feedback_section}"
        ),
        expected_output="Output finale completo e pronto all'uso.",
        agent=worker,
    )


def verification_task(verifier: Agent, user_input: str, plan: PlanPacket,
                      worker_output: str, worker_id: str) -> Task:
    """Task di verifica: il Verifier produce un VerificationReport JSON."""
    criteria = "\n".join(f"  - {c}" for c in plan.success_criteria)
    return Task(
        description=(
            "Valuta l'output del worker. Rispondi SOLO con JSON valido.\n\n"
            f"TASK UTENTE:\n{user_input}\n\n"
            f"WORKER USATO: {worker_id}\n\n"
            f"CRITERI DI SUCCESSO:\n{criteria}\n\n"
            f"PIANO:\n{plan.model_dump_json(indent=2)}\n\n"
            f"OUTPUT DA VALUTARE:\n{worker_output}\n\n"
            "Regole: FINISH=ok pronto, RETRY=da rifinire, REASSIGN=worker sbagliato, REPLAN=piano sbagliato\n\n"
            "Formato obbligatorio:\n"
            "```json\n"
            "{\n"
            '  "status": "OK|FAIL",\n'
            '  "score": 7,\n'
            '  "feedback": "...",\n'
            '  "evidence": ["esempio 1"],\n'
            '  "failure_type": "quality|worker_mismatch|planning_issue|other",\n'
            '  "recommended_action": "FINISH|RETRY|REASSIGN|REPLAN",\n'
            '  "recommended_worker": "writer|coder|analyst|null"\n'
            "}\n"
            "```"
        ),
        expected_output="JSON conforme a VerificationReport.",
        agent=verifier,
    )
