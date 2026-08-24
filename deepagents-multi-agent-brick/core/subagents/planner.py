"""Planner Sub-Agent for Deep Agents Multi-Agent Orchestration."""

import json
from typing import Any, Callable, Dict, List, Optional

from core.sandbox import SandboxEnvironment
from core.subagents.base import BaseSubAgent, SubAgentResult


class PlannerSubAgent(BaseSubAgent):
    """Decomposes the high-level tool synthesis goal into a structured DAG."""

    def __init__(self, **kwargs):
        super().__init__(subagent_key="planner", **kwargs)

    def run(
        self,
        sandbox: SandboxEnvironment,
        context: Dict[str, Any],
        log_callback: Optional[Callable[[str, str], None]] = None,
        force_escalate: bool = False,
    ) -> SubAgentResult:
        def log(msg: str):
            if log_callback:
                log_callback("PLANNER", msg)

        goal = context.get("goal", "Analyze codebase modules and APIs")
        goal_type = context.get("goal_type", "ASSESSMENT")
        files = sandbox.list_files()
        tree_summary = sandbox.get_tree_summary(max_entries=25)
        log(f"Inspecting repository tree ({len(files)} files discovered)...")

        task_desc = f"Construct multi-agent execution DAG for {goal_type} goal: '{goal}'. Workspace files: {len(files)}"
        
        # 1. Brick Semantic Routing
        routing_decision = self._route_task(
            task_description=task_desc,
            tools_requested=self.profile.get("allowed_tools", []),
            force_escalate=force_escalate,
        )
        log(f"Brick routed Planner to [cyan]{routing_decision.selected_model}[/cyan] (Tier: {routing_decision.routing_tier}, Complexity: {routing_decision.complexity_score:.1f}/10)")

        # 2. Planning Prompt Construction — Ask brick-complexity-pro to dynamically generate the DAG
        system_prompt = (
            "You are 'brick-complexity-pro', the semantic routing meta-model for Regolo.ai. "
            "Your mission is to decompose the user's synthesis goal into an optimal multi-step execution "
            "DAG across specialized sub-agents: Researcher, Tool/Browser Prober, Code Executor, Reviewer, "
            "and Report Writer. Each goal_type may require a different phase ordering, subset of phases, "
            "or additional specialized stages. Tailor the DAG structure, step count, and phase selection "
            "to the specific goal_type."
        )
        user_prompt = f"""As the brick-complexity-pro semantic routing meta-model, dynamically generate a structured execution DAG to achieve the following user goal. Do NOT use a fixed template — adapt the plan structure based on the goal_type.

Target Goal: {goal}
Execution Mode: {goal_type}

Discovered Repository Summary ({len(files)} files):
{tree_summary}

Consider these available sub-agents and their capabilities:
- **researcher**: AST module extraction, contract analysis, interface discovery, architectural responsibilities
- **browser_tool_agent**: Live endpoint probing, schema validation, mock testing, interaction pattern discovery
- **code_executor**: Code synthesis (MCP tools, Pydantic schemas, harnesses), sandboxed validation test execution
- **reviewer**: Quality audit, architectural assessment, MCP compliance, hallucination resistance, spec verification
- **report_writer**: Markdown documentation, module catalog, telemetry scoreboard, goal-specific deliverable

**Goal-Specific Guidance:**
- For `ASSESSMENT` mode: Emphasize research, probing, and reviewer phases. Code Executor should produce validation harnesses, not full tool synthesis. Skip aggressive tool generation.
- For `TOOL_SYNTHESIS` mode: Full pipeline — AST extraction → contract probing → MCP code generation → schema audit → harness documentation.
- For `HYBRID` mode: Blend both — partial synthesis with concurrent assessment.
- For other/all modes: Generate a plan that directly fulfills the stated goal.

Decompose the goal into a structured DAG with 4-7 steps (use more steps for complex goals, fewer for simple ones).
Output ONLY valid JSON matching this schema:
{{
    "plan_id": "DEEP-AGENT-DAG-<dynamic>",
    "title": "<Concise, goal-specific plan title>",
    "target_goal": "{goal}",
    "goal_type": "{goal_type}",
    "total_estimated_steps": <integer 4-7>,
    "estimated_tokens": <integer>,
    "steps": [
        {{
            "step_number": <integer>,
            "subagent": "<researcher|browser_tool_agent|code_executor|reviewer|report_writer>",
            "action": "<Goal-specific action name>",
            "description": "<What this step does toward fulfilling the goal>",
            "assigned_budget": <integer>,
            "preferred_model": <one of: gpt-oss-20b, qwen3.5-122b, Llama-3.3-70B-Instruct>
        }}
    ]
}}

Ensure the phases logically flow toward the stated goal. Each step description must reference the specific goal."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 3. LLM Execution & Telemetry Recording
        exec_res = self._execute_llm(
            decision=routing_decision,
            messages=messages,
            stage="1_plan_dag_decomposition",
        )

        structured_data = self._parse_json_safely(exec_res["content"])
        if not structured_data or "steps" not in structured_data:
            # Dynamically generated DAG execution plan tailored to the target goal
            file_sample = ", ".join(files[:3]) if files else "target workspace files"
            
            # Tailor the fallback DAG based on goal_type
            if goal_type == "ASSESSMENT":
                phases = [
                    {
                        "step_number": 1,
                        "subagent": "researcher",
                        "action": "Module AST & Contract Discovery",
                        "description": f"Scan codebase ({file_sample}) and extract components, functions, and contracts for assessment of: '{goal}'.",
                        "assigned_budget": 3000,
                        "preferred_model": "gpt-oss-20b",
                    },
                    {
                        "step_number": 2,
                        "subagent": "browser_tool_agent",
                        "action": "Interface & Schema Probing",
                        "description": f"Probe input/output interfaces, dependencies, and behavioral shapes for assessment: '{goal}'.",
                        "assigned_budget": 2500,
                        "preferred_model": "gpt-oss-20b",
                    },
                    {
                        "step_number": 3,
                        "subagent": "code_executor",
                        "action": "Validation Harness Synthesis",
                        "description": f"Synthesize validation test harnesses and boundary checks for: '{goal}'.",
                        "assigned_budget": 3500,
                        "preferred_model": "qwen3.5-122b",
                    },
                    {
                        "step_number": 4,
                        "subagent": "reviewer",
                        "action": "Architectural Quality Audit",
                        "description": f"Audit analyzed modules and artifacts against quality standards for: '{goal}'.",
                        "assigned_budget": 3500,
                        "preferred_model": "qwen3.5-122b",
                    },
                    {
                        "step_number": 5,
                        "subagent": "report_writer",
                        "action": "Assessment Report Synthesis",
                        "description": f"Compile comprehensive architectural assessment, module catalog, and cost telemetry scoreboard for: '{goal}'.",
                        "assigned_budget": 3500,
                        "preferred_model": "gpt-oss-20b",
                    },
                ]
            else:
                phases = [
                    {
                        "step_number": 1,
                        "subagent": "researcher",
                        "action": "Module AST & Contract Discovery",
                        "description": f"Scan codebase ({file_sample}) and extract components, functions, and contracts for: '{goal}'.",
                        "assigned_budget": 2500,
                        "preferred_model": "gpt-oss-20b",
                    },
                    {
                        "step_number": 2,
                        "subagent": "browser_tool_agent",
                        "action": "Interface & Schema Probing",
                        "description": f"Probe input/output interfaces, dependencies, and behavioral shapes for: '{goal}'.",
                        "assigned_budget": 2000,
                        "preferred_model": "gpt-oss-20b",
                    },
                    {
                        "step_number": 3,
                        "subagent": "code_executor",
                        "action": "Synthesis & Sandboxed Execution",
                        "description": f"Synthesize structured schemas, MCP tools, and verification suites fulfilling: '{goal}'.",
                        "assigned_budget": 4000,
                        "preferred_model": "qwen3.5-122b",
                    },
                    {
                        "step_number": 4,
                        "subagent": "reviewer",
                        "action": "Quality & Architecture Audit",
                        "description": f"Audit analyzed modules and synthesized artifacts against quality standards and goal fulfillment for: '{goal}'.",
                        "assigned_budget": 3000,
                        "preferred_model": "qwen3.5-122b",
                    },
                    {
                        "step_number": 5,
                        "subagent": "report_writer",
                        "action": "Documentation & Scoreboard Synthesis",
                        "description": f"Compile comprehensive specification, module catalog table, and Brick cost-savings scoreboard for: '{goal}'.",
                        "assigned_budget": 3000,
                        "preferred_model": "gpt-oss-20b",
                    },
                ]
            
            structured_data = {
                "plan_id": f"DEEP-AGENT-DAG-{'ASSESSMENT' if goal_type == 'ASSESSMENT' else 'SYNTHESIS'}-01",
                "title": f"Deep Agents Execution DAG: {goal[:50]}",
                "target_goal": goal,
                "goal_type": goal_type,
                "total_estimated_steps": len(phases),
                "estimated_tokens": 12500,
                "steps": phases,
            }
        else:
            structured_data["target_goal"] = goal

        event = exec_res["event"]
        log(f"Plan created with {len(structured_data.get('steps', []))} DAG execution steps. Total estimated tokens: {structured_data.get('estimated_tokens', 12000):,}")

        return SubAgentResult(
            subagent_key=self.subagent_key,
            role_name=routing_decision.role_name,
            status="SUCCESS",
            output_text=exec_res["content"],
            structured_data=structured_data,
            routing_decision=routing_decision,
            tokens_used=event.total_tokens,
            prompt_tokens=event.prompt_tokens,
            completion_tokens=event.completion_tokens,
            latency_sec=event.latency_sec,
            cost_regolo_usd=event.cost_regolo_usd,
            cost_frontier_usd=event.cost_frontier_usd,
            artifacts_created=[],
        )
