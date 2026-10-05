import math
import re
import numpy as np


def tokenize_text(text: str) -> list[str]:
    # clean raw text and segment into tokens
    clean_text = text.lower()
    return re.findall(r"\b[a-z0-9_]{2,}\b", clean_text)


def compute_vector(text: str, dimension: int = 256) -> list[float]:
    # compute a deterministic dense embedding vector for local similarity
    tokens = tokenize_text(text)
    if not tokens:
        return [0.0] * dimension

    vector = np.zeros(dimension, dtype=float)
    for token in tokens:
        token_hash = hash(token) % dimension
        weight = 1.0 + math.log(1.0 + tokens.count(token))
        vector[token_hash] += weight

    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()


def calculate_cosine_similarity(
    vector_a: list[float], vector_b: list[float]
) -> float:
    # compute cosine similarity between two numeric vectors
    array_a = np.array(vector_a, dtype=float)
    array_b = np.array(vector_b, dtype=float)
    norm_a = np.linalg.norm(array_a)
    norm_b = np.linalg.norm(array_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(array_a, array_b) / (norm_a * norm_b))
