"""Restricted evaluator for policy `when` expressions. No Python `eval`."""

from __future__ import annotations

from typing import Any

from simpleeval import EvalWithCompoundTypes


class Ns(dict):
    """Read-only dict that also supports attribute access (`candidate.channel`).
    Missing keys raise, so a typo in the policy is caught at load time, not silently False."""

    def __getattr__(self, name: str) -> Any:
        try:
            return wrap(self[name])
        except KeyError:
            raise AttributeError(f"unknown field '{name}'") from None

    def __getitem__(self, key):
        return wrap(super().__getitem__(key))


def wrap(value: Any) -> Any:
    if isinstance(value, dict) and not isinstance(value, Ns):
        return Ns(value)
    if isinstance(value, list):
        return [wrap(v) for v in value]
    return value


class RuleError(Exception):
    pass


class ExpressionEvaluator:
    def __init__(self):
        self._evaluator = EvalWithCompoundTypes(functions={"len": len, "min": min, "max": max, "abs": abs})
        self._parsed: dict[str, Any] = {}

    def evaluate(self, expr: str, context: dict[str, Any]) -> Any:
        self._evaluator.names = {k: wrap(v) for k, v in context.items()}
        try:
            if expr not in self._parsed:
                self._parsed[expr] = self._evaluator.parse(expr)
            return self._evaluator.eval(expr, previously_parsed=self._parsed[expr])
        except Exception as e:  # simpleeval raises many types; normalise them
            raise RuleError(f"{expr!r}: {e}") from e
