<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# Programmatic Tool Calling: How to Build Smarter LLM Agents on Regolo GPUs

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

Runnable code for the article:
https://regolo.ai/programmatic-tool-calling-how-to-build-smarter-llm-agents-on-regolo-gpus/

## What this project covers

- Classic JSON function/tool calling loop
- Programmatic tool calling with generated mini-programs
- Restricted Python runtime with AST validation
- Multi-step support workflow using multiple tools
- Live API connectivity test + local safety tests

## Project structure

- `config.py`: environment configuration
- `regolo_client.py`: OpenAI-compatible Regolo client
- `tools.py`: demo tool implementations
- `classic_tool_calling.py`: standard two-step tool call loop
- `programmatic_tool_calling.py`: planning + execution for PTC pattern
- `runtime/program_executor.py`: sandboxed program validation + execution
- `tests/test_programmatic_tool_calling.py`: test suite

## Quick start

```bash
cd programmatic-tool-calling-how-to-build-smarter-llm-agents-on-regolo-gpus
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set API key in `.env` and keep the model configurable:

```bash
REGOLO_API_KEY=your_key_here
REGOLO_BASE_URL=https://api.regolo.ai/v1
REGOLO_MODEL=Llama-3.3-70B-Instruct
REGOLO_REASONING_EFFORT=medium
```

Run demo:

```bash
python main.py
```

Run tests:

```bash
pytest -q
```

### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
