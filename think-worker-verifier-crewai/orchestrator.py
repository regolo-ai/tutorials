"""
orchestrator.py
===============
Orchestratore stateful del pattern Thinker-Worker-Verifier.

Separa execution layer (Crew/Agent/Task) da control layer (stato e routing).
Implementa la state machine del diagramma:
    PLAN -> EXECUTE -> VERIFY -> [FINISH|RETRY|REASSIGN|REPLAN]
"""
from __future__ import annotations
from crewai import Crew, Process
from agents import thinker_agent, verifier_agent
from config import settings
from feedback_controller import FeedbackController
from memory_layer import MemoryManager
from models import FeedbackAction, PlanPacket, SessionState, WorkerResult
from parsers import parse_model
from tasks import execution_task, planning_task, verification_task
from worker_pool import WorkerPool

class TWVOrchestrator:
    """Orchestratore principale. Utilizzo: state = TWVOrchestrator().run(task)"""

    def __init__(self) -> None:
        self.memory   = MemoryManager()
        self.pool     = WorkerPool()
        self.feedback = FeedbackController()
        self.thinker  = thinker_agent()
        self.verifier = verifier_agent()

    def run(self, user_input: str, state: Optional[SessionState] = None, step_callback: Optional[callable] = None) -> SessionState:
        if state is None:
            state = SessionState(user_input=user_input)
            self.memory.remember_input(user_input)
            if step_callback:
                step_callback("PLAN_START", state)
            self._plan(state)
            if step_callback:
                step_callback("PLAN_DONE", state)
        else:
            # Riprendiamo l'esecuzione da uno stato pregresso salvato
            if step_callback:
                step_callback("RESUME", state)

        while True:
            if step_callback:
                step_callback("EXECUTE_START", state)
            self._execute(state)
            if step_callback:
                step_callback("EXECUTE_DONE", state)
                step_callback("VERIFY_START", state)
            self._verify(state)
            if step_callback:
                step_callback("VERIFY_DONE", state)
                
            decision = self.feedback.decide(state, state.latest_report)
            if step_callback:
                step_callback("DECISION", state, decision)

            if decision == FeedbackAction.FINISH:
                state.final_output = state.latest_output
                return state
            if decision == FeedbackAction.RETRY:
                state.retry_count += 1
            elif decision == FeedbackAction.REASSIGN:
                state.reassign_count += 1
                self._reassign(state)
            elif decision == FeedbackAction.REPLAN:
                state.replan_count += 1
                self._plan(state, verifier_feedback=state.latest_report.feedback)

    def _plan(self, state: SessionState, verifier_feedback: str = "") -> None:
        ctx = self.memory.recall_for_thinker(state.user_input)
        task = planning_task(self.thinker, state.user_input,
                             self.pool.catalog(), ctx, verifier_feedback)
        crew = Crew(agents=[self.thinker], tasks=[task], process=Process.sequential,
                    memory=self.memory.memory, embedder=settings.embedder,
                    verbose=settings.verbose)
        result = crew.kickoff()
        raw = result.raw if hasattr(result, "raw") else str(result)
        plan = parse_model(raw, PlanPacket)

        # Self-call: il Thinker chiede di ridecomporsi
        if plan.requires_self_call and state.replan_count < settings.max_replans:
            state.replan_count += 1
            self._plan(state, f"Self-call richiesto. Note: {plan.thinker_notes}")
            return

        state.plan = plan
        state.selected_worker = plan.selected_worker
        self.memory.remember_plan(plan)

    def _execute(self, state: SessionState) -> None:
        profile = self.pool.get(state.selected_worker)
        ctx = self.memory.recall_for_worker(profile.worker_id, state.user_input)
        fb = state.latest_report.feedback if state.latest_report else ""
        task = execution_task(profile.agent, state.plan, ctx, fb, state.user_input)
        crew = Crew(agents=[profile.agent], tasks=[task], process=Process.sequential,
                    memory=self.memory.memory, embedder=settings.embedder,
                    verbose=settings.verbose)
        result = crew.kickoff()
        wr = WorkerResult(
            worker_id=profile.worker_id,
            attempt=len(state.worker_outputs) + 1,
            content=result.raw if hasattr(result, "raw") else str(result),
        )
        state.worker_outputs.append(wr)
        self.memory.remember_worker_result(wr)

    def _verify(self, state: SessionState) -> None:
        task = verification_task(self.verifier, state.user_input, state.plan,
                                 state.latest_output or "", state.selected_worker or "")
        crew = Crew(agents=[self.verifier], tasks=[task], process=Process.sequential,
                    memory=self.memory.memory, embedder=settings.embedder,
                    verbose=settings.verbose)
        result = crew.kickoff()
        raw = result.raw if hasattr(result, "raw") else str(result)
        from models import VerificationReport
        report = parse_model(raw, VerificationReport)
        state.verification_reports.append(report)
        self.memory.remember_verification(report)

    def _reassign(self, state: SessionState) -> None:
        rec = state.latest_report.recommended_worker if state.latest_report else None
        if rec and rec in self.pool.ids() and rec != state.selected_worker:
            state.selected_worker = rec
        else:
            state.selected_worker = self.pool.fallback(
                state.selected_worker or self.pool.ids()[0])
