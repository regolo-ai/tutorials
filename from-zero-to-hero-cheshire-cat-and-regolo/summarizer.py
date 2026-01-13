"""
Summarizer tool for Cheshire Cat using Regolo API
"""

from cat.mad_hatter.decorators import tool
import sys
import os

# Add parent directory to path to import regolo_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from regolo_client import regolo_chat
except ImportError:
    # Fallback for when running inside Cheshire Cat
    import requests

    def regolo_chat(messages, temperature=0.2):
        API_KEY = os.environ.get("REGOLO_API_KEY")
        if not API_KEY:
            return "ERROR: REGOLO_API_KEY not set"

        response = requests.post(
            "https://api.regolo.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": "Llama-3.3-70B-Instruct",
                "temperature": temperature,
                "messages": messages,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


@tool(return_direct=True)
def summarize_text(text: str, max_bullets: int = 5, tool_input: str = None) -> str:
    """
    Summarize a long text into bullet points using an open-source model on regolo.ai.
    Useful for: meeting notes, long emails, documentation, technical papers.

    Args:
        text: The text to summarize
        max_bullets: Maximum number of bullet points (default: 5)
    """

    prompt = (
        f"Summarize the following text into {max_bullets} concise bullet points. "
        "Focus on key decisions, risks, action items, and technical details.\n\n"
        f"TEXT:\n{text}"
    )

    try:
        answer = regolo_chat(
            [
                {
                    "role": "system", 
                    "content": "You are an expert technical summarizer for enterprise teams."
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # Low temp for consistent summaries
        )
        return f"📝 Summary:\n\n{answer}"

    except Exception as e:
        return f"❌ Error calling Regolo API: {str(e)}"


@tool(return_direct=True)
def technical_qa(question: str, context: str = "", tool_input: str = None) -> str:
    """
    Answer technical questions using open-source LLM reasoning.
    Useful for: architecture decisions, code review, best practices.

    Args:
        question: The technical question to answer
        context: Optional context or code snippet
    """

    prompt = f"Question: {question}\n"
    if context:
        prompt += f"\nContext:\n{context}\n"

    try:
        answer = regolo_chat(
            [
                {
                    "role": "system",
                    "content": "You are a senior software architect with expertise in production systems, scalability, and best practices."
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return f"🔧 Technical Answer:\n\n{answer}"

    except Exception as e:
        return f"❌ Error: {str(e)}"
