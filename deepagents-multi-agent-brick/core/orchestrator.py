"""Deep Agents Multi-Agent Orchestrator with Brick Semantic Routing.
Coordinates Planner, Researcher, Tool Agent, Code Executor, Reviewer, and Report Writer.
"""

import time
from typing import Any, Callable, Dict, List, Optional

import config
from core.brick_router import BrickRouter
from core.budget_controller import BudgetController, get_budget_controller
from core.regolo_client import RegoloClient
from core.sandbox import SandboxEnvironment
from core.subagents.browser_tool_agent import BrowserToolAgent
from core.subagents.code_executor import CodeExecutorSubAgent
from core.subagents.planner import PlannerSubAgent
from core.subagents.report_writer import ReportWriterSubAgent
from core.subagents.researcher import ResearcherSubAgent
from core.subagents.reviewer import ReviewerSubAgent


class DeepAgentOrchestrator:
    """End-to-End Orchestrator for the Deep Agents Pipeline."""

    def __init__(
        self,
        client: Optional[RegoloClient] = None,
        router: Optional[BrickRouter] = None,
        budget_controller: Optional[BudgetController] = None,
    ):
        self.client = client or RegoloClient()
        self.router = router or BrickRouter(client=self.client)
        self.budget_controller = budget_controller or get_budget_controller()

        # Initialize sub-agents
        self.planner = PlannerSubAgent(
            client=self.client, router=self.router, budget_controller=self.budget_controller
        )
        self.researcher = ResearcherSubAgent(
            client=self.client, router=self.router, budget_controller=self.budget_controller
        )
        self.tool_agent = BrowserToolAgent(
            client=self.client, router=self.router, budget_controller=self.budget_controller
        )
        self.code_executor = CodeExecutorSubAgent(
            client=self.client, router=self.router, budget_controller=self.budget_controller
        )
        self.reviewer = ReviewerSubAgent(
            client=self.client, router=self.router, budget_controller=self.budget_controller
        )
        self.report_writer = ReportWriterSubAgent(
            client=self.client, router=self.router, budget_controller=self.budget_controller
        )

    def run_pipeline(
        self,
        sandbox: SandboxEnvironment,
        goal: str = "Synthesize typed MCP tool harness from raw repository APIs",
        log_callback: Optional[Callable[[str, str], None]] = None,
        human_approval_callback: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Dict[str, Any]:
        """Execute the entire Deep Agents multi-agent flow."""
        def log(agent_tag: str, message: str):
            if log_callback:
                log_callback(agent_tag, message)

        # Initialize a fresh budget run session for this pipeline execution
        self.budget_controller.start_new_run()

        pipeline_start = time.time()
        
        # Classify high-level intent
        goal_lower = goal.lower()
        if any(w in goal_lower for w in ["assessment", "analizza", "analisi", "audit", "review", "struttura"]):
            goal_type = "ASSESSMENT"
        elif any(w in goal_lower for w in ["tool", "mcp", "harness", "fastmcp", "sintetizza", "schema"]):
            goal_type = "TOOL_SYNTHESIS"
        else:
            goal_type = "HYBRID"

        pipeline_context: Dict[str, Any] = {
            "goal": goal,
            "goal_type": goal_type,
        }
        results_log: Dict[str, Any] = {}

        log("ORCHESTRATOR", f"Starting Deep Agents pipeline with Goal: '{goal}' (Mode: {goal_type})")
        log("BUDGET", f"Total Pipeline Token Budget: {self.budget_controller.total_budget:,} tokens")

        # -------------------------------------------------------------
        # STEP 1: PLANNER
        # -------------------------------------------------------------
        log("ORCHESTRATOR", "▶ Activating Stage 1: Deep Agent Planner")
        planner_res = self.planner.run(
            sandbox=sandbox,
            context=pipeline_context,
            log_callback=log_callback,
        )
        pipeline_context["planner_output"] = planner_res.structured_data
        results_log["planner"] = planner_res.to_dict()

        # Human Approval Gate (Optional interactive checkpoint)
        if human_approval_callback:
            log("ORCHESTRATOR", "Awaiting Human-In-The-Loop DAG Approval...")
            approved = human_approval_callback(planner_res.structured_data)
            if not approved:
                log("ORCHESTRATOR", "❌ Plan rejected by operator. Terminating pipeline.")
                return {"status": "ABORTED", "reason": "Operator rejected execution DAG", "results": results_log}
            log("ORCHESTRATOR", "✔ Plan approved by operator. Proceeding to execution DAG.")

        # -------------------------------------------------------------
        # STEP 2: RESEARCHER
        # -------------------------------------------------------------
        log("ORCHESTRATOR", "▶ Activating Stage 2: API & Tool Researcher")
        researcher_res = self.researcher.run(
            sandbox=sandbox,
            context=pipeline_context,
            log_callback=log_callback,
        )
        pipeline_context["researcher_output"] = researcher_res.structured_data
        results_log["researcher"] = researcher_res.to_dict()

        # -------------------------------------------------------------
        # STEP 3: BROWSER / TOOL AGENT
        # -------------------------------------------------------------
        log("ORCHESTRATOR", "▶ Activating Stage 3: Live Tool & Schema Prober")
        tool_agent_res = self.tool_agent.run(
            sandbox=sandbox,
            context=pipeline_context,
            log_callback=log_callback,
        )
        pipeline_context["tool_agent_output"] = tool_agent_res.structured_data
        results_log["tool_agent"] = tool_agent_res.to_dict()

        # -------------------------------------------------------------
        # STEP 4: CODE EXECUTOR
        # -------------------------------------------------------------
        log("ORCHESTRATOR", "▶ Activating Stage 4: MCP Code Executor & Synthesizer")
        executor_res = self.code_executor.run(
            sandbox=sandbox,
            context=pipeline_context,
            log_callback=log_callback,
        )
        pipeline_context["code_executor_output"] = executor_res.structured_data
        results_log["code_executor"] = executor_res.to_dict()

        # -------------------------------------------------------------
        # STEP 5: REVIEWER
        # -------------------------------------------------------------
        log("ORCHESTRATOR", "▶ Activating Stage 5: Harness & Spec Reviewer")
        reviewer_res = self.reviewer.run(
            sandbox=sandbox,
            context=pipeline_context,
            log_callback=log_callback,
        )
        pipeline_context["reviewer_output"] = reviewer_res.structured_data
        results_log["reviewer"] = reviewer_res.to_dict()

        # -------------------------------------------------------------
        # STEP 6: REPORT WRITER
        # -------------------------------------------------------------
        log("ORCHESTRATOR", "▶ Activating Stage 6: Harness Report Writer")
        pipeline_context["results_log"] = results_log
        pipeline_context["routing_decisions"] = [v.get("routing_decision", {}) for v in results_log.values()]
        report_res = self.report_writer.run(
            sandbox=sandbox,
            context=pipeline_context,
            log_callback=log_callback,
        )
        pipeline_context["report_writer_output"] = report_res.structured_data
        results_log["report_writer"] = report_res.to_dict()

        pipeline_duration = round(time.time() - pipeline_start, 2)
        telemetry_summary = self.budget_controller.get_summary()

        log("ORCHESTRATOR", f"✔ Deep Agents Pipeline Completed in {pipeline_duration}s!")
        log("BUDGET", f"Cost: ${telemetry_summary['total_regolo_cost_usd']:.4f} (Regolo) vs ${telemetry_summary['total_frontier_cost_usd']:.4f} (Frontier) -> Savings: {telemetry_summary['savings_percentage']}%")

        return {
            "status": "SUCCESS",
            "duration_sec": pipeline_duration,
            "results": results_log,
            "telemetry": telemetry_summary,
            "diff": sandbox.compute_diff(),
            "report_file": str(config.HARNESS_OUTPUT_DIR / "HARNESS_SPEC.md"),
        }
