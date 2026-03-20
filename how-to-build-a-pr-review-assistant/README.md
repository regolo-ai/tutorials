# PR Review Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Regolo](https://img.shields.io/badge/Powered%20by-Regolo%20GPU-green)](https://regolo.ai)

This repository contains all the code from the guide [AI-Native Software Development: How to Build a PR Review Assistant with Regolo Instead of Another Generic Copilot](https://regolo.ai/ai-native-software-development-how-to-build-a-pr-review-assistant-with-regolo-instead-of-another-generic-copilot/) — ready to test and deploy.

## What it does

- loads variables from a local `.env` file in the same folder as the script
- selects a model through the `REGOLO_CORE_MODEL` variable
- reads the Git diff from staged changes or from the latest commit
- sends the diff to the chosen model and prints the review in Markdown

## Requirements

- Python 3.10+
- access to the Regolo API
- a Git repository with at least one available diff

## Environment variables

Create a `.env` file in the same folder as `main.py`:

```env
REGOLO_API_KEY=your_api_key
REGOLO_BASE_URL=https://api.regolo.ai
REGOLO_CORE_MODEL=qwen3.5-122b
```

### Supported variables

- `REGOLO_API_KEY` required
- `REGOLO_BASE_URL` optional, default: `https://api.regolo.ai`
- `REGOLO_CORE_MODEL` optional, default: `qwen3.5-122b`

## Installation

Install the required dependency:

```bash
pip install requests
```

## Usage

Run the script from the project folder:

```bash
python3 main.py
```

The script first tries the staged diff with `git diff --cached`. If nothing is staged, it falls back to `git diff HEAD~1 HEAD`.

## Output

The result is printed in Markdown with these sections:

- Summary
- Risks
- Suggested review comments
- Missing tests
- Rollout notes

## Notes

- If `REGOLO_API_KEY` is missing, the script exits with an error.
- If no valid diff exists, the script exits with an error.
- The selected model is the one set in `REGOLO_CORE_MODEL`.
