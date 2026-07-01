<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# How to Make RAG 32x Memory‑Efficient with Binary Quantization

This tutorial demonstrates how to reduce the memory footprint of a retrieval‑augmented generation (RAG) pipeline by 32× using binary quantization, while retaining retrieval accuracy through float‑32 re‑ranking.

> **Article**: <https://regolo.ai/how-to-make-rag-32x-memory-efficient-with-binary-quantization/> 

## 🚀 Quick Start

```bash
# 1️⃣ Clone the repository and change to this folder
git clone https://github.com/regolo-ai/tutorials.git && cd tutorials/how-to-make-rag-32x-efficient

# 2️⃣ Install dependencies
pip install -r requirements.txt

# 3️⃣ Run the demo
python crew.py "What are common diabetes treatment approaches?"
```

The script will:
1. Load your .env configuration for embeddings and LLM.
2. Encode a small sample corpus using the chosen embedding model.
3. Build a binary‑quantized FAISS index.
4. Retrieve top‑5 chunks, re‑rank them, and generate a concise answer.

## 📚 What You’ll Learn

- **Binary quantization**: Convert float‑32 embeddings to 1‑bit per dimension, cutting memory usage 32×.
- **FAISS binary index**: Leverage Hamming distance search for fast retrieval.
- **Re‑ranking**: Restore accuracy with a float‑32 dot‑product over the top‑k candidates.
- **OpenAI‑compatible provider flexibility**: Switch between Regolo, OpenAI, Groq, Ollama, or local transformers purely via `.env`.
- **CrewAI integration**: Chain retrieval and synthesis agents in a single, sequential workflow.

## ✅ Prerequisites

- `python >=3.13` or `3.12`
- A valid clipboard‑style API key in `.env` (`OPENAI_API_KEY`, `GROQ_API_KEY`, or `OPENAI_API_KEY`)
- Optional: Ollama running locally for offline inference

## 🛠️ Configuring with `.env`

Copy the provided `how-to-make-rag-32x-efficient/.env.example` to `how-to-make-rag-32x-efficient/.env` and fill in the API key.

## 📄 License

This tutorial is licensed under the MIT license. See the repository root for details.

---

*Powered by [Regolo.ai](https://regolo.ai)*
