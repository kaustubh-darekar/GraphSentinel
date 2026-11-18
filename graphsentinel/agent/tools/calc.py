"""A safe arithmetic calculator (no eval)."""

from __future__ import annotations

import ast
import operator

from graphsentinel.agent.tools.base import Tool, schema

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        if isinstance(node.op, ast.Pow) and abs(_eval(node.right)) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("only numbers and + - * / % ** are allowed")


def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression."""
    try:
        value = _eval(ast.parse(expression, mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError) as exc:
        return f"Error: {exc}"
    return str(int(value) if float(value).is_integer() else round(value, 6))


TOOLS = [
    Tool("calc.calculate", "Evaluate an arithmetic expression.",
         schema({"expression": {"type": "string"}}, ["expression"]), calculate),
]
