#!/usr/bin/env python3
import os
import sys
import re
import subprocess
from dotenv import load_dotenv

# Ensure the reviewer directory is in python load path
reviewer_dir = os.path.dirname(os.path.abspath(__file__))
if reviewer_dir not in sys.path:
    sys.path.insert(0, reviewer_dir)

from langchain_openai import ChatOpenAI

# Import from review_crew
from review_crew import run_review, REGOLO_MODEL, REGOLO_API_KEY, get_root_code

# 1. Load configuration
curr_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(curr_dir, ".env"))
load_dotenv()

def get_project_root():
    # If this file is inside 'reviewer/', the project root is its parent directory
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(curr_dir) == "reviewer":
        return os.path.dirname(curr_dir)
    return curr_dir

# Create 'tests' output directory in the project root if it doesn't exist
PROJECT_ROOT = get_project_root()
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
os.makedirs(TESTS_DIR, exist_ok=True)
errors_report_path = os.path.join(TESTS_DIR, "REVIEW_ERRORS.md")

# 2. Regex Patterns for fast local scanning of secrets before RAG/LLM (Ultra-fast pre-flight check)
SECRET_PATTERNS = {
    "Regolo / OpenAI API Key": r"sk-[a-zA-Z0-9_-]{24,}",
    "Private Key": r"-----BEGIN (RSA|EC|DSA|GPG)? PRIVATE KEY-----",
    "AWS Access Key ID": r"AKIA[0-9A-Z]{16}",
    "Slack Token": r"xox[bapr]-[0-9]{12}-[a-zA-Z0-9_-]+",
    "Database URL with Credentials": r"postgres(ql)?://[^:]+:[^@]+@[a-zA-Z0-9.-]+:\d+/[a-zA-Z0-9_-]+",
}

def scan_secrets(diff_text: str) -> list:
    """
    Scan the git diff for potential hardcoded secrets or sensitive credentials.
    Only checks added lines (lines starting with '+' but not '+++').
    """
    found_secrets = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            for name, pattern in SECRET_PATTERNS.items():
                match = re.search(pattern, line)
                if match:
                    secret_snippet = match.group(0)
                    masked = secret_snippet[:8] + "..." + secret_snippet[-4:] if len(secret_snippet) > 12 else "..."
                    found_secrets.append(f"Detected possible '{name}' (value: {masked}) at line: {line.strip()}")
    return found_secrets

def get_git_diff() -> tuple:
    """
    Retrieve the current git diff and determine the repository status.
    Returns a tuple: (diff_text, status_type) where status_type is 'uncommitted', 'unpushed', or 'clean'.
    """
    try:
        # Check if we are inside a git repository
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("ERROR: This directory is not a Git repository.")
        sys.exit(1)

    # Check if there is at least one commit in the repository (i.e. HEAD exists)
    has_commits = True
    try:
        subprocess.run(["git", "rev-parse", "--verify", "HEAD"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        has_commits = False

    if not has_commits:
        # No commits yet, get combined staged and unstaged changes
        diff_unstaged = subprocess.check_output(["git", "diff"]).decode("utf-8")
        diff_staged = subprocess.check_output(["git", "diff", "--cached"]).decode("utf-8")
        diff_uncommitted = diff_unstaged + "\n" + diff_staged
        if diff_uncommitted.strip():
            return diff_uncommitted, "uncommitted"
        return "", "clean"

    # 1. Check for uncommitted changes (staged + unstaged)
    diff_uncommitted = subprocess.check_output(["git", "diff", "HEAD"]).decode("utf-8")
    
    if diff_uncommitted.strip():
        return diff_uncommitted, "uncommitted"

    # 2. If no local changes, check for commits not yet pushed to remote tracking branch
    try:
        # Check if an upstream tracking branch is set
        subprocess.run(["git", "rev-parse", "--abbrev-ref", "@{u}"], check=True, capture_output=True)
        # Compare with remote tracking branch
        diff_unpushed = subprocess.check_output(["git", "diff", "@{u}..HEAD"]).decode("utf-8")
        if diff_unpushed.strip():
            return diff_unpushed, "unpushed"
    except subprocess.CalledProcessError:
        # If no upstream is set, fallback to diff with origin/main or origin/master
        for fallback_branch in ["origin/main", "origin/master"]:
            try:
                diff_unpushed = subprocess.check_output(["git", "diff", f"{fallback_branch}..HEAD"]).decode("utf-8")
                if diff_unpushed.strip():
                    return diff_unpushed, "unpushed"
            except subprocess.CalledProcessError:
                continue

    return "", "clean"

def generate_commit_message(diff_text: str) -> str:
    """
    Generate a semantic, professional commit message (Conventional Commits) using Regolo LLM.
    """
    print("Generating commit message...")
    
    # Avoid context saturation by truncating if diff is extremely large
    max_len = 12000
    if len(diff_text) > max_len:
        diff_text = diff_text[:max_len] + "\n\n...[Diff truncated due to length limits]..."

    prompt = f"""You are an expert Git assistant. Analyze the following diff of changes and generate a professional, concise commit message following the 'Conventional Commits' standard (e.g., feat(api): add login route, fix(sec): correct vulnerable hash, style: formatting).
The message must have a title of at most 72 characters, and optionally a brief description. Respond EXCLUSIVELY with the text of the commit message, without any markdown blocks, introductory words, or comments.

Diff:
{diff_text}
"""
    try:
        llm = ChatOpenAI(
            model=REGOLO_MODEL,
            api_key=REGOLO_API_KEY,
            base_url="https://api.regolo.ai/v1",
            temperature=0.1
        )
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"Warning: Could not generate commit message via LLM ({e}). Using a fallback message.")
        return "chore: automated update verified by AI reviewer"

def main():
    print("="*80)
    print("AI-SHIPPING ASSISTANT: PRE-PUSH CHECK & COMMIT/PUSH AUTOMATION")
    print("="*80)
    
    # 1. Retrieve the git diff
    diff_text, status = get_git_diff()
    
    if not diff_text:
        print("ℹ️ No local changes or unpushed commits detected. Running full codebase review on the root anyway!")
    else:
        print(f"Detected changes of type: {status.upper()}")
    
    # 2. Local secrets scanning (Ultra-fast Regex)
    print("Phase 1: Local fast scanning for hardcoded secrets...")
    secrets_found = scan_secrets(diff_text)
    if secrets_found:
        print("🔴 BLOCKED: Potential hardcoded secrets detected in git diff!")
        report_content = "# Pre-Push Security Error (Local Scan)\n\n"
        report_content += "The push was blocked immediately because sensitive secrets were detected in the code:\n\n"
        for secret in secrets_found:
            print(f" - {secret}")
            report_content += f"- {secret}\n"
        report_content += "\n**Required Action:** Please remove plaintext keys and credentials before trying again. Use environment variables or .env files.\n"
        
        with open(errors_report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"\nDetailed error report created in: {errors_report_path}")
        sys.exit(1)
        
    print("✅ No secrets detected with local fast scan.")

    # 3. Deep analysis using CrewAI (LLM + RAG)
    print("\nPhase 2: Starting deep audit with the Virtual Agent team (CrewAI)...")
    try:
        # Get all code from the project root, excluding the reviewer folder
        root_code = get_root_code(PROJECT_ROOT)
        report_output = run_review(code_content=root_code)
    except Exception as e:
        print(f"🔴 ERROR during CrewAI execution: {str(e)}")
        sys.exit(1)
        
    # 4. Parse Lead Engineer verdict
    # Check if the report contains "BLOCKED", "REQUEST CHANGES", or red markers indicating block
    is_blocked = "BLOCKED" in report_output or "REQUEST CHANGES" in report_output or "🔴" in report_output
    
    if is_blocked:
        print("\n🔴 BLOCKED: The Lead Engineer or Security Auditor has blocked the release!")
        
        # Write error report for developer remediation
        with open(errors_report_path, "w", encoding="utf-8") as f:
            f.write(report_output)
            
        print(f"\nViolation report saved to: {errors_report_path}")
        print("Share this file with your LLM coding assistant or check the report details to fix the violations.")
        sys.exit(1)
        
    print("\n🟢 APPROVED: Code matches security policies and meets quality standards!")
    
    # Clear old error report if it exists
    if os.path.exists(errors_report_path):
        try:
            os.remove(errors_report_path)
        except OSError:
            pass

    # 5. Handle Commit and Push automation
    if status == "uncommitted":
        print("\nPhase 3: Automated Commit & Push...")
        # Generate semantic commit message
        commit_msg = generate_commit_message(diff_text)
        print(f"\nGenerated commit message:\n---\n{commit_msg}\n---")
        
        try:
            # Stage all changes
            subprocess.run(["git", "add", "-A"], check=True)
            # Create git commit
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            # Push changes
            print("Sending commits to remote repository (git push)...")
            subprocess.run(["git", "push"], check=True)
            print("\n🚀 Operation completed successfully! Code reviewed, committed, and pushed.")
        except subprocess.CalledProcessError as e:
            print(f"🔴 Error executing Git commands: {e}")
            sys.exit(1)
    elif status == "unpushed":
        print("\nPhase 3: Sending already recorded commits...")
        try:
            subprocess.run(["git", "push"], check=True)
            print("\n🚀 Operation completed successfully! Pre-existing commits reviewed and pushed.")
        except subprocess.CalledProcessError as e:
            print(f"🔴 Error executing git push: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
