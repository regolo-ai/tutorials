"""Restricted Python program execution for programmatic tool calling."""

from __future__ import annotations

import ast
import textwrap
from typing import Any


ALLOWED_NODES = {
    ast.Module,
    ast.Assign,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Call,
    ast.Expr,
    ast.Constant,
    ast.List,
    ast.Dict,
    ast.Tuple,
    ast.keyword,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Compare,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.Eq,
    ast.NotEq,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.If,
    ast.IfExp,
    ast.For,
    ast.ListComp,
    ast.comprehension,
    ast.Subscript,
    ast.Slice,
    ast.Return,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
}


FORBIDDEN_NAMES = {
    "__import__",
    "eval",
    "exec",
    "open",
    "compile",
    "globals",
    "locals",
    "vars",
    "input",
    "help",
    "dir",
}


def _validate_program(program_source: str, allowed_functions: set[str]) -> None:
    tree = ast.parse(program_source)

    for node in ast.walk(tree):
        if type(node) not in ALLOWED_NODES:
            raise ValueError(f"Unsupported syntax: {type(node).__name__}")

        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValueError(f"Forbidden identifier used: {node.id}")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only direct function calls are allowed")
            if node.func.id not in allowed_functions:
                raise ValueError(f"Function not allowed: {node.func.id}")


def execute_program(program_source: str, tools_runtime: dict[str, Any]) -> Any:
    clean_source = textwrap.dedent(program_source).strip()
    _validate_program(clean_source, allowed_functions=set(tools_runtime.keys()))

    local_env: dict[str, Any] = {}
    safe_globals = {"__builtins__": {}}
    safe_globals.update(tools_runtime)

    exec(clean_source, safe_globals, local_env)

    if "result" not in local_env:
        raise ValueError("Program must set a `result` variable.")

    return local_env["result"]
