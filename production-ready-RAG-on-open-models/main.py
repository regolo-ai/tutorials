"""
Main Pipeline
Complete end-to-end production RAG system.
"""

import os
import asyncio
from typing import List
from semantic_chunker import semantic_chunk
from embedder import embed_chunks
from hybrid_store import HybridStore
from retriever import HybridRetriever
from production_rag import cached_rag


def load_sample_documents() -> List[str]:
    """
    Load sample documents from data/ folder or use defaults.

    Returns:
        List of document texts
    """
    data_dir = "data"

    if os.path.exists(data_dir):
        docs = []
        for filename in os.listdir(data_dir):
            if filename.endswith(".txt"):
                with open(os.path.join(data_dir, filename), "r") as f:
                    docs.append(f.read())

        if docs:
            print(f"✓ Loaded {len(docs)} documents from {data_dir}/")
            return docs

    # Default sample document
    return ["""
Production-Ready RAG Systems

Retrieval Augmented Generation (RAG) combines two powerful techniques: 
information retrieval and natural language generation. The retrieval 
component searches through a knowledge base using embeddings to find 
semantically relevant documents.

The generation component then uses a large language model like Llama-3.3 
to synthesize information from the retrieved chunks into a coherent answer.

Semantic Chunking

Traditional RAG systems often use fixed-size chunking, which breaks text 
at arbitrary character boundaries. This leads to loss of context and 
lower retrieval quality. Semantic chunking instead respects document 
structure by splitting on paragraphs and sentences.

Hybrid Retrieval

Dense vector search alone can miss important keyword matches. Hybrid 
retrieval combines semantic search (using embeddings) with lexical search 
(using BM25) to achieve 20% better recall than either method alone.

Reranking

The initial retrieval step often returns relevant-ish but not perfect 
results. Cross-encoder reranking evaluates query-document pairs jointly 
and can boost precision@5 from 65% to 87%.

gte-Qwen2 Embeddings

gte-Qwen2-7B-instruct is currently the #1 ranked open-source embedding 
model on MTEB benchmarks, outperforming even OpenAI's text-embedding-3-large 
on both English and multilingual tasks.

Llama-3.3 Generation

Llama-3.3-70B-Instruct provides state-of-the-art open-source text generation 
with strong reasoning capabilities and low hallucination rates when properly 
prompted with retrieved context.
    """]


async def build_rag_pipeline():
    """
    Build and test complete RAG pipeline.
    """
    print("=" * 60)
    print("Production RAG Pipeline - Regolo + Open Models")
    print("=" * 60)

    # 1. Load documents
    print("\n[1/6] Loading documents...")
    documents = load_sample_documents()

    # 2. Semantic chunking
    print("\n[2/6] Semantic chunking...")
    all_chunks = []
    for i, doc in enumerate(documents):
        chunks = semantic_chunk(doc, chunk_size=800, overlap=100, doc_id=f"doc_{i}")
        all_chunks.extend(chunks)
    print(f"✓ Created {len(all_chunks)} chunks")

    # 3. Embed with gte-Qwen2
    print("\n[3/6] Embedding with gte-Qwen2...")
    all_chunks = embed_chunks(all_chunks)

    # 4. Index in hybrid store
    print("\n[4/6] Building hybrid index...")
    store = HybridStore(persist_path="./rag_index")
    store.index(all_chunks)

    # 5. Create retriever
    print("\n[5/6] Initializing retriever...")
    retriever = HybridRetriever(store)

    # 6. Test queries
    print("\n[6/6] Testing queries...")
    test_queries = [
        "What is production-ready RAG?",
        "How does semantic chunking work?",
        "What is hybrid retrieval?",
        "Why use gte-Qwen2 embeddings?"
    ]

    print("\n" + "=" * 60)
    print("Query Results")
    print("=" * 60)

    for query in test_queries:
        print(f"\n🔍 Query: {query}")

        # Retrieve
        retrieved = retriever.retrieve(query, top_k=3)

        print(f"\n📄 Retrieved {len(retrieved)} chunks:")
        for i, doc in enumerate(retrieved, 1):
            print(f"  [{i}] {doc[:100]}...")

        # Generate answer
        answer = await cached_rag(query, retriever, use_cache=False)

        print(f"\n💡 Answer:")
        print(f"  {answer}")
        print()

    print("=" * 60)
    print("✓ Pipeline test complete!")
    print("=" * 60)

    return retriever


async def interactive_mode(retriever: HybridRetriever):
    """
    Interactive Q&A mode.

    Args:
        retriever: HybridRetriever instance
    """
    print("\n" + "=" * 60)
    print("Interactive Mode (type 'exit' to quit)")
    print("=" * 60)

    while True:
        query = input("\n🔍 Your question: ").strip()

        if query.lower() in ['exit', 'quit', 'q']:
            print("\nGoodbye!")
            break

        if not query:
            continue

        try:
            answer = await cached_rag(query, retriever)
            print(f"\n💡 Answer: {answer}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    # Check API key
    if not os.environ.get("REGOLO_API_KEY"):
        print("\n❌ ERROR: REGOLO_API_KEY not set")
        print("Set it with: export REGOLO_API_KEY=your_key_here")
        print("Get your key from: https://regolo.ai/dashboard\n")
        exit(1)

    # Run pipeline
    retriever = asyncio.run(build_rag_pipeline())

    # Interactive mode
    asyncio.run(interactive_mode(retriever))
