"""
Evaluation Module
Measures retrieval and generation quality with standard metrics.
"""

from typing import List, Dict
import numpy as np


def evaluate_retrieval(
    queries: List[str],
    retrieved: List[List[str]],
    ground_truth: List[List[str]]
) -> Dict[str, float]:
    """
    Measure retrieval quality with precision, recall, F1.

    Args:
        queries: List of queries
        retrieved: List of retrieved doc lists per query
        ground_truth: List of relevant doc lists per query

    Returns:
        Dict with precision@k, recall@k, f1@k
    """
    if len(retrieved) != len(ground_truth):
        raise ValueError("Retrieved and ground_truth must have same length")

    precisions = []
    recalls = []

    for ret, truth in zip(retrieved, ground_truth):
        # Convert to sets for intersection
        ret_set = set(ret)
        truth_set = set(truth)

        relevant_retrieved = ret_set & truth_set

        precision = len(relevant_retrieved) / len(ret) if ret else 0
        recall = len(relevant_retrieved) / len(truth) if truth else 0

        precisions.append(precision)
        recalls.append(recall)

    avg_precision = np.mean(precisions)
    avg_recall = np.mean(recalls)

    # F1 score
    if avg_precision + avg_recall > 0:
        f1 = 2 * avg_precision * avg_recall / (avg_precision + avg_recall)
    else:
        f1 = 0.0

    return {
        "precision@k": round(avg_precision, 3),
        "recall@k": round(avg_recall, 3),
        "f1@k": round(f1, 3)
    }


def evaluate_generation(
    answers: List[str],
    ground_truth_answers: List[str]
) -> Dict[str, float]:
    """
    Simplified answer quality evaluation.
    For production, use RAGAS or similar frameworks.

    Args:
        answers: Generated answers
        ground_truth_answers: Expected answers

    Returns:
        Dict with answer_relevancy score
    """
    scores = []

    for ans, truth in zip(answers, ground_truth_answers):
        # Simplified: token overlap
        ans_tokens = set(ans.lower().split())
        truth_tokens = set(truth.lower().split())

        overlap = len(ans_tokens & truth_tokens)
        score = overlap / max(len(truth_tokens), 1)

        scores.append(min(score, 1.0))

    return {
        "answer_relevancy": round(np.mean(scores), 3)
    }


def calculate_hallucination_rate(
    answers: List[str],
    contexts: List[List[str]]
) -> float:
    """
    Estimate hallucination rate by checking if answer tokens
    appear in context. Simplified heuristic.

    Args:
        answers: Generated answers
        contexts: Retrieved contexts per answer

    Returns:
        Hallucination rate (0.0 to 1.0)
    """
    hallucination_scores = []

    for answer, context_list in zip(answers, contexts):
        answer_tokens = set(answer.lower().split())

        # Combine all context
        context_text = " ".join(context_list).lower()
        context_tokens = set(context_text.split())

        # Tokens in answer but not in context
        hallucinated = answer_tokens - context_tokens

        # Remove common words (stopwords approximation)
        common_words = {"the", "a", "an", "is", "are", "was", "were", "i", "you", "to", "of", "in", "on", "at"}
        hallucinated = hallucinated - common_words

        if len(answer_tokens) > 0:
            hallucination_score = len(hallucinated) / len(answer_tokens)
        else:
            hallucination_score = 0.0

        hallucination_scores.append(hallucination_score)

    return round(np.mean(hallucination_scores), 3)


if __name__ == "__main__":
    # Test evaluation
    test_queries = ["What is RAG?", "How does chunking work?"]

    test_retrieved = [
        ["RAG combines retrieval and generation.", "Chunking splits documents."],
        ["Semantic chunking preserves context.", "Fixed-size chunks break sentences."]
    ]

    test_ground_truth = [
        ["RAG combines retrieval and generation."],
        ["Semantic chunking preserves context."]
    ]

    metrics = evaluate_retrieval(test_queries, test_retrieved, test_ground_truth)
    print(f"\n✓ Retrieval metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
