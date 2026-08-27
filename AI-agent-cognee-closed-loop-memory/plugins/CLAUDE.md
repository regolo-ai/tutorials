# Regolo + Cognee Long-Term Memory Protocol

This repository uses **Cognee Knowledge Graph Memory** on **Regolo.ai**.

## Memory Guidelines for Claude Code:
1. Before modifying core modules, execute `cognee_recall` with your task intent.
2. Always follow linked `ArchitecturalDecision` (ADR) nodes.
3. Check for previous `PastCIError` nodes to avoid repeating solved bugs.
4. After completing a critical PR or security fix, call `cognee_record_pr`.
