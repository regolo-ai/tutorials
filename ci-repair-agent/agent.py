from __future__ import annotations

import os
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    TodoListMiddleware,
)
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.checkpoint.memory import InMemorySaver


def load_env_vars() -> tuple[float, float, float]:
    """Load cost configuration from environment, with fallback to manual parsing of .env file."""
    # Start with defaults
    input_cost = 0.002
    output_cost = 0.05
    max_cost = 1.00

    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if val.startswith(('"', "'")) and val.endswith(('"', "'")):
                        val = val[1:-1]
                    if key == "INPUT_COST":
                        try:
                            input_cost = float(val)
                        except ValueError:
                            pass
                    elif key == "OUTPUT_COST":
                        try:
                            output_cost = float(val)
                        except ValueError:
                            pass
                    elif key == "MAX_COST":
                        try:
                            max_cost = float(val)
                        except ValueError:
                            pass

    # Give precedence to actual environment variables if set
    if "INPUT_COST" in os.environ:
        try:
            input_cost = float(os.environ["INPUT_COST"].strip())
        except ValueError:
            pass
    if "OUTPUT_COST" in os.environ:
        try:
            output_cost = float(os.environ["OUTPUT_COST"].strip())
        except ValueError:
            pass
    if "MAX_COST" in os.environ:
        try:
            max_cost = float(os.environ["MAX_COST"].strip())
        except ValueError:
            pass

    return input_cost, output_cost, max_cost


class CostLimitExceededError(Exception):
    """Raised when the total accumulated cost exceeds MAX_COST."""
    def __init__(self, current_cost: float, max_cost: float):
        self.current_cost = current_cost
        self.max_cost = max_cost
        super().__init__(f"Cost limit exceeded: {current_cost:.5f} > {max_cost:.5f}")


class CostLimitMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.input_cost_rate, self.output_cost_rate, self.max_cost_limit = load_env_vars()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.limit_exceeded = False

    def wrap_model_call(self, request: ModelRequest, handler):
        # Check before calling if limit is already exceeded
        if self.total_cost > self.max_cost_limit:
            self.limit_exceeded = True
            raise CostLimitExceededError(self.total_cost, self.max_cost_limit)

        print(f"     [Model Call] Sending request to LLM...", flush=True)
        response = handler(request)

        # Retrieve token counts from response
        ai_message = None
        if isinstance(response, ModelResponse):
            if response.result and len(response.result) > 0:
                ai_message = response.result[0]
        elif hasattr(response, "result"):
            if response.result and len(response.result) > 0:
                ai_message = response.result[0]
        else:
            ai_message = response

        if ai_message and hasattr(ai_message, "usage_metadata") and ai_message.usage_metadata:
            usage = ai_message.usage_metadata
            input_tokens = usage.get("input_tokens", 0) or 0
            output_tokens = usage.get("output_tokens", 0) or 0
            
            # calculate cost for this call
            call_cost = (input_tokens / 1000.0) * self.input_cost_rate + (output_tokens / 1000.0) * self.output_cost_rate
            
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += call_cost
            print(f"     [Model Call] Response received. Tokens: {input_tokens} In, {output_tokens} Out. Cost: ${call_cost:.5f} (Total: ${self.total_cost:.5f}/{self.max_cost_limit:.4f})", flush=True)
        else:
            print(f"     [Model Call] Response received (no usage metadata). Total Cost: ${self.total_cost:.5f}", flush=True)

        # Check after calling if we now exceeded limit
        if self.total_cost > self.max_cost_limit:
            self.limit_exceeded = True
            raise CostLimitExceededError(self.total_cost, self.max_cost_limit)

        return response

    async def awrap_model_call(self, request: ModelRequest, handler):
        # Check before calling if limit is already exceeded
        if self.total_cost > self.max_cost_limit:
            self.limit_exceeded = True
            raise CostLimitExceededError(self.total_cost, self.max_cost_limit)

        print(f"     [Model Call Async] Sending request to LLM...", flush=True)
        response = await handler(request)

        # Retrieve token counts from response
        ai_message = None
        if isinstance(response, ModelResponse):
            if response.result and len(response.result) > 0:
                ai_message = response.result[0]
        elif hasattr(response, "result"):
            if response.result and len(response.result) > 0:
                ai_message = response.result[0]
        else:
            ai_message = response

        if ai_message and hasattr(ai_message, "usage_metadata") and ai_message.usage_metadata:
            usage = ai_message.usage_metadata
            input_tokens = usage.get("input_tokens", 0) or 0
            output_tokens = usage.get("output_tokens", 0) or 0
            
            # calculate cost for this call
            call_cost = (input_tokens / 1000.0) * self.input_cost_rate + (output_tokens / 1000.0) * self.output_cost_rate
            
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += call_cost
            print(f"     [Model Call Async] Response received. Tokens: {input_tokens} In, {output_tokens} Out. Cost: ${call_cost:.5f} (Total: ${self.total_cost:.5f}/{self.max_cost_limit:.4f})", flush=True)
        else:
            print(f"     [Model Call Async] Response received (no usage metadata). Total Cost: ${self.total_cost:.5f}", flush=True)

        # Check after calling if we now exceeded limit
        if self.total_cost > self.max_cost_limit:
            self.limit_exceeded = True
            raise CostLimitExceededError(self.total_cost, self.max_cost_limit)

        return response


def print_consolidated_cost_report(tasks: list[dict], input_cost_rate: float, output_cost_rate: float, max_cost_limit: float) -> None:
    print("\n" + "="*50)
    print("           AGENT CONSOLIDATED COST REPORT")
    print("="*50)
    
    total_input = 0
    total_output = 0
    total_cost = 0.0
    any_limit_exceeded = False
    
    print(f"{'Task ID':<25} | {'Input':<8} | {'Output':<8} | {'Cost ($)':<10}")
    print("-" * 50)
    for t in tasks:
        tid = t.get("task_id", t.get("id", "unknown"))
        inp = t.get("input_tokens", 0)
        outp = t.get("output_tokens", 0)
        cost = t.get("cost", 0.0)
        limit_ex = t.get("limit_exceeded", False)
        if limit_ex:
            any_limit_exceeded = True
        
        total_input += inp
        total_output += outp
        total_cost += cost
        
        # truncate Task ID if too long
        if len(tid) > 25:
            tid_disp = tid[:22] + "..."
        else:
            tid_disp = tid
            
        print(f"{tid_disp:<25} | {inp:<8} | {outp:<8} | ${cost:.5f}")
        
    print("-" * 50)
    print(f"{'TOTAL':<25} | {total_input:<8} | {total_output:<8} | ${total_cost:.5f}")
    print(f"Input Cost Rate:          ${input_cost_rate:.4f} / 1k tokens")
    print(f"Output Cost Rate:         ${output_cost_rate:.4f} / 1k tokens")
    print(f"Max Cost Limit:           ${max_cost_limit:.4f}")
    if any_limit_exceeded or total_cost > max_cost_limit:
        print("STATUS:                   Cost Limit EXCEEDED! ❌")
    else:
        print("STATUS:                   Within Cost Limits ✅")
    print("="*50 + "\n")

from config import get_chat_model
from tools import (
    git_diff,
    read_file,
    run_pytest,
    run_ruff,
    run_typecheck,
    write_file,
)

SYSTEM_PROMPT = """
You are a CI repair agent for a Python repository.

Your job is to fix the reported failure with the smallest safe change.

Mandatory completion protocol:
1. Inspect the relevant source and failing test.
2. Modify only files needed for the fix.
3. Run pytest after every meaningful code change.
4. Run ruff before declaring success.
5. If type checking is configured, run it too.
6. Do not claim success unless every required checker returns passed=true.
7. If a checker fails, read its exact output, fix the specific error, and retry.
8. Stop after the harness call budget is exhausted; then report the unresolved
   failure, the checker output, and the current git diff.

Never modify .github/, infra/, terraform/, migration files, lock files,
CI configuration, or test files unless explicitly authorized.
"""

MODEL_CALL_LIMIT = int(os.environ.get("AGENT_MODEL_CALL_LIMIT", "12"))
TOOL_CALL_LIMIT = int(os.environ.get("AGENT_TOOL_CALL_LIMIT", "30"))


def build_agent(cost_middleware: CostLimitMiddleware | None = None):
    """Build the LangChain agent using an OpenAI-compatible chat model."""
    model = get_chat_model()

    if cost_middleware is None:
        cost_middleware = CostLimitMiddleware()

    return create_agent(
        model=model,
        tools=[
            read_file,
            write_file,
            run_pytest,
            run_ruff,
            run_typecheck,
            git_diff,
        ],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
        middleware=[
            TodoListMiddleware(),
            cost_middleware,
            ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=TOOL_CALL_LIMIT, exit_behavior="end"),
        ],
    )


REQUIRED_CHECKS = [
    ("pytest", run_pytest),
    ("ruff", run_ruff),
]


def verify_completion(use_mypy: bool = False) -> dict:
    """Deterministic completion gate. Runs outside the model."""
    checks = {}

    for name, checker in REQUIRED_CHECKS:
        checks[name] = checker.invoke({})

    if use_mypy:
        checks["mypy"] = run_typecheck.invoke({})

    passed = all(result["passed"] for result in checks.values())

    return {
        "passed": passed,
        "checks": checks,
        "diff": git_diff.invoke({}),
    }


def compact_failure_report(report: dict) -> str:
    failures = []

    for name, result in report["checks"].items():
        if not result["passed"]:
            failures.append(
                f"## {name} failed\n"
                f"Command: {result['command']}\n"
                f"Exit code: {result['exit_code']}\n"
                f"stdout:\n{result['stdout']}\n"
                f"stderr:\n{result['stderr']}"
            )

    return "\n\n".join(failures)


MAX_ATTEMPTS = int(os.environ.get("AGENT_MAX_ATTEMPTS", "3"))


def repair_ci_failure(issue: str, thread_id: str) -> dict:
    """Run the self-verification loop: Act -> Verify -> Feedback -> Retry -> Escalate."""
    cost_middleware = CostLimitMiddleware()
    agent = build_agent(cost_middleware=cost_middleware)
    feedback = ""
    report = None
    limit_exceeded = False

    attempt = 1
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if cost_middleware.total_cost > cost_middleware.max_cost_limit:
            limit_exceeded = True
            break

        print(f"\n   --- Attempt {attempt}/{MAX_ATTEMPTS} ---", flush=True)

        task = f"""
Fix this CI failure:

{issue}

Attempt: {attempt}/{MAX_ATTEMPTS}

{feedback}
"""
        try:
            print(f"   [Agent Loop] Invoking agent...", flush=True)
            agent.invoke(
                {"messages": [{"role": "user", "content": task}]},
                config={"configurable": {"thread_id": thread_id}},
            )
            print(f"   [Agent Loop] Agent invocation finished successfully.", flush=True)
        except CostLimitExceededError as exc:
            print(f"   [Agent Loop] Stopping execution: {exc}", flush=True)
            limit_exceeded = True
            break
        except Exception as exc:  # network/provider errors, rate limits, etc.
            if isinstance(exc, CostLimitExceededError) or "CostLimitExceededError" in type(exc).__name__:
                print(f"   [Agent Loop] Stopping execution: {exc}", flush=True)
                limit_exceeded = True
                break
            print(f"   [Agent Loop] Attempt {attempt} raised an error: {exc}", flush=True)
            feedback = f"The previous attempt raised an error: {exc}. Try a smaller, safer change."
            continue

        print(f"   [Agent Loop] Verifying completion with local checkers...", flush=True)
        report = verify_completion(use_mypy=False)

        if report["passed"]:
            print(f"   [Agent Loop] Verification PASSED! ✅", flush=True)
            break
        else:
            print(f"   [Agent Loop] Verification FAILED! ❌", flush=True)
            for check_name, check_res in report["checks"].items():
                print(f"     - {check_name}: {'PASSED ✅' if check_res['passed'] else 'FAILED ❌'} (Exit Code={check_res['exit_code']})", flush=True)

        feedback = f"""
The last attempt is NOT accepted. Do not summarize or claim success.

Fix only the failing checks below:

{compact_failure_report(report)}
"""

    if report and report["passed"]:
        return {
            "status": "verified_success",
            "attempts": attempt,
            "diff": report["diff"],
            "checks": report["checks"],
            "total_cost": cost_middleware.total_cost,
            "input_tokens": cost_middleware.total_input_tokens,
            "output_tokens": cost_middleware.total_output_tokens,
            "limit_exceeded": limit_exceeded or cost_middleware.limit_exceeded,
        }

    return {
        "status": "needs_human_review" if not (limit_exceeded or cost_middleware.limit_exceeded) else "cost_limit_exceeded",
        "attempts": attempt if (limit_exceeded or cost_middleware.limit_exceeded) else MAX_ATTEMPTS,
        "diff": report["diff"] if report else "",
        "checks": report["checks"] if report else {},
        "reason": "Cost limit exceeded" if (limit_exceeded or cost_middleware.limit_exceeded) else (compact_failure_report(report) if report else "No report available"),
        "total_cost": cost_middleware.total_cost,
        "input_tokens": cost_middleware.total_input_tokens,
        "output_tokens": cost_middleware.total_output_tokens,
        "limit_exceeded": limit_exceeded or cost_middleware.limit_exceeded,
    }


if __name__ == "__main__":
    result = repair_ci_failure(
        issue="""
        POST /users returns HTTP 500 when the request has a valid email
        but omits the optional display_name field. Fix the implementation.
        Do not change tests or API contracts.
        """,
        thread_id="ci-repair-demo-001",
    )

    input_cost, output_cost, max_cost = load_env_vars()
    task_data = {
        "task_id": "ci-repair-demo-001",
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "cost": result["total_cost"],
        "limit_exceeded": result["limit_exceeded"],
    }
    print_consolidated_cost_report([task_data], input_cost, output_cost, max_cost)

    print(result["status"])
    print(result["diff"])
