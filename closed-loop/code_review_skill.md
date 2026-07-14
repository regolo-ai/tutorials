# code_review_skill.md

## Goal
Fix Python syntax and logic bugs safely before any patch is deployed.

## Rules
- Preserve the original function names and signatures unless the task explicitly requires a refactor.
- Output only complete, valid Python code when generating a patch.
- Do not wrap code in Markdown fences.
- Prefer the smallest safe fix over a large rewrite.
- Never claim success before local verification passes.
- Treat compiler errors, test failures, and schema failures as hard blockers.
- If verification fails, use the exact failure message to guide the next attempt.
- Keep side effects minimal and avoid changing unrelated code.
- Preserve comments and docstrings unless they are clearly wrong or obsolete.
- When uncertain, choose the version that is easier to verify deterministically.

## Verification checklist
- The file compiles with Python `compile()`.
- Imports are valid and referenced names exist.
- Indentation is correct.
- Colons are present in `if`, `for`, `while`, `try`, `except`, `elif`, `else`, `def`, and `class` blocks.
- Return paths are syntactically valid.
- No accidental Markdown, prose, or JSON is mixed into the code output.
- The patched file can safely replace the previous file only after verification passes.

## Lessons learned
- If a previous patch failed because of a `SyntaxError`, repair syntax first before attempting any logic improvements.
- Never emit explanatory text before or after the Python source code.
- If the model returns code fences such as ```python, strip them before verification and deployment.
- A missing colon in `except`, `if`, or `def` blocks is a common failure mode and must be checked explicitly.
- When a patch fails verification, append the exact compiler error to this file so the next run has concrete feedback.
- Deterministic local checks are more trustworthy than self-reported AI confidence.
- Deployment must be blocked automatically when verification returns FAIL.
- Iteration 1: semantic gate failed -> The candidate patch is identical to the original code; it introduces no changes and therefore does not fix any issue.
- Iteration 1: semantic gate failed -> The patch changes __all__ from containing the public API to being empty, which breaks 'from module import *' functionality and contradicts the purpose of defining those attributes in __getattr__.
- Iteration 1: semantic gate failed -> The patch introduces an unrelated change by adding '__all__ = ["divide"]', which was not present in the original code and is not necessary to fix the logic.
- Iteration 1: semantic gate failed -> The patch introduces a regression by misspelling the LoRA filename in the MODELS dictionary: 'virtual-tryoff-lora_diffusers.safetensors' was changed to 'virtual-tryoff-lora_diffensors.safetensors' (added an 'n'), which will cause the download to fail.
- Iteration 1: semantic gate failed -> The candidate patch is identical to the original code. No changes were made to fix any issue.
