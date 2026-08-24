"""Researcher Sub-Agent for Deep Agents Multi-Agent Orchestration."""

import ast
import json
import re
from typing import Any, Callable, Dict, List, Optional

from core.sandbox import SandboxEnvironment
from core.subagents.base import BaseSubAgent, SubAgentResult


class ResearcherSubAgent(BaseSubAgent):
    """Inspects raw codebase API endpoints and extracts formal contracts & failure modes."""

    def __init__(self, **kwargs):
        super().__init__(subagent_key="researcher", **kwargs)

    def run(
        self,
        sandbox: SandboxEnvironment,
        context: Dict[str, Any],
        log_callback: Optional[Callable[[str, str], None]] = None,
        force_escalate: bool = False,
    ) -> SubAgentResult:
        def log(msg: str):
            if log_callback:
                log_callback("RESEARCHER", msg)

        goal = context.get("goal", "Analyze codebase modules and APIs")
        goal_type = context.get("goal_type", "ASSESSMENT")

        # 1. Extract AST ground truth modules and endpoints from the actual codebase
        ast_modules, ast_endpoints = self._extract_ast_modules_and_endpoints(sandbox)

        # Read representative code snippets for LLM context without blowing token budget
        files = sandbox.list_files()
        api_files = [
            f for f in files
            if f.endswith(".py") and not f.startswith("tests/") and not f.startswith("test/") and not f.startswith("harness/")
        ]
        
        file_snippets = {}
        for f in api_files[:8]:
            content = sandbox.read_file(f)
            if content:
                file_snippets[f] = content[:1500]

        log(f"Extracted {len(ast_modules)} AST Python modules & {len(ast_endpoints)} functional contracts from workspace...")

        task_desc = f"Analyze Python AST modules ({len(ast_modules)} found) and functional contracts for goal: '{goal}'"
        
        # 2. Brick Semantic Routing
        routing_decision = self._route_task(
            task_description=task_desc,
            tools_requested=self.profile.get("allowed_tools", []),
            force_escalate=force_escalate,
        )
        log(f"Brick routed Researcher to [cyan]{routing_decision.selected_model}[/cyan] (Tier: {routing_decision.routing_tier}, Complexity: {routing_decision.complexity_score:.1f}/10)")

        # 3. Researcher Prompt
        system_prompt = (
            "You are an expert Codebase & API Researcher. Your task is to analyze Python modules, "
            "evaluate architectural responsibilities, extract class/function contracts, and assess code quality."
        )
        user_prompt = f"""Goal: {goal} (Mode: {goal_type})

Discovered AST Modules ({len(ast_modules)}):
{json.dumps(ast_modules[:15], indent=2)}

Discovered Function Contracts ({len(ast_endpoints)}):
{json.dumps(ast_endpoints[:15], indent=2)}

Representative Source Code Snippets:
{json.dumps(file_snippets, indent=2)}

Analyze each discovered module, describe its role and architectural purpose in the system, and catalog functional contracts.
Output ONLY valid JSON matching this schema:
{{
    "modules_analyzed": [
        {{
            "file_path": "<relative/file/path.py>",
            "module_name": "<module_name>",
            "components": ["<Class1>", "<func2>"],
            "description": "<Concise functional description of this module and its purpose>"
        }}
    ],
    "endpoints_analyzed": [
        {{
            "name": "<clean_tool_identifier>",
            "raw_function": "<ClassName.method_name or function_name>",
            "parameters": {{
                "<param_name>": "<type and constraint>"
            }},
            "edge_cases": ["<edge_case_1>", "<edge_case_2>"],
            "recommended_mcp_name": "<clean_snake_case_tool_name>",
            "docstring": "<concise functional description>"
        }}
    ],
    "research_summary": "<Concise assessment of discovered modules, architectural patterns, and code structure>"
}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 4. LLM Execution & Telemetry Recording
        exec_res = self._execute_llm(
            decision=routing_decision,
            messages=messages,
            stage="2_api_contract_research",
        )

        structured_data = self._parse_json_safely(exec_res["content"])
        
        # Merge AST ground truth reliably
        if not structured_data:
            structured_data = {}

        llm_modules = structured_data.get("modules_analyzed", [])
        llm_endpoints = structured_data.get("endpoints_analyzed", [])

        # Build comprehensive modules list combining LLM enriched descriptions with all AST modules
        llm_mod_map = {m.get("file_path"): m for m in llm_modules if isinstance(m, dict) and m.get("file_path")}
        final_modules = []
        for ast_m in ast_modules:
            f_path = ast_m.get("file_path")
            if f_path in llm_mod_map:
                enriched = llm_mod_map[f_path]
                final_modules.append({
                    "file_path": f_path,
                    "module_name": ast_m.get("module_name", enriched.get("module_name")),
                    "components": ast_m.get("components") or enriched.get("components", []),
                    "description": enriched.get("description") or ast_m.get("description"),
                })
            else:
                final_modules.append(ast_m)

        if not final_modules and ast_modules:
            final_modules = ast_modules
        elif not final_modules and not ast_modules:
            final_modules = [
                {
                    "file_path": "main.py",
                    "module_name": "main",
                    "components": ["main"],
                    "description": "Punto di ingresso e orchestrazione del progetto.",
                }
            ]

        final_endpoints = llm_endpoints if llm_endpoints else ast_endpoints
        if not final_endpoints and ast_endpoints:
            final_endpoints = ast_endpoints

        structured_data["modules_analyzed"] = final_modules
        structured_data["endpoints_analyzed"] = final_endpoints
        if not structured_data.get("research_summary"):
            structured_data["research_summary"] = (
                f"Analizzati {len(final_modules)} moduli sorgente e {len(final_endpoints)} contratti funzionali "
                f"nel repository di destinazione."
            )

        event = exec_res["event"]
        endpoints_count = len(structured_data.get("endpoints_analyzed", []))
        modules_count = len(structured_data.get("modules_analyzed", []))
        log(f"Research complete: [bold green]{modules_count} modules[/bold green] & [bold green]{endpoints_count} contracts[/bold green] cataloged.")

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

    def _extract_ast_modules_and_endpoints(self, sandbox: SandboxEnvironment) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract both module overviews and method contracts from Python source code AST."""
        files = sandbox.list_files()
        ignored_prefixes = (
            "tests/", "test/", "harness/", "node_modules/", "site-packages/",
            ".pytest_cache/", "__pycache__/", "dist/", "build/"
        )
        py_files = [
            f for f in files
            if f.endswith(".py") and not any(f.startswith(prefix) for prefix in ignored_prefixes)
        ]
        
        modules = []
        endpoints = []

        for f in py_files:
            content = sandbox.read_file(f)
            if not content:
                continue
            try:
                tree = ast.parse(content, filename=f)
                mod_doc = ast.get_docstring(tree)
                components = []
                file_endpoints = []

                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        components.append(f"Class `{class_name}`")
                        class_doc = ast.get_docstring(node)
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                                ep = self._func_to_endpoint(item, f, class_name, class_doc)
                                if ep:
                                    file_endpoints.append(ep)
                    elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                        components.append(f"Function `{node.name}()`")
                        ep = self._func_to_endpoint(node, f, None, None)
                        if ep:
                            file_endpoints.append(ep)

                # Determine module description
                if mod_doc:
                    desc = mod_doc.strip().split("\n")[0]
                elif components:
                    desc = f"Definisce {', '.join(components[:3])} con logica funzionale core."
                else:
                    desc = "Modulo di configurazione e supporto all'applicazione."

                modules.append({
                    "file_path": f,
                    "module_name": f.replace("/", ".").rstrip(".py"),
                    "components": components if components else [f"`{f}`"],
                    "description": desc,
                })

                endpoints.extend(file_endpoints)
            except Exception:
                pass

        return modules[:50], endpoints[:50]

    def _func_to_endpoint(
        self,
        func_node: ast.FunctionDef,
        file_path: str,
        class_name: Optional[str],
        class_doc: Optional[str],
    ) -> Dict[str, Any]:
        """Convert an AST FunctionDef node to an endpoint dictionary."""
        func_name = func_node.name
        raw_target = f"{class_name}.{func_name}" if class_name else func_name
        docstring = ast.get_docstring(func_node)
        
        if docstring:
            first_line = docstring.strip().split("\n")[0]
        elif class_doc:
            first_line = f"{class_doc.strip().split(chr(10))[0]} (Method: {func_name})"
        else:
            first_line = f"Execute `{raw_target}` operation in `{file_path}`."

        params = {}
        for arg in func_node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            param_name = arg.arg
            type_str = "str"
            if arg.annotation:
                try:
                    type_str = ast.unparse(arg.annotation)
                except Exception:
                    type_str = "Any"
            params[param_name] = f"{type_str}"

        if not params:
            params["payload"] = "str (input parameter)"

        mcp_name = f"{class_name.lower()}_{func_name}" if class_name else func_name
        mcp_name = re.sub(r"[^a-zA-Z0-9_]", "_", mcp_name).strip("_")

        return {
            "name": func_name,
            "raw_function": raw_target,
            "file_path": file_path,
            "class_name": class_name,
            "parameters": params,
            "edge_cases": ["Empty input string validation", "Type mismatch constraint", "Timeout threshold ceiling"],
            "recommended_mcp_name": mcp_name,
            "docstring": first_line,
        }
