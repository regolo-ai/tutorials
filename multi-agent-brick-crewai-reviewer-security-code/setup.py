#!/usr/bin/env python3
import os
import sys

# ANSI Color Codes for high-fidelity professional terminal UI
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
END = "\033[0m"

# Standard security templates tailored for different environments
TEMPLATES = {
    "1": {
        "name": "🚀 Standard SaaS & Web Application (Next.js / Python / Postgres)",
        "policies": """# Security Rules and Coding Standards - SaaS Standard

## SEC-01: Cryptography & Sensitive Data Protection
* **Rule**: It is strictly forbidden to use weak or deprecated hashing algorithms (e.g., `md5`, `sha1`) for password hashing, digital signatures, token generation, or encryption.
* **Remediation**: Use secure algorithms like `bcrypt`, `argon2`, or the approved utility `secure_auth_vault.crypto`.

## SEC-02: Hardcoded Secrets Prevention
* **Rule**: Do not hardcode API keys, OAuth tokens, passwords, database credentials, or secret keys into source code.
* **Remediation**: Always load configuration secrets at runtime from environment variables using a safe helper (e.g., `os.getenv`).

## COD-01: Performance & Database Optimization (N+1 Prevention)
* **Rule**: Avoid executing database queries inside a loop (`for`/`while`) which results in N+1 query bottlenecks.
* **Remediation**: Fetch related data in a single batch query (e.g., bulk fetching, SQL `JOIN`, or using ORM eager loading).

## COD-02: Silent Exception Swallowing
* **Rule**: Empty `try-except` blocks (e.g., `except Exception: pass` or `except: pass`) are strictly prohibited as they hide bugs and prevent production debugging.
* **Remediation**: Always log errors with structured traceback information using a logger (e.g., `logger.error`), or re-raise the exception if unhandleable.
"""
    },
    "2": {
        "name": "💳 Fintech & High-Security Compliance (Strict API / PCI-DSS / Encryption)",
        "policies": """# Security Rules and Coding Standards - Fintech Compliance

## SEC-01: Highly Secure Encryption Standards (Fintech-Grade)
* **Rule**: Use ONLY approved cryptographic libraries (e.g., `cryptography.hazmat` or `bcrypt`). The use of `md5`, `sha1`, `sha256` without salt, or custom crypto implementations is strictly prohibited.
* **Remediation**: Always utilize salted password hashing and AES-256-GCM for data encryption at rest.

## SEC-02: Hardcoded Credentials & Secure Vaulting
* **Rule**: Hardcoding secrets (database credentials, private keys, integration tokens) is a critical compliance breach.
* **Remediation**: Retrieve secrets exclusively from trusted environments (e.g., Vault, AWS Secrets Manager, or strictly controlled env vars).

## SEC-03: SQL Injection Prevention (Strict Raw Queries)
* **Rule**: Never concatenate strings to form SQL queries. This is the primary vector for SQL injection.
* **Remediation**: Always use parameterized queries (prepared statements) provided by the database driver or ORM.

## COD-01: Precise Audit Logging for Financial Mutations
* **Rule**: State-mutating operations on balances, payments, or transaction records must be wrapped in a transactional try-catch and have precise trace logging.
* **Remediation**: Log every transaction attempt, failure, or retry with unique idempotency keys, avoiding the log exposure of PII (Personally Identifiable Information).
"""
    },
    "3": {
        "name": "🤖 AI & Machine Learning Pipeline (Serverless / Model Cache / Memory Safety)",
        "policies": """# Corporate Security Rules and Coding Standards - AI & ML Pipeline

## SEC-01: Model & Input Vector Sanitization
* **Rule**: Never trust input data fed directly into LLMs, models, or vector stores. Unsanitized data can lead to prompt injection or denial of service.
* **Remediation**: Implement strict input schema validation (e.g., using `Pydantic`) and size/token limitations.

## SEC-02: Model Secrets & Inference Credentials
* **Rule**: Do not hardcode inference endpoints, HuggingFace hubs, or model provider API keys.
* **Remediation**: Use runtime environment variables to inject API keys, and keep separate non-production models for local testing.

## COD-01: Efficient Compute & Data Streaming (Memory Overflows)
* **Rule**: Do not load massive datasets or un-chunked embedding vectors entirely into CPU memory at once, which will cause container/server OOM (Out Of Memory) crashes.
* **Remediation**: Stream data from the database/S3 in batches, or use generators (`yield`) to execute calculations iteratively.

## COD-02: Floating Point & NaN Robustness
* **Rule**: Never assume calculation outputs are valid without catching `NaN` (Not-a-Number), division-by-zero, or infinite outputs.
* **Remediation**: Assert vector lengths and numerical boundaries before passing embeddings to vector stores or using Cosine Similarity calculations.
"""
    }
}

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def render_banner():
    banner = f"""
{BOLD}{MAGENTA} ╔═══════════════════════════════════════════════════════════════════╗
 ║  {CYAN}██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗     {YELLOW}█████╗ ██╗{MAGENTA}  ║
 ║  {CYAN}██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗   {YELLOW}██╔══██╗ ██║{MAGENTA} ║
 ║  {CYAN}██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║   {YELLOW}███████║ ██║{MAGENTA} ║
 ║  {CYAN}██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║   {YELLOW}██╔══██║ ██║{MAGENTA} ║
 ║  {CYAN}██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝██╗{YELLOW}██║  ██║ ██║{MAGENTA} ║
 ║  {CYAN}╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝{YELLOW}╚═╝  ╚═╝ ╚═╝{MAGENTA} ║
 ║                                                                   ║
 ║            {WHITE}{BOLD}Corporate AI-Reviewer Setup Assistant                  {MAGENTA}║
 ╚═══════════════════════════════════════════════════════════════════╝{END}
"""
    print(banner)

def render_menu():
    print(f"{BOLD}{WHITE}Select a security guidelines template for your project:{END}\\n")
    for key, val in TEMPLATES.items():
        print(f" {BOLD}{CYAN}[{key}]{END} {WHITE}{val['name']}{END}")
    print(f" {BOLD}{CYAN}[4]{END} {YELLOW}Keep existing/default policies file{END}")
    print()

def get_project_root():
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(curr_dir) == "reviewer":
        return os.path.dirname(curr_dir)
    return curr_dir

def get_reviewer_dir():
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(curr_dir) == "reviewer":
        return curr_dir
    return os.path.join(curr_dir, "reviewer")

def generate_vscode_task():
    project_root = get_project_root()
    vscode_dir = os.path.join(project_root, ".vscode")
    tasks_file = os.path.join(vscode_dir, "tasks.json")
    settings_file = os.path.join(vscode_dir, "settings.json")
    
    # Check if we should use local virtualenv
    venv_python = "${workspaceFolder}/.venv/bin/python"
    # Fallback to standard interpreter command if .venv doesn't exist locally
    python_cmd = venv_python if os.path.exists(os.path.join(project_root, ".venv")) else "${command:python.interpreterPath}"

    # Generate settings.json to pre-select the .venv interpreter in VS Code
    if not os.path.exists(settings_file) and os.path.exists(os.path.join(project_root, ".venv")):
        os.makedirs(vscode_dir, exist_ok=True)
        settings_content = """{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python"
}"""
        with open(settings_file, "w", encoding="utf-8") as f:
            f.write(settings_content)
        print(f" {GREEN}✔{END} {WHITE}Created .vscode/settings.json pointing to .venv!{END}")

    if os.path.exists(tasks_file):
        # Let's try to update the command in tasks.json if it exists
        try:
            import json
            import re
            with open(tasks_file, "r", encoding="utf-8") as f:
                content = f.read()
            # Basic comment stripping to allow json parsing of .json files with comments
            clean_content = re.sub(r"//.*", "", content)
            data = json.loads(clean_content)
            
            updated = False
            if "tasks" in data and isinstance(data["tasks"], list):
                for task in data["tasks"]:
                    if task.get("label") == "Review Code":
                        task["command"] = python_cmd
                        updated = True
                        break
                
            if updated:
                with open(tasks_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                print(f" {GREEN}✔{END} {WHITE}Updated existing .vscode/tasks.json to use the correct Python interpreter!{END}")
                return
            else:
                print(f" {YELLOW}⚠{END} {WHITE}Could not find 'Review Code' task in existing tasks.json to auto-update.{END}")
        except Exception as e:
            # Fallback to simple regex/string replacement if JSON load fails due to complex comments
            try:
                import re
                with open(tasks_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if '"label": "Review Code"' in content:
                    # Replace command under the Review Code block
                    pattern = r'(\{\s*"label"\s*:\s*"Review Code"[\s\S]*?"command"\s*:\s*")[^"]+(")'
                    if re.search(pattern, content):
                        new_content = re.sub(pattern, r'\1' + python_cmd + r'\2', content)
                        with open(tasks_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        print(f" {GREEN}✔{END} {WHITE}Updated existing .vscode/tasks.json using regex!{END}")
                        return
            except Exception:
                pass
            print(f" {YELLOW}⚠{END} {WHITE}.vscode/tasks.json already exists but could not be auto-updated. Skipping.{END}")
        return

    os.makedirs(vscode_dir, exist_ok=True)
    
    tasks_content = f"""{{
    "version": "2.0.0",
    "tasks": [
        {{
            "label": "Review Code",
            "type": "shell",
            "command": "{python_cmd}",
            "args": [
                "${{workspaceFolder}}/reviewer/preflight.py"
            ],
            "options": {{
                "cwd": "${{workspaceFolder}}"
            }},
            "group": {{
                "kind": "build",
                "isDefault": true
            }},
            "presentation": {{
                "reveal": "always",
                "panel": "new",
                "focus": true,
                "clear": true
            }},
            "problemMatcher": []
        }}
    ]
}}"""
    with open(tasks_file, "w", encoding="utf-8") as f:
        f.write(tasks_content)
    print(f" {GREEN}✔{END} {WHITE}Created .vscode/tasks.json task for integration!{END}")

def verify_or_create_env():
    project_root = get_project_root()
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        print(f" {GREEN}✔{END} {WHITE}.env configuration already exists. Skipping.{END}")
        return

    env_template = """# Regolo API Credentials
REGOLO_API_KEY=your_regolo_api_key_here
REGOLO_MODEL=gemma4-31b
"""
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(env_template)
    print(f" {YELLOW}⚠{END} {WHITE}Created new .env template. Please edit it with your REGOLO_API_KEY.{END}")

def main():
    clear_terminal()
    render_banner()
    render_menu()
    
    choice = input(f"{BOLD}{WHITE}Choose option (1-4): {END}").strip()
    while choice not in ["1", "2", "3", "4"]:
        print(f"{RED}Invalid option. Please enter a number between 1 and 4.{END}")
        choice = input(f"{BOLD}{WHITE}Choose option (1-4): {END}").strip()

    print()
    print(f"{BOLD}{BLUE}===================================================================={END}")
    print(f"{BOLD}{WHITE}              INITIALIZING SETUP & INFRASTRUCTURE                  {END}")
    print(f"{BOLD}{BLUE}===================================================================={END}")
    print()

    reviewer_dir = get_reviewer_dir()

    # 1. Handle policy templates
    policy_file = os.path.join(reviewer_dir, "security_policies.md")
    if choice in ["1", "2", "3"]:
        selected_template = TEMPLATES[choice]
        print(f" {GREEN}▶{END} Writing custom security policies: {selected_template['name']}...")
        with open(policy_file, "w", encoding="utf-8") as f:
            f.write(selected_template["policies"])
        print(f" {GREEN}✔{END} Custom policies updated in '{policy_file}'!")
    else:
        print(f" {GREEN}▶{END} Keeping current security policies in '{policy_file}'.")

    # 2. Setup database/embedding local storage (ChromaDB)
    print(f" {GREEN}▶{END} Populating Vector DB with selected policies (ChromaDB)...")
    try:
        # Inject reviewer path to sys.path to find db_setup
        if reviewer_dir not in sys.path:
            sys.path.insert(0, reviewer_dir)
        from db_setup import init_db
        init_db()
        print(f" {GREEN}✔{END} Local Chroma DB generated successfully!")
    except Exception as e:
        print(f" {RED}✘{END} Failed to populate Chroma DB: {e}")
        print(f" {YELLOW}ℹ{END} Check that sentence-transformers and chromadb are correctly installed.")
    
    # 3. Create helper workspace configs
    print(f" {GREEN}▶{END} Generating VS Code tasks configuration...")
    generate_vscode_task()

    print(f" {GREEN}▶{END} Checking environment secrets configuration...")
    verify_or_create_env()

    # 4. Success summary and CTA
    print()
    print(f"{BOLD}{GREEN}===================================================================={END}")
    print(f"{BOLD}{GREEN}        CONGRATULATIONS! SETUP COMPLETED SUCCESSFULLY 🎉           {END}")
    print(f"{BOLD}{GREEN}===================================================================={END}")
    print(f"""
{BOLD}{WHITE}Next Steps to get started:{END}
 1. Check/Edit your {CYAN}.env{END} and enter your {BOLD}REGOLO_API_KEY{END}.
 2. Make some code modifications or commits in your branch.
 3. To run a safe ship & push, open VS Code Command Palette:
    └─ Press {BOLD}{YELLOW}Cmd+Shift+P{END} (or {BOLD}{YELLOW}Ctrl+Shift+P{END})
    └─ Type {BOLD}Run Task{END} and select: 👉 {BOLD}{GREEN}Review Code{END}

{BOLD}{MAGENTA}Enjoy zero-leak compliance reviews with absolute corporate privacy!{END}
""")

if __name__ == "__main__":
    main()
