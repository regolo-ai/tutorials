import os
import chromadb
from chromadb.utils import embedding_functions

# Configure the persistent path for ChromaDB relative to this script
DB_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")

def init_db():
    print("Initializing the local ChromaDB vector database...")
    client = chromadb.PersistentClient(path=DB_PATH)
    
    # Use a lightweight and efficient local embedding model
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # Create or retrieve the security policies collection
    collection = client.get_or_create_collection(
        name="security_policies", 
        embedding_function=emb_fn
    )
    
    # Read the policies file
    policy_file = os.path.join(os.path.dirname(__file__), "security_policies.md")
    if not os.path.exists(policy_file):
        raise FileNotFoundError(f"File {policy_file} not found.")
        
    with open(policy_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Logically split sections based on markdown rules (headers starting with ##)
    sections = content.split("## ")
    
    documents = []
    metadatas = []
    ids = []
    
    # Handle the introduction / preamble
    intro = sections[0].strip()
    if intro:
        documents.append(intro)
        metadatas.append({"source": "security_policies.md", "section": "intro"})
        ids.append("policy_intro")
        
    # Handle and index each individual security rule
    for i, section in enumerate(sections[1:], start=1):
        full_text = "## " + section.strip()
        # Extract the identification code of the rule (e.g., SEC-01, COD-01)
        first_line = section.split("\n")[0].strip()
        rule_code = first_line.split(":")[0].strip() if ":" in first_line else f"RULE_{i}"
        
        documents.append(full_text)
        metadatas.append({"source": "security_policies.md", "section": rule_code})
        ids.append(f"policy_{rule_code.lower().replace('-', '_')}")
        
    print(f"Found {len(documents)} rule blocks to index.")
    
    # Insert or update rules inside the vector DB
    collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print("ChromaDB vector database successfully configured and populated!")

if __name__ == "__main__":
    init_db()
