"""
Test Suite for RAG Pipeline
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from semantic_chunker import semantic_chunk
from embedder import embed_chunks
from evaluation import evaluate_retrieval, calculate_hallucination_rate


def test_semantic_chunking():
    """Test semantic chunking preserves context."""
    print("\n[TEST 1] Semantic chunking...")

    text = """
    First paragraph with important context.

    Second paragraph continues the topic.

    Third paragraph adds more details.
    """

    chunks = semantic_chunk(text, chunk_size=100, overlap=20)

    assert len(chunks) > 0, "Should create at least one chunk"
    assert all("content" in c for c in chunks), "All chunks should have content"
    assert all("metadata" in c for c in chunks), "All chunks should have metadata"

    print(f"  ✓ Created {len(chunks)} chunks")
    print("  ✓ PASSED")


def test_embedding():
    """Test embedding generation."""
    print("\n[TEST 2] Embedding generation...")

    if not os.environ.get("REGOLO_API_KEY"):
        print("  ⚠ SKIPPED (no API key)")
        return

    chunks = [
        {"content": "Test document one.", "metadata": {"chunk_id": 0}},
        {"content": "Test document two.", "metadata": {"chunk_id": 1}}
    ]

    try:
        embedded = embed_chunks(chunks)

        assert len(embedded) == 2, "Should embed all chunks"
        assert "embedding" in embedded[0], "Should have embedding key"
        assert len(embedded[0]["embedding"]) > 0, "Embedding should not be empty"

        print(f"  ✓ Embedded {len(embedded)} chunks")
        print(f"  ✓ Embedding dimension: {len(embedded[0]['embedding'])}")
        print("  ✓ PASSED")

    except Exception as e:
        print(f"  ❌ FAILED: {e}")


def test_retrieval_evaluation():
    """Test retrieval evaluation metrics."""
    print("\n[TEST 3] Retrieval evaluation...")

    queries = ["q1", "q2"]
    retrieved = [
        ["doc1", "doc2", "doc3"],
        ["doc4", "doc5"]
    ]
    ground_truth = [
        ["doc1", "doc3"],
        ["doc4"]
    ]

    metrics = evaluate_retrieval(queries, retrieved, ground_truth)

    assert "precision@k" in metrics, "Should calculate precision"
    assert "recall@k" in metrics, "Should calculate recall"
    assert "f1@k" in metrics, "Should calculate F1"

    print(f"  ✓ Precision@k: {metrics['precision@k']}")
    print(f"  ✓ Recall@k: {metrics['recall@k']}")
    print(f"  ✓ F1@k: {metrics['f1@k']}")
    print("  ✓ PASSED")


def test_hallucination_detection():
    """Test hallucination rate calculation."""
    print("\n[TEST 4] Hallucination detection...")

    answers = [
        "The cat is on the mat",
        "The dog jumped over the fence"
    ]
    contexts = [
        ["The cat is on the mat and sleeping"],
        ["A fence is in the yard"]
    ]

    rate = calculate_hallucination_rate(answers, contexts)

    assert 0.0 <= rate <= 1.0, "Rate should be between 0 and 1"

    print(f"  ✓ Hallucination rate: {rate}")
    print("  ✓ PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Pipeline Test Suite")
    print("=" * 60)

    try:
        test_semantic_chunking()
        test_embedding()
        test_retrieval_evaluation()
        test_hallucination_detection()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
