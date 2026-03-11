# Programmatic Tool Calling: How to Build Smarter LLM Agents on Regolo GPUs

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Runnable Code](https://img.shields.io/badge/Code-Runnable%20Examples-1F9D55)
![GPU Ready](https://img.shields.io/badge/GPU-100%25%20Ready-0A84FF)
![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI%20Compatible-black)

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
