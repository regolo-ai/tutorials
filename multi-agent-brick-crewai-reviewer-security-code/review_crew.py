import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from crewai import Agent, Task, Crew, Process
import chromadb
from chromadb.utils import embedding_functions

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
load_dotenv()

# Verify that the Regolo API Key is configured
REGOLO_API_KEY = os.getenv("REGOLO_API_KEY")
if not REGOLO_API_KEY:
    print("ERROR: The REGOLO_API_KEY environment variable is not configured in the .env file.")
    print("Please create a .env file and add: REGOLO_API_KEY=your_regolo_key")
    sys.exit(1)

# Retrieve or set the default Regolo model
REGOLO_MODEL = os.getenv("REGOLO_MODEL", "brick-v1-beta")

# Absolute path for the local ChromaDB vector database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

# ---------------------------------------------------------
# 1. Optimized Brain Configurations (REGOLO.AI Brick Router)
# ---------------------------------------------------------
# We dynamically select the model specified in the .env file (REGOLO_MODEL), 
# with 'brick-v1-beta' as a robust and cost-effective fallback.

senior_dev_llm = ChatOpenAI(
    model=REGOLO_MODEL,
    api_key=REGOLO_API_KEY,
    base_url="https://api.regolo.ai/v1",
    temperature=0.1  # Low temperature for highly precise code syntax analysis
)

security_auditor_llm = ChatOpenAI(
    model=REGOLO_MODEL,
    api_key=REGOLO_API_KEY,
    base_url="https://api.regolo.ai/v1",
    temperature=0.1  # Low temperature for extremely strict compliance and rule matching
)

lead_engineer_llm = ChatOpenAI(
    model=REGOLO_MODEL,
    api_key=REGOLO_API_KEY,
    base_url="https://api.regolo.ai/v1",
    temperature=0.2  # Balanced temperature for high-quality report synthesis and actionable insights
)

# ---------------------------------------------------------
# 2. Cached & Optimized Custom Tool Definition for RAG
# ---------------------------------------------------------
# Global cache for database connection and model loading to prevent overhead
_cached_collection = None

def _get_security_collection():
    global _cached_collection
    if _cached_collection is None:
        if not os.path.exists(DB_PATH):
            raise FileNotFoundError(
                "The vector database does not exist yet. Please run db_setup.py first "
                "to populate it with corporate security policies."
            )
        # PersistentClient and SentenceTransformer embedding functions are initialized only once
        client = chromadb.PersistentClient(path=DB_PATH)
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _cached_collection = client.get_collection(
            name="security_policies", 
            embedding_function=emb_fn
        )
    return _cached_collection

@tool("Query Security Policies KB")
def query_security_policies(query: str) -> str:
    """
    Search and query the local corporate security guidelines knowledge base.
    Pass key concepts, words, or phrases about the code (e.g., 'crypto', 'hashing', 'api_key', 'database_loop')
    to extract the security rules and policies to comply with.
    """
    try:
        collection = _get_security_collection()
        
        # Query the cached vector database
        results = collection.query(
            query_texts=[query],
            n_results=2
        )
        
        documents = results.get("documents", [[]])[0]
        if not documents:
            return f"No internal policies detected for query: '{query}'."
            
        formatted_output = "\n\n---\n\n".join(documents)
        return f"Company policies found in RAG for '{query}':\n\n{formatted_output}"
        
    except FileNotFoundError as fnf:
        return str(fnf)
    except Exception as e:
        return f"Error while querying the vector database: {str(e)}"


# ---------------------------------------------------------
# 3. Virtual Agent Team Creation (CrewAI)
# ---------------------------------------------------------

# Agent 1: Senior Developer
senior_developer = Agent(
    role="Senior Software Engineer",
    goal="Analyze the provided code to identify style issues, computational inefficiencies, logical bugs, unnecessary algorithmic complexity, or redundancies.",
    backstory=(
        "You are an extremely meticulous and pragmatic senior developer. "
        "You love writing elegant, readable, and maintainable code (Clean Code). "
        "Your focus is on performance, software structure, and removing redundant or inefficient logic. "
        "You are direct, constructive, and very strict about code quality."
    ),
    llm=senior_dev_llm,
    verbose=True,
    max_iter=4,
    allow_delegation=False
)

# Agent 2: Security Auditor (Equipped with RAG Tool)
security_auditor = Agent(
    role="Security Auditor",
    goal="Perform a security audit on the provided code by comparing it with the company's official security guidelines extracted from the RAG.",
    backstory=(
        "You are an experienced and paranoid cybersecurity auditor. "
        "Before inspecting the code, you always consult the internal company security policies database "
        "using the 'Query Security Policies KB' tool to make sure you know the constraints on cryptography, "
        "credential management, database optimization (N+1 queries), and error handling. "
        "You do not care about coding style, but you are inflexible when it comes to security and compliance with policies."
    ),
    tools=[query_security_policies],
    llm=security_auditor_llm,
    verbose=True,
    max_iter=4,
    allow_delegation=False
)

# Agent 3: Lead Engineer (Manager and final decision maker)
lead_engineer = Agent(
    role="Lead Engineer",
    goal="Analyze the reports from the Senior Developer and the Security Auditor to compile a structured final executive report, deciding whether to approve or block the Pull Request.",
    backstory=(
        "You are the technical lead of the development team. Your task is to make clear and final decisions. "
        "You synthesize the technical findings of the Senior Developer and the severe violations highlighted by the Security Auditor. "
        "If there are security violations (e.g., weak password hashing, secrets in code, SQL queries in loops), you MUST BLOCK the Pull Request. "
        "You write a very high-quality, structured, no-nonsense Markdown report that is perfectly formatted for developers."
    ),
    llm=lead_engineer_llm,
    verbose=True,
    max_iter=4,
    allow_delegation=False
)


# ---------------------------------------------------------
# 4. Sequential Task Definitions
# ---------------------------------------------------------

# Task for the Senior Developer
code_review_task = Task(
    description=(
        "Carefully examine the following source code:\n\n"
        "```python\n{code_to_review}\n```\n\n"
        "Identify maintainability issues, computational inefficiencies, duplicated or redundant code, "
        "and violations of Clean Code principles. Produce a clear list of style or logical issues, "
        "indicating the exact line of code and providing the recommended solution for each."
    ),
    expected_output=(
        "A detailed, structured list of technical findings related to style, logical bugs, "
        "algorithmic complexity, or inefficiencies found in the code, with line numbers and refactoring advice."
    ),
    agent=senior_developer
)

# Task for the Security Auditor
security_audit_task = Task(
    description=(
        "Carefully examine the same source code:\n\n"
        "```python\n{code_to_review}\n```\n\n"
        "You must verify if the code contains vulnerabilities or security violations. "
        "Use the 'Query Security Policies KB' tool with a single comprehensive query "
        "(such as 'security requirements' or 'password encryption secrets database_loop') to retrieve company policies. "
        "Compare the code with these official company guidelines. "
        "Identify security violations, assign a severity level (e.g., CRITICAL, HIGH, MEDIUM), "
        "and explain how to remediate each issue based on the guidelines."
    ),
    expected_output=(
        "A detailed security audit report listing the violations found against "
        "company policies, citing specific rules from the Knowledge Base (e.g., SEC-01, SEC-02, COD-01, COD-02) and compliant solutions."
    ),
    agent=security_auditor
)

# Task for the Lead Engineer (Synthesis and Decision)
synthesis_task = Task(
    description=(
        "Examine the reports produced by the Senior Software Engineer (style, performance, and logical bugs) "
        "and the Security Auditor (security and compliance with company policies).\n\n"
        "Synthesize their findings into a single, beautiful executive report in Markdown. "
        "The report must contain the following sections:\n"
        "1. **Final Decision**: Clearly state at the top whether the Pull Request is `🔴 BLOCKED` (if there are Critical/High severity security violations like MD5, hardcoded keys, or SQL queries in loops) or `🟢 APPROVED`.\n"
        "2. **Security Audit Summary (RAG-Verified)**: Table or list of security violations found, mapped to the company policy code (e.g., SEC-01) and the fix explanation.\n"
        "3. **Code Quality & Performance Summary**: List of algorithmic inefficiencies and style recommendations from the Senior Developer.\n"
        "4. **Remediation Plan**: A concise, bulleted list of mandatory steps the developer must take to unblock the PR.\n\n"
        "Maintain a professional, pragmatic, and direct tone. Avoid generic introductions and conclusions."
    ),
    expected_output=(
        "A final structured executive report in Markdown format including the Pull Request status, "
        "a summary of security violations with RAG policy references, code quality findings, and an action plan."
    ),
    agent=lead_engineer,
    context=[code_review_task, security_audit_task]
)


# ---------------------------------------------------------
# 5. Crew Configuration and Execution
# ---------------------------------------------------------
code_review_crew = Crew(
    agents=[senior_developer, security_auditor, lead_engineer],
    tasks=[code_review_task, security_audit_task, synthesis_task],
    process=Process.sequential,
    verbose=True,
    cache=False
)

def get_project_root():
    # If this file is inside 'reviewer/', the project root is its parent directory
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(curr_dir) == "reviewer":
        return os.path.dirname(curr_dir)
    return curr_dir

def get_root_code(project_root: str) -> str:
    """
    Scans the project root directory and concatenates all Python files,
    excluding the 'reviewer' folder and common non-project directories like '.venv', '.git', etc.
    """
    exclude_dirs = {"reviewer", ".venv", "venv", ".git", "__pycache__", "tests", "chroma_db", ".vscode"}
    code_parts = []
    
    # We want to traverse files in alphabetical order for consistency
    for root, dirs, files in os.walk(project_root):
        # Filter directories in-place to avoid scanning excluded ones
        dirs[:] = sorted([d for d in dirs if d not in exclude_dirs and not d.startswith(".")])
        
        for file in sorted(files):
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                # Compute relative path for cleaner reporting
                rel_path = os.path.relpath(file_path, project_root)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    code_parts.append(f"# === File: {rel_path} ===\n{content}\n")
                except Exception as e:
                    print(f"Warning: Could not read file {file_path}: {e}")
                    
    if not code_parts:
        return "# No Python code files found in the root directory (excluding 'reviewer')."
        
    return "\n".join(code_parts)

def run_review(code_content: str | None = None):
    # Load code from the project root (excluding reviewer) if not provided
    project_root = get_project_root()
    if code_content is None:
        code_content = get_root_code(project_root)
        
    print("\n" + "="*80)
    print("STARTING AUTOMATED CODE REVIEW & SECURITY AUDIT (CrewAI + Regolo AI)")
    print("="*80)
    print(f"Inference Model: {REGOLO_MODEL}")
    print("Note: Data is processed with Zero Data Retention criteria for maximum privacy.\n")
    
    # Execute the crew with input parameters
    inputs = {
        "code_to_review": code_content
    }
    
    result = code_review_crew.kickoff(inputs=inputs)
    
    print("\n" + "="*80)
    print("FINAL REPORT IN MARKDOWN GENERATED BY THE LEAD ENGINEER:")
    print("="*80 + "\n")
    print(result)
    
    # Save final report to a markdown file inside the project root 'test' directory with date versioning
    from datetime import datetime
    test_dir = os.path.join(project_root, "test")
    os.makedirs(test_dir, exist_ok=True)
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    version = 1
    while True:
        filename = f"review_report_{current_date}_v{version}.md"
        output_report_path = os.path.join(test_dir, filename)
        if not os.path.exists(output_report_path):
            break
        version += 1
        
    with open(output_report_path, "w", encoding="utf-8") as f:
        f.write(result)
        
    print(f"\nReport successfully saved to: {output_report_path}")
    return result

if __name__ == "__main__":
    run_review()
