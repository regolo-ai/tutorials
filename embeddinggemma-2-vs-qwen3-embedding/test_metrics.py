import math
from benchmark import (
    cosine_similarity,
    mrl_truncate_and_normalize,
    ndcg_at_k,
    recall_at_k,
    mrr_at_k,
    format_query,
    format_document,
)


def test_mrl_truncate_and_normalize():
    vec = [3.0, 4.0, 12.0, 84.0]
    trunc = mrl_truncate_and_normalize(vec, 2)
    assert len(trunc) == 2
    assert math.isclose(trunc[0], 0.6, rel_tol=1e-6)
    assert math.isclose(trunc[1], 0.8, rel_tol=1e-6)
    norm = math.sqrt(sum(x * x for x in trunc))
    assert math.isclose(norm, 1.0, rel_tol=1e-6)


def test_ranking_metrics():
    # Relevant docs: d1 (grade 2), d3 (grade 1)
    qrels = {"d1": 2, "d3": 1}
    # Perfect ranking
    perfect = ["d1", "d3", "d2", "d4", "d5"]
    assert math.isclose(ndcg_at_k(perfect, qrels, 10), 1.0, rel_tol=1e-6)
    assert math.isclose(recall_at_k(perfect, qrels, 5), 1.0, rel_tol=1e-6)
    assert math.isclose(mrr_at_k(perfect, qrels, 10), 1.0, rel_tol=1e-6)

    # Imperfect ranking: d2 first, d3 second, d1 third
    subopt = ["d2", "d3", "d1", "d4", "d5"]
    assert 0.5 < ndcg_at_k(subopt, qrels, 10) < 0.9
    assert math.isclose(mrr_at_k(subopt, qrels, 10), 0.5, rel_tol=1e-6)
    assert math.isclose(recall_at_k(subopt, {"d1": 2, "d6": 1}, 5), 0.5, rel_tol=1e-6)


def test_instruction_formatting():
    # EmbeddingGemma 2 uses task prefix for queries and title/text prefix for docs
    gemma_q = format_query("embeddinggemma-2:270m-bf16-text", "find leaky bucket", "code")
    assert gemma_q.startswith("task: code retrieval | query: ")

    gemma_doc = format_document("embeddinggemma-2:270m-bf16-text", "Rate limiter", "def allow(): pass")
    assert gemma_doc == "title: Rate limiter | text: def allow(): pass"

    # Qwen3-Embedding uses Instruct/Query for queries and raw text for docs
    qwen_q = format_query("Qwen3-Embedding-8B", "find leaky bucket", "code")
    assert qwen_q.startswith("Instruct: ") and "\nQuery:find leaky bucket" in qwen_q

    qwen_doc = format_document("Qwen3-Embedding-8B", "Rate limiter", "def allow(): pass")
    assert qwen_doc == "Rate limiter\ndef allow(): pass"
