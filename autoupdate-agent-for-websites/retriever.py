from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import time

from chroma_client import get_chroma_http_client

CHROMA_COLLECTION = "autoupdate-agent"


def get_retriever():
    """
    Initialize and return the ChromaDB retriever.
    This connects to the vector database and sets up the embedding model for search.
    Returns:
        A LangChain Retriever configured to return the top 5 most similar chunks.
    """
    print("\n[INFO] Connecting to ChromaDB...")
    client = get_chroma_http_client()
    
    print("[INFO] Initializing HuggingFace Embeddings Model (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)...")
    print("[INFO] This might take a few seconds as it loads weights into memory...")
    start_time = time.time()
    
    # Initialize the same embedding model used during document ingestion
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_folder="cache"
    )
    
    elapsed = time.time() - start_time
    print(f"[INFO] Embeddings Model loaded successfully in {elapsed:.2f} seconds!")

    # Connect to the specific ChromaDB collection
    print(f"[INFO] Accessing ChromaDB collection: '{CHROMA_COLLECTION}'...")
    vectordb = Chroma(
        client=client,
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
    )

    # Configure the retriever to fetch the top relevant document chunks
    retriever = vectordb.as_retriever(
        search_kwargs={"k": 15}  # Increased to provide more context for chronological questions
    )
    return retriever