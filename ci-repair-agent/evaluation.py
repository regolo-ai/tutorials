import json
import time
from pathlib import Path

from agent import repair_ci_failure


def load_tasks() -> list[dict]:
    return json.loads(Path("benchmarks/tasks.json").read_text())


def evaluate() -> list[dict]:
    results = []
    tasks = load_tasks()
    total_tasks = len(tasks)

    print(f"\n🚀 Starting Evaluation of {total_tasks} tasks...\n", flush=True)

    for idx, task in enumerate(tasks, 1):
        task_id = task["id"]
        issue = task["issue"]
        print(f"================================================================================", flush=True)
        print(f" ▶ Task {idx}/{total_tasks}: {task_id}", flush=True)
        print(f"   Issue: {issue}", flush=True)
        print(f"================================================================================", flush=True)

        started = time.perf_counter()

        result = repair_ci_failure(
            issue=issue,
            thread_id=f"eval-{task_id}",
        )

        duration_s = round(time.perf_counter() - started, 2)
        print(f"\n   ✓ Task '{task_id}' finished in {duration_s}s. Status: {result['status']}\n", flush=True)

        results.append(
            {
                "task_id": task_id,
                "verified_success": result["status"] == "verified_success",
                "attempts": result["attempts"],
                "duration_s": duration_s,
                "final_status": result["status"],
                "cost": result.get("total_cost", 0.0),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "limit_exceeded": result.get("limit_exceeded", False),
            }
        )

    return results


if __name__ == "__main__":
    from agent import print_consolidated_cost_report, load_env_vars

    rows = evaluate()
    tsr = sum(row["verified_success"] for row in rows) / len(rows)

    input_cost, output_cost, max_cost = load_env_vars()
    print_consolidated_cost_report(rows, input_cost, output_cost, max_cost)

    print(json.dumps(rows, indent=2))
    print(f"Verified task success rate: {tsr:.1%}")
