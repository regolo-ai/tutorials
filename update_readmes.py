import os
import re

LOGO_BLOCK = """<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

"""

BADGE_BLOCK = """
<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />
"""

PROMO_BLOCK = """> [!IMPORTANT]  
> ## 🎁 Special Offer: 30 Days Free Trial
> 
> To power your AI agent, you need an API key. Sign up for Regolo today and get **30 days completely free**, plus a massive **70% discount for the following 3 months!**
> 
> 🚀 **[CLICK HERE TO GET STARTED AND CLAIM YOUR FREE TRIAL](https://regolo.ai/pricing)** 🚀
> 
> ---
> **Explore Regolo:** [Platform](https://regolo.ai) | [Models Library](https://regolo.ai/models-library/) | [Documentation & Guides](https://regolo.ai/docs) | [YouTube](https://www.youtube.com/@regoloai) | [Discord](https://discord.gg/wHxwWCC8)"""

def process_readme(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if logo already injected (like the autoupdate one)
    if "https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" in content and path.endswith('autoupdate-agent-for-websites/README.md'):
        return # Skip the one we already manually did

    original_content = content
    
    # 1. Insert Logo
    if "Regolo_logo_positive.png" not in content:
        # Find the first H1
        content = re.sub(r'^(#\s+.*)$', LOGO_BLOCK + r'\1', content, count=1, flags=re.MULTILINE)

    # 2. Insert Badges right after H1
    if "badge/build-passing-brightgreen" not in content:
        # Match H1 line, then any existing markdown badges right after it, and replace with H1 + BADGE_BLOCK
        content = re.sub(r'^(#\s+.*?)\n(?:\[!\[.*?\]\(.*?\)\]\(.*?\)\n)*(?:<div align="center">.*?</div>\n)?', r'\1\n' + BADGE_BLOCK, content, count=1, flags=re.MULTILINE | re.DOTALL)

    # 3. Replace Promo Block
    # Look for "### 🎁 Get Started Free..." up to either the next "## " or "---" or EOF
    # Some blocks have Discord at the end, let's catch it broadly.
    promo_pattern1 = r'### 🎁 Get Started Free.*?(?=\n## |\n---|\Z)'
    if re.search(promo_pattern1, content, flags=re.DOTALL):
        content = re.sub(promo_pattern1, PROMO_BLOCK, content, flags=re.DOTALL)
    else:
        # Try to find discord link and replace that section if no "Get Started Free"
        pass

    # Ensure no old regolo links are lingering if we did the replace
    
    if content != original_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {path}")

for root, dirs, files in os.walk('.'):
    # skip .git and virtualenvs
    if '.git' in root or '.venv' in root or 'node_modules' in root:
        continue
    for file in files:
        if file.lower() == 'readme.md':
            process_readme(os.path.join(root, file))

