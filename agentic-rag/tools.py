import json
from storage import (
    search_parent_summaries,
    read_child_chunks_by_parent,
    keyword_search_chunks,
)

# function definitions for tool calling with brick-complexity-pro
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "search_topic_index",
            "description": "searches parent summaries to identify relevant documents and their unique identifiers",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "general topic or thematic keywords to search",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "maximum number of parent summaries to retrieve",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_chunk_details",
            "description": "reads granular section chunks belonging to a target parent document",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "identifier of the parent document obtained from the topic index",
                    },
                    "focus_query": {
                        "type": "string",
                        "description": "optional query to rank and filter granular sections",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "maximum number of child chunks to retrieve",
                    },
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyword_search",
            "description": "searches exact terms, identifiers, or codes across granular sections",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "exact keyword or code to match",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "maximum number of matching sections to retrieve",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
]


def execute_tool_call(tool_name: str, arguments: dict) -> dict:
    # safe dispatcher executing the requested retrieval tool
    if tool_name == "search_topic_index":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 2)
        results = search_parent_summaries(query=query, top_k=top_k)
        return {
            "status": "success",
            "tool": tool_name,
            "count": len(results),
            "results": results,
        }

    if tool_name == "read_chunk_details":
        document_id = arguments.get("document_id", "")
        focus_query = arguments.get("focus_query", "")
        top_k = arguments.get("top_k", 2)
        results = read_child_chunks_by_parent(
            document_id=document_id, query=focus_query, top_k=top_k
        )
        return {
            "status": "success",
            "tool": tool_name,
            "document_id": document_id,
            "count": len(results),
            "results": results,
        }

    if tool_name == "keyword_search":
        keyword = arguments.get("keyword", "")
        top_k = arguments.get("top_k", 2)
        results = keyword_search_chunks(keyword=keyword, top_k=top_k)
        return {
            "status": "success",
            "tool": tool_name,
            "count": len(results),
            "results": results,
        }

    return {
        "status": "error",
        "message": f"unrecognized tool: {tool_name}",
    }
