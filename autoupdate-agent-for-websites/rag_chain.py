from typing import List
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from llm_langchain import llm
from retriever import get_retriever


def format_docs(docs) -> str:
    """
    Format the retrieved documents into a single string to be passed as context to the LLM.
    Args:
        docs: List of retrieved document objects.
    Returns:
        Formatted string containing the source and content of each document.
    """
    parts: List[str] = []
    for d in docs:
        source = d.metadata.get('source', 'n/a')
        lastmod = d.metadata.get('lastmod', 'n/a')
        parts.append(f"Source: {source}\nLast Modified / Publication Date: {lastmod}\nText:\n{d.page_content}")
    return "\n\n---\n\n".join(parts)


def get_rag_chain():
    """
    Build and return the Retrieval-Augmented Generation (RAG) chain.
    The chain combines document retrieval, prompt formatting, and LLM inference.
    Returns:
        A LangChain Runnable that processes the user question and returns the answer.
    """
    retriever = get_retriever()

    # Get the current date to give temporal awareness to the LLM
    today_date = datetime.now().strftime("%B %d, %Y")

    # System prompt defining the assistant's behavior and constraints
    system_prompt = f"""You are an AutoUpdate Agent of a company.
Today's date is: {today_date}

Reply in English, in a concise and practical way.
When asked about the "latest" or "newest" articles, use Today's date to find the most recent ones chronologically in the provided context.
Use ONLY the information present in the context when possible.
If something is not in the context, state it clearly and suggest who to contact in the company."""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "Context:\n{context}\n\nUser Question:\n{question}",
            ),
        ]
    )

    # Compose the RAG chain using the LangChain Expression Language (LCEL)
    rag_chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain