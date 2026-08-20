# Analytics Query & Metric Engine

FastAPI analytics processor for custom business metric formulas and cached dataset imports.

## Current Open Issue #58:
- **Title**: `Critical Fix: Eliminate arbitrary eval() in formula calculator and replace unsafe pickle deserialization`
- **Description**: Security audit found that `/analytics/calculate` uses Python's `eval()` which allows Remote Code Execution (CWE-94). Additionally, `/analytics/cache/load` uses `pickle.loads()` allowing arbitrary object execution (CWE-502).
- **Target**: Replace `eval()` with safe AST parsing (using `ast.parse` and whitelist operators `+ - * /`) and replace `pickle` with standard JSON serialization.
