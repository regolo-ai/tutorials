⚠ Redis not available - caching disabled
============================================================
Production RAG Pipeline - Regolo + Open Models
============================================================

[1/6] Loading documents...

[2/6] Semantic chunking...
✓ Created 3 chunks

[3/6] Embedding with gte-Qwen2...
Embedding 3 chunks with gte-Qwen2...
✓ Embedded 3 chunks in 0.53s
  Embedding dimension: 3584

[4/6] Building hybrid index...
Indexing 3 chunks...
  ✓ Indexed in ChromaDB (dense)
  ✓ Indexed in BM25 (lexical)

✓ Hybrid index built successfully

[5/6] Initializing retriever...
Loading cross-encoder reranker...
config.json: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 794/794 [00:00<00:00, 1.36MB/s]
model.safetensors: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 90.9M/90.9M [00:03<00:00, 26.3MB/s]
tokenizer_config.json: 1.33kB [00:00, 2.23MB/s]
vocab.txt: 232kB [00:00, 664kB/s] 
tokenizer.json: 711kB [00:00, 3.79MB/s]
special_tokens_map.json: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 132/132 [00:00<00:00, 567kB/s]
README.md: 3.67kB [00:00, 7.81MB/s]
✓ Reranker loaded

[6/6] Testing queries...

============================================================
Query Results
============================================================

🔍 Query: What is production-ready RAG?

📄 Retrieved 3 chunks:
  [1] Production-Ready RAG Systems

Retrieval Augmented Generation (RAG) combines two powerful techniques:...
  [2]  even OpenAI's text-embedding-3-large 
on both English and multilingual tasks.

Llama-3.3 Generation...
  [3] ing instead respects document 
structure by splitting on paragraphs and sentences.

Hybrid Retrieval...

💡 Answer:
  Production-Ready RAG Systems combine two powerful techniques: information retrieval and natural language generation [1].


🔍 Query: How does semantic chunking work?

📄 Retrieved 3 chunks:
  [1] Production-Ready RAG Systems

Retrieval Augmented Generation (RAG) combines two powerful techniques:...
  [2] ing instead respects document 
structure by splitting on paragraphs and sentences.

Hybrid Retrieval...
  [3]  even OpenAI's text-embedding-3-large 
on both English and multilingual tasks.

Llama-3.3 Generation...

💡 Answer:
  Semantic chunking respects document structure by splitting on paragraphs and sentences [1], [2].


🔍 Query: What is hybrid retrieval?

📄 Retrieved 3 chunks:
  [1] ing instead respects document 
structure by splitting on paragraphs and sentences.

Hybrid Retrieval...
  [2] Production-Ready RAG Systems

Retrieval Augmented Generation (RAG) combines two powerful techniques:...
  [3]  even OpenAI's text-embedding-3-large 
on both English and multilingual tasks.

Llama-3.3 Generation...

💡 Answer:
  Hybrid retrieval combines semantic search (using embeddings) with lexical search (using BM25) to achieve 20% better recall than either method alone [1].


🔍 Query: Why use gte-Qwen2 embeddings?

📄 Retrieved 3 chunks:
  [1] ing instead respects document 
structure by splitting on paragraphs and sentences.

Hybrid Retrieval...
  [2] Production-Ready RAG Systems

Retrieval Augmented Generation (RAG) combines two powerful techniques:...
  [3]  even OpenAI's text-embedding-3-large 
on both English and multilingual tasks.

Llama-3.3 Generation...

💡 Answer:
  I don't know based on the provided context.

============================================================
✓ Pipeline test complete!
============================================================

============================================================
Interactive Mode (type 'exit' to quit)
============================================================

🔍 Your question: exit

Goodbye!