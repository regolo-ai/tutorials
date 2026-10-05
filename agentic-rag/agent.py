import json
import re
import time
import requests
from config import (
    regolo_base_url,
    regolo_model_name,
    regolo_api_key,
    max_retrieval_rounds,
)
from tools import execute_tool_call


def extract_tool_action(text: str) -> dict:
    # parse structured tool call or final answer payload from model text
    match = re.search(r"\{[\s\S]*\"action\"[\s\S]*\}", text)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data
    except Exception:
        # fallback greedy parser
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return {}
        return {}


def run_agentic_rag(
    question: str, max_rounds: int = max_retrieval_rounds, api_key: str = ""
) -> dict:
    start_time = time.time()
    active_key = api_key or regolo_api_key

    system_instruction = (
        "you are an autonomous retrieval agent operating under the regolo hierarchical architecture. "
        "you must search the local database to find facts. "
        "available tools:\n"
        "- search_topic_index: arguments {'query': 'thematic search query', 'top_k': 2}\n"
        "- read_chunk_details: arguments {'document_id': 'parent id', 'focus_query': 'keyword or filter', 'top_k': 2}\n"
        "- keyword_search: arguments {'keyword': 'exact phrase or code', 'top_k': 2}\n\n"
        "rules:\n"
        "1. always start by searching the topic index to locate parent documents.\n"
        "2. then read granular section chunks for candidate documents.\n"
        "3. evaluate evidence completeness before answering.\n"
        "4. respond strictly with a json object:\n"
        "to call a tool:\n"
        "{\"action\": \"tool_call\", \"tool\": \"search_topic_index\", \"arguments\": {\"query\": \"keywords\"}}\n"
        "to finalize answer:\n"
        "{\"action\": \"final_answer\", \"answer\": \"your grounded answer citing [chunk_id] sources\"}"
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"user inquiry: {question}"},
    ]

    tool_call_history = []
    collected_chunks = {}
    current_round = 0
    final_answer = ""

    if active_key:
        headers = {
            "authorization": f"bearer {active_key}",
            "content-type": "application/json",
        }

        while current_round < max_rounds:
            current_round += 1
            payload = {
                "model": regolo_model_name,
                "messages": messages,
                "temperature": 0.1,
            }

            try:
                response = requests.post(
                    f"{regolo_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=45,
                )
                response.raise_for_status()
                response_data = response.json()
                assistant_text = response_data["choices"][0]["message"][
                    "content"
                ]

                parsed_action = extract_tool_action(assistant_text)
                action_type = parsed_action.get("action", "")

                if action_type == "final_answer":
                    final_answer = parsed_action.get(
                        "answer", assistant_text
                    )
                    break

                tool_name = parsed_action.get("tool") or action_type
                if tool_name in [
                    "search_topic_index",
                    "read_chunk_details",
                    "keyword_search",
                ]:
                    arguments = parsed_action.get("arguments", {})
                    tool_result = execute_tool_call(tool_name, arguments)

                    tool_call_history.append({
                        "round": current_round,
                        "tool": tool_name,
                        "arguments": arguments,
                        "results_count": tool_result.get("count", 0),
                    })

                    # record extracted child chunks
                    if "results" in tool_result and isinstance(
                        tool_result["results"], list
                    ):
                        for item in tool_result["results"]:
                            if "chunk_id" in item:
                                collected_chunks[item["chunk_id"]] = item

                    messages.append({
                        "role": "assistant",
                        "content": assistant_text,
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            f"tool execution result for {tool_name}:\n"
                            f"{json.dumps(tool_result, ensure_ascii=False)}\n\n"
                            "evaluate if collected evidence covers the inquiry. "
                            "respond with another tool_call or produce final_answer citing [chunk_id]."
                        ),
                    })
                else:
                    # if the model answered directly without json wrapper
                    final_answer = assistant_text
                    break

            except Exception as error:
                final_answer = (
                    f"error during orchestration loop: {error}"
                )
                break
    else:
        # local deterministic simulation when api key is not configured
        current_round = 2
        topic_result = execute_tool_call(
            "search_topic_index", {"query": question, "top_k": 2}
        )
        tool_call_history.append({
            "round": 1,
            "tool": "search_topic_index",
            "arguments": {"query": question, "top_k": 2},
            "results_count": topic_result.get("count", 0),
        })

        for doc in topic_result.get("results", []):
            doc_id = doc["document_id"]
            chunk_result = execute_tool_call(
                "read_chunk_details",
                {"document_id": doc_id, "focus_query": question, "top_k": 2},
            )
            tool_call_history.append({
                "round": 2,
                "tool": "read_chunk_details",
                "arguments": {"document_id": doc_id},
                "results_count": chunk_result.get("count", 0),
            })
            for chunk in chunk_result.get("results", []):
                collected_chunks[chunk["chunk_id"]] = chunk

        final_answer = (
            "answer synthesized by local hierarchical controller without network key: "
            f"inspected {len(topic_result.get('results', []))} parent summaries and retrieved "
            f"{len(collected_chunks)} granular section chunks with verified citations."
        )

    duration = time.time() - start_time
    return {
        "pipeline": "agentic_rag_hierarchical",
        "question": question,
        "answer": final_answer,
        "tools_executed": tool_call_history,
        "steps_count": len(tool_call_history),
        "unique_chunks_count": len(collected_chunks),
        "chunks_used": list(collected_chunks.values()),
        "duration_seconds": round(duration, 3),
        "iterations": current_round,
    }
