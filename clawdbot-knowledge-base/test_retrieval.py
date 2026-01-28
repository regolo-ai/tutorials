#!/usr/bin/env python3
"""
Test script for RAG pipeline quality and performance
Run: python3 test_retrieval.py
"""

import time
from rag_pipeline import KnowledgeBaseRAG

def test_retrieval_quality():
    """Test retrieval accuracy with sample queries."""
    
    print("\n🧪 Testing RAG Pipeline Quality & Performance\n")
    print("="*60)
    
    # Initialize RAG
    rag = KnowledgeBaseRAG()
    if not rag.load_index():
        print("❌ No index found. Build one first:")
        print("   python3 rag_pipeline.py build")
        return
    
    # Sample test queries (customize for your knowledge base)
    test_queries = [
        "What is our GDPR data retention policy?",
        "How do we handle production incidents?",
        "What are the deployment procedures?",
        "Explain our security guidelines",
        "What is the process for code review?",
    ]
    
    results = []
    total_latency = 0
    total_cost = 0
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'─'*60}")
        print(f"📋 Test {i}/{len(test_queries)}: {query}")
        print(f"{'─'*60}")
        
        t0 = time.time()
        result = rag.query(query)
        query_time = (time.time() - t0) * 1000
        
        total_latency += query_time
        total_cost += result['cost_eur']
        
        print(f"\n📚 Answer:\n{result['answer'][:200]}...")
        print(f"\n📎 Top Sources:")
        for src in result['sources'][:3]:
            print(f"   • {src['file']} (relevance: {src['relevance']})")
        
        print(f"\n⏱️  Latency: {query_time:.0f}ms")
        print(f"💰 Cost: €{result['cost_eur']:.4f}")
        print(f"🔍 Retrieved: {result['retrieval_candidates']} → Reranked: {result['reranked_chunks']}")
        
        results.append({
            'query': query,
            'latency_ms': query_time,
            'cost_eur': result['cost_eur'],
            'sources': len(result['sources'])
        })
    
    # Summary statistics
    print(f"\n{'='*60}")
    print("📊 SUMMARY STATISTICS")
    print(f"{'='*60}")
    
    avg_latency = total_latency / len(test_queries)
    avg_cost = total_cost / len(test_queries)
    
    latencies = [r['latency_ms'] for r in results]
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    
    print(f"\n⏱️  Latency:")
    print(f"   ├─ Average: {avg_latency:.0f}ms")
    print(f"   ├─ p95: {p95_latency:.0f}ms")
    print(f"   ├─ Min: {min(latencies):.0f}ms")
    print(f"   └─ Max: {max(latencies):.0f}ms")
    
    print(f"\n💰 Cost:")
    print(f"   ├─ Average per query: €{avg_cost:.4f}")
    print(f"   ├─ Total (5 queries): €{total_cost:.4f}")
    print(f"   └─ Projected (1K queries): €{avg_cost * 1000:.2f}")
    
    print(f"\n📚 Knowledge Base:")
    print(f"   ├─ Documents: {rag.index['num_docs']}")
    print(f"   ├─ Chunks: {rag.index['num_chunks']}")
    print(f"   └─ Models: {rag.index['models']['embed']}, {rag.index['models']['rerank']}, {rag.index['models']['chat']}")
    
    print(f"\n{'='*60}")
    print("✅ Testing complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    test_retrieval_quality()
