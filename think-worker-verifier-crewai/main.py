"""
main.py — Interactive and Advanced Stateful TWV (Thinker-Worker-Verifier) Console UI.

This entry point coordinates user interactions via an ANSI-colored CLI terminal.
It implements architecture diagram rendering, step-by-step agent execution tracing,
historical task retrieval (resume state), and agent configuration inspection.
"""
from __future__ import annotations
import os
import sys
import time
from typing import Optional
from orchestrator import TWVOrchestrator

def main() -> None:
    """
    Main application entry point.
    Applies custom Pydantic patches, loads environment variables, suppresses telemetry,
    and runs the interactive or batch (pipe-based) command-line interface.
    """
    # Programmatically apply Pydantic monkeypatch to allow extra model fields in CrewAI Memory
    try:
        from pydantic_patch import apply_pydantic_patch
        apply_pydantic_patch()
    except Exception:
        pass

    # Suppress CrewAI and OpenTelemetry telemetry calls to avoid 'crew_memory' serialization issues
    os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
    os.environ["CREWAI_DISABLE_TRACKING"] = "true"
    os.environ["OTEL_SDK_DISABLED"] = "true"

    from dotenv import load_dotenv
    load_dotenv()

    from config import settings
    from history_store import HistoryStore
    from models import SessionState, FeedbackAction

    # ANSI escape codes for shell text formatting and colors
    C_RESET = "\033[0m"
    C_BOLD = "\033[1m"
    C_DIM = "\033[2m"
    C_CYAN = "\033[36m"
    C_GREEN = "\033[32m"
    C_YELLOW = "\033[33m"
    C_RED = "\033[31m"
    C_MAGENTA = "\033[35m"

    def draw_arch_diagram() -> None:
        """
        Renders a structured and colored ASCII diagram of the Thinker-Worker-Verifier architecture.
        """
        diagram = f"""
{C_CYAN}{C_BOLD}             ┌────────────────────────────────────────────────────────┐
             │                   TWVOrchestrator                      │
             │                                                        │
             │     ┌───────────┐  PlanPacket  ┌─────────────────┐     │
             │     │  THINKER  ├─────────────►│   WORKER POOL   │     │
             │     │ Decompose │◄─────────────│ writer / coder  │     │
             │     │  + Route  │  self-call   │    / analyst    │     │
             │     └─────┬─────┘              └────────┬────────┘     │
             │           │                             │ WorkerResult │
             │           │ Store/Recall                ▼              │
             │           │                    ┌─────────────────┐     │
             │           │◄───────────────────┤     MEMORY      │     │
             │           │                    │  Session State  │     │
             │           │                    └────────┬────────┘     │
             │           ▼                             ▼              │
             │  ┌─────────────────┐           ┌─────────────────┐     │
             │  │    FEEDBACK     │◄──────────┤    VERIFIER     │     │
             │  │   CONTROLLER    │  Report   │  Test/Check/QA  │     │
             │  └────────┬────────┘           └─────────────────┘     │
             │           │                                            │
             │           ├──────────────┬──────────────┐              │
             │           ▼              ▼              ▼              │
             │        REPLAN     RETRY/REASSIGN   OK → FINISH         │
             └─────────────────────────────────────────┬──────────────┘
                                                       ▼
                                                 {C_GREEN}FINAL OUTPUT{C_CYAN}{C_BOLD}
{C_RESET}"""
        print(diagram)

    def render_step(phase: str, state: SessionState, decision: Optional[FeedbackAction] = None) -> None:
        """
        Visual callback used during orchestrator execution.
        Prints real-time tracking information to depict agent status transitions.
        
        Args:
            phase: Key representing the current process state (e.g., "PLAN_START", "EXECUTE_DONE").
            state: The active SessionState object containing accumulated telemetry and results.
            decision: Optional FeedbackAction returned by the verifier evaluation.
        """
        time.sleep(0.5)
        if phase == "PLAN_START":
            print(f"\n[{C_CYAN}THINKER{C_RESET}] {C_BOLD}Analyzing user task and planning decomposition...{C_RESET}")
            print(f"  └─ {C_DIM}Consulting semantic memory and resolving optimal worker assignment...{C_RESET}")
        elif phase == "PLAN_DONE":
            p = state.plan
            if p:
                print(f"[{C_GREEN}THINKER - PLAN CREATED{C_RESET}]")
                print(f"  ├─ {C_BOLD}Summary:{C_RESET} {p.summary}")
                print(f"  ├─ {C_BOLD}Decomposed Steps:{C_RESET}")
                for i, step in enumerate(p.decomposition, 1):
                    print(f"  │  {i}. {step}")
                print(f"  ├─ {C_BOLD}Success Criteria:{C_RESET} {', '.join(p.success_criteria)}")
                print(f"  └─ {C_BOLD}Assigned Worker:{C_RESET} {C_YELLOW}{p.selected_worker.upper()}{C_RESET}")
        elif phase == "EXECUTE_START":
            print(f"\n[{C_YELLOW}WORKER - {state.selected_worker.upper()}{C_RESET}] {C_BOLD}Executing steps from the plan...{C_RESET}")
            print(f"  └─ {C_DIM}Attempt #{len(state.worker_outputs)+1} using worker-specific memory context...{C_RESET}")
        elif phase == "EXECUTE_DONE":
            print(f"[{C_GREEN}WORKER - EXECUTION COMPLETED{C_RESET}]")
            print(f"  └─ {C_DIM}Worker results compiled successfully. Advancing to verification...{C_RESET}")
        elif phase == "VERIFY_START":
            print(f"\n[{C_MAGENTA}VERIFIER{C_RESET}] {C_BOLD}Initiating QA & Quality Verification check...{C_RESET}")
            print(f"  └─ {C_DIM}Evaluating generated results against criteria established by Thinker...{C_RESET}")
        elif phase == "VERIFY_DONE":
            r = state.latest_report
            if r:
                color = C_GREEN if r.status == "OK" else C_RED
                print(f"[{C_MAGENTA}VERIFIER - VERIFICATION REPORT ISSUED{C_RESET}]")
                print(f"  ├─ {C_BOLD}Status:{C_RESET} {color}{r.status}{C_RESET}")
                print(f"  ├─ {C_BOLD}Quality Score:{C_RESET} {color}{r.score}/10{C_RESET}")
                print(f"  ├─ {C_BOLD}Feedback:{C_RESET} {r.feedback}")
                if r.evidence:
                    print(f"  └─ {C_BOLD}Evidence Provided:{C_RESET} {', '.join(r.evidence)}")
        elif phase == "DECISION":
            if decision == FeedbackAction.FINISH:
                print(f"\n{C_GREEN}✔ [FEEDBACK CONTROLLER] Quality thresholds satisfied! Completing task.{C_RESET}")
            elif decision == FeedbackAction.RETRY:
                print(f"\n{C_YELLOW}⚠ [FEEDBACK CONTROLLER] Quality is insufficient. Action: RETRY (same worker).{C_RESET}")
                print(f"  └─ {C_DIM}Instructing worker to refine output incorporating Verifier suggestions...{C_RESET}")
            elif decision == FeedbackAction.REASSIGN:
                print(f"\n{C_RED}⚠ [FEEDBACK CONTROLLER] Worker profile mismatch. Action: REASSIGN.{C_RESET}")
                print(f"  └─ {C_DIM}Re-allocating execution to a different specialty worker...{C_RESET}")
            elif decision == FeedbackAction.REPLAN:
                print(f"\n{C_RED}💥 [FEEDBACK CONTROLLER] Strategic plan error detected. Action: REPLAN.{C_RESET}")
                print(f"  └─ {C_DIM}Invoking Thinker to reformulate task steps and criteria...{C_RESET}")
        elif phase == "RESUME":
            print(f"\n{C_CYAN}▶ Resuming interrupted session:{C_RESET} {C_BOLD}{state.user_input}{C_RESET}")
            print(f"  ├─ Prior progress: {len(state.worker_outputs)} attempts recorded")
            print(f"  ├─ Retry: {state.retry_count} | Reassign: {state.reassign_count} | Replan: {state.replan_count}")
            if state.selected_worker:
                print(f"  └─ Active Worker: {C_YELLOW}{state.selected_worker.upper()}{C_RESET}")

    def print_summary(state: SessionState) -> None:
        """
        Prints a clean, comprehensive review of the final session run results.
        
        Args:
            state: The finalized SessionState containing run stats and output.
        """
        print("\n" + "=" * 70)
        print(f"  {C_BOLD}{C_GREEN}TWV ORCHESTRATOR RUN EXECUTION SUMMARY{C_RESET}")
        print("=" * 70)
        print(f"  Original Task      : {C_BOLD}{state.user_input}{C_RESET}")
        print(f"  Final Worker       : {C_YELLOW}{state.selected_worker.upper() if state.selected_worker else 'None'}{C_RESET}")
        print(f"  Total Attempts     : {len(state.worker_outputs)}")
        print(f"    ├─ Retry         : {state.retry_count}")
        print(f"    ├─ Reassign      : {state.reassign_count}")
        print(f"    └─ Replan        : {state.replan_count}")
        if state.latest_report:
            color = C_GREEN if state.latest_report.status == "OK" else C_RED
            print(f"  Verifier Verdict   : {color}{state.latest_report.status.value} (Score: {state.latest_report.score}/10){C_RESET}")
        print("=" * 70)
        print(f"\n  {C_BOLD}VALIDATED FINAL OUTPUT{C_RESET}\n" + "=" * 70)
        print(state.final_output or state.latest_output or f"{C_RED}(no output generated){C_RESET}")
        print("=" * 70 + "\n")

    def menu_history(store: HistoryStore) -> Optional[SessionState]:
        """
        Interactive sub-menu displaying past runs stored in SQLite DB.
        Allows users to select an uncompleted run to resume execution.
        
        Args:
            store: The SQLite HistoryStore instance.
        """
        sessions = store.list_sessions()
        if not sessions:
            print(f"\n{C_YELLOW}No historical sessions found in database.{C_RESET}")
            time.sleep(1.5)
            return None

        while True:
            print("\n" + "=" * 70)
            print(f"  {C_BOLD}{C_CYAN}HISTORICAL TASK ARCHIVE{C_RESET}")
            print("=" * 70)
            for i, s in enumerate(sessions, 1):
                short_input = s['user_input'][:50] + ("..." if len(s['user_input']) > 50 else "")
                print(f"  [{C_GREEN}{i}{C_RESET}] ID: {s['id']} | Date: {s['timestamp']} | Task: {C_BOLD}{short_input}{C_RESET}")
            print(f"  [{C_RED}0{C_RESET}] Back to main menu")
            print("=" * 70)

            choice = input(f"\nSelect a task number to inspect or resume: ").strip()
            if choice == "0":
                return None
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(sessions):
                    selected_id = sessions[idx]['id']
                    state = store.get_session(selected_id)
                    if state:
                        if state.final_output:
                            print(f"\n{C_GREEN}This task is already completed.{C_RESET}")
                            print(f"{C_BOLD}Saved Output:{C_RESET}\n{state.final_output}")
                            input(f"\n{C_DIM}Press ENTER to continue...{C_RESET}")
                            continue
                        else:
                            print(f"\n{C_YELLOW}Interrupted session retrieved successfully. Loading...{C_RESET}")
                            return state
                else:
                    print(f"{C_RED}Invalid selection.{C_RESET}")
            except ValueError:
                print(f"{C_RED}Please input a valid numeric value.{C_RESET}")

    store = HistoryStore()
    orchestrator = TWVOrchestrator()

    # If inputs are fed via system pipe / redirection, bypass interactive menu and execute in batch mode
    if not sys.stdin.isatty():
        user_input = sys.stdin.read().strip()
        if not user_input:
            sys.exit(1)
        state = orchestrator.run(user_input)
        print(state.final_output or state.latest_output or "")
        sys.exit(0)

    # Shell UI Interactive Loop
    while True:
        print("\n" + "=" * 70)
        print(f"  {C_BOLD}{C_CYAN}TWV STATEFUL SYSTEM{C_RESET} | Advanced Multi-Agent Orchestration")
        print("=" * 70)
        draw_arch_diagram()
        print("=" * 70)
        print(f"  [{C_GREEN}1{C_RESET}] Execute a NEW task")
        print(f"  [{C_GREEN}2{C_RESET}] View and RESUME historical tasks ({len(store.list_sessions())} in DB)")
        print(f"  [{C_GREEN}3{C_RESET}] View active agent model configurations")
        print(f"  [{C_RED}0{C_RESET}] Exit")
        print("=" * 70)

        cmd = input(f"\nSelect an option: ").strip()
        if cmd == "0":
            print(f"\nGoodbye!{C_RESET}")
            break

        elif cmd == "1":
            user_input = input(f"\n{C_BOLD}Enter task description:{C_RESET}\n> ").strip()
            if not user_input:
                print(f"{C_RED}Invalid task input.{C_RESET}")
                continue

            print(f"\n{C_GREEN}Starting orchestration pipeline...{C_RESET}")
            state = orchestrator.run(user_input, step_callback=render_step)
            store.save_session(state)
            print_summary(state)

        elif cmd == "2":
            resumed_state = menu_history(store)
            if resumed_state:
                print(f"\n{C_GREEN}Resuming task with retrieved session state...{C_RESET}")
                final_state = orchestrator.run(resumed_state.user_input, state=resumed_state, step_callback=render_step)
                store.save_session(final_state)
                print_summary(final_state)

        elif cmd == "3":
            print("\n" + "=" * 70)
            print(f"  {C_BOLD}ACTIVE AGENTS MODEL CONFIGURATION{C_RESET}")
            print("=" * 70)
            print(f"  Provider Base URL  : {settings.openai_api_base or 'Default OpenAI (SaaS)'}")
            print(f"  Model Thinker (🧠)  : {C_CYAN}{settings.thinker_model}{C_RESET}")
            print(f"  Model Worker  (🛠)  : {C_YELLOW}{settings.worker_model}{C_RESET}")
            print(f"  Model Verifier (🛡) : {C_MAGENTA}{settings.verifier_model}{C_RESET}")
            print("=" * 70)
            input(f"\n{C_DIM}Press ENTER to return to menu...{C_RESET}")

        else:
            print(f"{C_RED}Invalid option selected.{C_RESET}")

if __name__ == "__main__":
    main()
