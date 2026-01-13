"""
Semantic Chunking Module
Preserves context boundaries instead of arbitrary character splits.
"""

from typing import List, Dict
import re


def semantic_chunk(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
    doc_id: str = "doc_default"
) -> List[Dict]:
    """
    Chunk text by semantic boundaries (paragraphs, sentences).
    Preserves context better than fixed-char splits.

    Args:
        text: Raw document text
        chunk_size: Target size per chunk (soft limit)
        overlap: Character overlap between chunks
        doc_id: Document identifier for traceability

    Returns:
        List of dicts with 'content' and 'metadata'
    """
    # Split on semantic boundaries
    paragraphs = text.split("\n\n")

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # Skip empty paragraphs
        if not para.strip():
            continue

        # If adding this paragraph exceeds chunk_size, save current and start new
        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"

    # Add remaining chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    # Add overlap between chunks for context continuity
    overlapped_chunks = []
    for i, chunk in enumerate(chunks):
        content = chunk

        # Add overlap from previous chunk
        if i > 0 and overlap > 0:
            prev_overlap = chunks[i-1][-overlap:]
            content = prev_overlap + "\n" + content

        overlapped_chunks.append(content)

    # Add metadata for traceability
    chunks_with_meta = []
    for i, chunk in enumerate(overlapped_chunks):
        chunks_with_meta.append({
            "content": chunk,
            "metadata": {
                "chunk_id": i,
                "doc_id": doc_id,
                "chunk_size": len(chunk),
                "total_chunks": len(overlapped_chunks)
            }
        })

    return chunks_with_meta


def chunk_documents(documents: List[str], **kwargs) -> List[Dict]:
    """
    Chunk multiple documents.

    Args:
        documents: List of document texts
        **kwargs: Arguments passed to semantic_chunk

    Returns:
        List of all chunks with metadata
    """
    all_chunks = []

    for doc_idx, doc in enumerate(documents):
        doc_id = kwargs.pop('doc_id', f"doc_{doc_idx}")
        chunks = semantic_chunk(doc, doc_id=doc_id, **kwargs)
        all_chunks.extend(chunks)

    return all_chunks


if __name__ == "__main__":
    # Test
    sample = """
    Retrieval Augmented Generation (RAG) combines retrieval and generation.

    The retrieval component searches a knowledge base. It uses embeddings
    to find relevant documents based on semantic similarity.

    The generation component creates answers. It uses an LLM like Llama-3.3
    to synthesize information from retrieved chunks.

    Production RAG requires careful chunking, hybrid retrieval, and reranking
    to achieve high accuracy and low hallucination rates.
    """

    chunks = semantic_chunk(sample, chunk_size=200, overlap=50)
    print(f"\n✓ Created {len(chunks)} semantic chunks\n")

    for chunk in chunks:
        print(f"Chunk {chunk['metadata']['chunk_id']}:")
        print(f"  Size: {chunk['metadata']['chunk_size']} chars")
        print(f"  Content: {chunk['content'][:80]}...")
        print()
