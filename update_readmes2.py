import os
import re

BADGE_BLOCK_NEW = """<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />
"""

HOW_TO_USE = """### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
"""

def process_readme(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip the UI autoupdate sub-repo or weird cache folders if you want, but actually it applies.
    if 'snapshots' in path or 'node_modules' in path: return

    original = content

    # 1. Replace the existing BADGE_BLOCK
    old_badge_pattern = r'<div align="center">\s*<img src="https://img\.shields\.io/badge/build-passing-brightgreen\.svg" alt="Build passing" />.*?</div>\s*<br />'
    if re.search(old_badge_pattern, content, flags=re.DOTALL):
        content = re.sub(old_badge_pattern, BADGE_BLOCK_NEW.strip(), content, flags=re.DOTALL)
    
    # 2. Remove loose markdown badges
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if 'img.shields.io' in line and (line.strip().startswith('[!') or line.strip().startswith('![')):
            continue
        new_lines.append(line)
    content = '\n'.join(new_lines)
    
    # Remove triple empty lines
    content = re.sub(r'\n{3,}', '\n\n', content)

    # 3. Add How to Use
    if "### How to Use" not in content:
        if "> [!IMPORTANT]" in content:
            content = content.replace("> [!IMPORTANT]", HOW_TO_USE + "\n> [!IMPORTANT]")
        else:
            content += "\n" + HOW_TO_USE

    if content != original:
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

