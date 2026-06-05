import os
import re
import sys
import datetime
import warnings

# Suppress LangChain deprecation and missing User Agent warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ["USER_AGENT"] = "AutoUpdateAgentBot/1.0"

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn

from langchain_community.document_loaders import SitemapLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from chroma_client import get_chroma_http_client

CONFIG_FILE = "content_generator_source_url.txt"
LOG_FILE = "content_generator_log.txt"
CHROMA_COLLECTION = "autoupdate-agent"

console = Console()

def build_embeddings():
    # example model, multilingual
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_folder="cache"
    )

def split_documents(docs):
    # Clean excessive whitespaces to make chunks denser and more meaningful
    for doc in docs:
        doc.page_content = re.sub(r'\n+', '\n', doc.page_content)
        doc.page_content = re.sub(r' +', ' ', doc.page_content)
        
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " "],
    )
    return splitter.split_documents(docs)

def log_to_file(msg):
    """Appends plain text message to log file with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def log_step(msg, style="bold blue"):
    """Prints styled message to console and logs plain text."""
    console.print(f"[{style}]➜[/] {msg}")
    log_to_file(msg)

def log_error(msg):
    """Prints error to console and logs it."""
    console.print(f"[bold red]✖ ERROR:[/] {msg}")
    log_to_file(f"ERROR: {msg}")

def log_success(msg):
    """Prints success to console and logs it."""
    console.print(f"[bold green]✔[/] {msg}")
    log_to_file(f"SUCCESS: {msg}")

def get_or_ask_url():
    """Reads the URL from env var, config file, or prompts the user if missing/invalid."""
    env_url = os.environ.get("KNOWLEDGE_BASE_URL")
    if env_url:
        log_step(f"Found URL in .env variable KNOWLEDGE_BASE_URL: [cyan]{env_url}[/]")
        return env_url
    
    if not sys.stdout.isatty():
        log_error("No URL provided and running in background/non-interactive mode. Please set KNOWLEDGE_BASE_URL in .env")
        sys.exit(1)
        
    console.print(Panel.fit("[bold yellow]Auto-Updating Knowledge Base[/]\nPlease provide a URL to scan and ingest.", border_style="yellow"))
    
    
def scrape_web(url):
    """Scrapes the web content using SitemapLoader or WebBaseLoader and logs sources."""
    log_step(f"Downloading web content from: [cyan]{url}[/]")
    
    try:
        if url.endswith(".xml"):
            loader = SitemapLoader(web_path=url)
        else:
            loader = WebBaseLoader(web_path=url)
            
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Scraping website...", total=None)
            docs = loader.load()
            progress.update(task, completed=True)
            
        log_success(f"Successfully downloaded {len(docs)} web documents.")
        
        # Log all successfully parsed URLs to file only (to avoid cluttering terminal)
        if docs:
            log_to_file("List of successfully parsed URLs:")
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get('source', 'Unknown URL')
                log_to_file(f"  {i}. {source}")
            console.print(f"  [dim]Saved full list of {len(docs)} URLs to {LOG_FILE}[/]")
        
        return docs
    except Exception as e:
        log_error(f"Failed to scrape website: {str(e)}")
        return []

def main():
    log_to_file("=" * 50)
    log_to_file("Starting Content Generator Auto-Update Job")
    console.rule("[bold magenta]Content Generator Auto-Update[/]")
    
    url = get_or_ask_url()
    
    # 1. Web Scraping
    web_docs = scrape_web(url)
    
    if not web_docs:
        log_error("No documents found to process from the web. Exiting.")
        return

    log_step(f"Total web documents to process: [bold]{len(web_docs)}[/]")
    
    # 2. Chunking
    log_step("Splitting documents into chunks...")
    try:
        chunks = split_documents(web_docs)
        log_success(f"Total chunks created: {len(chunks)}")
    except Exception as e:
        log_error(f"Failed during chunking: {str(e)}")
        return
    
    # 3. Initialize Chroma & Clean old DB
    log_step("Connecting to ChromaDB...")
    client = None
    try:
        client = get_chroma_http_client()
        log_step(f"Clearing old documents in '{CHROMA_COLLECTION}' to prevent duplicates...")
        try:
            col = client.get_collection(CHROMA_COLLECTION)
            docs = col.get()
            if docs and docs['ids']:
                col.delete(ids=docs['ids'])
            log_success("Old documents deleted successfully (Collection preserved).")
        except Exception:
            # Collection might not exist yet, which is fine
            log_to_file("Collection doesn't exist yet, no need to delete documents.")
            console.print("  [dim]No previous collection found to clear, proceeding...[/]")
    except Exception as e:
        log_to_file(f"Error connecting to ChromaDB. (Message: {str(e)})")
        console.print(f"  [bold red]Error connecting to ChromaDB: {str(e)}[/]")
        return
        
    # 5. Fresh Ingestion
    log_step("Generating embeddings and saving to database...")
    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task1 = progress.add_task("Loading Embedding Model...", total=None)
            embeddings = build_embeddings()
            progress.update(task1, description="Embedding documents and uploading to ChromaDB...")
            
            vectordb = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                client=client,
                collection_name=CHROMA_COLLECTION,
            )
            progress.update(task1, completed=True)
            
        log_success("Embeddings saved to ChromaDB successfully.")
        log_step(f"Total chunks verified in database: [bold green]{vectordb._collection.count()}[/]")
    except Exception as e:
        log_error(f"CRITICAL ERROR during ingestion to ChromaDB: {str(e)}")
        return
    
    console.rule("[bold green]Auto-Update Job Completed Successfully[/]")
    log_to_file("Auto-Update Job Completed Successfully.")
    log_to_file("=" * 50)

if __name__ == "__main__":
    main()
