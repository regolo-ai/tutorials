import time
import requests
from config import regolo_base_url, regolo_model_name, regolo_api_key
from storage import search_baseline


def run_baseline_rag(
    question: str, top_k: int = 2, api_key: str = ""
) -> dict:
    start_time = time.time()
    active_key = api_key or regolo_api_key

    # single-pass flat retrieval without iterative reasoning
    retrieved_chunks = search_baseline(query=question, top_k=top_k)

    context_lines = []
    for chunk in retrieved_chunks:
        context_lines.append(
            f"[{chunk['chunk_id']}] {chunk['document_name']}: {chunk['content']}"
        )
    formatted_context = "\n\n".join(context_lines)

    # call brick-complexity-pro if regolo api key is provided
    if active_key:
        headers = {
            "authorization": f"bearer {active_key}",
            "content-type": "application/json",
        }
        payload = {
            "model": regolo_model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "answer using only the supplied context and cite supporting chunk ids. if evidence is insufficient, state what is missing.",
                },
                {
                    "role": "user",
                    "content": f"question:\n{question}\n\ncontext:\n{formatted_context}",
                },
            ],
            "temperature": 0.1,
        }
        try:
            response = requests.post(
                f"{regolo_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
        except Exception as error:
            answer = f"api execution error: {error}"
    else:
        # local deterministic simulation when network credentials are omitted
        answer = (
            "baseline generated answer based on retrieved flat chunks:\n"
            + "\n".join([f"- {item['chunk_id']}" for item in retrieved_chunks])
        )

    duration = time.time() - start_time
    return {
        "pipeline": "baseline_single_pass",
        "question": question,
        "answer": answer,
        "chunks_used": retrieved_chunks,
        "chunks_count": len(retrieved_chunks),
        "duration_seconds": round(duration, 3),
        "iterations": 1,
    }
