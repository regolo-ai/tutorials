import json
from config import MAX_CONTEXT_TOKENS
from utils import calculate_history_tokens, extract_json
from tools import ToolManager
from llm_client import LLMClient
from ui import TerminalUI


class ContextEngineAgent:
    def __init__(self):
        self.llm = LLMClient()
        self.tools = ToolManager(data_dir="data")
        self.ui = TerminalUI()
        self.history = []
        self.executed_tools = []
        self.required_tools = []
        self._setup_system_prompt()

    def _setup_system_prompt(self):
        system_instructions = (
            "You are an expert Context Engineer Agent. You operate in a runtime loop "
            "to answer questions using available tool hooks. Keep your active token footprint low.\n\n"
            "Required Tool Call JSON Output Format:\n"
            "{\n"
            "  \"thought\": \"Reasoning details...\",\n"
            "  \"tool\": \"tool_name\",\n"
            "  \"arguments\": {}\n"
            "}\n\n"
            "Required Task Completion JSON Output Format:\n"
            "{\n"
            "  \"thought\": \"Final summary reasoning...\",\n"
            "  \"response\": \"Your analytical report output...\"\n"
            "}\n\n"
            "Guidelines:\n"
            "1. Run operations step-by-step. Do not read complete files into context; query JIT chunks.\n"
            "2. Document insights to external storage via \"write_note\".\n"
            "3. Spawning sub-agents isolates complex mathematical transformations to clear your main thread.\n\n"
            "Available tools:\n"
            "- list_files\n"
            "- get_file_metadata(filename)\n"
            "- read_file_chunk(filename, start_line, limit)\n"
            "- find_top_active_user(filename, user_column, metric_column)\n"
            "- write_note(key, value)\n"
            "- spawn_sub_agent(task)\n\n"
            "Important: never produce the final response until runtime evidence has been gathered. "
            "For CSV analysis, inspect files and metadata first, read a small chunk, then use deterministic tools for calculations."
        )
        self.history.append({"role": "system", "content": system_instructions})

    def run(self, task: str):
        self.executed_tools = []
        self.required_tools = self._infer_required_tools(task)
        self.ui.header("Context Engine Agent", task)
        self.history.append({"role": "user", "content": f"Task: {task}"})

        for iteration in range(1, 10):
            self._ensure_compact_context()

            raw_response = self.llm.chat(self.history)
            self.history.append({"role": "assistant", "content": raw_response})

            parsed = extract_json(raw_response)
            if not parsed:
                self.ui.warning(f"Iteration {iteration}: could not parse LLM JSON. Retrying.")
                continue

            self.ui.thought(iteration, parsed.get("thought", "No thought provided."))

            if "response" in parsed:
                missing = self._missing_required_tools()
                if missing:
                    self.ui.guardrail(missing)
                    self.history.append({
                        "role": "user",
                        "content": (
                            "[ORCHESTRATOR GUARDRAIL] Final answer rejected. "
                            f"Missing required runtime tools: {', '.join(missing)}. "
                            "Return a JSON tool call for the next missing step."
                        ),
                    })
                    continue
                self.ui.final_report(parsed["response"])
                return parsed["response"]

            tool_name = parsed.get("tool")
            args = parsed.get("arguments", {})

            tool_output = self._execute_tool(tool_name, args)
            if self._tool_succeeded(tool_output):
                self.executed_tools.append(tool_name)
            self.ui.tool_result(tool_output)
            self.history.append({"role": "user", "content": f"Tool '{tool_name}' Result:\n{json.dumps(tool_output)}"})

        self.ui.warning("Agent reached the iteration limit before producing a verified final response.")
        return None

    def _execute_tool(self, tool_name, args):
        self.ui.tool_call(tool_name, args)
        if tool_name == "list_files":
            return self.tools.list_files()
        if tool_name == "get_file_metadata":
            return self.tools.get_file_metadata(args.get("filename", ""))
        if tool_name == "read_file_chunk":
            return self.tools.read_file_chunk(args.get("filename", ""), args.get("start_line", 1), args.get("limit", 10))
        if tool_name == "find_top_active_user":
            return self.tools.find_top_active_user(
                args.get("filename", ""),
                args.get("user_column", "user_id"),
                args.get("metric_column", "activity_score"),
            )
        if tool_name == "write_note":
            return self.tools.write_note(args.get("key", ""), args.get("value", ""))
        if tool_name == "spawn_sub_agent":
            return self._run_isolated_sub_agent(args.get("task", ""))
        return {"error": f"Tool '{tool_name}' is not recognized."}

    def _infer_required_tools(self, task):
        task_lower = task.lower()
        required = []
        if ".csv" in task_lower or "csv" in task_lower:
            required.extend(["list_files", "get_file_metadata", "read_file_chunk"])
        if "top active" in task_lower or "top user" in task_lower:
            required.append("find_top_active_user")
        if "persistent" in task_lower or "note" in task_lower or "memory" in task_lower:
            required.append("write_note")
        if "sub-agent" in task_lower or "sub agent" in task_lower:
            required.append("spawn_sub_agent")
        return required

    def _missing_required_tools(self):
        return [tool for tool in self.required_tools if tool not in self.executed_tools]

    def _tool_succeeded(self, tool_output):
        return not (isinstance(tool_output, dict) and "error" in tool_output)

    def _ensure_compact_context(self):
        """Compaction: Prunes context when tokens exceed threshold constraints."""
        current_tokens = calculate_history_tokens(self.history)
        self.ui.context_load(current_tokens, MAX_CONTEXT_TOKENS)

        if current_tokens > MAX_CONTEXT_TOKENS:
            self.ui.section("Compaction phase")

            keep_count = 2
            mid_history = self.history[1:-keep_count]
            recent_history = self.history[-keep_count:]

            compaction_prompt = (
                "You are an agent state compression engine. Summarize the progress of this interaction. "
                "Retain historical configurations, key metrics, and ongoing architectural goals. "
                "Keep the final output summary tight (under 120 words).\n\n"
                f"History to condense:\n{json.dumps(mid_history, indent=2)}"
            )

            summary = self.llm.chat([{"role": "user", "content": compaction_prompt}])

            compacted_messages = [
                self.history[0],
                {"role": "system", "content": f"[CONSOLIDATED INTERACTION BACKLOG]\n{summary}"},
                {"role": "system", "content": f"Active memory notes: {json.dumps(self.tools.read_notes())}"},
            ]
            compacted_messages.extend(recent_history)
            self.history = compacted_messages
            self.ui.success(f"Context compacted to ~{calculate_history_tokens(self.history)} tokens.")

    def _run_isolated_sub_agent(self, sub_task):
        """Sub-Agent Isolation: Executes a targeted pipeline in an isolated context environment."""
        self.ui.sub_agent(f"Spawning isolated context for: {sub_task}")
        sub_system = (
            "You are a calculation sub-agent. Solve the task step-by-step. "
            "Output JSON with either 'tool' (get_file_metadata, read_file_chunk, aggregate_revenue) or 'response'. "
            "Return only the compact final result to the orchestrator."
        )
        sub_history = [
            {"role": "system", "content": sub_system},
            {"role": "user", "content": sub_task},
        ]

        for step in range(4):
            raw = self.llm.chat(sub_history)
            parsed = extract_json(raw)
            if not parsed:
                continue

            if "response" in parsed:
                self.ui.sub_agent(f"Result: {parsed['response']}")
                return {"status": "success", "result": parsed["response"]}

            tool_name = parsed.get("tool")
            args = parsed.get("arguments", {})

            if tool_name in ["get_file_metadata", "read_file_chunk", "aggregate_revenue"]:
                self.ui.tool_call(f"sub_agent.{tool_name}", args)
                if tool_name == "aggregate_revenue":
                    res = self.tools.aggregate_revenue(
                        args.get("filename", ""),
                        args.get("revenue_column", "revenue"),
                        args.get("event_column", "event_type"),
                        args.get("event_value", "transaction"),
                    )
                elif tool_name == "get_file_metadata":
                    res = self.tools.get_file_metadata(args.get("filename", ""))
                else:
                    res = self.tools.read_file_chunk(args.get("filename", ""), args.get("start_line", 1), args.get("limit", 10))
                self.ui.tool_result(res)
            else:
                res = {"error": f"Tool {tool_name} is restricted for sub-agents."}

            sub_history.append({"role": "assistant", "content": raw})
            sub_history.append({"role": "user", "content": f"Tool '{tool_name}' Result:\n{json.dumps(res)}"})

        return {"status": "failure", "reason": "Reached execution limit."}