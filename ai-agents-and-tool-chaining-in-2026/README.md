# AI Agents and Tool Chaining in 2026

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Runnable Code](https://img.shields.io/badge/Code-Runnable%20Examples-1F9D55)
![GPU Ready](https://img.shields.io/badge/GPU-100%25%20Ready-0A84FF)
![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI%20Compatible-black)

This tutorial shows a small but complete contract-review workflow that chains multiple steps into one runnable script:

1. Load configuration from a local `.env` file.
2. Fetch available Regolo models.
3. Extract structured fields from a sample contract.
4. Rerank policy documents against the contract context.
5. Produce a final policy decision.

Article: https://regolo.ai/ai-agents-and-tool-chaining-in-2026-how-to-build-workflows-that-actually-finish-the-job/

## What the script does

The entry point is [main.py](main.py). It:

- loads `REGOLO_API_KEY` and optional runtime settings from a local `.env`
- discovers chat and rerank models from the Regolo API
- extracts contract metadata such as vendor, payment terms, renewal length, and uplift percentage
- reranks a small set of policy documents
- applies deterministic policy rules to generate a final decision

## Requirements

- Python 3.12+
- A valid `REGOLO_API_KEY`
- Network access to `https://api.regolo.ai`

The script uses only the Python standard library plus the Regolo API itself. It does not require `requests`.

## Environment Variables

Create a `.env` file in this folder with at least:

```env
REGOLO_API_KEY=your_api_key_here
```

Optional variables:

- `REGOLO_BASE_URL` - overrides the API base URL
- `REGOLO_CHAT_MODEL` - forces the chat model name
- `REGOLO_RERANK_MODEL` - forces the reranker model name
- `REGOLO_INSECURE_TLS` - set to `1`, `true`, `yes`, or `on` to bypass local certificate verification issues

## Run It

From this directory:

```bash
python main.py
```

You can also pass a custom contract file:

```bash
python main.py path/to/contract.txt
```

## Output

The script prints a JSON object containing:

- `selected_models`
- `extracted_contract_fields`
- `ranked_policy_evidence`
- `final_decision`

## Notes

- The final decision is deterministic now, so it does not depend on the model returning perfect JSON.
- If your macOS Python install has broken CA certificates, the script can retry TLS verification with the `REGOLO_INSECURE_TLS` fallback.
- The sample contract bundled in the script is intentionally non-compliant, so the default decision should not be `approve_standard_terms`.

## Related Article

- [AI Agents and Tool Chaining in 2026: How to Build Workflows That Actually Finish the Job](https://regolo.ai/ai-agents-and-tool-chaining-in-2026-how-to-build-workflows-that-actually-finish-the-job/)