"""Deterministic assertions for AI_Memory_Benchmark."""
from memory_engine import inspect_memory_handoff, sanitize_and_consolidate_file, select_memory_route


def main():
    f = {
        "path": "src/token_vault.py",
        "content": '"""' + ("Enterprise memory note: audit\n" * 40) + '"""\nAPI_SECRET = "sk-1234567890abcdef1234"\nVAULT_ROTATION_HOURS = 24\n',
    }
    res = sanitize_and_consolidate_file(f)
    assert "[REDACTED_SECRET]" in res["body"]
    assert "sk-1234567890abcdef1234" not in res["body"]
    assert "VAULT_ROTATION_HOURS = 24" in res["body"]
    assert res["reduction_pct"] > 70.0
    assert select_memory_route({"category": "recall"}, True) == ("brick-complexity-pro", "none")
    assert select_memory_route({"category": "refactor"}, True) == ("qwen3.5-122b", "high")
    print("All ai-memory secret sanitization, wiki consolidation, and routing assertions passed.")


if __name__ == "__main__":
    main()
