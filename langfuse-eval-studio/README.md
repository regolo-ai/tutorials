# Regolo Eval Studio · Langfuse & Open-Weight Model Evaluator

Companion interactive web studio and CLI for the Regolo Labs guide **"Tracing and evaluating open-weight models on Regolo with Langfuse: a practical guide"**.

Built with the Regolo Studio design system (`Space Grotesk`, emerald `#05df72`, 4-step wizard, zero external Python dependencies required).

## Features

1. **Test any model on your Regolo account:** queries `GET https://api.regolo.ai/v1/models` live with your `REGOLO_API_KEY` so you can evaluate `gemma4-31b`, `qwen3.8-27b`, `glm5.2`, `qwen3.5-122b`, `gpt-oss-120b`, `mistral-small-4`, or any newly added open-weight model.
2. **Single Model & Side-by-Side Compare mode:** run one model or compare two models head-to-head on the 20-question `regolo-docs-qa` RAG dataset (plus custom questions).
3. **Dual evaluation (`contains_expected_fact` + `faithfulness_judge`):** combines a free deterministic code check with an LLM-as-a-judge running on Regolo.
4. **PAYG vs Regolo Core subscription cost calculator:** computes exact token spend under both Pay-As-You-Go and the flat Regolo Core plan (`39 EUR/month` for `600M` tokens, or `11.70 EUR/month` during the 3-month promo) and flags hidden reasoning tokens.
5. **Optional Langfuse v4 ingestion + CI Regression Gate:** streams traces and numeric scores to a self-hosted EU or Frankfurt Cloud Langfuse instance (`/api/public/ingestion`) and generates a GitHub Actions PR Markdown report (`RegressionError` when faithfulness drops below `0.85`).

## Quickstart

```bash
cd ~/Desktop/langfuse-eval-studio

# 1. Run deterministic self-check and unit tests
python3 regolo_eval_tui.py --demo
python3 eval_wizard/test_server.py

# 2. Launch Regolo Eval Studio in your browser (http://127.0.0.1:8230)
python3 eval_wizard/server.py
```
