"""Finite AST interpreter for the division demo only. Does not execute Python source.

This is a reference oracle for Person A development, not Person B's pytest runner.
Imports, attribute access, arbitrary calls, loops, comprehensions and exponentiation
are unsupported. Unknown constructs fail closed as unsupported, never as passed.
"""

import ast
import math
import operator
from time import perf_counter

from shared.schemas import TestResult


class UnsupportedDemoCode(ValueError):
    pass


class Returned(Exception):
    def __init__(self, value):
        self.value = value


BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
           ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
EXCEPTIONS = {"ValueError": ValueError, "ZeroDivisionError": ZeroDivisionError, "TypeError": TypeError}


def _number(value):
    if not isinstance(value, (int, float, bool)) or abs(value) > 1e12 or not math.isfinite(value):
        raise UnsupportedDemoCode("Only finite, bounded numeric operations are supported")
    return value


def _expression(node, names):
    if isinstance(node, ast.Constant):
        return _number(node.value)
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
        left, right = _number(_expression(node.left, names)), _number(_expression(node.right, names))
        return _number(BINOPS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd, ast.Not)):
        value = _expression(node.operand, names)
        return -value if isinstance(node.op, ast.USub) else (+value if isinstance(node.op, ast.UAdd)
                                                           else not value)
    if isinstance(node, ast.Compare):
        left = _expression(node.left, names)
        for op, rhs in zip(node.ops, node.comparators, strict=True):
            if type(op) not in COMPARE:
                raise UnsupportedDemoCode("Unsupported comparison")
            right = _expression(rhs, names)
            if not COMPARE[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        value = None
        for child in node.values:
            value = _expression(child, names)
            if isinstance(node.op, ast.And) and not value:
                return value
            if isinstance(node.op, ast.Or) and value:
                return value
        return value
    if isinstance(node, ast.IfExp):
        return _expression(node.body if _expression(node.test, names) else node.orelse, names)
    raise UnsupportedDemoCode(f"Unsupported expression: {type(node).__name__}")


def _block(statements, names):
    for node in statements:
        if isinstance(node, ast.Return):
            raise Returned(_expression(node.value, names))
        if isinstance(node, ast.If):
            _block(node.body if _expression(node.test, names) else node.orelse, names)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                raise UnsupportedDemoCode("Only local-name assignments are supported")
            names[target.id] = _expression(node.value, names)
        elif isinstance(node, ast.Raise):
            exc = node.exc
            if isinstance(exc, ast.Name) and exc.id in EXCEPTIONS:
                raise EXCEPTIONS[exc.id]("demo exception")
            if (isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name)
                    and exc.func.id in EXCEPTIONS and not exc.keywords
                    and all(isinstance(arg, ast.Constant) for arg in exc.args)):
                raise EXCEPTIONS[exc.func.id]("demo exception")
            raise UnsupportedDemoCode("Only declared arithmetic exceptions are supported")
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # A docstring has no effect in the interpreter.
        elif isinstance(node, ast.Pass):
            continue
        elif not isinstance(node, ast.If):
            raise UnsupportedDemoCode(f"Unsupported statement: {type(node).__name__}")


def division_function(code: str):
    if len(code) > 8000:
        raise UnsupportedDemoCode("Demo source is too large")
    try:
        tree = ast.parse(code)
    except (SyntaxError, RecursionError) as exc:
        raise UnsupportedDemoCode("Invalid demo syntax") from exc
    if len(list(ast.walk(tree))) > 200:
        raise UnsupportedDemoCode("Demo AST is too large")
    body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str))]
    if len(body) != 1 or not isinstance(body[0], ast.FunctionDef):
        raise UnsupportedDemoCode("Expected only a divide(a, b) function")
    fn = body[0]
    if (fn.name != "divide" or fn.decorator_list or fn.args.vararg or fn.args.kwarg
            or fn.args.kwonlyargs or fn.args.defaults or fn.args.posonlyargs
            or [arg.arg for arg in fn.args.args] != ["a", "b"]):
        raise UnsupportedDemoCode("Expected the exact divide(a, b) interface")

    def invoke(a, b):
        try:
            _block(fn.body, {"a": a, "b": b})
        except Returned as result:
            return result.value
        raise UnsupportedDemoCode("Function did not return a value")

    return invoke


def check_division(code: str) -> list[TestResult]:
    fn = division_function(code)
    cases = [(6, 3), (7, 2), (-7, 2), (7, -2), (0, 4), (1, 3), (5.5, 2),
             (12345, 17), (-0.25, 0.5)]
    started = perf_counter()
    failures = []
    for a, b in cases:
        expected = a / b
        try:
            actual = fn(a, b)
            if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
                failures.append(f"divide({a}, {b}): expected {expected!r}, got {actual!r}")
        except UnsupportedDemoCode:
            raise
        except Exception as exc:
            failures.append(f"divide({a}, {b}): expected {expected!r}, raised {type(exc).__name__}")
    results = [TestResult(
        test_id="TEST-001", requirement_id="REQ-001", status="failed" if failures else "passed",
        output="REFERENCE AST EVALUATOR (not pytest): " + ("; ".join(failures) or "9 division cases passed"),
        duration_ms=round((perf_counter() - started) * 1000),
    )]
    started = perf_counter()
    failures = []
    for a in (0, 1, -5, 2.5):
        try:
            fn(a, 0)
            failures.append(f"divide({a}, 0): expected ValueError, but no exception was raised")
        except UnsupportedDemoCode:
            raise
        except ValueError:
            pass
        except Exception as exc:
            failures.append(f"divide({a}, 0): expected ValueError, got {type(exc).__name__}")
    results.append(TestResult(
        test_id="TEST-002", requirement_id="REQ-002", status="failed" if failures else "passed",
        output="REFERENCE AST EVALUATOR (not pytest): " + ("; ".join(failures) or "4 zero-divisor cases passed"),
        duration_ms=round((perf_counter() - started) * 1000),
    ))
    return results
