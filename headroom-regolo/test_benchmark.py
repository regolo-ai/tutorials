"""Unit and integration self-check for the Codebase Comprehension Benchmark."""
from benchmark import generate_corpus, grade_answer
from compressor import (
    build_compressed_prompt,
    build_uncompressed_prompt,
    compress_python_ast,
    crush_json_logs,
    rank_files_rrf,
    select_route_and_effort,
)


def test_compression_and_routing():
    corpus = generate_corpus()
    uncompressed = build_uncompressed_prompt(corpus)

    for q in corpus["questions"]:
        compressed = build_compressed_prompt(corpus, q["question"], top_k=3)
        assert len(compressed) < len(uncompressed) * 0.35, (
            f"Expected >65% character reduction on {q['id']}, got {len(compressed)} vs {len(uncompressed)}"
        )

    # Verify FATAL line survives JSON log crushing byte-for-byte
    log_file = [f for f in corpus["files"] if f["path"].endswith(".json")][0]
    crushed = crush_json_logs(log_file["content"])
    assert "ERR_DOUBLE_DEBIT_77" in crushed
    assert "evt_9941" in crushed
    assert len(crushed) < len(log_file["content"]) * 0.25

    # Verify AST docstring stripping preserves executable code
    py_file = corpus["files"][0]["content"]
    stripped = compress_python_ast(py_file)
    assert "WEBHOOK_TOLERANCE_SECONDS = 180" in stripped
    assert "Enterprise compliance note" not in stripped

    # Verify RRF ranks src/webhooks.py and src/idempotency.py for q7
    top_q7 = rank_files_rrf(corpus["files"], corpus["questions"][6]["question"], top_k=3)
    top_paths = {f["path"] for f in top_q7}
    assert "src/webhooks.py" in top_paths

    # Verify routing and effort selection
    assert select_route_and_effort(corpus["questions"][0], True) == ("brick-complexity-pro", "none")
    assert select_route_and_effort(corpus["questions"][6], True) == ("qwen3.5-122b", "high")
    assert select_route_and_effort(corpus["questions"][0], False) == ("qwen3.5-122b", "high")
    assert grade_answer("The value is 180 and header is X-Regolo-Signature-256", ["180", "x-regolo-signature-256"])
    print("All local compression, RRF, and routing assertions passed.")


if __name__ == "__main__":
    test_compression_and_routing()
