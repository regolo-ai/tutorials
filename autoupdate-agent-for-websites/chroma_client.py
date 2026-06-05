import chromadb
from chromadb.config import Settings

def get_chroma_http_client():
    """
    Create and return an HTTP client to communicate with the Dockerized ChromaDB.
    Returns:
        chromadb.HttpClient instance.
    """
    client = chromadb.HttpClient(
        host="localhost",
        port=8000,
        settings=Settings(
            allow_reset=False,
            anonymized_telemetry=False,
        ),
    )
    return client